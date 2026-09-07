"""Parses a review report's YAML frontmatter into typed objects.

The frontmatter is the machine-readable contract between the Reviewer
(which writes it) and the Issue Generator (which reads it) — the
Markdown body below the frontmatter is for humans only and is never
parsed.
"""

from dataclasses import dataclass
from typing import Literal

import yaml


@dataclass
class PrVerdict:
    pr_number: int
    verdict: Literal["approve", "request_changes"]
    reason: str


@dataclass
class Finding:
    description: str
    severity: Literal["none", "minor", "major"]
    related_pr: int | None


@dataclass
class ReviewReport:
    date: str
    verdicts: list[PrVerdict]
    findings: list[Finding]


def parse_review_report(text: str) -> ReviewReport:
    if not text.startswith("---\n"):
        raise ValueError("no YAML frontmatter found at the start of the report")

    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("no YAML frontmatter closing marker found")

    frontmatter = yaml.safe_load(text[4:end])

    return ReviewReport(
        # PyYAML parses an unquoted `date: 2026-08-20` as a datetime.date,
        # not a string — normalize explicitly so callers get a plain str
        # regardless of whether the report quoted its date.
        date=str(frontmatter["date"]),
        verdicts=[PrVerdict(**v) for v in frontmatter.get("verdicts", [])],
        findings=[Finding(**f) for f in frontmatter.get("findings", [])],
    )
