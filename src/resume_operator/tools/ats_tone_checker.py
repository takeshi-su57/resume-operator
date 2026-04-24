"""Single-call LLM tone checker for the #81 ATSReport.

Flags cliches and vague-positive filler phrases. Runs alongside the
keyword extractor and the deterministic structural checks; failures
return an empty list so the composite score falls back cleanly.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.ats_tone import CHECK_ATS_TONE
from resume_operator.state import ToneFlag
from resume_operator.tools.llm_provider import get_structured_llm

logger = logging.getLogger(__name__)


class _ToneFlagLLM(BaseModel):
    phrase: str
    line: str = ""
    suggestion: str = ""


class ATSToneLLMOutput(BaseModel):
    flags: list[_ToneFlagLLM] = Field(default_factory=list)


# Hard cap — prompt asks for 8, this trims drift. Rich table truncates visibly
# past ~10 rows; past 8 the signal gets lost in noise anyway.
MAX_TONE_FLAGS = 8


def check_tone(resume_text: str) -> list[ToneFlag]:
    """Return a capped list of tone flags. On any LLM failure, returns `[]`
    — tone is the lowest-weight dimension in the composite, so its absence
    doesn't dominate the score."""
    if not resume_text.strip():
        return []

    try:
        llm = get_structured_llm(ATSToneLLMOutput)
        prompt = CHECK_ATS_TONE.format(resume_text=resume_text)
        logger.debug("check_tone: LLM prompt: %s", prompt)
        parsed: ATSToneLLMOutput = llm.invoke(prompt)
        logger.debug("check_tone: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("check_tone: LLM returned schema-invalid data: %s", exc)
        return []
    except Exception as exc:
        logger.error("check_tone: LLM call failed: %s", exc)
        return []

    flags: list[ToneFlag] = []
    for r in parsed.flags[:MAX_TONE_FLAGS]:
        phrase = r.phrase.strip()
        if not phrase:
            continue
        flags.append(ToneFlag(phrase=phrase, line=r.line.strip(), suggestion=r.suggestion.strip()))
    logger.info("check_tone: completed — flags=%d", len(flags))
    return flags
