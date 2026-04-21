"""Render a human-readable `diff.md` from a `TailoredResume`.

Three sections:
  - Additions: facts-bank items pulled into the output
  - Rewordings: master items included but rephrased (shows before/after)
  - Deletions: master items considered but dropped
Skills and certifications are grouped separately for readability.
"""

from __future__ import annotations

from resume_operator.state import TailoredItem, TailoredResume
from resume_operator.tools.source_index import SourceIndex


def render_diff(tailored: TailoredResume, index: SourceIndex) -> str:
    additions = [
        i for i in tailored.items if i.action == "keep" and i.source_id.startswith("facts:")
    ]
    # "keep" master items aren't diff-worthy on their own — they were on the master already.
    # "reword" items always show before/after regardless of source.
    rewordings = [i for i in tailored.items if i.action == "reword"]
    deletions = [i for i in tailored.items if i.action == "drop"]

    lines: list[str] = ["# Tailoring Diff", ""]

    if tailored.notes:
        lines.append("## Strategy Notes")
        lines.extend(f"- {note}" for note in tailored.notes)
        lines.append("")

    lines.append("## Additions — items pulled from the facts bank")
    if additions:
        lines.extend(_render_items(additions, index, show_new=False))
    else:
        lines.append("_No facts-bank items pulled in._")
    lines.append("")

    lines.append("## Rewordings — master or facts items with adjusted phrasing")
    if rewordings:
        for item in rewordings:
            entry = index.get(item.source_id)
            kind = entry.kind if entry else "unknown"
            lines.append(f"- **{item.source_id}** ({kind})")
            lines.append(f"  - before: {item.original_text}")
            lines.append(f"  - after:  {item.new_text}")
    else:
        lines.append("_No rewordings._")
    lines.append("")

    lines.append("## Deletions — master items considered but dropped")
    if deletions:
        lines.extend(_render_items(deletions, index, show_new=False))
    else:
        lines.append("_No master items dropped._")
    lines.append("")

    return "\n".join(lines)


def _render_items(items: list[TailoredItem], index: SourceIndex, *, show_new: bool) -> list[str]:
    lines: list[str] = []
    for item in items:
        entry = index.get(item.source_id)
        kind = entry.kind if entry else "unknown"
        text = item.new_text if show_new and item.new_text else item.original_text
        lines.append(f"- **{item.source_id}** ({kind}) {text}")
    return lines
