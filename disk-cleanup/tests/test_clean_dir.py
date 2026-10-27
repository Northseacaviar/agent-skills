# -*- coding: utf-8 -*-
"""Self-test for clean_dir.py: run with `python tests/test_clean_dir.py`.

Covers: age/active filters, junction not followed, contents mode keeps the dir,
entry mode deletes one item, system paths refused, locked file reported as a
failure instead of silently skipped.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "clean_dir.py")
BASE = os.path.join(tempfile.gettempdir(), "clean_dir_selftest")


def wipe(path):
    """rmtree that also clears the read-only attribute left by earlier cases."""
    for root, _, files in os.walk(path):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o666)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def build_tree():
    if os.path.exists(BASE):
        wipe(BASE)
    os.makedirs(os.path.join(BASE, "cacheA", "sub"))
    os.makedirs(os.path.join(BASE, "outside"))
    with open(os.path.join(BASE, "outside", "keep.txt"), "w") as f:
        f.write("do not touch")
    old = time.time() - 30 * 86400
    for name, size in [("old1.bin", 3_000_000), ("sub/old2.bin", 2_000_000),
                       ("ro_old.bin", 1_000_000), ("old_small.txt", 10)]:
        p = os.path.join(BASE, "cacheA", name)
        with open(p, "wb") as f:
            f.write(b"x" * size)
        os.utime(p, (old, old))
    with open(os.path.join(BASE, "cacheA", "live.bin"), "wb") as f:
        f.write(b"y" * 500_000)
    os.chmod(os.path.join(BASE, "cacheA", "ro_old.bin"), 0o444)
    subprocess.run(["cmd", "/c", "mklink", "/J",
                    os.path.join(BASE, "cacheA", "jlink"),
                    os.path.join(BASE, "outside")], capture_output=True)


def run(plan, extra=()):
    plan_path = os.path.join(BASE, "plan.json")
    out = os.path.join(BASE, "res.json")
    with open(plan_path, "w") as f:
        json.dump({"targets": plan}, f)
    proc = subprocess.run([sys.executable, SCRIPT, plan_path, "--apply",
                           "--out", out] + list(extra),
                          capture_output=True, text=True)
    print(proc.stdout.strip())
    assert proc.returncode == 0, proc.stderr[-2000:]
    with open(out, encoding="utf-8") as f:
        return json.load(f)


def case_filters_and_refusals():
    build_tree()
    res = run([{"path": os.path.join(BASE, "cacheA"), "mode": "contents"},
               {"path": os.path.join(BASE, "outside", "keep.txt"), "mode": "entry"},
               {"path": "C:\\Windows", "mode": "contents"},
               {"path": "C:\\", "mode": "contents"},
               {"path": "C:\\Users", "mode": "contents"}])
    left = sorted(os.listdir(os.path.join(BASE, "cacheA")))
    assert "old1.bin" not in left and "old2.bin" not in left
    assert "ro_old.bin" not in left, "read-only cache file should be deleted"
    assert "live.bin" in left, "file modified in the last 5 min must survive"
    assert os.path.exists(os.path.join(BASE, "outside", "keep.txt")), "junction target touched"
    assert os.path.isdir(os.path.join(BASE, "cacheA")), "contents mode must keep the dir"
    refused = {r["path"]: r.get("refused") for r in res["targets"]}
    assert refused["C:\\Windows"] and refused["C:\\"] and refused["C:\\Users"]
    print("case 1 OK: filters, junction, refusals")


def case_no_active_skip():
    build_tree()
    res = run([{"path": os.path.join(BASE, "cacheA"), "mode": "contents"}],
              ["--skip-active-minutes", "0"])
    left = sorted(os.listdir(os.path.join(BASE, "cacheA")))
    assert "jlink" not in left, "junction itself should be unlinked"
    assert os.path.exists(os.path.join(BASE, "outside", "keep.txt")), "junction target touched"
    assert "live.bin" not in left
    print("case 2 OK: junction unlinked, target intact")


def case_entry_mode():
    build_tree()
    victim = os.path.join(BASE, "outside", "keep.txt")
    old = time.time() - 40 * 86400
    os.utime(victim, (old, old))
    run([{"path": victim, "mode": "entry"}])
    assert not os.path.exists(victim)
    print("case 3 OK: entry mode")


def case_locked_file():
    build_tree()
    locked = os.path.join(BASE, "cacheA", "held.bin")
    with open(locked, "wb") as f:
        f.write(b"b" * 2000)
    os.utime(locked, (time.time() - 86400 * 3,) * 2)
    handle = open(locked, "rb")
    try:
        res = run([{"path": os.path.join(BASE, "cacheA"), "mode": "contents"}],
                  ["--skip-active-minutes", "0"])
    finally:
        handle.close()
    assert os.path.exists(locked), "locked file must survive"
    assert res["failures"], "locked file must be reported, not silently skipped"
    print("case 4 OK: locked file reported as failure")


if __name__ == "__main__":
    case_filters_and_refusals()
    case_no_active_skip()
    case_entry_mode()
    case_locked_file()
    shutil.rmtree(BASE, ignore_errors=True)
    print("ALL OK")
