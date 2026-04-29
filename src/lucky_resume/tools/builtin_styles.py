"""Built-in StyleTemplate registry.

Two presets ship with every install — ``default`` (Helvetica, balanced
margins) and ``consolas`` (monospace power-user variant). They live as
package data under ``lucky_resume.data.styles``; no filesystem assumption
is made beyond what `importlib.resources` provides, so the same code
path works for editable wheels and PyInstaller bundles.

The rest of the pipeline accepts a ``builtin:<name>`` pseudo-path
wherever it would otherwise take a YAML path. ``resolve_style_source``
recognises the prefix and writes the bundled YAML to a temp file so
existing path-only consumers don't have to learn a new contract.
"""

from __future__ import annotations

import logging
import tempfile
from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel

from lucky_resume.tools.style import StyleTemplate, load_style

logger = logging.getLogger(__name__)

BUILTIN_PREFIX = "builtin:"


class BuiltinStyle(BaseModel):
    """Metadata for one shipped style preset."""

    # Stable identifier — matches the YAML stem and the suffix after the
    # `builtin:` prefix. Names are user-visible in the picker.
    name: str
    # One-line label for the picker chip. Falls back to `name` if blank.
    label: str
    # Short pitch shown beneath the chip.
    description: str
    # The parsed `StyleTemplate` — same shape as user YAMLs, so the rest
    # of the pipeline doesn't branch on origin.
    template: StyleTemplate


_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "default": (
        "Default",
        "Helvetica with balanced margins. Safe pick for any ATS.",
    ),
    "consolas": (
        "Consolas (monospace)",
        "Monospace power-user variant — needs Consolas.ttf in input/fonts/.",
    ),
}


def _styles_traversable() -> resources.abc.Traversable:
    return resources.files("lucky_resume.data.styles")


def list_builtin_styles() -> list[BuiltinStyle]:
    """Enumerate the shipped presets, parsed and ready to render.

    Order is stable (sorted by name) so chip order in the GUI doesn't
    flap between launches. Files that fail to parse are skipped with a
    log warning rather than crashing the request — a malformed bundled
    preset shouldn't hide the well-formed siblings."""

    out: list[BuiltinStyle] = []
    for entry in sorted(_styles_traversable().iterdir(), key=lambda p: p.name):
        if not entry.name.endswith((".yaml", ".yml")):
            continue
        stem = entry.name.rsplit(".", 1)[0]
        try:
            raw = yaml.safe_load(entry.read_text(encoding="utf-8"))
            template = StyleTemplate.model_validate(raw or {})
        except Exception as exc:  # noqa: BLE001 — bundle data is trusted but defensive
            logger.warning("builtin_styles: skipping %s — %s", entry.name, exc)
            continue
        label, description = _DESCRIPTIONS.get(stem, (stem.title(), ""))
        out.append(
            BuiltinStyle(
                name=stem,
                label=label,
                description=description,
                template=template,
            )
        )
    return out


def is_builtin_identifier(value: str | None) -> bool:
    """Return True when the value should be resolved by `resolve_style_source`."""
    return bool(value) and value.startswith(BUILTIN_PREFIX)  # type: ignore[union-attr]


def resolve_style_source(value: str) -> Path:
    """Return a real filesystem path for a ``builtin:<name>`` identifier.

    Other callers pass through plain paths unchanged via
    ``Path(value)``; this function only handles the prefixed form.
    Resolution copies the bundled YAML to a temp file so consumers like
    ``load_style(path)`` can keep using ``Path.exists()`` /
    ``read_text`` semantics. The temp file is created once per process
    and cached so repeated calls stay cheap."""

    if not is_builtin_identifier(value):
        return Path(value)
    name = value[len(BUILTIN_PREFIX) :]
    cache_key = (name,)
    cached = _resolved_cache.get(cache_key)
    if cached is not None and cached.exists():
        return cached
    src = _styles_traversable().joinpath(f"{name}.yaml")
    if not src.is_file():
        raise FileNotFoundError(f"unknown built-in style: {name}")
    tmp_dir = Path(tempfile.gettempdir()) / "lucky-resume" / "builtin-styles"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target = tmp_dir / f"{name}.yaml"
    target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _resolved_cache[cache_key] = target
    return target


def load_builtin_style(name: str) -> StyleTemplate:
    """Convenience: parse a single built-in by name."""
    return load_style(resolve_style_source(f"{BUILTIN_PREFIX}{name}"))


_resolved_cache: dict[tuple[str], Path] = {}
