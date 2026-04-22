"""Prompt template for proposing a skill-group categorization from a flat list."""

PROPOSE_SKILL_GROUPS = """Given a software engineer's flat list of skills,
propose a reasonable grouping by category. Use these canonical buckets (only
include ones that have items):

  - Languages & Runtimes
  - Frontend & APIs
  - Backend & Data
  - Cloud & Infrastructure
  - AI / ML
  - Tools & DevOps

Rules:
- Every skill in the input MUST appear in exactly one group.
- Do NOT invent skills that aren't in the input.
- Drop categories that would have no items — don't emit empty groups.
- Preserve the original capitalization of each skill (e.g. "PostgreSQL" not
  "postgresql").
- If a skill is ambiguous (e.g. "Docker" fits both Backend and Cloud),
  prefer the more specific category.

Flat skills list:
{skills}
"""
