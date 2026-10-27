# -*- coding: utf-8 -*-
"""Fixture + regression checks for privacy_scan.py (read-only on itself)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(os.path.dirname(HERE), "scripts", "privacy_scan.py")
BASE = os.path.join(tempfile.gettempdir(), "privacy_scan_fixture")


def git(*args):
    subprocess.run(["git", "-C", BASE] + list(args), check=True,
                   capture_output=True)


def wipe(path):
    for root, _, files in os.walk(path):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o666)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)
    if os.path.exists(path):
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", path], capture_output=True)


def build():
    if os.path.exists(BASE):
        wipe(BASE)
    os.makedirs(BASE, exist_ok=True)
    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")

    with open(os.path.join(BASE, "clean.py"), "w", encoding="utf-8") as f:
        f.write("ROOT = r'C:\\Users\\me\\project'\n"
                "URL = 'http://127.0.0.1:8080/api'\n"
                "CONTACT = 'you@example.com'\n"
                "# windows drive example: D:\\data\n")
    # build the dirty values at runtime: this file itself stays clean for scanners
    win_home = "C:" + "\\" + "Users" + "\\" + "\u5317\u6d77" + "\\" + "project"
    token = "gh" + "p_" + "a" * 36
    mail = "someone" + "@" + "qq.com"
    phone = "138" + "12345678"
    lan = "192.168." + "1.10"
    host = "DESKTOP-" + "AB12CD3"
    note = "\u5f53\u65f6\u62cd\u677f\u5b9a\u7684\uff0c\u540e\u6765\u590d\u76d8\u8fc7"
    with open(os.path.join(BASE, "leak.py"), "w", encoding="utf-8") as f:
        f.write("HOME = r'%s'\nTOKEN = '%s'\nMAIL = '%s'\nPHONE = '%s'\n"
                "LAN = '%s'\nHOST = '%s'\n# %s\n"
                % (win_home, token, mail, phone, lan, host, note))
    with open(os.path.join(BASE, "old.md"), "w", encoding="utf-8") as f:
        f.write("pass" + "word = hunter2secret\n")
    git("add", "-A")
    git("commit", "-qm", "add files")
    os.remove(os.path.join(BASE, "old.md"))
    git("add", "-A")
    git("commit", "-qm", "drop old")


def run(*extra):
    out = os.path.join(BASE, "scan.json")
    proc = subprocess.run([sys.executable, SCAN, BASE, "--json", out, "--quiet"]
                          + list(extra), capture_output=True, text=True)
    with open(out, encoding="utf-8") as f:
        data = json.load(f)
    return proc.returncode, data["findings"]


def rules(findings):
    return {f["rule"] for f in findings}


def main():
    build()
    code, cur = run()
    got = rules(cur)
    want = {"win_user_path", "github_token", "email", "cn_mobile", "lan_ip",
            "hostname", "process_narration"}
    missing = want - got
    assert not missing, "missing rules: %s" % missing
    assert code == 1, "findings must produce exit 1"
    assert not any(f["path"] == "clean.py" for f in cur), \
        "generic examples must not be flagged: %s" % [f for f in cur if f["path"] == "clean.py"]
    assert not any(f["rule"] == "secret_assign" and f["path"] == "clean.py"
                   for f in cur), "clean fixture has no credentials"
    print("current tree OK: %s" % sorted(got))

    code, hist = run("--history")
    assert code == 1
    assert any(f["path"] == "old.md" and f["rule"] == "secret_assign" for f in hist), \
        "deleted credential must be found in history"
    print("history OK: old.md secret found (%d findings total)" % len(hist))

    code, allowed = run("--allow", "leak.py")
    assert not any(f["path"] == "leak.py" for f in allowed)
    assert code == 0, "nothing left after allowlisting the only dirty file"
    print("allowlist OK")

    clean_repo = os.path.join(tempfile.gettempdir(), "privacy_scan_clean")
    if os.path.exists(clean_repo):
        wipe(clean_repo)
    os.makedirs(clean_repo, exist_ok=True)
    subprocess.run(["git", "-C", clean_repo, "init", "-q"], check=True)
    with open(os.path.join(clean_repo, "a.txt"), "w") as f:
        f.write("hello C:\\Users\\user\\x\n")
    subprocess.run(["git", "-C", clean_repo, "add", "-A"], check=True)
    proc = subprocess.run([sys.executable, SCAN, clean_repo], capture_output=True,
                          text=True)
    assert proc.returncode == 0, proc.stdout
    assert "CLEAN" in proc.stdout
    print("clean repo OK: exit 0")
    print("ALL OK")


if __name__ == "__main__":
    main()
