"""Generate PDF resumes using ReportLab — deterministic rendering from structured data.

The renderer is a pure function of `(ResumeMaster, TailoredResume, template)`.
No LLM involvement, no paragraph-splitting-on-newline, no whitespace heuristics.
Layout (margins, fonts, bullet styles) is controlled by this module — not by
LLM output formatting.

The `default` template targets both audiences:
  - ATS parsers: single column, selectable text, standard fonts, no images/tables-for-layout
  - Recruiters' 6-second scan: name banner + accent rule, small-caps section rules,
    right-aligned dates per role, hanging-indent bullets, one muted accent colour
"""

from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from resume_operator.state import FactsBank, ResumeMaster, TailoredItem, TailoredResume
from resume_operator.tools.source_index import build_source_index

logger = logging.getLogger(__name__)

# Template palette. One muted accent used only for the name rule, section rules,
# and the right-aligned date strings. Body text stays black.
_ACCENT = HexColor("#2C5282")  # deep muted blue
_MUTED_GREY = HexColor("#555555")
_RULE_GREY = HexColor("#CBD5E0")

# Margins: tighter than the baseline so a well-packed one-pager fits without feeling cramped.
_MARGIN = 0.6 * inch


def generate_pdf(
    master: ResumeMaster,
    tailored: TailoredResume,
    output_path: Path,
    template: str = "default",
    facts: FactsBank | None = None,
) -> Path:
    """Render a tailored resume to PDF from structured data.

    Args:
        master: The full hand-maintained master resume. Provides name/contact + role headers.
        tailored: The per-item tailoring decisions. Only `keep` and `reword` items are rendered.
        output_path: Where to write the PDF.
        template: Template name (default | compact | modern). Only `default` is implemented;
            unknown values fall back to default with a warning.
        facts: Optional facts bank — passing it lets the renderer correctly classify
            facts-bank items (projects, extra bullets) instead of treating them as skills.

    Returns:
        Path to the generated PDF file.
    """
    logger.info("pdf_generator: generating PDF at %s (template=%s)", output_path, template)
    if template != "default":
        logger.warning(
            "pdf_generator: template %r not implemented, falling back to default", template
        )

    plan = _build_render_plan(master, tailored, facts)
    if not plan.has_content():
        raise ValueError("tailored resume has no renderable items")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
    )

    flowables = _render_default(master, plan, doc.width)
    doc.build(flowables)
    logger.info(
        "pdf_generator: completed — roles=%d, bullets=%d, skills=%d, %s",
        len(plan.experience_by_role),
        sum(len(v) for v in plan.experience_by_role.values()),
        len(plan.skills),
        output_path,
    )
    return output_path


class _RenderPlan:
    """Structured, layout-agnostic view of what to render."""

    def __init__(self) -> None:
        self.summary: str = ""
        # ordered: role_id -> list of bullet texts (kept/reworded)
        self.experience_by_role: dict[str, list[str]] = {}
        self.education: list[str] = []
        self.skills: list[str] = []
        self.certifications: list[str] = []

    def has_content(self) -> bool:
        return bool(
            self.summary
            or self.experience_by_role
            or self.education
            or self.skills
            or self.certifications
        )


def _build_render_plan(
    master: ResumeMaster, tailored: TailoredResume, facts: FactsBank | None
) -> _RenderPlan:
    """Group kept/reworded tailored items by kind so the renderer can position them."""
    index = build_source_index(master, facts)
    plan = _RenderPlan()

    for item in tailored.kept_or_reworded():
        entry = index.get(item.source_id)
        kind = entry.kind if entry else _infer_kind(item)
        text = _text_for(item)

        if kind == "summary":
            plan.summary = text
        elif kind == "experience-bullet":
            role_id = _role_id_from_bullet_source(item.source_id)
            plan.experience_by_role.setdefault(role_id, []).append(text)
        elif kind.startswith("extra-bullet"):
            # "extra-bullet[exp-1]" carries the target role in brackets.
            role_id = _extract_role_id(kind) or "extras"
            plan.experience_by_role.setdefault(role_id, []).append(text)
        elif kind == "project":
            plan.experience_by_role.setdefault("projects", []).append(text)
        elif kind == "education":
            plan.education.append(text)
        elif kind == "skill":
            plan.skills.append(text)
        elif kind == "certification":
            plan.certifications.append(text)
        # experience-header items don't render — the role header comes from `master`.

    return plan


def _text_for(item: TailoredItem) -> str:
    return item.new_text.strip() if item.new_text.strip() else item.original_text.strip()


def _role_id_from_bullet_source(source_id: str) -> str:
    """`master:exp-1-b3` → `exp-1`."""
    body = source_id.split(":", 1)[1] if ":" in source_id else source_id
    # bullet ids follow the pattern `<role-id>-b<n>`; strip the trailing `-b<n>`.
    if "-b" in body:
        return body.rsplit("-b", 1)[0]
    return body


def _extract_role_id(kind: str) -> str | None:
    """`extra-bullet[exp-1]` → `exp-1`."""
    if "[" in kind and kind.endswith("]"):
        return kind[kind.index("[") + 1 : -1]
    return None


def _infer_kind(item: TailoredItem) -> str:
    """Fallback kind for items not in the index — shouldn't happen post-validation."""
    return "skill" if item.source_id.startswith(("master:skill", "facts:skill")) else "skill"


def _render_default(master: ResumeMaster, plan: _RenderPlan, frame_width: float) -> list[object]:
    styles = _default_styles()
    flowables: list[object] = []

    # --- Header: name banner + accent rule + contact line ---
    if master.name:
        flowables.append(Paragraph(escape(master.name), styles["name"]))
    flowables.append(
        HRFlowable(
            width="100%",
            thickness=1.2,
            color=_ACCENT,
            spaceBefore=1,
            spaceAfter=4,
        )
    )
    contact_parts = [p for p in (master.email, master.phone, master.location) if p]
    if contact_parts:
        flowables.append(Paragraph(escape("  ·  ".join(contact_parts)), styles["contact"]))

    # --- Summary ---
    if plan.summary:
        flowables.extend(_section_header("SUMMARY", frame_width))
        flowables.append(Paragraph(escape(plan.summary), styles["body"]))

    # --- Experience (roles in master order) ---
    if plan.experience_by_role:
        flowables.extend(_section_header("EXPERIENCE", frame_width))
        master_role_order = [r.id for r in master.experience]
        seen: set[str] = set()
        for role_id in master_role_order:
            bullets = plan.experience_by_role.get(role_id)
            if not bullets:
                continue
            seen.add(role_id)
            role = next((r for r in master.experience if r.id == role_id), None)
            if role is not None:
                flowables.append(_role_row(role, styles, frame_width))
            for bullet in bullets:
                flowables.append(Paragraph(_bullet(bullet), styles["bullet"]))
            flowables.append(Spacer(1, 0.05 * inch))
        # Virtual buckets ("projects", "extras") not tied to a master role.
        for virtual_id, bullets in plan.experience_by_role.items():
            if virtual_id in seen:
                continue
            flowables.append(Paragraph(escape(virtual_id.upper()), styles["role_title"]))
            for bullet in bullets:
                flowables.append(Paragraph(_bullet(bullet), styles["bullet"]))
            flowables.append(Spacer(1, 0.05 * inch))

    # --- Skills ---
    if plan.skills:
        flowables.extend(_section_header("SKILLS", frame_width))
        flowables.append(Paragraph(escape("  ·  ".join(plan.skills)), styles["body"]))

    # --- Education ---
    if plan.education:
        flowables.extend(_section_header("EDUCATION", frame_width))
        for entry in plan.education:
            flowables.append(Paragraph(escape(entry), styles["body"]))

    # --- Certifications ---
    if plan.certifications:
        flowables.extend(_section_header("CERTIFICATIONS", frame_width))
        for cert in plan.certifications:
            flowables.append(Paragraph(_bullet(cert), styles["bullet"]))

    flowables.append(Spacer(1, 0.05 * inch))
    return flowables


def _default_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "Name",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=24,
            textColor=HexColor("#1A202C"),
            spaceAfter=0,
            alignment=0,
        ),
        "contact": ParagraphStyle(
            "Contact",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            textColor=_MUTED_GREY,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12,
            textColor=_ACCENT,
            spaceBefore=8,
            spaceAfter=0,
        ),
        "role_title": ParagraphStyle(
            "RoleTitle",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=HexColor("#1A202C"),
            spaceBefore=0,
            spaceAfter=0,
        ),
        "role_dates": ParagraphStyle(
            "RoleDates",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=_MUTED_GREY,
            alignment=2,  # right
        ),
        "bullet": ParagraphStyle(
            # Inline bullet with hanging indent. Keeping the `•` inline (rather than
            # using `bulletText` on the style) means PDF text extractors read the
            # bullet and its content on the same line, which matters for ATS parsers
            # that consume text line-by-line. `firstLineIndent=-leftIndent` gives us
            # the visual hanging indent without a separate bullet frame.
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=HexColor("#2D3748"),
            leftIndent=14,
            firstLineIndent=-14,
            spaceAfter=1,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=HexColor("#2D3748"),
            spaceAfter=2,
        ),
    }


def _section_header(title: str, frame_width: float) -> list[object]:
    """Uppercase section title followed by a thin grey rule across the frame."""
    return [
        Paragraph(escape(title), _default_styles()["section"]),
        HRFlowable(
            width=frame_width,
            thickness=0.5,
            color=_RULE_GREY,
            spaceBefore=1,
            spaceAfter=3,
        ),
    ]


def _role_row(role: object, styles: dict[str, ParagraphStyle], frame_width: float) -> Table:
    """Two-column row: role + company on the left, dates/location right-aligned."""
    left = Paragraph(escape(_role_header_text(role)), styles["role_title"])
    right = Paragraph(escape(_role_meta_text(role)), styles["role_dates"])

    # 65 / 35 split — date strings are short, role/company is the prime real estate.
    left_w = frame_width * 0.65
    right_w = frame_width - left_w
    table = Table([[left, right]], colWidths=[left_w, right_w])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return table


def _bullet(text: str) -> str:
    """Format bullet content as `• <text>` so the glyph and content extract on one line."""
    return f"• {escape(text)}"


def _role_header_text(role: object) -> str:
    title = getattr(role, "role", "") or ""
    company = getattr(role, "company", "") or ""
    if title and company:
        return f"{title} — {company}"
    return title or company


def _role_meta_text(role: object) -> str:
    location = getattr(role, "location", "") or ""
    start = getattr(role, "start_date", "") or ""
    end = getattr(role, "end_date", "") or ""
    dates = f"{start} – {end}".strip(" –") if (start or end) else ""
    parts = [p for p in (location, dates) if p]
    return "  ·  ".join(parts)
