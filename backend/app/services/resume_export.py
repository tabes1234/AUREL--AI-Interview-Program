"""履历成章：简历导出（PDF / DOCX）。

- PDF 使用 reportlab platypus：自动分页、长文本自动换行；中文优先注册本机
  微软雅黑/黑体/宋体，全部失败时回退 Adobe CID 字体 STSong-Light（无需字体文件）。
- DOCX 使用 python-docx：显式设置中文字体（w:eastAsia），确保中文正常显示。
- 版式差异由模板目录（resume_templates）驱动：分节顺序、主题色、标题对齐、分栏。
"""

import io
import re

from app.schemas.resume import ResumeContent
from app.services.resume_templates import get_template

SECTION_TITLES = {
    "summary": "个人概述",
    "work": "实习与工作经历",
    "projects": "项目经历",
    "education": "教育经历",
    "skills": "技能与工具",
    "certificates": "证书与语言能力",
    "awards": "奖项与其他经历",
    "links": "作品与链接",
}

_PLACEHOLDER = re.compile(r"【待补充[^】]*】")


def _has_content(text: str | None) -> bool:
    return bool(text and text.strip())


def export_filename(resume_title: str, version_no: int, ext: str) -> str:
    safe = re.sub(r"[\\/:*?\"<>|\s]+", "_", resume_title).strip("_") or "resume"
    return f"{safe}_v{version_no}.{ext}"


# ---------- 内容装配（PDF / DOCX 共用） ----------


def _ordered_sections(content: ResumeContent, template: dict) -> list[tuple[str, list]]:
    """按模板 section_order 返回非空小节：(key, 渲染所需数据)。"""
    ordered: list[tuple[str, list]] = []
    for key in template["section_order"]:
        if key == "summary":
            if _has_content(content.basics.summary):
                ordered.append((key, [content.basics.summary]))
        elif key == "links":
            if _has_content(content.basics.links):
                ordered.append((key, [content.basics.links]))
        elif key == "education":
            if content.education:
                ordered.append((key, content.education))
        elif key in ("work", "projects"):
            entries = content.work if key == "work" else content.projects
            if entries:
                ordered.append((key, entries))
        elif key == "skills" and content.skills:
            ordered.append((key, content.skills))
        elif key == "certificates" and content.certificates:
            ordered.append((key, content.certificates))
        elif key == "awards" and content.awards:
            ordered.append((key, content.awards))
    return ordered


def _contact_line(content: ResumeContent) -> str:
    basics = content.basics
    parts = [basics.phone, basics.email, basics.location, basics.links]
    return " ｜ ".join(p.strip() for p in parts if p and p.strip())


def _entry_period(start: str, end: str) -> str:
    return " — ".join(x for x in (start.strip(), end.strip()) if x)


# ---------- PDF ----------

_PDF_FONT: str | None = None


def _pdf_font() -> str:
    global _PDF_FONT
    if _PDF_FONT:
        return _PDF_FONT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        (r"C:\Windows\Fonts\msyh.ttc", {"subfontIndex": 0}),
        (r"C:\Windows\Fonts\simhei.ttf", {}),
        (r"C:\Windows\Fonts\simsun.ttc", {"subfontIndex": 0}),
        (r"C:\Windows\Fonts\msyhbd.ttc", {"subfontIndex": 0}),
    ]
    for path, kwargs in candidates:
        try:
            pdfmetrics.registerFont(TTFont("AurelCJK", path, **kwargs))
            _PDF_FONT = "AurelCJK"
            return _PDF_FONT
        except Exception:  # noqa: BLE001 — 字体缺失时逐个回退
            continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _PDF_FONT = "STSong-Light"
    return _PDF_FONT


def export_pdf(content: ResumeContent, template_id: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    template = get_template(template_id) or get_template("clean")
    accent = colors.HexColor(template["accent"])
    font = _pdf_font()

    name_style = ParagraphStyle(
        "Name", fontName=font, fontSize=20, leading=26,
        alignment=TA_CENTER if template["header_align"] == "center" else 0,
        textColor=colors.HexColor("#263B57"),
    )
    contact_style = ParagraphStyle(
        "Contact", fontName=font, fontSize=9, leading=14,
        alignment=TA_CENTER if template["header_align"] == "center" else 0,
        textColor=colors.HexColor("#7185A2"),
    )
    heading_style = ParagraphStyle(
        "Heading", fontName=font, fontSize=12, leading=16, spaceBefore=10, spaceAfter=4,
        textColor=accent,
    )
    body_style = ParagraphStyle(
        "Body", fontName=font, fontSize=10, leading=16, textColor=colors.HexColor("#263B57"),
    )
    muted_style = ParagraphStyle(
        "Muted", fontName=font, fontSize=9, leading=14, textColor=colors.HexColor("#7185A2"),
    )
    bullet_style = ParagraphStyle(
        "Bullet", fontName=font, fontSize=10, leading=16, leftIndent=10,
        bulletIndent=0, textColor=colors.HexColor("#263B57"),
    )

    def esc(text: str) -> str:
        cleaned = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # 待补充占位在导出中保持可见，方便用户发现缺失信息
        return cleaned

    story: list = []
    name = content.basics.name.strip() or "（姓名待补充）"
    story.append(Paragraph(esc(name), name_style))
    contact = _contact_line(content)
    if contact:
        story.append(Spacer(1, 2))
        story.append(Paragraph(esc(contact), contact_style))
    story.append(HRFlowable(width="100%", thickness=0.8, color=accent, spaceBefore=6, spaceAfter=2))

    for key, items in _ordered_sections(content, template):
        story.append(Paragraph(SECTION_TITLES[key], heading_style))
        story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#DCE8F7"), spaceAfter=4))
        if key in ("summary", "links"):
            story.append(Paragraph(esc(str(items[0])), body_style))
        elif key == "education":
            for e in items:
                head = " ｜ ".join(
                    x for x in (e.school, e.degree, e.major) if _has_content(x)
                )
                period = _entry_period(e.start, e.end)
                story.append(Paragraph(esc(head) + (f"　{esc(period)}" if period else ""), body_style))
                if _has_content(e.details):
                    story.append(Paragraph(esc(e.details), muted_style))
        elif key in ("work", "projects"):
            for e in items:
                head = " ｜ ".join(x for x in (e.name, e.role) if _has_content(x))
                period = _entry_period(e.start, e.end)
                line = esc(head) + (f"　{esc(period)}" if period else "")
                if _has_content(e.link):
                    line += f"　{esc(e.link)}"
                story.append(Paragraph(line, body_style))
                for hl in e.highlights:
                    if _has_content(hl):
                        story.append(Paragraph(esc(hl), bullet_style, bulletText="·"))
        elif key == "skills":
            for s in items:
                label = " ｜ ".join(x for x in (s.name, s.level) if _has_content(x))
                detail = f"：{s.detail}" if _has_content(s.detail) else ""
                if _has_content(label) or detail:
                    story.append(Paragraph(esc(label) + esc(detail), bullet_style, bulletText="·"))
        elif key == "certificates":
            for c in items:
                line = " ｜ ".join(x for x in (c.name, c.issuer, c.date) if _has_content(x))
                story.append(Paragraph(esc(line), bullet_style, bulletText="·"))
        elif key == "awards":
            for a in items:
                line = " ｜ ".join(x for x in (a.name, a.issuer, a.date) if _has_content(x))
                story.append(Paragraph(esc(line), bullet_style, bulletText="·"))
                if _has_content(a.detail):
                    story.append(Paragraph(esc(a.detail), muted_style))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=content.basics.name or "简历",
    )
    doc.build(story)
    return buffer.getvalue()


# ---------- DOCX ----------


def export_docx(content: ResumeContent, template_id: str) -> bytes:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    template = get_template(template_id) or get_template("clean")
    accent = RGBColor.from_string(template["accent"].lstrip("#"))
    ink = RGBColor(0x26, 0x3B, 0x57)
    muted = RGBColor(0x71, 0x85, 0xA2)

    doc = docx.Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    def para(text: str, *, size=10.5, bold=False, color=None, align=None, bullet=False):
        style = "List Bullet" if bullet else None
        p = doc.add_paragraph(style=style)
        run = p.add_run(text)
        run.font.size = Pt(size)
        run.font.bold = bold
        if color is not None:
            run.font.color.rgb = color
        run.font.name = "Calibri"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
        if align is not None:
            p.alignment = align
        return p

    def heading(text: str):
        para(text, size=12.5, bold=True, color=accent)
        para("", size=2)

    name = content.basics.name.strip() or "（姓名待补充）"
    align = WD_ALIGN_PARAGRAPH.CENTER if template["header_align"] == "center" else None
    para(name, size=20, bold=True, color=ink, align=align)
    contact = _contact_line(content)
    if contact:
        para(contact, size=9, color=muted, align=align)

    for key, items in _ordered_sections(content, template):
        heading(SECTION_TITLES[key])
        if key in ("summary", "links"):
            para(str(items[0]))
        elif key == "education":
            for e in items:
                head = " ｜ ".join(x for x in (e.school, e.degree, e.major) if _has_content(x))
                period = _entry_period(e.start, e.end)
                para((head + ("　" + period if period else "")).strip("｜ "), bold=True)
                if _has_content(e.details):
                    para(e.details, size=9.5, color=muted)
        elif key in ("work", "projects"):
            for e in items:
                head = " ｜ ".join(x for x in (e.name, e.role) if _has_content(x))
                period = _entry_period(e.start, e.end)
                if _has_content(e.link):
                    head += f" ｜ {e.link}"
                para((head + ("　" + period if period else "")).strip("｜ "), bold=True)
                for hl in e.highlights:
                    if _has_content(hl):
                        para(hl, bullet=True)
        elif key == "skills":
            for s in items:
                label = " ｜ ".join(x for x in (s.name, s.level) if _has_content(x))
                para((label + (f"：{s.detail}" if _has_content(s.detail) else "")).strip("｜ "), bullet=True)
        elif key == "certificates":
            for c in items:
                para(" ｜ ".join(x for x in (c.name, c.issuer, c.date) if _has_content(x)), bullet=True)
        elif key == "awards":
            for a in items:
                para(" ｜ ".join(x for x in (a.name, a.issuer, a.date) if _has_content(x)), bullet=True)
                if _has_content(a.detail):
                    para(a.detail, size=9.5, color=muted)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
