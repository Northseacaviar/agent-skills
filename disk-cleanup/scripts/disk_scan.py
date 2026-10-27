# -*- coding: utf-8 -*-
"""Read-only disk usage scan for Windows (works anywhere Python runs).

Aggregates file bytes onto root-relative path prefixes, so every reported
number is the FULL size of that directory, not just its shallow layers.

Usage:
  python disk_scan.py "C:\\" 3 out.json [--big 200]
    arg1  root to scan
    arg2  how many path levels to report (default 3)
    arg3  output JSON path
    --big MB  threshold for the big-file list (default 200)

Why not PowerShell: Directory.EnumerateFiles(.., AllDirectories) wrapped in
one try/catch aborts the whole walk on the first access-denied folder and
returns a silent zero-piece of the total. os.scandir + explicit stack with
per-entry guard keeps going and is ~10-30x faster.
"""
import json
import os
import sys
import time


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "C:\\"
    maxdepth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    out_path = sys.argv[3] if len(sys.argv) > 3 else "disk_scan.json"
    big_mb = 200.0
    if "--big" in sys.argv:
        big_mb = float(sys.argv[sys.argv.index("--big") + 1])
    big_bytes = big_mb * 1024 * 1024

    agg = {}          # prefix tuple -> bytes
    big = []          # (path, bytes)
    errors = 0
    root_files = 0    # files sitting directly in root (not in any subdir)
    t0 = time.time()

    stack = [(root, ())]
    while stack:
        d, parts = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            size = e.stat(follow_symlinks=False).st_size
                            if size == 0:
                                continue
                            if size >= big_bytes:
                                big.append((e.path, size))
                            if not parts:
                                root_files += size
                                continue
                            for i in range(1, min(len(parts), maxdepth) + 1):
                                key = parts[:i]
                                agg[key] = agg.get(key, 0) + size
                        elif e.is_dir(follow_symlinks=False):
                            stack.append((e.path, parts + (e.name,)))
                    except OSError:
                        errors += 1
        except OSError:
            errors += 1

    by_depth = {}
    for prefix, size in sorted(agg.items(), key=lambda kv: -kv[1]):
        by_depth.setdefault(str(len(prefix)), []).append(
            {"path": os.path.join(root, *prefix), "gb": round(size / 1073741824, 2)}
        )

    big.sort(key=lambda kv: -kv[1])
    totals = sum(v for k, v in agg.items() if len(k) == 1)
    result = {
        "root": root,
        "elapsed_s": round(time.time() - t0, 1),
        "errors": errors,
        "total_scanned_gb": round(totals / 1073741824, 2),
        "root_files_gb": round(root_files / 1073741824, 2),
        "dirs_by_depth": {k: v[:40] for k, v in sorted(by_depth.items())},
        "big_files": [
            {"path": p, "gb": round(s / 1073741824, 2)} for p, s in big[:60]
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    # ASCII-only console line: Chinese paths through git-bash pipes are lossy.
    print(
        "DONE %.1fs errors=%d scanned=%.2fGB root_files=%.2fGB big=%d out=%s"
        % (result["elapsed_s"], errors, result["total_scanned_gb"],
           result["root_files_gb"], len(big), out_path)
    )


if __name__ == "__main__":
    main()
