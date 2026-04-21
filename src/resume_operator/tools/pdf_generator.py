"""Generate PDF resumes using ReportLab — deterministic rendering from structured data.

The renderer is a pure function of `(ResumeMaster, TailoredResume, template)`.
No LLM involvement, no paragraph-splitting-on-newline, no whitespace heuristics.
Layout (margins, fonts, bullet styles) is controlled by this module — not by
LLM output formatting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from resume_operator.state import FactsBank, ResumeMaster, TailoredItem, TailoredResume
from resume_operator.tools.source_index import build_source_index

logger = logging.getLogger(__name__)


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
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    flowables = _render_default(master, plan)
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


def _render_default(master: ResumeMaster, plan: _RenderPlan) -> list[object]:
    styles = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "Name",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        spaceAfter=2,
        alignment=0,
    )
    contact_style = ParagraphStyle(
        "Contact", parent=styles["BodyText"], fontSize=9, textColor="#555555", spaceAfter=8
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
    )
    role_style = ParagraphStyle(
        "Role",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=11,
        spaceBefore=4,
        spaceAfter=1,
    )
    role_meta_style = ParagraphStyle(
        "RoleMeta",
        parent=styles["BodyText"],
        fontSize=9,
        textColor="#555555",
        spaceAfter=2,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["BodyText"],
        fontSize=10,
        leading=13,
        leftIndent=14,
        spaceAfter=1,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["BodyText"], fontSize=10, leading=13, spaceAfter=2
    )

    flowables: list[object] = []

    # --- Header ---
    if master.name:
        flowables.append(Paragraph(escape(master.name), name_style))
    contact_parts = [p for p in (master.email, master.phone, master.location) if p]
    if contact_parts:
        flowables.append(Paragraph(escape(" | ".join(contact_parts)), contact_style))

    # --- Summary ---
    if plan.summary:
        flowables.append(Paragraph("SUMMARY", section_style))
        flowables.append(Paragraph(escape(plan.summary), body_style))

    # --- Experience (roles in master order) ---
    if plan.experience_by_role:
        flowables.append(Paragraph("EXPERIENCE", section_style))
        master_role_order = [r.id for r in master.experience]
        seen: set[str] = set()
        # First, roles that exist on the master (preserves resume order).
        for role_id in master_role_order:
            bullets = plan.experience_by_role.get(role_id)
            if not bullets:
                continue
            seen.add(role_id)
            role = next((r for r in master.experience if r.id == role_id), None)
            if role is not None:
                flowables.append(Paragraph(_role_header(role), role_style))
                meta = _role_meta(role)
                if meta:
                    flowables.append(Paragraph(escape(meta), role_meta_style))
            for bullet in bullets:
                flowables.append(Paragraph("• " + escape(bullet), bullet_style))
        # Then, virtual buckets ("projects", "extras", etc.) not tied to a master role.
        for virtual_id, bullets in plan.experience_by_role.items():
            if virtual_id in seen:
                continue
            flowables.append(Paragraph(virtual_id.upper(), role_style))
            for bullet in bullets:
                flowables.append(Paragraph("• " + escape(bullet), bullet_style))

    # --- Skills ---
    if plan.skills:
        flowables.append(Paragraph("SKILLS", section_style))
        flowables.append(Paragraph(escape(" • ".join(plan.skills)), body_style))

    # --- Education ---
    if plan.education:
        flowables.append(Paragraph("EDUCATION", section_style))
        for entry in plan.education:
            flowables.append(Paragraph(escape(entry), body_style))

    # --- Certifications ---
    if plan.certifications:
        flowables.append(Paragraph("CERTIFICATIONS", section_style))
        for cert in plan.certifications:
            flowables.append(Paragraph("• " + escape(cert), bullet_style))

    flowables.append(Spacer(1, 0.05 * inch))
    return flowables


def _role_header(role: object) -> str:
    title = escape(getattr(role, "role", "") or "")
    company = escape(getattr(role, "company", "") or "")
    return f"{title} — {company}".strip(" —")


def _role_meta(role: object) -> str:
    parts = []
    location = getattr(role, "location", "") or ""
    start = getattr(role, "start_date", "") or ""
    end = getattr(role, "end_date", "") or ""
    if location:
        parts.append(location)
    if start or end:
        parts.append(f"{start} – {end}".strip(" –"))
    return " | ".join(parts)
