"""Tests for `tools.builtin_styles` — the bundled style preset registry."""

from __future__ import annotations

import pytest

from lucky_resume.tools.builtin_styles import (
    BUILTIN_PREFIX,
    is_builtin_identifier,
    list_builtin_styles,
    load_builtin_style,
    resolve_style_source,
)
from lucky_resume.tools.style import StyleTemplate


class TestListBuiltinStyles:
    def test_default_and_consolas_present(self) -> None:
        names = {style.name for style in list_builtin_styles()}
        assert "default" in names
        assert "consolas" in names

    def test_returns_parsed_templates(self) -> None:
        for style in list_builtin_styles():
            assert isinstance(style.template, StyleTemplate)
            # The bundled YAMLs declare a font_family — empty would
            # signal a parse fall-through to the model defaults.
            assert style.template.font_family

    def test_order_is_stable(self) -> None:
        first = [s.name for s in list_builtin_styles()]
        second = [s.name for s in list_builtin_styles()]
        assert first == second


class TestIsBuiltinIdentifier:
    def test_recognises_prefix(self) -> None:
        assert is_builtin_identifier("builtin:default")
        assert is_builtin_identifier(f"{BUILTIN_PREFIX}consolas")

    def test_rejects_plain_paths_and_falsy(self) -> None:
        assert not is_builtin_identifier("input/style.default.yaml")
        assert not is_builtin_identifier("")
        assert not is_builtin_identifier(None)


class TestResolveStyleSource:
    def test_returns_existing_file_for_known_builtin(self) -> None:
        path = resolve_style_source("builtin:default")
        assert path.exists()
        # Cache hit returns the same file path on a repeat call.
        assert resolve_style_source("builtin:default") == path

    def test_unknown_builtin_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            resolve_style_source("builtin:does-not-exist")

    def test_plain_path_passes_through_unchanged(self) -> None:
        # Non-prefixed strings get wrapped in `Path` and returned as-is —
        # callers that already pass paths shouldn't be surprised.
        from pathlib import Path

        assert resolve_style_source("input/style.default.yaml") == Path(
            "input/style.default.yaml"
        )


class TestLoadBuiltinStyle:
    def test_returns_validated_template(self) -> None:
        template = load_builtin_style("default")
        assert isinstance(template, StyleTemplate)
        # The shipped default YAML declares `name: default`; if the
        # loader skipped the YAML and returned model defaults, this
        # would still be "default" by coincidence — also assert the
        # font is something the YAML actually sets.
        assert template.font_family in {"Helvetica", "Times-Roman", "Courier"}
