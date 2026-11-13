# -*- coding: utf-8 -*-
"""把中译 Markdown 排成 DOCX，再用 Word COM 导出 PDF。

用法：
    python md_to_docx_pdf.py 译文.md [输出名]

依赖：python-docx、pywin32、Word（导出 PDF 用）。
规则：'# ' 文章标题；'## ' 一级节（自动分页，仅限 摘要/一、二…/结论 这类）；
      '### ' 小节；'> ' 公式或引文；'---' 分隔；其余为正文段落。
"""
import os
import re
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BODY_CN = "宋体"          # 正文中文
HEAD_CN = "黑体"          # 标题中文
INK = (0x1E, 0x1B, 0x18)
ACCENT = (0x8E, 0x3B, 0x2E)
DIM = (0x6B, 0x63, 0x57)


def set_font(run, size=10.5, bold=False, color=None, cn=BODY_CN):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = cn
    # 关键：eastAsia 不写就回落，中文与数字会变成两种字
    run._element.rPr.rFonts.set(qn("w:eastAsia"), cn)
    if color:
        run.font.color.rgb = RGBColor(*color)


def clean(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return re.sub(r"\*([^*\n]+)\*", r"\1", text)


def build(md_path, out_dir=None):
    md = open(md_path, encoding="utf-8").read().splitlines()
    base = os.path.splitext(os.path.basename(md_path))[0]
    out_dir = out_dir or os.path.dirname(os.path.abspath(md_path))
    docx_path = os.path.join(out_dir, base + ".docx")

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.6)
    sec.top_margin = sec.bottom_margin = Cm(2.4)

    st = doc.styles["Normal"]
    st.font.name = BODY_CN
    st.font.size = Pt(10.5)
    st._element.rPr.rFonts.set(qn("w:eastAsia"), BODY_CN)

    for raw in md:
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("# "):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(10)
            set_font(p.add_run(clean(line[2:].strip())), 19, True, INK, HEAD_CN)
        elif line.startswith("## "):
            title = clean(line[3:].strip())
            # 只给「摘要 / 一、二、… / 结论 / 参考文献」这类分页，避免半空页
            if re.match(r"^[一二三四五六七八九十]|^摘要|^结论|^参考文献", title) and doc.paragraphs:
                doc.add_page_break()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(10)
            set_font(p.add_run(title), 15, True, ACCENT, HEAD_CN)
        elif line.startswith("### "):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(6)
            set_font(p.add_run(clean(line[4:].strip())), 12.5, True, INK, HEAD_CN)
        elif line.startswith(">"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.0)
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            set_font(p.add_run(clean(line.lstrip("> ").strip())), 10.5, False, (0x3D, 0x36, 0x2D))
        elif re.match(r"^-{3,}$", line.strip()):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            set_font(p.add_run("　" * 40), 8, False, (0xD8, 0xD2, 0xC6))
        else:
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.55
            p.paragraph_format.space_after = Pt(7)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            set_font(p.add_run(clean(line.strip())), 10.5)

    doc.save(docx_path)
    print("DOCX:", docx_path, os.path.getsize(docx_path))

    import win32com.client as win32
    pdf_path = os.path.join(out_dir, base + ".pdf")
    app = win32.Dispatch("Word.Application")
    app.Visible = False
    try:
        d = app.Documents.Open(docx_path, ReadOnly=False)
        d.SaveAs(pdf_path, FileFormat=17)
        pages = d.ComputeStatistics(2)
        d.Close(False)
    finally:
        app.Quit()
    print("PDF:", pdf_path, os.path.getsize(pdf_path), "页数", pages)
    return pdf_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    build(sys.argv[1])
