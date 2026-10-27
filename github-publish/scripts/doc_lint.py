# -*- coding: utf-8 -*-
"""Style + structure check for public-facing markdown (README, release notes).

Two jobs, both advisory:
  * AI-writing tells: stock phrases, em-dash / bold density, inline-header
    bullet lists, "not just X but Y", CN 三段式 connectors.
  * Ship-readiness: a version string, install/usage and license sections, no
    leftover TODO, no machine paths or links into a local-only docs/ folder.

Usage:
  python doc_lint.py README.md [more.md ...]
  python doc_lint.py --all <repo>          # every tracked *.md
  python doc_lint.py README.md --strict    # exit 1 when hints >= --max (10)

Output is ASCII per line plus the matched text; UTF-8 is fine on a terminal.
"""
import argparse
import os
import re
import subprocess
import sys

CN_PHRASES = [
    "首先", "其次", "最后", "综上所述", "总的来说", "值得注意的是", "值得一提",
    "在当今", "随着.{0,14}的发展", "旨在", "致力于", "赋能", "助力", "一站式",
    "全方位", "深入浅出", "闭环", "抓手", "底层逻辑", "颗粒度", "生态位",
    "具有重要意义", "至关重要", "不可或缺", "本文将", "让我们一起",
    "不仅.{0,24}而且", "不是.{0,16}而是", "为.{0,10}提供有力支撑",
]
EN_PHRASES = [
    "serves as", "stands as", "is a testament", "pivotal", "seamless",
    "robust", "leverage", "delve", "furthermore", "moreover",
    "in today's", "landscape", "showcase", "underscore", "crucial",
    "comprehensive", "streamline", "empower", "cutting-edge", "game-changer",
    "it's worth noting", "at its core", "the real question",
]
VERSION_RE = re.compile(r"\bv?\d+\.\d+\.\d+\b")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
INLINE_HEADER_RE = re.compile(r"^\s*[-*]\s+\*\*[^*]{2,20}\*\*[：:]")
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/(?:home|Users)/|file:///)")
DOCS_LINK_RE = re.compile(r"\]\(\.{0,2}/?docs/")


def strip_code(text):
    """Drop fenced blocks and inline code so examples are not judged as prose."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    return text


def check_text(path, raw):
    text = strip_code(raw)
    chars = max(len(text), 1)
    hits = []

    for phrase in CN_PHRASES + EN_PHRASES:
        for m in re.finditer(phrase, text):
            hits.append({"kind": "ai_phrase", "path": path, "text": m.group(0)})

    em = text.count("—") + text.count("——")
    if em * 1000.0 / chars > 2.0:
        hits.append({"kind": "em_dash", "path": path,
                     "text": "%d per 1000 chars" % em})
    bold = len(re.findall(r"\*\*[^*]+\*\*", text))
    if bold * 1000.0 / chars > 6.0:
        hits.append({"kind": "bold", "path": path,
                     "text": "%d per 1000 chars" % bold})
    for i, line in enumerate(text.splitlines(), 1):
        if INLINE_HEADER_RE.match(line):
            hits.append({"kind": "inline_header_list", "path": path,
                         "text": line.strip()[:60]})
        if EMOJI_RE.search(line) and line.lstrip().startswith("#"):
            hits.append({"kind": "emoji_heading", "path": path,
                         "text": line.strip()[:60]})

    if not VERSION_RE.search(text):
        hits.append({"kind": "no_version", "path": path,
                     "text": "no vX.Y.Z in this file"})
    low = text.lower()
    if not any(k in low for k in ("install", "安装", "quick start", "usage", "使用")):
        hits.append({"kind": "no_usage_section", "path": path,
                     "text": "no install/usage wording"})
    if not any(k in low for k in ("license", "许可", "mit", "apache")):
        hits.append({"kind": "no_license", "path": path,
                     "text": "no license wording"})
    for m in re.finditer(r"\b(TODO|TBD|FIXME)\b", text):
        hits.append({"kind": "placeholder", "path": path, "text": m.group(0)})
    for m in LOCAL_PATH_RE.finditer(text):
        hits.append({"kind": "local_path", "path": path, "text": m.group(0)})
    for m in DOCS_LINK_RE.finditer(text):
        hits.append({"kind": "docs_link", "path": path, "text": m.group(0)})
    return hits


def tracked_md(repo):
    out = subprocess.run(["git", "-C", repo, "ls-files", "*.md"],
                         capture_output=True, text=True, errors="replace")
    return [p for p in out.stdout.splitlines() if p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--all", action="store_true", help="treat arg as repo root")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--max", type=int, default=10)
    args = ap.parse_args()

    files = []
    if args.all:
        repo = args.paths[0]
        files = [os.path.join(repo, p) for p in tracked_md(repo)]
    else:
        files = args.paths

    all_hits = []
    for f in files:
        if not os.path.isfile(f):
            print("SKIP  %s (not found)" % f)
            continue
        with open(f, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        hits = check_text(f, raw)
        all_hits.extend(hits)
        counts = {}
        for h in hits:
            counts[h["kind"]] = counts.get(h["kind"], 0) + 1
        summary = " ".join("%s=%d" % kv for kv in sorted(counts.items()))
        print("%-40s hits=%-3d %s" % (f.replace(os.sep, "/"), len(hits), summary))
        for h in hits[:12]:
            print("    %-20s %s" % (h["kind"], h["text"]))
        if len(hits) > 12:
            print("    ... %d more" % (len(hits) - 12))

    print("TOTAL files=%d hits=%d" % (len(files), len(all_hits)))
    if args.strict and len(all_hits) >= args.max:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
