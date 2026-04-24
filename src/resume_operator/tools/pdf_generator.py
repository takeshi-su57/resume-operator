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
from reportlab.lib.styles import ParagraphStyle
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
from resume_operator.tools.style import StyleTemplate, build_all_styles

logger = logging.getLogger(__name__)


# --- Unicode sanitization -------------------------------------------------
#
# Helvetica (ReportLab's built-in Type-1 font) ships with Adobe Standard
# Encoding — roughly Latin-1 plus a handful of punctuation. When the LLM
# emits chars outside that coverage (arrows, non-breaking hyphens, curly
# quotes, zero-width spaces…), ReportLab renders the `.notdef` glyph — a
# black filled box. Translate the common offenders to ASCII equivalents
# before the text hits the renderer.

_TRANSLATE: dict[int, str] = {
    # Dashes
    0x2011: "-",  # non-breaking hyphen
    0x2013: "-",  # en dash
    0x2212: "-",  # minus sign
    # Arrows
    0x2192: "->",  # rightwards arrow
    0x2190: "<-",  # leftwards arrow
    0x21D2: "=>",  # rightwards double arrow
    0x21D0: "<=",  # leftwards double arrow
    0x2194: "<->",  # left-right arrow
    # Quotes
    0x2018: "'",  # left single quote
    0x2019: "'",  # right single quote / apostrophe
    0x201A: "'",  # single low-9 quote
    0x201C: '"',  # left double quote
    0x201D: '"',  # right double quote
    0x201E: '"',  # double low-9 quote
    # Ellipsis + punctuation
    0x2026: "...",  # horizontal ellipsis
    # Whitespace
    0x00A0: " ",  # non-breaking space
}

# Invisible chars to strip outright — they carry no rendered glyph and often
# end up as `.notdef` boxes when the LLM slips them in.
_STRIP_CHARS = "".join(
    chr(c)
    for c in (
        0x200B,  # zero-width space
        0x200C,  # zero-width non-joiner
        0x200D,  # zero-width joiner
        0x2060,  # word joiner
        0xFEFF,  # BOM / zero-width no-break space
        0x00AD,  # soft hyphen
    )
)
_STRIP_TABLE: dict[int, None] = {ord(c): None for c in _STRIP_CHARS}


def _sanitize_for_pdf(text: str) -> str:
    """Translate exotic Unicode to ASCII and strip invisible/zero-width chars.

    Runs at the renderer boundary. `tailored.yaml` / `facts_bank.yaml` keep the
    LLM's original text; only the PDF text stream is normalized.
    """
    if not text:
        return text
    # Strip the invisible offenders first so subsequent whitespace collapse works.
    cleaned = text.translate(_STRIP_TABLE).translate(_TRANSLATE)
    # Collapse any run of whitespace (including the non-breaking space we just
    # converted) down to a single space, without touching deliberate newlines.
    lines = [" ".join(line.split()) for line in cleaned.splitlines()]
    return "\n".join(lines).strip()


def generate_pdf(
    master: ResumeMaster,
    tailored: TailoredResume,
    output_path: Path,
    template: str = "default",
    facts: FactsBank | None = None,
    style: StyleTemplate | None = None,
) -> Path:
    """Render a tailored resume to PDF from structured data.

    Args:
        master: The full hand-maintained master resume. Provides name/contact + role headers.
        tailored: The per-item tailoring decisions. Only `keep` and `reword` items are rendered.
        output_path: Where to write the PDF.
        template: Legacy string template name — kept for back-compat; `style` overrides it (#72).
        facts: Optional facts bank — passing it lets the renderer correctly classify
            facts-bank items (projects, extra bullets) instead of treating them as skills.
        style: Full `StyleTemplate` controlling fonts/sizes/colours/margins/spacing. When
            `None`, a default template is used (matches the pre-#72 hardcoded constants).

    Returns:
        Path to the generated PDF file.
    """
    effective_style = style if style is not None else StyleTemplate()
    logger.info(
        "pdf_generator: generating PDF at %s (style=%r, font=%r)",
        output_path,
        effective_style.name,
        effective_style.font_family,
    )

    plan = _build_render_plan(master, tailored, facts)
    if not plan.has_content():
        raise ValueError("tailored resume has no renderable items")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    margin_side = effective_style.margins.side * inch
    margin_top = effective_style.margins.top * inch
    margin_bottom = effective_style.margins.bottom * inch
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=margin_side,
        rightMargin=margin_side,
        topMargin=margin_top,
        bottomMargin=margin_bottom,
    )

    flowables = _render_default(master, plan, doc.width, effective_style)
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
        self.headline: str = ""  # #70: tailored_headline (dynamic) or master.headline (fallback)
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

    # Tailored summary (issue #66) / headline (issue #70) — dynamic per-JD
    # strings the tailor writes fresh each run. When non-empty they win over
    # their static `master.*` equivalents.
    if tailored.tailored_summary:
        plan.summary = tailored.tailored_summary
    plan.headline = tailored.tailored_headline or master.headline

    for item in tailored.kept_or_reworded():
        entry = index.get(item.source_id)
        kind = entry.kind if entry else _infer_kind(item)
        text = _text_for(item)

        if kind == "summary":
            # If the optimizer populated `tailored_summary`, that already filled
            # plan.summary; skip here to avoid duplicate rendering.
            if tailored.tailored_summary:
                continue
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


def _render_default(
    master: ResumeMaster,
    plan: _RenderPlan,
    frame_width: float,
    style: StyleTemplate,
) -> list[object]:
    styles = build_all_styles(style)
    accent_color = HexColor(style.colors.accent)
    rule_color = HexColor(style.colors.rule)
    flowables: list[object] = []

    # --- Header: name → tagline → accent rule → contact → links ---
    if master.name:
        flowables.append(Paragraph(escape(_sanitize_for_pdf(master.name)), styles["name"]))
    # Tagline sits between name and rule so name+tagline feel like one block (#68).
    # #70: tailored_headline wins over master.headline when non-empty — the tailor
    # crafts it per-JD (same pattern as tailored_summary). master.headline is the
    # fallback used for score-only runs or when the tailor didn't emit one.
    effective_headline = plan.headline
    if effective_headline:
        flowables.append(
            Paragraph(escape(_sanitize_for_pdf(effective_headline)), styles["headline"])
        )
    flowables.append(
        HRFlowable(
            width="100%",
            thickness=style.accent_rule_thickness,
            color=accent_color,
            spaceBefore=1,
            spaceAfter=4,
        )
    )
    contact_parts = [
        _sanitize_for_pdf(p) for p in (master.email, master.phone, master.location) if p
    ]
    if contact_parts:
        flowables.append(Paragraph(escape("  ·  ".join(contact_parts)), styles["contact"]))
    # Second contact line for portfolio / LinkedIn / GitHub when present (#68).
    if master.links:
        link_parts = [
            _sanitize_for_pdf(f"{lk.label}: {lk.url}" if lk.label else lk.url)
            for lk in master.links
            if lk.url or lk.label
        ]
        if link_parts:
            flowables.append(Paragraph(escape("  ·  ".join(link_parts)), styles["contact"]))

    # --- Summary ---
    # Uses the dedicated `summary` style (#74): same as body but with a ~2
    # character-width first-line indent so the paragraph reads as prose.
    if plan.summary:
        flowables.extend(_section_header("SUMMARY", frame_width, styles, style, rule_color))
        flowables.append(Paragraph(escape(_sanitize_for_pdf(plan.summary)), styles["summary"]))

    # --- Experience (roles in master order) ---
    if plan.experience_by_role:
        flowables.extend(_section_header("EXPERIENCE", frame_width, styles, style, rule_color))
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
                flowables.append(Paragraph(_bullet(bullet, style), styles["bullet"]))
            # Per-role tech line (#68). Sits right under the bullets as a dim italic
            # summary — ATS keyword bonus + recruiter skim aid.
            if role is not None and role.tech:
                tech_str = "Tech: " + ", ".join(role.tech)
                flowables.append(Paragraph(escape(_sanitize_for_pdf(tech_str)), styles["tech"]))
            flowables.append(Spacer(1, 0.05 * inch))
        # Virtual buckets ("projects", "extras") not tied to a master role.
        for virtual_id, bullets in plan.experience_by_role.items():
            if virtual_id in seen:
                continue
            flowables.append(
                Paragraph(escape(_sanitize_for_pdf(virtual_id.upper())), styles["role_title"])
            )
            for bullet in bullets:
                flowables.append(Paragraph(_bullet(bullet, style), styles["bullet"]))
            flowables.append(Spacer(1, 0.05 * inch))

    # --- Skills ---
    # When the master has `skill_groups`, render grouped (one line per category,
    # bolded category label + comma-separated items). Otherwise fall back to the
    # flat `·`-separated line (#68 back-compat).
    tailored_skills_set = {s for s in plan.skills}
    visible_groups: list[tuple[str, list[str]]] = []
    for group in master.skill_groups:
        # Only include items that survived tailoring (were kept/reworded into plan.skills).
        # If plan.skills is empty (e.g. the tailor didn't return skill items), fall
        # through to the flat path below.
        if tailored_skills_set:
            filtered = [s for s in group.items if s in tailored_skills_set]
        else:
            filtered = list(group.items)
        if filtered:
            visible_groups.append((group.category, filtered))

    if visible_groups:
        flowables.extend(_section_header("SKILLS", frame_width, styles, style, rule_color))
        for category, items in visible_groups:
            sanitized_items = [_sanitize_for_pdf(i) for i in items]
            line = f"<b>{escape(_sanitize_for_pdf(category))}:</b> " + escape(
                ", ".join(sanitized_items)
            )
            flowables.append(Paragraph(line, styles["body"]))
    elif plan.skills:
        flowables.extend(_section_header("SKILLS", frame_width, styles, style, rule_color))
        sanitized_skills = [_sanitize_for_pdf(s) for s in plan.skills]
        flowables.append(Paragraph(escape("  ·  ".join(sanitized_skills)), styles["body"]))

    # --- Education ---
    if plan.education:
        flowables.extend(_section_header("EDUCATION", frame_width, styles, style, rule_color))
        for entry in plan.education:
            flowables.append(Paragraph(escape(_sanitize_for_pdf(entry)), styles["body"]))

    # --- Certifications ---
    if plan.certifications:
        flowables.extend(_section_header("CERTIFICATIONS", frame_width, styles, style, rule_color))
        for cert in plan.certifications:
            flowables.append(Paragraph(_bullet(cert, style), styles["bullet"]))

    flowables.append(Spacer(1, 0.05 * inch))
    return flowables


def _section_header(
    title: str,
    frame_width: float,
    styles: dict[str, ParagraphStyle],
    style: StyleTemplate,
    rule_color: HexColor,
) -> list[object]:
    """Uppercase section title followed by a thin rule across the frame.

    All visual knobs (rule thickness, colour, section-title style) come from
    the StyleTemplate (#72) — no hardcoded constants.
    """
    return [
        Paragraph(escape(title), styles["section"]),
        HRFlowable(
            width=frame_width,
            thickness=style.section_rule_thickness,
            color=rule_color,
            spaceBefore=1,
            spaceAfter=3,
        ),
    ]


def _role_row(role: object, styles: dict[str, ParagraphStyle], frame_width: float) -> Table:
    """Two-column row: role + company on the left, dates/location right-aligned."""
    left = Paragraph(escape(_sanitize_for_pdf(_role_header_text(role))), styles["role_title"])
    right = Paragraph(escape(_sanitize_for_pdf(_role_meta_text(role))), styles["role_dates"])

    # 65 / 35 split — date strings are short, role/company is the prime real estate.
    left_w = frame_width * 0.65
    right_w = frame_width - left_w
    # hAlign='LEFT' is required: Table's default 'CENTER' subtracts ~6pt on the
    # left even when total colWidths == frame_width, outdenting the role title
    # relative to the surrounding section/bullet paragraphs.
    table = Table([[left, right]], colWidths=[left_w, right_w], hAlign="LEFT")
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


def _bullet(text: str, style: StyleTemplate) -> str:
    """Format bullet content as `<glyph> <text>` so the glyph and content extract on one line.

    The glyph comes from the StyleTemplate (#72) — defaults to `•` but users
    can override per-template.
    """
    return f"{style.bullet_glyph} {escape(_sanitize_for_pdf(text))}"


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
