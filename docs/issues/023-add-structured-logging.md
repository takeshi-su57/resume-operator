# [Feature]: Add structured logging throughout the pipeline

## Description

Add Python `logging` to all nodes and tools. Follow security rules: never log API keys or full resume text at INFO level. Log node entry/exit, LLM call durations, and errors.

## Motivation

When something goes wrong in production, logs are the primary debugging tool. Structured logging at appropriate levels (INFO for progress, DEBUG for details, ERROR for failures) makes pipeline issues diagnosable.

## Tasks

- [ ] Create logging setup in `config.py` or new `src/resume_operator/logging_config.py` based on `LOG_LEVEL` env var
- [ ] Add logger to each node file: `logger = logging.getLogger(__name__)`
- [ ] Log at INFO: node started, node completed, ATS score value, output path
- [ ] Log at DEBUG: prompt text sent to LLM, raw LLM response, parsed data
- [ ] Log at ERROR: exception details when nodes fail
- [ ] Never log: API keys, full resume text at INFO, personal data at INFO
- [ ] Initialize logging in `main.py` before graph execution

## Acceptance Criteria

- `LOG_LEVEL=DEBUG` shows detailed pipeline trace
- `LOG_LEVEL=INFO` shows progress without sensitive data
- Security rules from `.claude/rules/security.md` are followed

## Key Files

- `src/resume_operator/config.py`
- `src/resume_operator/main.py`
- All files in `src/resume_operator/nodes/`

## Dependencies

- #022

## Labels

`enhancement`, `priority:medium`
