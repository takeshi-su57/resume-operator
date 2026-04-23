"""Tests for `tools.style` — StyleTemplate schema, loader, font resolution, builders."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from resume_operator.tools.style import (
    ColorPalette,
    Margins,
    StyleTemplate,
    StyleTemplateError,
    TextStyle,
    build_all_styles,
    build_paragraph_style,
    load_style,
    register_font_family,
    save_style,
)


class TestStyleTemplateDefaults:
    def test_defaults_match_the_pre_72_constants(self) -> None:
        """Without explicit overrides, the template encodes what was hardcoded
        before #72 — margins 0.6in, name 24pt, section 12pt, body 10pt."""
        t = StyleTemplate()
        assert t.name == "default"
        assert t.font_family == "Helvetica"
        assert t.margins.top == 0.6
        assert t.margins.side == 0.6
        assert t.name_style.size == 24
        assert t.section.size == 12
        assert t.role_title.size == 11
        assert t.body.size == 10
        assert t.bullet_glyph == "•"

    def test_text_style_leading_auto_computed(self) -> None:
        """When `leading` is None, the builder uses `size * 1.2`."""
        spec = TextStyle(size=10)
        template = StyleTemplate()
        ps = build_paragraph_style("Body", spec, template)
        assert ps.leading == pytest.approx(12)

    def test_text_style_leading_honours_explicit_value(self) -> None:
        spec = TextStyle(size=10, leading=15)
        ps = build_paragraph_style("Body", spec, StyleTemplate())
        assert ps.leading == 15


class TestLoadStyle:
    def test_none_path_returns_defaults(self) -> None:
        assert load_style(None) == StyleTemplate()

    def test_missing_path_returns_defaults(self, tmp_path: Path) -> None:
        assert load_style(tmp_path / "nope.yaml") == StyleTemplate()

    def test_empty_file_returns_defaults(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        assert load_style(p) == StyleTemplate()

    def test_loads_partial_override(self, tmp_path: Path) -> None:
        """User YAMLs don't have to repeat every field — missing ones fall
        back to defaults."""
        p = tmp_path / "partial.yaml"
        p.write_text(
            "name: tight\n"
            "margins:\n  side: 0.4\n  top: 0.4\n  bottom: 0.4\n"
            "name_style:\n  size: 28\n",
            encoding="utf-8",
        )
        t = load_style(p)
        assert t.name == "tight"
        assert t.margins.side == 0.4
        assert t.name_style.size == 28
        # Untouched fields stay at defaults.
        assert t.section.size == 12
        assert t.bullet_glyph == "•"

    def test_raises_on_non_mapping(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("- list-not-mapping\n", encoding="utf-8")
        with pytest.raises(StyleTemplateError, match="mapping"):
            load_style(p)

    def test_raises_on_schema_violation(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("margins:\n  side: not-a-number\n", encoding="utf-8")
        with pytest.raises(StyleTemplateError, match="schema"):
            load_style(p)


class TestSaveStyle:
    def test_roundtrip(self, tmp_path: Path) -> None:
        out = tmp_path / "style.yaml"
        template = StyleTemplate(
            name="custom",
            font_family="Aptos",
            colors=ColorPalette(accent="#ff0000"),
            margins=Margins(top=0.5, bottom=0.5, side=0.5),
        )
        save_style(template, out)
        assert out.exists()
        loaded = load_style(out)
        assert loaded.name == "custom"
        assert loaded.font_family == "Aptos"
        assert loaded.colors.accent == "#ff0000"
        assert loaded.margins.side == 0.5


class TestFontResolution:
    def test_built_in_returns_as_is(self) -> None:
        assert register_font_family("Helvetica") == "Helvetica"
        assert register_font_family("Times-Roman") == "Times-Roman"
        assert register_font_family("Courier") == "Courier"

    def test_missing_font_falls_back_to_helvetica(self, tmp_path: Path) -> None:
        """Unknown family with no TTF in input/fonts/ should fall back to
        Helvetica and log a warning."""
        # Isolate the module-level cache + point input/fonts/ to empty tmp dir.
        import resume_operator.tools.style as style_module

        with (
            patch.dict(style_module._RESOLVED_FONTS, {}, clear=True),
            patch.object(style_module, "_user_font_dir", lambda: tmp_path / "fonts"),
        ):
            result = register_font_family("DoesNotExist")
        assert result == "Helvetica"

    def test_warn_once_cache(self, tmp_path: Path) -> None:
        """Same unresolved family is only warned about once per process."""
        import resume_operator.tools.style as style_module

        with (
            patch.dict(style_module._RESOLVED_FONTS, {}, clear=True),
            patch.object(style_module, "_user_font_dir", lambda: tmp_path / "fonts"),
        ):
            register_font_family("SomeMissing")
            register_font_family("SomeMissing")
            # After first call, the family is cached as "Helvetica".
            assert style_module._RESOLVED_FONTS["SomeMissing"] == "Helvetica"


class TestBuildAllStyles:
    def test_returns_every_key_the_renderer_uses(self) -> None:
        styles = build_all_styles(StyleTemplate())
        expected = {
            "name",
            "headline",
            "contact",
            "section",
            "role_title",
            "role_dates",
            "body",
            "summary",  # #74: dedicated summary style with first-line indent
            "bullet",
            "tech",
        }
        assert set(styles.keys()) == expected

    def test_alignment_maps_to_reportlab_int(self) -> None:
        template = StyleTemplate()
        styles = build_all_styles(template)
        # role_dates has alignment="right" in defaults → ReportLab 2.
        assert styles["role_dates"].alignment == 2
        # name has alignment="left" (default) → 0.
        assert styles["name"].alignment == 0

    def test_color_key_resolves_to_hex(self) -> None:
        """A `color: accent` key in a TextStyle should resolve to the
        ColorPalette's accent hex at build time."""
        template = StyleTemplate()
        styles = build_all_styles(template)
        # Section style uses color="accent" by default → should match palette.
        section_color_hex = styles["section"].textColor.hexval()
        # hexval is like '0x2c5282ff' — lowercase.
        assert section_color_hex.lower().startswith("0x2c5282")


class TestStylePolish74:
    """Pins the #74 knob defaults so future style rewrites can't silently
    undo the gap / indent / bullet tweaks the user asked for."""

    def test_name_has_space_after_so_headline_doesnt_touch_it(self) -> None:
        styles = build_all_styles(StyleTemplate())
        assert styles["name"].spaceAfter >= 6

    def test_summary_style_first_line_indent(self) -> None:
        """SUMMARY paragraph opens with a ~2 char-width first-line indent."""
        styles = build_all_styles(StyleTemplate())
        assert styles["summary"].firstLineIndent >= 10
        # Continuation lines stay flush — no left indent on the style itself.
        assert styles["summary"].leftIndent == 0

    def test_summary_is_distinct_from_body(self) -> None:
        """The indent only affects the SUMMARY paragraph; `body` (used for
        education / skills flow / virtual buckets) stays flush."""
        styles = build_all_styles(StyleTemplate())
        assert styles["body"].firstLineIndent == 0
        assert styles["body"].firstLineIndent != styles["summary"].firstLineIndent

    def test_bullet_indent_is_four_char_widths(self) -> None:
        """Bullets indent ~4 char-widths from the left frame edge."""
        styles = build_all_styles(StyleTemplate())
        assert styles["bullet"].leftIndent >= 20
        # Hanging indent: wrapped continuation aligns with the first bullet character.
        assert styles["bullet"].firstLineIndent == -styles["bullet"].leftIndent

    def test_role_title_and_section_share_left_edge(self) -> None:
        """Role header lines must start at the same x as SECTION headers —
        both zero leftIndent so they align visually."""
        styles = build_all_styles(StyleTemplate())
        assert styles["role_title"].leftIndent == 0
        assert styles["section"].leftIndent == 0
