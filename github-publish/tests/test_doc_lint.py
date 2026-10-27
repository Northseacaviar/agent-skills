# -*- coding: utf-8 -*-
"""Regression checks for doc_lint.py."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LINT = os.path.join(os.path.dirname(HERE), "scripts", "doc_lint.py")
BASE = os.path.join(tempfile.gettempdir(), "doc_lint_fixture")

SLOP = """# 智能工具箱

在当今快速发展的技术 landscape 中，本工具旨在赋能开发者，助力团队打造一站式解决方案。

- **性能**：性能得到了显著提升
- **体验**：体验更加流畅
- **安全**：安全能力全面增强

首先，它很快。其次，它很好用。最后，它值得信赖。综上所述，这是一个不可或缺的工具。
"""

CLEAN = """# demo-tool v1.0.0

给 CSV 文件做去重，比较两列。

## 安装

    pip install demo-tool

## 使用

    demo-tool dedupe a.csv b.csv

## 许可

MIT
"""


def lint(path, *extra):
    proc = subprocess.run([sys.executable, LINT, path] + list(extra),
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def main():
    os.makedirs(BASE, exist_ok=True)
    slop = os.path.join(BASE, "slop.md")
    clean = os.path.join(BASE, "clean.md")
    with open(slop, "w", encoding="utf-8") as f:
        f.write(SLOP)
    with open(clean, "w", encoding="utf-8") as f:
        f.write(CLEAN)

    _, out = lint(slop)
    for kind in ("ai_phrase", "inline_header_list", "no_version"):
        assert kind in out, "slop file should trip %s:\n%s" % (kind, out)
    assert "no_license" in out and "no_usage_section" in out
    print("slop detected OK")

    _, out = lint(clean)
    assert "no_version" not in out, out
    assert "no_usage_section" not in out, out
    assert "no_license" not in out, out
    assert "inline_header_list" not in out, out
    print("clean file OK")

    code, out = lint(slop, "--strict")
    assert code == 1, "strict mode must fail on a sloppy file"
    print("strict mode OK")
    print("ALL OK")


if __name__ == "__main__":
    main()
