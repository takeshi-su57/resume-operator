# [Feature]: Per-application versioned output folder

## Description

Replace the single overwriting output path with a per-application folder: `data/applications/{YYYY-MM-DD}_{slug}/{resume.pdf, results.json, tailored.yaml, diff.md}`. Each pipeline run creates a new folder; no overwrites.

## Motivation

Running the pipeline twice previously overwrote the first output. That meant no history of "what did I submit to company X on date Y?" — which is exactly what the future job-application tracker (Level 3 in [plan 002](../../../../luckyplans/plans/002-resume-ats-tailor/plan.md)) will need as its hand-off point.

It's also a safety net: if a later LLM run produces a worse tailoring, the prior good one is still on disk.

## Implementation

- [x] [`tools/output_dir.py`](../../src/resume_operator/tools/output_dir.py) — `resolve_output_dir(parent, jd_path, jd_text, company=None, today=None)` reserves a fresh folder; slug priority is `company` → JD filename stem → 8-char SHA-256 hash of the JD text. Collisions append `-2`, `-3`.
- [x] `state.output_dir` field added to `ResumeOptimizerState`; `state.output_path` continues to be the absolute PDF path (always `{output_dir}/resume.pdf` on the CLI happy path).
- [x] CLI `--output` semantics changed: now means *parent* directory (default `data/applications/`), not a file path. Per-run subfolder name is always derived automatically.
- [x] [`main.py`](../../src/resume_operator/main.py) — calls `resolve_output_dir` before invoking the graph, passes `output_dir` and `output_path` in the initial state.
- [x] [`nodes/report_results.py`](../../src/resume_operator/nodes/report_results.py) writes `results.json`, `diff.md`, and `tailored.yaml` (new) into `state.output_dir`. Falls back to legacy `data/results.json` + `data/diff.md` paths when `output_dir` is empty (for tests and direct graph invocations).
- [x] `generate_pdf` already writes to `state.output_path`, which now points inside `output_dir`.
- [x] Tests: `tests/test_output_dir.py` covers slug priority, collision handling, default parent, and parent-creation; `tests/test_report_results.py` covers per-folder writing including `tailored.yaml`.
- [x] Docs: `docs/architecture.md` and `README.md` updated.

## Acceptance Criteria — Verified

- Two consecutive runs against the same JD produce two separate folders, no overwrites ✓ — verified by clearing `data/applications/` and running twice; got `2026-04-21_job/` and `2026-04-21_job-2/`.
- Each folder is self-contained (PDF + structured tailored data + score + diff) ✓ — `ls data/applications/2026-04-21_job/` → `diff.md  results.json  resume.pdf  tailored.yaml`.
- Folder naming is predictable and date-sortable ✓ — `{YYYY-MM-DD}_{slug}` always sorts chronologically.

## Proof of Work

```
$ rm -rf data/applications && uv run python -m resume_operator run --master input/master_resume.example.yaml --facts input/facts_bank.example.yaml --job input/job.txt
output_dir: reserved data/applications/2026-04-21_job
…
generate_pdf: completed — output=data/applications/2026-04-21_job/resume.pdf, size=3069 bytes
report_results: completed — wrote data/applications/2026-04-21_job/results.json + …/diff.md, …/tailored.yaml

$ uv run python -m resume_operator run --master … --facts … --job …  # second run
output_dir: reserved data/applications/2026-04-21_job-2

$ ls data/applications/
2026-04-21_job/
2026-04-21_job-2/
```

## Key Files

- `src/resume_operator/state.py` (`output_dir` field)
- `src/resume_operator/tools/output_dir.py` (new)
- `src/resume_operator/nodes/report_results.py` (writes into `output_dir`)
- `src/resume_operator/main.py` (`--output` semantics changed; reserves folder before graph)
- `tests/test_output_dir.py` (new), `tests/test_report_results.py`
- `docs/architecture.md`, `README.md`

## Dependencies

- #026 ✓ (`tailored.yaml` and `diff.md` rely on the `TailoredResume` structure)

## Labels

`enhancement`, `priority:medium`
