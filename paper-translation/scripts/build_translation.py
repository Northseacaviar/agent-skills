# -*- coding: utf-8 -*-
"""把中译 markdown 排成 docx 并导 PDF；支持按锚点插入原版图表截图，
也支持文末附录式的 [[IMG:file|图注]] 行内标记。

用法： python build_translation.py spec.json

spec.json 字段：
    lib      : 译文目录（信息用）
    md       : 中译 markdown 路径（docx/pdf 由它派生）
    img_dir  : 截图目录
    inserts  : [[锚句, 文件名, 图注], ...]  —— 插在该段之后

正文每行也可是 `[[IMG:图片名|图注]]`，用于附录逐张排。
"""
import json
import os
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BODY_FONT = "宋体"
HEAD_FONT = "黑体"
INK = (0x1E, 0x1B, 0x18)
ACCENT = (0x8E, 0x3B, 0x2E)
DIM = (0x6B, 0x63, 0x57)


def set_font(run, size=11, bold=False, color=None, font=HEAD_FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    if color:
        run.font.color.rgb = RGBColor(*color)


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    md = spec["md"]
    docx_path = md[:-3] + ".docx"
    pdf_path = md[:-3] + ".pdf"
    img_dir = spec.get("img_dir", os.path.join(os.path.dirname(md), "图"))
    inserts = [tuple(x) for x in spec.get("inserts", [])]
    used = set()

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.6)
    sec.top_margin = sec.bottom_margin = Cm(2.4)
    st = doc.styles["Normal"]
    st.font.name = BODY_FONT
    st.font.size = Pt(10.5)
    st._element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)

    def add_image(filename, caption):
        path = os.path.join(img_dir, filename)
        if not os.path.exists(path):
            print("缺图", filename)
            return
        from PIL import Image as _Im
        w_px, h_px = _Im.open(path).size
        # 按高封顶：太高会把整页占满、前一页留白
        w_cm = min(15.6, 20.0 * w_px / h_px)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.add_run().add_picture(path, width=Cm(w_cm))
        c = doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_after = Pt(10)
        set_font(c.add_run(caption), 9.5, False, DIM)

    for raw in open(md, encoding="utf-8").read().splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("# "):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(10)
            set_font(p.add_run(line[2:].strip()), 19, True, INK)
        elif line.startswith("## "):
            title = line[3:].strip()
            # 只给「一、二、三…」级标题分页，否则摘要会被单独顶到新页
            if re.match(r"^[一二三四五六七八九十]", title) and doc.paragraphs:
                doc.add_page_break()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(10)
            set_font(p.add_run(title), 15, True, ACCENT)
        elif line.startswith("### "):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(6)
            set_font(p.add_run(line[4:].strip()), 12.5, True, INK)
        elif line.startswith(">"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.0)
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            set_font(p.add_run(line.lstrip("> ").strip()), 10.5, False, (0x3D, 0x36, 0x2D))
        elif re.match(r"^-{3,}$", line.strip()):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            set_font(p.add_run("　" * 40), 8, False, (0xD8, 0xD2, 0xC6))
        elif line.startswith("[[IMG:"):
            fn, cap = line[6:].rstrip("]").split("|", 1)
            add_image(fn.strip(), cap.strip())
        elif line.startswith("*") and line.endswith("*") and len(line) > 20:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(10)
            set_font(p.add_run(line.strip("*")), 9.5, False, DIM)
        else:
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.55
            p.paragraph_format.space_after = Pt(7)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line.strip())
            text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
            set_font(p.add_run(text), 10.5, font=BODY_FONT)
            for anchor, fn, cap in inserts:
                # 锚句要在剥离 ** 之后的 text 上比，带星号的锚句永远命不中
                if fn in used:
                    continue
                if anchor in text:
                    used.add(fn)
                    add_image(fn, cap)

    missing = [fn for _, fn, _ in inserts if fn not in used]
    if missing:
        print("未插入（锚点没命中）:", missing)
    doc.save(docx_path)
    print("DOCX", os.path.getsize(docx_path))

    import win32com.client as win32
    app = win32.Dispatch("Word.Application")
    app.Visible = False
    d = app.Documents.Open(docx_path, ReadOnly=False)
    d.SaveAs(pdf_path, FileFormat=17)
    pages = d.ComputeStatistics(2)
    d.Close(False)
    app.Quit()
    print("PDF", os.path.getsize(pdf_path), "页数", pages)


if __name__ == "__main__":
    main(sys.argv[1])
