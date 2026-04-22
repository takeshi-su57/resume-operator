"""Source ID index for tailored items.

Given a `ResumeMaster` and (optional) `FactsBank`, build a lookup table that
maps every valid `source_id` to its canonical text. `optimize_content` uses
this both to feed the LLM a menu of sources and to validate that every
`TailoredItem.source_id` the LLM produces actually exists — the fabrication
guard for #026.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from resume_operator.state import FactsBank, ResumeMaster


@dataclass
class SourceEntry:
    """One row in the source index: canonical ID + the text the LLM may keep/reword."""

    source_id: str
    text: str
    # `kind` lets the diff renderer group items: "experience-bullet", "skill", etc.
    kind: str


@dataclass
class SourceIndex:
    entries: dict[str, SourceEntry] = field(default_factory=dict)

    def __contains__(self, source_id: str) -> bool:
        return source_id in self.entries

    def __iter__(self) -> object:
        return iter(self.entries.values())

    def as_prompt_menu(self) -> str:
        """Render the index as a compact menu the LLM can see in the prompt."""
        lines: list[str] = []
        for entry in self.entries.values():
            text = entry.text if len(entry.text) <= 300 else entry.text[:297] + "..."
            lines.append(f"- [{entry.source_id}] ({entry.kind}) {text}")
        return "\n".join(lines)

    def get(self, source_id: str) -> SourceEntry | None:
        return self.entries.get(source_id)


def build_source_index(master: ResumeMaster, facts: FactsBank | None) -> SourceIndex:
    """Build a `SourceIndex` covering every citable item on the master + facts bank."""
    idx = SourceIndex()

    if master.summary:
        _add(idx, "master:summary", master.summary, "summary")

    for exp in master.experience:
        header = f"{exp.role} @ {exp.company}".strip(" @")
        _add(idx, f"master:{exp.id}", header, "experience-header")
        for bullet in exp.bullets:
            _add(idx, f"master:{bullet.id}", bullet.text, "experience-bullet")

    for edu in master.education:
        text = f"{edu.degree} — {edu.school}".strip(" —")
        _add(idx, f"master:{edu.id}", text, "education")

    # #68: skill groups and the legacy flat list both get flattened into the
    # index so tailor fabrication-guard IDs stay `master:skill:<name>` either way.
    for skill in master.all_skills():
        _add(idx, f"master:skill:{skill}", skill, "skill")

    for cert in master.certifications:
        _add(idx, f"master:cert:{cert}", cert, "certification")

    if facts is not None:
        for project in facts.projects:
            _add(idx, f"facts:{project.id}", project.text, "project")
        for extra in facts.extra_bullets:
            kind = f"extra-bullet[{extra.role_id}]" if extra.role_id else "extra-bullet"
            _add(idx, f"facts:{extra.id}", extra.text, kind)
        for skill in facts.skills_beyond_master:
            _add(idx, f"facts:skill:{skill}", skill, "skill")
        for cert in facts.certifications_beyond_master:
            _add(idx, f"facts:cert:{cert}", cert, "certification")

    return idx


def _add(idx: SourceIndex, source_id: str, text: str, kind: str) -> None:
    idx.entries[source_id] = SourceEntry(source_id=source_id, text=text, kind=kind)
