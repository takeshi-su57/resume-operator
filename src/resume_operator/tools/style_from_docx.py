"""Extract a `StyleTemplate` from a reference `.docx` file (#72).

Walks the document's named styles (Normal, Heading, Heading 2, Heading 3,
Body Text) and maps the ones we can recognise onto our `StyleTemplate`
fields. Fields we can't derive stay at their defaults — users can hand-tweak
the YAML afterwards.

This is a best-effort importer, not a 1:1 cloner. Word supports layout
features (tab stops, multi-column, small-caps) that don't translate
directly to our ReportLab-based renderer. The extractor covers the visual
knobs that do translate: fonts, sizes, colours, margins.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Pt

from resume_operator.tools.style import (
    ColorPalette,
    Margins,
    StyleTemplate,
    TextStyle,
)

logger = logging.getLogger(__name__)


class StyleExtractionError(ValueError):
    """Raised when a .docx can't be opened or parsed."""


def extract_style_from_docx(path: Path) -> StyleTemplate:
    """Read a .docx reference CV and return a StyleTemplate derived from it.

    The result is a starting point — the user is expected to hand-tweak the
    saved YAML. Specifically:
      - Font family name comes through as-is (e.g. "Aptos"); usability depends
        on the user dropping the TTF into `input/fonts/`.
      - Colours, sizes, margins map cleanly when the .docx uses standard Word
        styles (Normal / Heading / Heading 2 / Heading 3 / Body).
      - Per-element spacing / indents / alignment stay at StyleTemplate
        defaults — Word's tab-stops and spacing model doesn't map 1:1.
    """
    if not path.exists():
        raise StyleExtractionError(f".docx not found: {path}")
    try:
        doc = Document(str(path))
    except Exception as exc:
        raise StyleExtractionError(f"could not open {path}: {exc}") from exc

    style_map = _collect_style_metadata(doc)
    palette = _derive_palette(style_map)
    margins = _derive_margins(doc)
    font_family = _derive_font_family(style_map)

    template = StyleTemplate(
        name=path.stem,
        font_family=font_family,
        colors=palette,
        margins=margins,
    )

    # Override per-element sizes/colours from the .docx where we can find them.
    _override_text_style(
        template.name_style, style_map, keys=("Heading", "Title"), color_key="name"
    )
    _override_text_style(template.section, style_map, keys=("Heading 2",), color_key="accent")
    _override_text_style(template.role_title, style_map, keys=("Heading 3",), color_key="name")
    _override_text_style(
        template.body, style_map, keys=("Body Text", "Normal", "Body"), color_key="body"
    )
    _override_text_style(
        template.bullet,
        style_map,
        keys=("List Bullet", "Body Text", "Normal", "Body"),
        color_key="body",
    )

    logger.info(
        "extract_style_from_docx: %s — font=%r, name=%.1fpt, section=%.1fpt",
        path,
        template.font_family,
        template.name_style.size,
        template.section.size,
    )
    return template


def _collect_style_metadata(doc: Any) -> dict[str, dict[str, object]]:
    """Walk the doc's paragraph-level styles and snapshot what we care about.

    Returns a dict keyed by style name, with fields we can pull off: `font_name`,
    `size_pt`, `bold`, `italic`, `color` (hex string without `#` prefix or None).
    """
    result: dict[str, dict[str, object]] = {}
    for s in doc.styles:
        if s.type != 1:  # 1 = WD_STYLE_TYPE.PARAGRAPH
            continue
        font = s.font
        result[s.name] = {
            "font_name": font.name,
            "size_pt": font.size.pt if font.size else None,
            "bold": bool(font.bold) if font.bold is not None else False,
            "italic": bool(font.italic) if font.italic is not None else False,
            "color": _hex_from_color(font.color),
        }
    return result


def _hex_from_color(color: object) -> str | None:
    """Extract a Word `ColorFormat` as a 6-char hex string, or None."""
    if color is None:
        return None
    rgb = getattr(color, "rgb", None)
    if rgb is None:
        return None
    return str(rgb)  # python-docx RGBColor stringifies to hex like "0F4761"


def _derive_font_family(style_map: dict[str, dict[str, object]]) -> str:
    """Pick the document's default body font.

    Preference order: Body Text → Normal → Body → first style with a named font → Helvetica.
    """
    for key in ("Body Text", "Normal", "Body"):
        info = style_map.get(key)
        if info and info.get("font_name"):
            name = str(info["font_name"])
            return _sanitize_font_name(name)
    for info in style_map.values():
        if info.get("font_name"):
            return _sanitize_font_name(str(info["font_name"]))
    return "Helvetica"


def _sanitize_font_name(name: str) -> str:
    """Word fonts sometimes come with suffixes / fallback chains — trim those."""
    # Strip parenthetical fallbacks: "Aptos (Body CS)" → "Aptos"
    if "(" in name:
        name = name.split("(", 1)[0].strip()
    # Trim any comma-separated fallbacks.
    if "," in name:
        name = name.split(",", 1)[0].strip()
    return name or "Helvetica"


def _derive_palette(style_map: dict[str, dict[str, object]]) -> ColorPalette:
    """Pick accent / name / body / muted colours from the doc styles.

    Best-effort: the Heading-style colour becomes the accent; the Normal/Body
    colour becomes the body colour. Muted and rule keep their defaults.
    """
    palette = ColorPalette()

    # Accent from whichever heading-ish style has a colour set.
    for key in ("Heading 2", "Heading 3", "Heading", "Title"):
        info = style_map.get(key)
        if info and info.get("color"):
            palette.accent = f"#{info['color']}"
            break

    # Name colour: Heading / Title takes priority; falls back to accent.
    for key in ("Heading", "Title", "Heading 1"):
        info = style_map.get(key)
        if info and info.get("color"):
            palette.name = f"#{info['color']}"
            break
    else:
        palette.name = palette.accent if palette.accent != ColorPalette().accent else palette.name

    # Body colour.
    for key in ("Body Text", "Normal", "Body"):
        info = style_map.get(key)
        if info and info.get("color"):
            palette.body = f"#{info['color']}"
            break

    return palette


def _derive_margins(doc: Any) -> Margins:
    if not doc.sections:
        return Margins()
    sec = doc.sections[0]
    # python-docx returns Emu; `.inches` does the conversion.
    return Margins(
        top=float(sec.top_margin.inches) if sec.top_margin else Margins().top,
        bottom=float(sec.bottom_margin.inches) if sec.bottom_margin else Margins().bottom,
        side=float(sec.left_margin.inches) if sec.left_margin else Margins().side,
    )


def _override_text_style(
    target: TextStyle,
    style_map: dict[str, dict[str, object]],
    *,
    keys: tuple[str, ...],
    color_key: str,
) -> None:
    """Apply the first matching Word style's size / bold / italic onto `target`.

    `color_key` isn't applied here — palette-level colours were already set in
    `_derive_palette`; this function just pulls sizes and weights. Leaves the
    target's color pointing at its StyleTemplate palette key (e.g. "accent").
    """
    for key in keys:
        info = style_map.get(key)
        size = info.get("size_pt") if info else None
        if info and isinstance(size, int | float):
            target.size = float(size)
            # Leading stays at None → auto (size * 1.2) unless the user edits it.
            if info.get("bold"):
                target.bold = True
            if info.get("italic"):
                target.italic = True
            # color_key unused here but preserved in the signature so future
            # extractor passes can override colors per element if we want that.
            _ = color_key
            return


# Keep the Pt import referenced so type-checkers don't flag it as unused; some
# future extractor passes will use it directly.
_ = Pt
