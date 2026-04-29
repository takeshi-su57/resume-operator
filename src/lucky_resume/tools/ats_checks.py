"""Deterministic ATS-compatibility checks (#81).

These checks don't need an LLM — they're pattern-match over plain resume
text + master metadata. They return the structural half of the
`ATSReport`: contact info presence, section presence, job title match,
word count, measurable-results count.

Separated from the LLM-driven keyword / tone passes so they can run on
every `ats_score` invocation at near-zero cost.
"""

from __future__ import annotations

import re

from lucky_resume.state import (
    ContactCheck,
    JobTitleMatch,
    ResumeMaster,
    SectionCheck,
)

# --- Contact info --------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"""(
        \+?\d{1,3}[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}  # +1 (555) 123-4567 / 555-123-4567
        |
        \d{3}[\s.-]\d{3,4}[\s.-]\d{4}                         # 080-1234-5678
    )""",
    re.VERBOSE,
)
# Address is the loosest check — we look for a city/state/zip shape or any
# "street"/"ave"/"road" keyword. ATS reviewers flag missing address specifically,
# but it's also the field users intentionally omit for privacy — so we just
# surface presence, not quality.
_ADDRESS_HINT_RE = re.compile(
    r"\b(street|st\.|avenue|ave\.|road|rd\.|boulevard|blvd\.?)\b"
    r"|\b[A-Z][a-z]+,\s*[A-Z]{2}\b"  # "Seattle, WA"
    r"|\b\d{5}(-\d{4})?\b",  # US zip
    re.IGNORECASE,
)


def check_contact(master: ResumeMaster, text: str) -> ContactCheck:
    """True when the field looks populated. Uses master metadata first (the
    authoritative source), then falls back to regex over the resume text.
    """
    email = bool(master.email.strip()) or bool(_EMAIL_RE.search(text))
    phone = bool(master.phone.strip()) or bool(_PHONE_RE.search(text))
    address = bool(master.location.strip()) or bool(_ADDRESS_HINT_RE.search(text))
    return ContactCheck(email_present=email, phone_present=phone, address_present=address)


# --- Section headings ----------------------------------------------------

# ATS scanners look for canonical section words. We're permissive on case and
# surrounding punctuation but strict on the word itself — a "PROFESSIONAL
# EXPERIENCE" heading counts, "things I've done" doesn't.
_SECTION_PATTERNS = {
    "summary": re.compile(
        r"^\s*(professional\s+)?(summary|profile|objective|about)\b", re.IGNORECASE | re.MULTILINE
    ),
    "experience": re.compile(
        r"^\s*(professional\s+|work\s+)?(experience|employment|work\s+history)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    "education": re.compile(r"^\s*education\b", re.IGNORECASE | re.MULTILINE),
    "skills": re.compile(r"^\s*(technical\s+|core\s+)?skills\b", re.IGNORECASE | re.MULTILINE),
}


def check_sections(master: ResumeMaster, text: str) -> SectionCheck:
    """Each section is present if the master has data for it OR the text
    contains a canonical heading for it."""
    return SectionCheck(
        summary=bool(master.summary.strip()) or bool(_SECTION_PATTERNS["summary"].search(text)),
        experience=bool(master.experience) or bool(_SECTION_PATTERNS["experience"].search(text)),
        education=bool(master.education) or bool(_SECTION_PATTERNS["education"].search(text)),
        skills=bool(master.all_skills() if master else [])
        or bool(_SECTION_PATTERNS["skills"].search(text)),
    )


# --- Job title match -----------------------------------------------------

# Extract "the JD's job title" — the first line-like phrase in the JD that
# looks like a title. This is intentionally naive: ATS reviewers just check
# "does the exact phrase appear." A more sophisticated parser is a separate
# improvement; right now we need a defensible first-pass signal.
_TITLE_HINT_RE = re.compile(
    r"(?:position|role|job\s+title|we\s+are\s+hiring\s+(?:a|an))\s*[:\s]\s*([^\n]+)",
    re.IGNORECASE,
)


def extract_jd_title(jd_text: str) -> str:
    """Best-effort JD title extraction. Looks for "Position: X" / "Role: X"
    patterns first; falls back to the first non-empty line if the JD starts
    with a clean heading."""
    hint = _TITLE_HINT_RE.search(jd_text)
    if hint:
        return hint.group(1).strip().rstrip(".,;:")
    # Fallback — first non-empty line, clipped. JD files often start with the title.
    for line in jd_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return ""


def check_job_title(master: ResumeMaster, jd_text: str) -> JobTitleMatch:
    """Compare the JD's title against every role title on the master resume."""
    jd_title = extract_jd_title(jd_text)
    if not jd_title:
        return JobTitleMatch(jd_title="", resume_titles=[])

    resume_titles = [r.role for r in master.experience if r.role]
    # Include the static headline if present — it often carries the role label.
    if master.headline:
        resume_titles.insert(0, master.headline)

    jd_lower = jd_title.lower()
    exact = any(t.strip().lower() == jd_lower for t in resume_titles)
    # Partial match: the JD title is a substring of a resume title, or any
    # non-trivial substring of the JD title appears in a resume title.
    partial = False
    if not exact:
        for t in resume_titles:
            t_lower = t.lower()
            if jd_lower in t_lower or t_lower in jd_lower:
                partial = True
                break
    return JobTitleMatch(
        exact_match=exact,
        partial_match=partial,
        jd_title=jd_title,
        resume_titles=resume_titles,
    )


# --- Measurable results --------------------------------------------------

# Industry reviewers count bullets that carry quantified impact — percentages,
# currency, multipliers, raw counts. We count once per bullet; a bullet with
# "reduced latency by 40% and grew MAU by 3x" counts once, not twice.
_METRIC_RE = re.compile(
    r"""(
        \d+\s*%                         # 40%
        |
        \$\s*\d                         # $10, $1.2M
        |
        \b\d+(?:\.\d+)?\s*(?:x|X)\b     # 3x, 2.5x
        |
        \b\d+\s*(?:requests?|users?|customers?|clients?|transactions?|queries|endpoints?|services?|teams?|engineers?|hours?|days?|weeks?|months?|years?)\b
        |
        \b(?:increased|decreased|reduced|grew|cut|saved|boosted|improved)\s+by\s+\d
    )""",
    re.VERBOSE | re.IGNORECASE,
)


def count_measurable_results(text: str) -> int:
    """How many bullets (or summary lines) carry a quantified result.

    The unit of counting is "lines that match at least one metric pattern" —
    a single bullet with two metrics counts once, matching how ATS reviewers
    score.
    """
    count = 0
    for line in text.splitlines():
        if _METRIC_RE.search(line):
            count += 1
    return count


# --- Word count ----------------------------------------------------------

# Industry advice: resumes under 400 words read thin; over 1000 read bloated.
# The bound is generous — senior-level CVs can legitimately hit 900+.
WORD_COUNT_MIN = 400
WORD_COUNT_MAX = 1000


def count_words(text: str) -> int:
    """Plain whitespace-split count. Close enough to what ATS reviewers report."""
    return len([w for w in text.split() if w.strip()])


def word_count_ok(count: int) -> bool:
    return WORD_COUNT_MIN <= count <= WORD_COUNT_MAX
