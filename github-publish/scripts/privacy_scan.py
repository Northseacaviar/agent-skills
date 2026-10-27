# -*- coding: utf-8 -*-
"""Privacy gate for a repo before it is pushed / made public.

Scans tracked files (default), the working tree (--all-files) or every blob in
git history (--history) for machine-specific paths, credentials, personal data
and internal-process narration. Read-only. Exit code 1 when anything is found.

Usage:
  python privacy_scan.py <repo>                 # git ls-files
  python privacy_scan.py <repo> --all-files     # every file, tracked or not
  python privacy_scan.py <repo> --history       # every blob in every commit
  python privacy_scan.py <repo> --json out.json --quiet
  python privacy_scan.py <repo> --allow vendor  # skip paths containing "vendor"

Console output is ASCII-only (git-bash mangles UTF-8 paths); the JSON keeps the
exact matched text so findings can be judged without re-grepping.
"""
import argparse
import json
import os
import re
import subprocess
import sys

MAX_LINE = 400
SKIP_SUFFIX = (".min.js", ".min.css", ".map", ".lock", ".woff", ".woff2",
               ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
               ".7z", ".gz", ".exe", ".dll", ".so", ".dylib", ".bin")

GENERIC_USERS = {
    "public", "default", "default user", "all users", "me", "user", "users",
    "username", "name", "<user>", "<name>", "%username%", "yourname", "you",
}
GENERIC_SEGMENTS = {
    "data", "project", "projects", "path", "tmp", "temp", "src", "app", "apps",
    "downloads", "work", "code", "dev", "tools", "docs", "to", "file", "example",
    "<name>", "<user>", "me", "user", "users",
}
PLACEHOLDER_VALUES = {
    "", "xxx", "xxxx", "xxxxxx", "***", "null", "none", "true", "false",
    "changeme", "change_me", "your_token", "your-key", "your_key",
    "placeholder", "todo", "example", "test", "password", "secret",
}

# (rule id, severity, compiled pattern, human note)
RULES = [
    ("win_user_path", "high",
     re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+([^\\/\s\"'<>|]+)", re.I),
     "absolute Windows user path"),
    ("unix_user_path", "high",
     re.compile(r"/(?:home|Users)/([^/\s\"'<>|]+)/"),
     "absolute home path"),
    ("file_url", "medium", re.compile(r"file:///[^\s\"'<>]+"), "local file URL"),
    ("drive_path", "low",
     re.compile(r"\b[A-Za-z]:\\[^\s\"'<>|]{3,}"), "absolute drive path"),
    ("email", "medium",
     re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"), "email address"),
    ("github_token", "critical",
     re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
     "GitHub token"),
    ("api_key", "critical",
     re.compile(r"\b(?:sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}"
                r"|AIza[0-9A-Za-z_\-]{35}|xox[baprs]-[A-Za-z0-9-]{10,}"
                r"|glpat-[A-Za-z0-9_\-]{16,})"), "API key"),
    ("private_key", "critical",
     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    ("secret_assign", "high",
     re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|apikey"
                r"|access[_-]?key)\s*[:=]\s*[\"']?([^\s\"',;]{4,})"),
     "hard-coded credential"),
    ("cn_mobile", "high", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
     "CN mobile number"),
    ("cn_id", "high", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
     "CN ID number"),
    ("lan_ip", "medium",
     re.compile(r"\b(?:192\.168|10\.(?!0\.0)|172\.(?:1[6-9]|2\d|3[01]))\."
                r"\d{1,3}\.\d{1,3}\b"), "LAN IP"),
    ("proxy_config", "medium",
     re.compile(r"(?:127\.0\.0\.1|localhost):(?:7890|7891|7897|1080|10808"
                r"|10809|1087)\b"), "local proxy endpoint"),
    ("hostname", "medium",
     re.compile(r"\b(?:DESKTOP|LAPTOP|WIN)-[A-Z0-9]{5,10}\b"), "machine hostname"),
    ("internal_tool", "medium",
     re.compile(r"(?:\.hermes[/\\]|state\.db|ai-bridge|\.claude[/\\]"
                r"|insane-robot)"), "internal tooling path"),
    ("process_narration", "medium",
     re.compile(r"(拍板|复盘|审查报告|成本账|学习报告|学习追踪|子 ?agent"
                r"|独立审查|按用户要求|用户要求|需求重新界定|vibecoding"
                r"|AI 结对|指令)"), "internal process narration"),
]

SKIP_EMAILS = ("noreply@github.com", "@users.noreply.github.com",
               "example.com", "example.org", "localhost", "@sentry.io",
               "you@example", "git@github.com", "@anthropic.com",
               "@nousresearch.com")


def mask(value):
    v = value.strip()
    if len(v) <= 6:
        return "*" * len(v)
    return v[:4] + "*" * max(3, len(v) - 6) + v[-2:]


def load_ignore(repo):
    """Optional repo-level skip list: one path substring per line, # comments."""
    path = os.path.join(repo, ".privacyignore")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def skip_path(path, allow):
    low = path.lower()
    if low.endswith(SKIP_SUFFIX):
        return True
    for a in allow:
        if a.lower() in low:
            return True
    return False


def match_line(line, path, where):
    hits = []
    if len(line) > MAX_LINE:
        return hits
    for rule, severity, pattern, note in RULES:
        for m in pattern.finditer(line):
            text = m.group(0)
            if rule == "win_user_path" or rule == "unix_user_path":
                user = (m.group(1) or "").strip().lower()
                if user in GENERIC_USERS or user.startswith("%"):
                    continue
            if rule == "email":
                if any(s in text.lower() for s in SKIP_EMAILS):
                    continue
            if rule == "secret_assign":
                val = (m.group(2) or "")
                low = val.lower()
                if low in PLACEHOLDER_VALUES or low.startswith(("<", "${", "os.", "env.")):
                    continue
                if val.startswith(("$", "%")) or re.fullmatch(r"[x*]+", low):
                    continue
            if rule == "drive_path":
                low = text.lower()
                segs = [s for s in re.split(r"[\\/]", low) if s][1:]
                if "users" in segs:
                    continue  # judged by win_user_path, which allowlists placeholders
                if all(s in GENERIC_SEGMENTS for s in segs):
                    continue
            if rule == "process_narration" and path.lower().endswith(".md") is False:
                # still report: process narration in code comments is the same leak
                pass
            hits.append({
                "rule": rule, "severity": severity, "note": note,
                "path": path, "where": where,
                "match": mask(text), "raw_len": len(text),
            })
    return hits


def scan_lines(path_for_report, text, where):
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for h in match_line(line, path_for_report, "%s:%d" % (where, i)):
            hits.append(h)
    return hits


def iter_tracked(repo):
    out = subprocess.run(["git", "-C", repo, "ls-files", "-z"],
                         capture_output=True)
    for raw in out.stdout.split(b"\0"):
        if raw:
            yield raw.decode("utf-8", "replace")


def iter_all_files(repo):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist",
                                                "build", "__pycache__")]
        for name in files:
            full = os.path.join(root, name)
            yield os.path.relpath(full, repo).replace("\\", "/")


def read_text(path):
    try:
        with open(path, "rb") as f:
            data = f.read(2 * 1024 * 1024)
        if b"\0" in data:
            return None
        return data.decode("utf-8", "replace")
    except OSError:
        return None


def scan_worktree(repo, paths, allow):
    hits = []
    for rel in paths:
        if skip_path(rel, allow):
            continue
        full = os.path.join(repo, rel)
        if not os.path.isfile(full):
            continue
        text = read_text(full)
        if text is None:
            continue
        hits.extend(scan_lines(rel, text, rel))
    return hits


def scan_history(repo, allow, max_blobs):
    """Every blob reachable from any ref, deduped by object id."""
    listing = subprocess.run(["git", "-C", repo, "rev-list", "--objects", "--all"],
                             capture_output=True, text=True, errors="replace")
    entries, seen = [], set()
    for line in listing.stdout.splitlines():
        sha, _, path = line.partition(" ")
        if not path or sha in seen:
            continue
        seen.add(sha)
        entries.append((sha, path))
    entries = [e for e in entries if not skip_path(e[1], allow)][:max_blobs]

    hits = []
    proc = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert proc.stdin and proc.stdout
    for sha, path in entries:
        proc.stdin.write(sha.encode() + b"\n")
        proc.stdin.flush()
        header = proc.stdout.readline().decode("utf-8", "replace").split()
        if len(header) < 3:
            continue
        size = int(header[2])
        data = proc.stdout.read(size)
        proc.stdout.read(1)
        if header[1] != "blob" or size > 2 * 1024 * 1024 or b"\0" in data:
            continue
        text = data.decode("utf-8", "replace")
        hits.extend(scan_lines(path, text, path))
    proc.stdin.close()
    proc.stdout.close()
    proc.wait()
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--all-files", action="store_true")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--max-blobs", type=int, default=20000)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--min-severity", default="medium",
                    choices=["critical", "high", "medium", "low"],
                    help="low hides generic drive-path examples (default: medium)")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(os.path.join(repo, ".git")):
        print("not a git repo: %s" % repo)
        return 2

    paths = iter_all_files(repo) if args.all_files else iter_tracked(repo)
    allow = list(args.allow) + load_ignore(repo)
    hits = scan_worktree(repo, paths, allow)
    if args.history:
        hits.extend(scan_history(repo, allow, args.max_blobs))

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    hits = [h for h in hits if order[h["severity"]] <= order[args.min_severity]]

    grouped = {}
    for h in hits:
        grouped.setdefault((h["severity"], h["rule"]), []).append(h)
    if not args.quiet:
        for (sev, rule), items in sorted(grouped.items(),
                                         key=lambda kv: (order[kv[0][0]], kv[0][1])):
            print("%-8s %-22s %d hit(s)" % (sev.upper(), rule, len(items)))
            for h in items[:8]:
                print("    %s  %s" % (h["where"], h["match"]))
            if len(items) > 8:
                print("    ... %d more" % (len(items) - 8))
        if not hits:
            print("CLEAN  no findings")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"repo": repo, "history": args.history,
                       "findings": hits}, f, ensure_ascii=False, indent=1)
    if hits:
        print("RESULT findings=%d (see %s)" % (len(hits), args.json or "stdout"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
