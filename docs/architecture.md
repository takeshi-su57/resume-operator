# Architecture

## System Overview

resume-operator is a LangGraph-based pipeline that loads a hand-maintained master resume (YAML), scores ATS compatibility, analyzes gaps, optimizes content, and generates tailored PDFs. A legacy PDF-first input path is kept for back-compat and bootstrap.

## Agent Flow

```
START
  |
  +--- master_path set? ---+
  |                        |
  | YES                    | NO (legacy)
  v                        v
load_master            parse_resume
  |                        |
  +-----------+------------+
              |
              v
         ats_score          Score master resume against JD (initial pass)
              |
       [conditional]        ATS score >= skip_threshold (default 0.9)?
              |         \
              | NO       \ YES — skip the loop entirely
              v            \
         analyze_gaps       |
              |             |
              v             |
       optimize_content     |
              |             |
              v             |
       ats_score_tailored   |   Score the tailored output (#78 loop body)
              |             |
              +<-------+    |
              |        |    |
     user gate in CLI  |    |
    (accept? / cap?)   |    |
              |        |    |
         [continue]    |    |
              |        |    |
     propose_changes   |    |    LLM emits rewrite_master / rewrite_fact /
              |        |    |    new_fact proposals, each grounded in a source_id
              v        |    |
     run_approval_flow |    |    Y / N / Fix loop (unbounded) per proposal
              |        |    |
     apply_approvals   |    |    Accepted proposals -> facts_bank.yaml;
              |        |    |    rewrite_master carries `overrides: master:...`
              |        |    |    so source_index hides the shadowed master entry
              +--------+    |
         [user accepts      |
         or cap decline]    |
              |             |
              v             v
         generate_pdf      (skip path joins here too)
              |
              v
         report_results
              |
              v
             END
```

## Input Contracts

| Contract | CLI flag | Node | Notes |
|----------|----------|------|-------|
| **Master YAML (preferred)** | `--master` | `load_master` | No LLM. Hand-maintained source of truth. |
| **Resume PDF (legacy)** | `--resume` | `parse_resume` | LLM-parsed. Kept for back-compat and `bootstrap`. |
| **Facts bank (optional)** | `--facts` | `load_master` | YAML pool of items beyond the master. `optimize_content` may pull from here. |

Use `resume-operator bootstrap --resume old.pdf --output data/master_resume.yaml` once to seed the YAML from an existing PDF, then maintain the YAML by hand.

When a tailoring run comes back thin (fewer than `enrich_threshold` items kept, default 6), `run` itself pauses and offers an interactive interview: the LLM asks grounded questions drawn from the intersection of your master and the JD's requirements, you answer in free text, the LLM polishes your answer to an ATS-ready bullet, and accepted items append to the facts bank with a `source: "enrich YYYY-MM-DD"` stamp. The graph then re-invokes once with the enriched facts. The facts bank grows durably across sessions. Pass `--no-enrich` to skip the interview (e.g., for headless / CI runs).

If a `--facts <yaml>` path is provided (or `data/facts_bank.yaml` exists), the facts bank is loaded alongside the master and handed to `optimize_content` as a distinct pool the LLM may pull from when a fact strengthens the match for the JD.

## Conditional Routing

After `ats_score`, a routing function checks the score against `ATS_SKIP_THRESHOLD` (configurable, default 0.9):

- **Score >= threshold**: Skip optimization — route directly to `report_results`. The report notes `optimization_skipped: true`.
- **Score < threshold**: Normal path — continue through `analyze_gaps`, `optimize_content`, `generate_pdf`, then `report_results`.

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| CLI | `main.py` | Typer commands: run, score, parse-resume, bootstrap |
| Graph | `graph.py` | LangGraph StateGraph with conditional routing |
| State | `state.py` | Pydantic model flowing through all nodes (`ResumeMaster`, `ResumeData`, `ATSScore`, …) |
| Nodes | `nodes/` | One function per file, returns state delta |
| Tools | `tools/` | I/O utilities (PDF, LLM, YAML, JSON parsing) |
| Prompts | `prompts/` | LLM prompt templates |
| Config | `config.py` | Pydantic Settings from env vars |

## Data Flow

1. **Input**: `master_resume.yaml` (preferred) or resume PDF + job description text
2. **load_master / parse_resume**: Load structured resume data
3. **ats_score**: LLM-based ATS compatibility scoring (0.0-1.0)
4. **Routing**: Skip or continue based on score threshold
5. **analyze_gaps**: LLM identifies gaps, strengths, suggestions
6. **optimize_content**: LLM rewrites resume sections
7. **generate_pdf**: ReportLab renders optimized PDF
8. **report_results**: JSON report to `data/results.json`

## Tailoring as Per-Item Decisions

`optimize_content` does not produce free-form text blobs. It builds a `TailoredResume` — a list of `TailoredItem` decisions over a `SourceIndex` (built from `ResumeMaster` + `FactsBank`). Every item references a stable `source_id` like `master:exp-1-b1` or `facts:proj-2`. Three actions: `keep`, `reword`, `drop`. Fabricated `source_id`s (LLM inventing IDs) are rejected at the node boundary and logged.

`report_results` writes `data/diff.md` — a human-readable before/after of every keep/reword/drop decision, grouped into Additions (pulled from facts bank), Rewordings (with before/after text), and Deletions.

`generate_pdf` is a pure function of `(ResumeMaster, TailoredResume, FactsBank?, template)` (#027). The renderer groups tailored items by `kind` (summary, experience-bullet, project, education, skill, certification), splices facts-bank `extra-bullet[role-id]` items under their target role, and lays out the page deterministically — no paragraph-splitting on LLM whitespace.

**Summary handling (#66)**: `TailoredResume.tailored_summary` is a dedicated JD-crafted 2-3 sentence opener the optimizer writes fresh for every run. When non-empty, the renderer uses it for the SUMMARY section instead of a kept/reworded `master:summary` item. That avoids a double-render and lets the summary pull harder toward the JD than a per-item reword would.

**Unicode sanitization (#66)**: every string that reaches the renderer passes through `_sanitize_for_pdf` — a boundary-layer that translates exotic Unicode (arrows `→`, non-breaking hyphens `‑`, curly quotes `'"`, horizontal ellipsis `…`) to ASCII and strips zero-width characters. Helvetica (the built-in font) can't render those glyphs, so without sanitization they come out as black `.notdef` boxes. `tailored.yaml` and `facts_bank.yaml` keep the LLM's original text; only the PDF text stream is normalized.

**Senior-format fields (#68)**: `ResumeMaster` carries four optional additions that bring the render closer to senior-engineer CV conventions:
- `headline` — static fallback tagline under the name. The renderer prefers the per-JD `TailoredResume.tailored_headline` (#70) when non-empty; `master.headline` only shows when the tailor didn't emit one (e.g. score-only runs).
- `links` — structured Portfolio/LinkedIn/GitHub rendered as a second contact line
- `skill_groups` — categorised skills (Languages / Frontend / Backend / Cloud). Flattens into the source_index with the same `master:skill:<name>` IDs, so the tailor's fabrication guard doesn't need to know whether the master is grouped or flat.
- `ExperienceEntry.tech` — per-role tech stack rendered as a dim `Tech: A, B, C` line after the bullets
All four are optional; older YAMLs without them fall back gracefully (no headline line, flat skills, no tech line).

**Bootstrap interview (#70)**: after the LLM parses a resume PDF, `bootstrap` runs an interactive interview asking the user for any senior-format field the LLM couldn't extract (missing headline, URLs for Portfolio/LinkedIn/GitHub, per-role tech stacks, skill categorisation). The interview skips silently when stdin isn't a TTY or when `--no-interview` is passed. For skill grouping, the interview calls a separate LLM via `tools/skill_grouping.propose_groups` that proposes categories from the flat skill list; the user accepts or rejects the whole block.

**Dynamic headline (#70)**: `TailoredResume.tailored_headline` is a fresh JD-crafted tagline written by the optimizer every run, alongside `tailored_summary`. Grounded strictly in master facts (titles, years, companies, tech) — no invented "Ex-Google". Same accept/reject fabrication-safety shape as the summary. When non-empty it replaces `master.headline` in the rendered PDF.

**StyleTemplate (#72)**: every visual knob the renderer used to hardcode (font family, sizes, colours, margins, spacing, rule thickness, bullet glyph) now lives in a `StyleTemplate` Pydantic model serialised to YAML. `tools/style.py` defines the schema, loads from YAML, registers TTF fonts on demand, and builds ReportLab `ParagraphStyle` objects. `tools/style_from_docx.py` walks a reference `.docx` and emits a StyleTemplate YAML mirroring its named-style choices (font family, sizes, colours, margins). CLI surface: `extract-style --from <ref.docx> --output <style.yaml>` produces the YAML; `run --style <path>` applies it. Precedence: CLI flag → `RESUME_STYLE_PATH` env → `input/style.default.yaml` → code defaults.

**Iterative approval loop (#78)** — see [docs/guides/iterative-tailor-approval.md](guides/iterative-tailor-approval.md) for the user-facing walkthrough. After the first tailor pass, `run` enters a user-driven loop (unless `--no-approve` is set or stdin isn't a TTY). Each iteration shows the ATS score on the current tailored output and offers Accept → done / Reject → continue / cap-reached → "continue anyway?". On continue, `propose_changes` asks the LLM for up to 5 grounded proposals of three kinds:
- `rewrite_master` — polishes an existing master bullet; when approved, lands in `facts_bank.extra_bullets` with `overrides: "master:exp-..."` set. The next tailor iteration's `build_source_index` hides the shadowed master entry, so the prompt menu and rendered PDF see exactly one version per thought. Zero duplication, and **`master_resume.yaml` stays hand-authored and read-only** — every accepted change lands in facts_bank.
- `rewrite_fact` — replaces an existing facts-bank entry's text in place (same id, for source_index stability).
- `new_fact` — brand-new bullet extrapolated from an existing source; the prompt forces the LLM to cite which item supports the claim so the user can reality-check it.
Each proposal goes through a three-button UX in `tools/approval_flow.py` — `Y`es / `N`o / `F`ix (free-text feedback → `revise_proposal` emits v2 → back to the same three buttons, unbounded). Rejected proposals go into a per-run `rejected_suggestions` list that feeds back into `propose_changes` so the LLM doesn't re-propose ideas the user has already vetoed. The loop exits when the user accepts, when the LLM has no more proposals, when the user quits, or when they decline to continue past the iteration cap — in which case the best-scoring iteration seen is rendered. CLI: `--max-iter N` (default 3, also `RESUME_MAX_ITERATIONS`), `--no-approve` for headless.

Font-family handling: Helvetica/Times/Courier are built into ReportLab; custom families look for `input/fonts/<Name>.ttf` (plus optional `<Name>-Bold.ttf`, `<Name>-Italic.ttf`, `<Name>-BoldItalic.ttf`). Missing TTFs log a one-time warning and fall back to Helvetica — the render keeps going.

Templates are configured via `RESUME_TEMPLATE` (`default | compact | modern`); only `default` is implemented today, unknown values fall back to default with a warning.

The `default` template targets both audiences: ATS parsers (single-column selectable text, standard fonts, no images or layout tables) and recruiters' six-second scan (name banner + thin accent rule, uppercase section labels with a pale rule underneath, role header with right-aligned dates on the same line, hanging-indent bullets, one muted deep-blue accent used sparingly).

## LLM Output Handling

All LLM-calling nodes use LangChain's `with_structured_output` (via `tools/llm_provider.get_structured_llm`). Each node defines an `…LLMOutput` Pydantic schema near its node function; LangChain hands the schema to the provider via native function/tool-calling and returns an already-validated instance. No manual JSON parsing or prompt-time "return ONLY valid JSON" boilerplate.

Schema mismatches surface as `pydantic.ValidationError` (or provider-specific `BadRequestError` when the schema itself is incompatible with strict mode) and are recorded in `state.errors` via the standard record-and-continue pattern.

**Provider compatibility** (see `.env.example` for the full list): OpenAI (gpt-4o, gpt-4o-mini), Anthropic (Claude 3.5), and Google (Gemini 1.5) are fully supported. OpenRouter works with OpenAI-origin models; some open-weights models return truncated JSON under strict mode.

## Per-Application Output Folder

Each `run` reserves a fresh folder before invoking the graph (#029):

```
data/applications/{YYYY-MM-DD}_{slug}/
├── resume.pdf       ← from generate_pdf
├── results.json     ← from report_results
├── tailored.yaml    ← serialized TailoredResume
└── diff.md          ← human-readable per-item diff
```

Slug priority: explicit `JobDescription.company` (when known) → JD filename stem → 8-char SHA-256 hash of the JD text. Collisions append `-2`, `-3`, etc. — runs never overwrite each other.

`--output` overrides the parent (default `data/applications/`); the per-run subfolder name is always derived automatically.

## Error Handling

- Each node catches exceptions and records them in `state.errors`
- Pipeline continues on failure — downstream nodes check preconditions
- Final report includes all accumulated errors
