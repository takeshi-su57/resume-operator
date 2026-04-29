"""Tests for the deterministic ATS checks (#81).

Covers the structural half of `ATSReport` — no LLM, pure regex / string
matching. Each check has a positive path, a negative path, and at least
one edge case.
"""

from __future__ import annotations

import pytest

from lucky_resume.state import (
    EducationEntry,
    ExperienceEntry,
    ResumeMaster,
)
from lucky_resume.tools.ats_checks import (
    WORD_COUNT_MAX,
    WORD_COUNT_MIN,
    check_contact,
    check_job_title,
    check_sections,
    count_measurable_results,
    count_words,
    extract_jd_title,
    word_count_ok,
)


def _master(**kwargs: object) -> ResumeMaster:
    base = ResumeMaster(name="Jane Doe")
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


class TestContactCheck:
    def test_master_fields_are_authoritative(self) -> None:
        master = _master(email="jane@example.com", phone="555-1234", location="Seattle, WA")
        check = check_contact(master, "")  # empty text — master should still win
        assert check.email_present
        assert check.phone_present
        assert check.address_present

    def test_regex_fallback_when_master_empty(self) -> None:
        master = _master()  # all contact fields empty
        text = "Contact me at jane@example.com or 555-123-4567. 123 Main Street."
        check = check_contact(master, text)
        assert check.email_present
        assert check.phone_present
        assert check.address_present

    def test_missing_everything(self) -> None:
        check = check_contact(_master(), "no contact info here")
        assert not check.email_present
        assert not check.phone_present
        assert not check.address_present

    def test_us_zip_counts_as_address(self) -> None:
        check = check_contact(_master(), "mail: PO Box 12345-6789")
        assert check.address_present

    def test_japanese_phone_format(self) -> None:
        check = check_contact(_master(), "call me at 080-1234-5678")
        assert check.phone_present


class TestSectionCheck:
    def test_master_with_data_is_sufficient(self) -> None:
        master = _master(
            summary="A summary",
            experience=[ExperienceEntry(id="exp-1", role="Eng", company="Acme")],
            education=[EducationEntry(id="edu-1", degree="BS")],
            skills=["Python"],
        )
        sc = check_sections(master, "")
        assert sc.summary and sc.experience and sc.education and sc.skills

    def test_text_headings_are_fallback(self) -> None:
        text = "SUMMARY\nsome text\nWORK EXPERIENCE\n...\nEDUCATION\n...\nTECHNICAL SKILLS\n..."
        sc = check_sections(_master(), text)
        assert sc.summary and sc.experience and sc.education and sc.skills

    def test_all_missing(self) -> None:
        sc = check_sections(_master(), "no recognized sections here")
        assert not (sc.summary or sc.experience or sc.education or sc.skills)

    def test_permissive_on_casing_and_variants(self) -> None:
        text = "Professional Summary\n\nProfessional Experience\n\nCore Skills\n"
        sc = check_sections(_master(), text)
        assert sc.summary
        assert sc.experience
        assert sc.skills


class TestJobTitleExtraction:
    def test_position_hint(self) -> None:
        assert extract_jd_title("Position: Staff Backend Engineer") == "Staff Backend Engineer"

    def test_role_hint(self) -> None:
        assert extract_jd_title("Role: Senior SRE") == "Senior SRE"

    def test_falls_back_to_first_line(self) -> None:
        jd = "\n\nSenior Full-Stack LLM Engineer\n\nWe're looking for..."
        assert extract_jd_title(jd) == "Senior Full-Stack LLM Engineer"

    def test_empty_jd_returns_empty(self) -> None:
        assert extract_jd_title("") == ""
        assert extract_jd_title("   \n  \n") == ""


class TestJobTitleMatch:
    def test_exact_match(self) -> None:
        master = _master(experience=[ExperienceEntry(id="exp-1", role="Senior Backend Engineer")])
        match = check_job_title(master, "Position: Senior Backend Engineer")
        assert match.exact_match
        assert not match.partial_match  # exact supersedes partial
        assert match.jd_title == "Senior Backend Engineer"

    def test_partial_match_substring(self) -> None:
        master = _master(experience=[ExperienceEntry(id="exp-1", role="Backend Engineer")])
        match = check_job_title(master, "Position: Senior Backend Engineer")
        assert not match.exact_match
        assert match.partial_match

    def test_no_match(self) -> None:
        master = _master(experience=[ExperienceEntry(id="exp-1", role="Data Analyst")])
        match = check_job_title(master, "Position: Senior Backend Engineer")
        assert not match.exact_match
        assert not match.partial_match

    def test_headline_included_in_candidates(self) -> None:
        master = _master(headline="Senior Backend Engineer · 8+ years · Python")
        match = check_job_title(master, "Position: Senior Backend Engineer")
        # Partial — headline is "Senior Backend Engineer · ..." which contains the JD title.
        assert match.partial_match

    def test_empty_jd_title_returns_empty_match(self) -> None:
        match = check_job_title(_master(), "")
        assert not (match.exact_match or match.partial_match)
        assert match.jd_title == ""


class TestMeasurableResults:
    def test_percent(self) -> None:
        text = "- Reduced p99 latency by 40% on the order service\n- Hired 4 engineers"
        # Line 1 matches 40% + "reduced...by 40" (same line counted once).
        # Line 2: "4 engineers" → matches the count pattern.
        assert count_measurable_results(text) == 2

    def test_currency(self) -> None:
        assert count_measurable_results("Saved $1.2M in infra costs") == 1

    def test_multiplier(self) -> None:
        assert count_measurable_results("Grew MAU 3x over 6 months") == 1

    def test_generic_counts(self) -> None:
        text = "Shipped 50 endpoints serving 2M requests per day"
        # Two count-units on the same line = one counted line.
        assert count_measurable_results(text) == 1

    def test_no_metrics(self) -> None:
        assert count_measurable_results("Led the team and built things") == 0


class TestWordCount:
    def test_basic_count(self) -> None:
        assert count_words("one two three four five") == 5

    def test_whitespace_normalised(self) -> None:
        assert count_words("one\ntwo  three\t\tfour") == 4

    def test_empty(self) -> None:
        assert count_words("") == 0
        assert count_words("   \n\t  ") == 0

    @pytest.mark.parametrize(
        "count, ok",
        [
            (WORD_COUNT_MIN - 1, False),
            (WORD_COUNT_MIN, True),
            (700, True),
            (WORD_COUNT_MAX, True),
            (WORD_COUNT_MAX + 1, False),
        ],
    )
    def test_bounds(self, count: int, ok: bool) -> None:
        assert word_count_ok(count) is ok
