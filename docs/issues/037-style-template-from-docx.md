# [Feature]: StyleTemplate — extract visual style from .docx references, apply at render time

## Description

Move every hardcoded style knob in `tools/pdf_generator.py` (font family, sizes, colours, margins, spacing, rule thickness, bullet glyph) into a `StyleTemplate` Pydantic model, serialised as YAML. Add an `extract-style` CLI that walks a reference `.docx` and produces a StyleTemplate the user can hand-tweak. Add a `--style` flag on `run` so different applications can use different templates against the same master.

## Motivation

User request: *"you can modify the resume format too. you can extract infos from the andy-wang-cv. for example. font-size and font-weight, font-family, padding, margins, gaps, and how to configure the experience titles, etc. so it's a kind of a template for style, not just the content."*

Today's renderer has the style baked into constants (`_ACCENT`, `_MARGIN`, numbers inside `_default_styles()`). Tuning the look means editing Python. Splitting style into a YAML template turns visual iteration into a YAML edit, and opens the door to "adopt this reference CV's look" in one command.

## Scope & reality constraints

**What the extractor can reliably read from a .docx:**
- Font family names (per-style)
- Font sizes per Word style
- Font weight (bold, italic)
- Theme + explicit RGB colours
- Section margins (`sectPr`)
- Paragraph spacing / line height
- Alignment

**Where we can't be 1:1:**
- Font *family availability* — if the `.docx` specifies Calibri but the runtime has no Calibri TTF, we fall back to Helvetica (with a one-time warning). Helvetica/Times/Courier are built into ReportLab; anything else needs a TTF in `input/fonts/{family}.ttf`.
- Word tab-stops / two-column layouts — we already simulate right-aligned role dates via a Table (#68). Full multi-column layouts are out of scope.
- Small-caps / kerning — ReportLab approximates.

## Target State

### StyleTemplate

`src/resume_operator/tools/style.py` defines:

```python
class ColorPalette(BaseModel):
    name: str = "#1A202C"        # name banner text
    body: str = "#2D3748"        # body/bullet text
    accent: str = "#2C5282"      # section labels + rules
    muted: str = "#555555"       # contact, dates, tech line
    rule: str = "#CBD5E0"        # thin section dividers

class Margins(BaseModel):
    top: float = 0.6  # inches
    bottom: float = 0.6
    side: float = 0.6

class TextStyle(BaseModel):
    size: float
    leading: float | None = None       # default: size * 1.2
    color: str = "body"                # key into ColorPalette
    bold: bool = False
    italic: bool = False
    alignment: Literal["left", "center", "right"] = "left"
    space_before: float = 0
    space_after: float = 0
    left_indent: float = 0
    first_line_indent: float = 0

class StyleTemplate(BaseModel):
    name: str = "default"
    font_family: str = "Helvetica"
    colors: ColorPalette = Field(default_factory=ColorPalette)
    margins: Margins = Field(default_factory=Margins)
    name_style: TextStyle = ...
    headline: TextStyle = ...
    contact: TextStyle = ...
    section: TextStyle = ...
    role_title: TextStyle = ...
    role_dates: TextStyle = ...
    body: TextStyle = ...
    bullet: TextStyle = ...
    tech: TextStyle = ...
    accent_rule_thickness: float = 1.2
    section_rule_thickness: float = 0.5
    bullet_glyph: str = "•"
```

### `input/style.default.yaml`

Ships the current hardcoded values as a YAML file. Users drop in overrides; renderer falls back to code defaults when fields are missing.

### `tools/style_from_docx.py`

Uses `python-docx` to walk a .docx's XML. Maps Word styles to our fields via a best-effort table (e.g. "Heading 1" → section, default font → font_family, first large-font paragraph → name_style). Output: a YAML that mirrors the StyleTemplate schema. User reviews and hand-tweaks.

### `extract-style` CLI

```
resume-operator extract-style --from input/andy-wang-cv.docx --output input/style.from-andy.yaml
```

One-time. Writes a YAML the user can apply via `--style`.

### `--style` on `run`

```
resume-operator run --master m.yaml --job j.txt --style input/style.from-andy.yaml
```

Precedence:
1. `--style` flag
2. `RESUME_STYLE_PATH` env var
3. `input/style.default.yaml` if it exists
4. Hardcoded `StyleTemplate()` defaults

### Font fallback

- Built-in Helvetica/Times/Courier/plus their bold+italic variants are free.
- Anything else: look for `input/fonts/{family}.ttf`. If found, register via `reportlab.pdfbase.pdfmetrics.registerFont(TTFont(family, path))`. If not found: log a one-time warning (`"Font 'Calibri' not found in input/fonts/ — falling back to Helvetica"`) and use Helvetica.
- The warn-once set is module-level so `run` invocations spanning multiple fonts log each unresolved family once, not per-page.

## Success Metrics — Verified

- `extract-style --from "input/andy-wang-cv - Copy.docx" --output input/style.andy.yaml` produced a parseable YAML with the right knobs extracted: *"Font family: Aptos, Margins: 0.5in top / 0.5in bottom / 0.5in side, Name size: 20.0pt, Section size: 16.0pt, Body size: 12.0pt"* — all values match what the .docx actually contains.
- `run --master data/master_resume.yaml --facts data/facts_bank.yaml --job input/job.txt --style input/style.andy.yaml --no-enrich` rendered the tailored PDF using the extracted template. Log confirms: `pdf_generator: generating PDF … (style='andy-wang-cv - Copy', font='Aptos')`.
- Font-family fallback verified: Aptos has no TTF in `input/fonts/`, so `register_font_family` logs `Font family 'Aptos' not found in input/fonts — falling back to Helvetica. Drop Aptos.ttf in input/fonts to use this font.` once. Subsequent calls hit the module-level cache — no spam.
- Default rendering (without `--style`) still works identically — `StyleTemplate()` defaults encode the pre-#72 hardcoded constants.
- 226 tests pass (26 new: TestStyleTemplateDefaults, TestLoadStyle, TestSaveStyle, TestFontResolution, TestBuildAllStyles, TestExtractStyle, TestExtractStyleCommand, TestRunStyleFlag).

## Key Files

- `src/resume_operator/tools/style.py` (new) — StyleTemplate + loader + font registration + paragraph-style builder
- `src/resume_operator/tools/style_from_docx.py` (new) — docx → StyleTemplate
- `src/resume_operator/tools/pdf_generator.py` — refactor to consume StyleTemplate
- `src/resume_operator/main.py` — `extract-style` command, `--style` flag on `run`
- `src/resume_operator/config.py` — `resume_style_path: str = ""`
- `input/style.default.yaml` (new)
- `pyproject.toml` — add `python-docx`
- `tests/test_style.py`, `tests/test_style_from_docx.py`, updates to `test_pdf_generator.py`

## Dependencies

- #68 (senior-format fields and layout — styles wrap the same paragraphs)
- #66 (sanitizer + hierarchy — unchanged, sits under the new template)

## Labels

`enhancement`, `priority:high`
