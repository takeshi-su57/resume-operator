# [Feature]: Add structured logging throughout the pipeline

## Description

Add Python `logging` to all nodes and tools. Follow security rules: never log API keys or full resume text at INFO level. Log node entry/exit, LLM call durations, and errors.

## Motivation

When something goes wrong in production, logs are the primary debugging tool. Structured logging at appropriate levels (INFO for progress, DEBUG for details, ERROR for failures) makes pipeline issues diagnosable.

## Tasks

- [x] Use existing `config.py` `log_level` field (already defined, was unused); add `_setup_logging(verbose)` helper in `main.py` that reads `get_settings().log_level`, overridden by `--verbose` flag
- [x] Add `logger = logging.getLogger(__name__)` to all nodes (6 files) and all tools (3 files) — 9 files total, 38 logging calls
- [x] Log at INFO: node started/completed with key metrics (skills count, score value, file sizes, output paths), tool entry/completion (extraction chars/pages, PDF sections, LLM provider/model)
- [x] Log at DEBUG: LLM prompt text, raw LLM response, raw resume text length — in all 4 LLM-calling nodes (`parse_resume`, `ats_score`, `analyze_gaps`, `optimize_content`)
- [x] Log at ERROR: exception details in all nodes before appending to `state.errors`
- [x] Security verified: no API keys logged at any level, raw resume text only at DEBUG, no PII at INFO
- [x] Initialize logging in all 3 CLI commands (`run`, `score`, `parse-resume`) via `_setup_logging()` before graph execution
- [x] Added `--verbose` flag to `parse-resume` command (was missing)

## Acceptance Criteria

- `LOG_LEVEL=DEBUG` shows detailed pipeline trace
- `LOG_LEVEL=INFO` shows progress without sensitive data
- Security rules from `.claude/rules/security.md` are followed

## Key Files

- `src/resume_operator/config.py`
- `src/resume_operator/main.py`
- All files in `src/resume_operator/nodes/`

## Dependencies

- #017

## Labels

`enhancement`, `priority:medium`
