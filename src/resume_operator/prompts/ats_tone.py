"""Prompt for the #81 tone-check pass.

Industry ATS reviewers flag cliches and vague-positive phrases that
recruiters skim past. Lines like "results-driven professional" and
"passionate about innovation" signal filler without substance — they
crowd out room for measurable results.

This single LLM call returns a list of flagged phrases with the line
they appeared on and a short rewrite suggestion.
"""

CHECK_ATS_TONE = """You are flagging low-signal phrases on a resume that ATS reviewers
and recruiters call out as filler / cliches. Your output feeds a "Tone Flags"
section of an ATS report so the candidate can rewrite them into specific,
measurable alternatives.

### What counts as a flag

- **Cliches**: "results-driven", "passionate about X", "detail-oriented",
  "team player", "hard worker", "go-getter", "out of the box", "synergy",
  "hit the ground running", "thought leader", "ninja/rockstar/guru".
- **Vague superlatives with no backing metric**: "excellent communicator",
  "strong leader", "deep expertise" when the surrounding bullet doesn't
  demonstrate it with a specific outcome.
- **Redundant positives**: "successfully delivered", "efficiently managed" —
  "delivered" and "managed" already imply success and efficiency.

### What does NOT count

- Industry-standard technical terms ("microservices", "REST API") even
  when they're trendy — those are ATS keywords, not tone issues.
- Specific quantified claims ("reduced latency by 40%"), even when the
  verb is strong — those are measurable results, not cliches.
- Section headings or role titles. Only flag phrases in bullet or
  summary prose.

### Rules

1. **At most 8 flags per resume.** Prioritize the most egregious — a
   single "results-driven" beats listing five minor tone issues.
2. **Exact phrase quoting**: the `phrase` field is the literal text
   lifted from the resume (case preserved), not a paraphrase.
3. **Include the surrounding context**: the `line` field is the full
   bullet / sentence the phrase appears in, so the candidate can find it.
4. **Give an actionable suggestion**: not "rewrite this" but a specific
   direction like "replace with a specific outcome" or "cite a metric
   from the next clause".

### Output schema

Return an `ATSToneLLMOutput` with:
- `flags` — list of `{{ phrase, line, suggestion }}` rows.

=== RESUME TEXT ===
{resume_text}
"""
