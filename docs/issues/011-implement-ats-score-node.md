# [Feature]: Implement ats_score node

## Description

Implement the ATS scoring node. It takes the parsed `ResumeData` and `JobDescription` from state, sends them to the LLM with the ATS scoring prompt template, and returns an `ATSScore` with score, reasoning, keyword matches, and keyword gaps.

## Motivation

ATS scoring is the core value proposition — telling users how well their resume matches a job description. This is the first node that depends on a prior node's output (parse_resume), introducing state flow between nodes.

## Tasks

- [ ] Import `tools.llm_provider.get_llm` and `prompts.ats_scoring.ATS_SCORE`
- [ ] Serialize `state.resume` to JSON for the prompt (use `.model_dump_json()`)
- [ ] Format the `ATS_SCORE` template with resume JSON and `state.job_description.raw_text`
- [ ] Call `get_llm().invoke()` with formatted prompt
- [ ] Parse JSON response into `ATSScore` fields
- [ ] Return `{"ats_score": ATSScore(...)}`
- [ ] Error handling: catch exceptions, append to `state.errors`, return default `ATSScore`

## Acceptance Criteria

- Node returns `{"ats_score": ATSScore(...)}` with populated fields
- Uses prompt template, not inline strings
- Errors caught and recorded, pipeline continues

## Key Files

- `src/resume_operator/nodes/ats_score.py`
- `src/resume_operator/prompts/ats_scoring.py`

## Dependencies

- #006

## Labels

`enhancement`, `priority:high`
