# -*- coding: utf-8 -*-
"""Guarded cache cleaner: dry-run by default, explicit manifest, hard denylist.

Usage:
  python clean_dir.py plan.json            # dry-run: prints the exact entry list
  python clean_dir.py plan.json --apply    # execute after the user approved
  python clean_dir.py --target "C:\\Users\\me\\AppData\\Local\\NVIDIA\\DXCache"

plan.json:
  {"targets": [
      {"path": "C:\\\\Users\\\\me\\\\AppData\\\\Local\\\\NVIDIA\\\\DXCache",
       "mode": "contents",              # contents = clear entries, keep the dir
       "reason": "shader cache"},
      {"path": "D:\\\\Downloads\\\\old-installer.zip", "mode": "entry"}  # delete one item
   ]}

Modes:
  contents  clear every entry inside <path>, keep <path> itself (apps rebuild it)
  entry     delete <path> itself (a file, an installer, or one whole directory)

Safety rules (refused outright, no override flag):
  * drive roots, C:\\Windows, C:\\Program Files*, C:\\ProgramData, $RECYCLE.BIN
  * System Volume Information, Recovery, Boot, PerfLogs, Config.MSI, MSOCache
  * a user profile root, or a top-level personal folder as a "contents" target
  * paths containing wildcards, or a target that is itself a link/junction
Recursive delete never follows links/junctions: the link is unlinked, its
target is untouched. Files modified within --skip-active-minutes (default 5)
and files newer than --min-age-days are left in place. Console output is
ASCII-only on purpose; the --out JSON is UTF-8.
"""
import json
import os
import shutil
import stat
import sys
import time

GB = 1073741824.0

DENY_TOP = {
    "windows", "program files", "program files (x86)", "programdata",
    "$recycle.bin", "system volume information", "recovery", "boot",
    "perflogs", "config.msi", "msocache",
}
PERSONAL = {
    "desktop", "documents", "downloads", "pictures", "videos", "music",
    "onedrive", "favorites", "links", "contacts", "searches", "saved games",
    "3d objects",
}


def log(msg):
    print(msg)


def long_path(p):
    if os.name != "nt":
        return p
    p = os.path.abspath(p)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def is_link(p):
    try:
        if os.path.islink(p):
            return True
        if hasattr(os.path, "isjunction") and os.path.isjunction(p):
            return True
        return stat.S_ISLNK(os.lstat(p).st_mode)
    except OSError:
        return False


def walk_files(p):
    """Yield (path, st) for files under p, never following links."""
    stack = [p]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(long_path(d)) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            yield e.path, e.stat(follow_symlinks=False)
                    except OSError:
                        continue
        except OSError:
            continue


def dir_size(p):
    total = 0
    files = 0
    for _, st in walk_files(p):
        total += st.st_size
        files += 1
    return total, files


def free_bytes(anchor):
    try:
        return shutil.disk_usage(anchor).free
    except OSError:
        return None


def check_target(path, mode):
    """Return a refusal reason, or None when the target is acceptable."""
    if not path or path != path.strip():
        return "empty or padded path"
    if any(c in path for c in "*?"):
        return "wildcard path"
    p = os.path.abspath(os.path.expandvars(path))
    if not os.path.exists(long_path(p)):
        return "not found"
    if is_link(p):
        return "target is a link/junction"
    parts = [x for x in p.replace("/", "\\").split("\\")[1:] if x]
    if not parts:
        return "drive root"
    low = [x.lower() for x in parts]
    if low[0] in DENY_TOP:
        return "protected system location (%s)" % parts[0]
    if low[0] == "users":
        if len(parts) == 1:
            return "users directory"
        if len(parts) == 2:
            return "user profile root"
        if len(parts) == 3 and low[2] in PERSONAL:
            return "top-level personal folder"
        if len(parts) == 3 and mode == "contents":
            return "whole user profile - pick a cache dir instead"
    if mode == "contents" and not os.path.isdir(long_path(p)):
        return "contents mode needs a directory"
    return None


def remove(p):
    """Delete a file or a tree without following links. Raises OSError."""
    lp = long_path(p)
    if is_link(lp) or not os.path.isdir(lp):
        try:
            os.unlink(lp)
        except PermissionError:
            os.chmod(lp, stat.S_IWRITE)
            os.unlink(lp)
        return
    with os.scandir(lp) as it:
        children = [e.path for e in it]
    for child in children:
        remove(child)
    os.rmdir(lp)


def prune_empty(p):
    """Remove now-empty subdirectories, keep p itself."""
    with os.scandir(long_path(p)) as it:
        children = [e.path for e in it if e.is_dir(follow_symlinks=False)]
    for c in children:
        prune_empty(c)
        try:
            os.rmdir(long_path(c))
        except OSError:
            pass


def fresh(st, min_age_days, skip_active_minutes):
    age = time.time() - st.st_mtime
    if age < skip_active_minutes * 60:
        return "modified in last %gm" % skip_active_minutes
    if age < min_age_days * 86400:
        return "newer than %gd" % min_age_days
    return None


def measure(path, mode):
    if mode == "entry":
        if is_link(path) or not os.path.isdir(path):
            try:
                return os.lstat(path).st_size, 1
            except OSError:
                return 0, 0
        return dir_size(path)
    total, files = 0, 0
    with os.scandir(long_path(path)) as it:
        for e in it:
            try:
                if e.is_dir(follow_symlinks=False):
                    s, f = dir_size(e.path)
                    total += s
                    files += f
                else:
                    total += e.stat(follow_symlinks=False).st_size
                    files += 1
            except OSError:
                continue
    return total, files


def clean_target(t, apply, min_age_days, skip_active_minutes, out_failures):
    path = t["path"]
    mode = t.get("mode", "contents")
    reason = check_target(path, mode)
    if reason:
        return {"path": path, "mode": mode, "refused": reason, "entries": 0,
                "deleted_bytes": 0, "deleted": 0, "skipped": 0, "failures": []}
    p = os.path.abspath(os.path.expandvars(path))
    before = free_bytes(p)
    total, entries = measure(p, mode)
    result = {"path": p, "mode": mode, "reason": t.get("reason", ""),
              "entries": entries, "entries_gb": round(total / GB, 2),
              "deleted_bytes": 0, "deleted": 0, "skipped": 0,
              "failures": [], "applied": bool(apply)}
    if not apply:
        return result

    if mode == "entry":
        item = long_path(p)
        st = os.lstat(item)
        why = fresh(st, min_age_days, skip_active_minutes)
        if why:
            result["skipped"] += 1
            result["skip_reason"] = why
        else:
            try:
                remove(item)
                result["deleted"] = entries
                result["deleted_bytes"] = total
            except OSError as exc:
                result["failures"].append({"path": p, "error": str(exc)})
                out_failures.append({"path": p, "error": str(exc)})
    else:
        with os.scandir(long_path(p)) as it:
            top = [e.path for e in it]
        for entry in top:
            try:
                if is_link(entry) or not os.path.isdir(entry):
                    st = os.lstat(entry)
                    why = fresh(st, min_age_days, skip_active_minutes)
                    if why:
                        result["skipped"] += 1
                        continue
                    remove(entry)
                    result["deleted"] += 1
                    result["deleted_bytes"] += st.st_size
                else:
                    # filter per file: a cache dir can contain a live download
                    drop = []
                    for fp, st in walk_files(entry):
                        if not fresh(st, min_age_days, skip_active_minutes):
                            drop.append((fp, st.st_size))
                    if not drop:
                        result["skipped"] += 1
                        continue
                    for fp, sz in drop:
                        try:
                            remove(fp)
                            result["deleted"] += 1
                            result["deleted_bytes"] += sz
                        except OSError as exc:
                            result["failures"].append({"path": fp, "error": str(exc)})
                            out_failures.append({"path": fp, "error": str(exc)})
                    prune_empty(entry)
                    try:
                        os.rmdir(long_path(entry))
                    except OSError:
                        pass
            except OSError as exc:
                result["failures"].append({"path": entry, "error": str(exc)})
                out_failures.append({"path": entry, "error": str(exc)})

    after = free_bytes(p)
    if before is not None and after is not None:
        result["free_delta_gb"] = round((after - before) / GB, 2)
    return result


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    apply = "--apply" in argv
    min_age_days = 0.0
    skip_active_minutes = 5.0
    out_path = None
    if "--min-age-days" in argv:
        min_age_days = float(argv[argv.index("--min-age-days") + 1])
    if "--skip-active-minutes" in argv:
        skip_active_minutes = float(argv[argv.index("--skip-active-minutes") + 1])
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]

    if "--target" in argv:
        targets = [{"path": argv[argv.index("--target") + 1], "mode": "contents"}]
    else:
        with open(argv[0], "r", encoding="utf-8") as f:
            targets = json.load(f).get("targets", [])
    if not targets:
        print("no targets")
        return 2

    results = []
    failures = []
    total = 0
    for t in targets:
        r = clean_target(t, apply, min_age_days, skip_active_minutes, failures)
        results.append(r)
        total += r.get("deleted_bytes", 0)
        tag = "REFUSED" if r.get("refused") else ("APPLIED" if apply else "DRY-RUN")
        log("%-8s %6.2f GB  files=%d %s%s" % (
            tag, r.get("deleted_bytes", 0) / GB, r.get("entries", 0), r["path"],
            ("  <- " + r["refused"]) if r.get("refused") else ""))

    summary = {
        "applied": apply,
        "min_age_days": min_age_days,
        "skip_active_minutes": skip_active_minutes,
        "targets": results,
        "failures": failures[:200],
        "total_deleted_gb": round(total / GB, 2),
    }
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1)
    log("TOTAL deleted=%.2f GB failures=%d applied=%s" % (
        total / GB, len(failures), apply))
    return 0


if __name__ == "__main__":
    sys.exit(main())
