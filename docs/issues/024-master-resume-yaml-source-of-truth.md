# [Feature]: Introduce `master_resume.yaml` as source of truth

## Description

Replace PDF-as-input with a structured YAML master resume that's hand-maintained. The PDF becomes a derivative of the YAML, not the source of truth. Parsing a PDF becomes a one-time bootstrap command, not a per-run step.

## Motivation

Every run currently re-parses the same PDF via LLM (`src/resume_operator/nodes/parse_resume.py`). That wastes an LLM call per run, compounds extraction errors across runs, and hides the architectural point that the resume should live as structured data. It also blocks downstream v2 features (#025 facts bank, #026 item-level diff) that need a stable structured source.

This is the parent issue for the v2 rework. See [luckyplans plan 002](../../../../luckyplans/plans/002-resume-ats-tailor/plan.md) for the broader rationale.

## Implementation

- [x] Schema designed in `ResumeMaster` (Pydantic) with stable IDs on every experience entry (`exp-N`) and bullet (`exp-N-bM`)
- [x] `ResumeMaster`, `ExperienceEntry`, `ExperienceBullet`, `EducationEntry` added to [state.py](../../src/resume_operator/state.py)
- [x] [`tools/master_resume.py`](../../src/resume_operator/tools/master_resume.py) with `load_master`, `save_master`, `resume_data_to_master`
- [x] One-time `bootstrap` CLI command: `resume-operator bootstrap --resume <pdf> --output <yaml>` — reuses the LLM parse path once, then writes YAML with stable IDs
- [x] `run` and `score` CLIs accept `--master` (preferred) or `--resume` (legacy); both paths exercise the same graph
- [x] New [`load_master` node](../../src/resume_operator/nodes/load_master.py) reads YAML with no LLM call
- [x] Graph entry is a conditional edge keyed on `state.master_path` — routes to `load_master` or `parse_resume`
- [x] [`input/master_resume.example.yaml`](../../input/master_resume.example.yaml) added
- [x] Downstream nodes still consume `state.resume` (legacy `ResumeData`); `load_master` populates a flattened view alongside `state.master`. Full downstream migration is deferred to #026.
- [x] Docs updated: `docs/architecture.md`, `README.md`, `.claude/CLAUDE.md`

## Acceptance Criteria — Verified

- `resume-operator run --master data/master_resume.yaml --job job.txt` runs end-to-end with no PDF parsing (verified with real OpenRouter call, ATS 71%, no errors)
- `bootstrap` produces a valid `master_resume.yaml` from an existing PDF via a single LLM-assisted pass
- Normal runs make zero LLM calls for ingestion (`load_master` is pure YAML I/O)
- 123 existing tests pass + 11 new tests for the YAML/bootstrap path

## Key Files

- `src/resume_operator/state.py`
- `src/resume_operator/tools/master_resume.py` (new)
- `src/resume_operator/nodes/load_master.py` (new)
- `src/resume_operator/graph.py`
- `src/resume_operator/main.py` (adds `bootstrap`, `--master` on `run`/`score`)
- `input/master_resume.example.yaml` (new)
- `docs/architecture.md`

## Follow-ups

- #026 will migrate downstream nodes (ats_score, analyze_gaps, optimize_content) off `ResumeData` and onto `ResumeMaster` with item-level references. Until then, `load_master` bridges the two shapes.
- #025 builds a `facts_bank.yaml` alongside the master, reusing the same load pattern.

## Labels

`enhancement`, `priority:high`
