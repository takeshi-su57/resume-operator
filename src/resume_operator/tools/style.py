"""Style template — the renderer's visual knobs as a YAML-serialisable schema.

All the numbers the renderer used to hardcode (`_ACCENT`, `_MARGIN`, sizes
inside `_default_styles()`) move here. A `StyleTemplate` instance is loaded
from a YAML file and passed through to the PDF renderer (#72).

Precedence for which template to use:
  1. `--style PATH` CLI flag
  2. `RESUME_STYLE_PATH` env var
  3. `input/style.default.yaml` if it exists
  4. Hardcoded defaults from this module

Font family handling:
  - Helvetica / Times-Roman / Courier and their bold/italic variants are
    built into ReportLab. No action needed.
  - Anything else needs a TTF in `input/fonts/<family>.ttf`. We try to
    register it at first use; on failure we warn once and fall back to
    Helvetica — the rest of the render continues unchanged.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


# --- Schema --------------------------------------------------------------


class ColorPalette(BaseModel):
    """Named colours referenced by TextStyle via string key."""

    name: str = "#1A202C"  # name banner text
    body: str = "#2D3748"  # body + bullet text
    accent: str = "#2C5282"  # section labels + rules
    muted: str = "#555555"  # contact / dates / tech line
    rule: str = "#CBD5E0"  # thin section dividers


class Margins(BaseModel):
    """Page margins in inches."""

    top: float = 0.6
    bottom: float = 0.6
    side: float = 0.6


class TextStyle(BaseModel):
    """One ParagraphStyle's worth of knobs.

    `leading` defaults to `size * 1.2` when unset. `color` is a key into
    `ColorPalette` (e.g. "accent"); the builder resolves it to a HexColor.
    """

    size: float
    leading: float | None = None
    color: str = "body"
    bold: bool = False
    italic: bool = False
    alignment: Literal["left", "center", "right"] = "left"
    space_before: float = 0
    space_after: float = 0
    left_indent: float = 0
    first_line_indent: float = 0


class StyleTemplate(BaseModel):
    """The full set of visual knobs the PDF renderer consumes."""

    name: str = "default"
    font_family: str = "Helvetica"  # see module docstring for family handling
    colors: ColorPalette = Field(default_factory=ColorPalette)
    margins: Margins = Field(default_factory=Margins)

    # Per-element styles — one TextStyle per ParagraphStyle the renderer emits.
    name_style: TextStyle = Field(
        default_factory=lambda: TextStyle(size=24, leading=26, color="name", bold=True)
    )
    headline: TextStyle = Field(
        default_factory=lambda: TextStyle(size=11, leading=14, color="accent", space_after=2)
    )
    contact: TextStyle = Field(
        default_factory=lambda: TextStyle(size=9.5, leading=12, color="muted", space_after=8)
    )
    section: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=12, leading=14, color="accent", bold=True, space_before=12
        )
    )
    role_title: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=11, leading=14, color="name", bold=True, space_before=2
        )
    )
    role_dates: TextStyle = Field(
        default_factory=lambda: TextStyle(size=9.5, leading=14, color="muted", alignment="right")
    )
    body: TextStyle = Field(
        default_factory=lambda: TextStyle(size=10, leading=13, color="body", space_after=2)
    )
    bullet: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=10,
            leading=13,
            color="body",
            left_indent=14,
            first_line_indent=-14,
            space_after=1,
        )
    )
    tech: TextStyle = Field(
        default_factory=lambda: TextStyle(
            size=9,
            leading=12,
            color="muted",
            italic=True,
            left_indent=14,
            space_before=2,
            space_after=2,
        )
    )

    # Rules + bullet glyph
    accent_rule_thickness: float = 1.2
    section_rule_thickness: float = 0.5
    bullet_glyph: str = "•"


# --- Loader --------------------------------------------------------------


class StyleTemplateError(ValueError):
    """Raised when a style YAML is present but malformed."""


def load_style(path: Path | None) -> StyleTemplate:
    """Load a StyleTemplate from YAML. Returns defaults if `path` is None or missing.

    Raises `StyleTemplateError` only on present-but-malformed files — missing
    is treated as "use defaults", same contract as `load_facts`.
    """
    if path is None or not path.exists():
        logger.debug("load_style: no template at %s — using defaults", path)
        return StyleTemplate()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise StyleTemplateError(f"style YAML parse error: {exc}") from exc
    if raw is None:
        return StyleTemplate()
    if not isinstance(raw, dict):
        raise StyleTemplateError(
            f"style template must be a mapping at the top level, got {type(raw).__name__}"
        )
    try:
        template = StyleTemplate.model_validate(raw)
    except Exception as exc:
        raise StyleTemplateError(f"style schema validation failed: {exc}") from exc
    logger.info(
        "load_style: loaded %s (name=%r, font=%r)", path, template.name, template.font_family
    )
    return template


def save_style(template: StyleTemplate, path: Path) -> None:
    """Serialise a StyleTemplate to YAML. Used by `extract-style`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = template.model_dump()
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    logger.info("save_style: wrote %s", path)


# --- Font registration ---------------------------------------------------

# ReportLab built-ins — always usable, no registration needed.
_BUILT_IN_FONTS = {
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
}

# Per-process cache: families we've already resolved (registered or warned about).
# Keys are input family names; values are the effective family name we ended up using.
_RESOLVED_FONTS: dict[str, str] = {}


def _user_font_dir() -> Path:
    """Directory where users drop TTF files to register custom families."""
    return Path("input/fonts")


def register_font_family(family: str) -> str:
    """Resolve a family name to a usable font. Falls back to Helvetica with a
    one-time warning when a custom family has no TTF in `input/fonts/`.

    Returns the name to pass as `fontName=` to ReportLab.
    """
    if family in _BUILT_IN_FONTS:
        return family
    if family in _RESOLVED_FONTS:
        return _RESOLVED_FONTS[family]

    # Try to register regular + bold + italic + bold-italic if TTFs are present.
    font_dir = _user_font_dir()
    variants = {
        family: [f"{family}.ttf", f"{family}-Regular.ttf"],
        f"{family}-Bold": [f"{family}-Bold.ttf"],
        f"{family}-Oblique": [f"{family}-Italic.ttf", f"{family}-Oblique.ttf"],
        f"{family}-BoldOblique": [f"{family}-BoldItalic.ttf", f"{family}-BoldOblique.ttf"],
    }

    regular_registered = False
    for variant_name, candidate_filenames in variants.items():
        for filename in candidate_filenames:
            ttf_path = font_dir / filename
            if ttf_path.exists():
                try:
                    pdfmetrics.registerFont(TTFont(variant_name, str(ttf_path)))
                    if variant_name == family:
                        regular_registered = True
                    logger.info(
                        "register_font_family: registered %s from %s", variant_name, ttf_path
                    )
                except Exception as exc:  # noqa: BLE001 — ReportLab swallows in some font errors
                    logger.warning(
                        "register_font_family: failed to register %s: %s", variant_name, exc
                    )
                break  # try next variant

    if regular_registered:
        _RESOLVED_FONTS[family] = family
        return family

    logger.warning(
        "Font family %r not found in %s — falling back to Helvetica. "
        "Drop %s.ttf in %s to use this font.",
        family,
        font_dir,
        family,
        font_dir,
    )
    _RESOLVED_FONTS[family] = "Helvetica"
    return "Helvetica"


# --- ParagraphStyle builder ----------------------------------------------


def _color_for(key: str, palette: ColorPalette) -> HexColor:
    """Resolve a TextStyle.color key (e.g. 'accent') against the palette.

    Also accepts raw hex strings ('#ff0000') so users can specify colours inline.
    """
    if key.startswith("#"):
        return HexColor(key)
    # Fall back to "body" if the key is missing from the palette.
    hex_value = getattr(palette, key, None) or palette.body
    return HexColor(hex_value)


def _font_name(family: str, *, bold: bool, italic: bool) -> str:
    """Pick the right registered variant for bold/italic combinations.

    For built-in Helvetica/Times/Courier this maps to the standard suffix
    convention. For custom families registered via `register_font_family`,
    the variant names follow the same convention.
    """
    base = register_font_family(family)
    if bold and italic:
        candidate = f"{base}-BoldOblique"
    elif bold:
        candidate = f"{base}-Bold"
    elif italic:
        candidate = f"{base}-Oblique"
    else:
        return base

    # If the bold/italic variant wasn't registered, fall back to the base.
    # Checking `pdfmetrics.getRegisteredFontNames()` is the safe lookup.
    try:
        pdfmetrics.getFont(candidate)
        return candidate
    except KeyError:
        return base


_ALIGNMENT_MAP = {"left": 0, "center": 1, "right": 2}


def build_paragraph_style(name: str, spec: TextStyle, template: StyleTemplate) -> ParagraphStyle:
    """Build a ReportLab ParagraphStyle from a TextStyle spec.

    `name` is the stylesheet key (e.g. "Name", "Section") used only for
    ReportLab internal registration.
    """
    base = getSampleStyleSheet()["BodyText"]
    leading = spec.leading if spec.leading is not None else spec.size * 1.2
    return ParagraphStyle(
        name,
        parent=base,
        fontName=_font_name(template.font_family, bold=spec.bold, italic=spec.italic),
        fontSize=spec.size,
        leading=leading,
        textColor=_color_for(spec.color, template.colors),
        alignment=_ALIGNMENT_MAP[spec.alignment],
        spaceBefore=spec.space_before,
        spaceAfter=spec.space_after,
        leftIndent=spec.left_indent,
        firstLineIndent=spec.first_line_indent,
    )


def build_all_styles(template: StyleTemplate) -> dict[str, ParagraphStyle]:
    """Build every ParagraphStyle the renderer uses, keyed by the short name
    the renderer references (e.g. "name", "headline", "section", ...).
    """
    return {
        "name": build_paragraph_style("Name", template.name_style, template),
        "headline": build_paragraph_style("Headline", template.headline, template),
        "contact": build_paragraph_style("Contact", template.contact, template),
        "section": build_paragraph_style("Section", template.section, template),
        "role_title": build_paragraph_style("RoleTitle", template.role_title, template),
        "role_dates": build_paragraph_style("RoleDates", template.role_dates, template),
        "body": build_paragraph_style("Body", template.body, template),
        "bullet": build_paragraph_style("Bullet", template.bullet, template),
        "tech": build_paragraph_style("Tech", template.tech, template),
    }
