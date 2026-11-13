# -*- coding: utf-8 -*-
"""去掉券商研报 PDF 的渠道水印：整页背景图 + 页脚隐形白字，然后逐页比对文字长度。

用法：
    python remove_watermark.py <src.pdf> <dst.pdf> [--dry-run]

做法：
    1. pikepdf：抽掉出现在多数页面上的大图（按 /Resources/XObject 的 xref 认，不认 rect），
       并把内容流里对应的 `Do` 一并摘掉。
    2. pymupdf：redaction 删白色、<=4pt、无空格的长串隐形文字（渠道追踪串）。
    3. 逐页打印 len(get_text()) 与原文的差；只允许藏隐形字那几页变短。

依赖：pymupdf、pikepdf（非标准库，需 pip install pymupdf pikepdf）。
"""
import argparse

import pikepdf
import pymupdf
from pikepdf import Name, unparse_content_stream

WHITE = 0xFFFFFF


def find_images(doc, share, min_pixels):
    n = doc.page_count
    counts = {}
    for page in doc:
        for im in page.get_images(full=True):
            counts[im[0]] = counts.get(im[0], 0) + 1
    cands = []
    for xref, c in counts.items():
        if c < max(2, share * n):
            continue
        info = doc.extract_image(xref)
        if info["width"] * info["height"] >= min_pixels:
            cands.append(xref)
            print(f"[img ] xref {xref}: {info['width']}x{info['height']} "
                  f"on {c}/{n} pages -> 整页水印图候选")
    return cands


def find_invisible_text(doc, max_size):
    hits = []
    for i, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    t = span["text"].strip()
                    if (span["color"] == WHITE and span["size"] <= max_size
                            and len(t) >= 12 and " " not in t):
                        hits.append((i, t, span["bbox"]))
                        print(f"[text] p{i + 1}: {t[:32]}… len={len(t)} "
                              f"size={span['size']} color=white")
    return hits


def strip_images(src, dst, xrefs):
    pdf = pikepdf.open(src)
    targets = set(xrefs)
    touched = 0
    for i, page in enumerate(pdf.pages):
        resources = page.get("/Resources", None)
        if resources is None:
            continue
        xobj = resources.get("/XObject", None)
        if xobj is None:
            continue
        names = []
        for key in list(xobj.keys()):
            try:
                objgen = xobj[key].objgen
            except Exception:
                continue
            if objgen[0] in targets:
                names.append(str(key))
        for nm in names:
            del xobj[Name(nm)]
        if not names:
            continue
        cs = pikepdf.parse_content_stream(page)
        kept = [(operands, op) for operands, op in cs
                if not (str(op) == "Do" and len(operands) == 1 and str(operands[0]) in names)]
        page.Contents = pdf.make_stream(unparse_content_stream(kept))
        touched += 1
        print(f"[img ] p{i + 1}: dropped {names}, {len(cs) - len(kept)} Do op(s)")
    pdf.save(dst)
    return touched


def strip_text(src, dst, max_size):
    doc = pymupdf.open(src)
    total = 0
    for page in doc:
        dirty = 0
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    t = span["text"].strip()
                    if (span["color"] == WHITE and span["size"] <= max_size
                            and len(t) >= 12 and " " not in t):
                        for rect in page.search_for(t):
                            page.add_redact_annot(rect, fill=False)
                            dirty += 1
        # 不要用 page.first_redact 判断：它不是公开稳定的属性，改成自己计数
        if dirty:
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                                  graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                                  text=pymupdf.PDF_REDACT_TEXT_REMOVE)
            total += dirty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--share", type=float, default=0.6,
                    help="出现在多少比例的页面上算整页水印图（默认 0.6）")
    ap.add_argument("--min-pixels", type=int, default=1_000_000)
    ap.add_argument("--max-text-size", type=float, default=4.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    doc = pymupdf.open(a.src)
    before = [len(p.get_text()) for p in doc]
    imgs = find_images(doc, a.share, a.min_pixels)
    find_invisible_text(doc, a.max_text_size)
    doc.close()

    if a.dry_run:
        print("— dry run，未写文件")
        return

    mid = a.dst + ".img.tmp"
    if imgs:
        strip_images(a.src, mid, imgs)
    else:
        import shutil
        shutil.copyfile(a.src, mid)
        print("[img ] 未找到整页水印图，跳过")
    n = strip_text(mid, a.dst, a.max_text_size)
    print(f"[text] redacted {n} span(s)")

    out = pymupdf.open(a.dst)
    after = [len(p.get_text()) for p in out]
    print("\nper-page text length (src -> dst, diff)")
    for i, (b, c) in enumerate(zip(before, after)):
        flag = "" if b == c else "  <-- changed"
        print(f"  p{i + 1:<3} {b:>6} -> {c:>6}  {c - b:+d}{flag}")
    print(f"\n{len(before)} pages, {a.src} -> {a.dst}")
    print("下一步：把首页与任意正文页各渲一张 PNG 自己看，确认页眉 logo 与正文没被一起删掉。")


if __name__ == "__main__":
    main()
