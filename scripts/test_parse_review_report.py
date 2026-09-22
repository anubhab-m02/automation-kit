from parse_review_report import parse_review_report

_SAMPLE = """---
date: 2026-08-20
verdicts:
  - pr_number: 42
    verdict: approve
    reason: "Tests pass, no sensitive paths touched."
  - pr_number: 43
    verdict: request_changes
    reason: "Missing test coverage for the new branch."
findings:
  - description: "retrieval/search.py's RELEVANCE_FLOOR comment is stale."
    severity: minor
    related_pr: null
  - description: "config_store.py silently swallows a JSONDecodeError."
    severity: major
    related_pr: 43
---

# Review report — 2026-08-20

body text, not parsed
"""


def test_parses_date():
    report = parse_review_report(_SAMPLE)
    assert report.date == "2026-08-20"


def test_parses_all_verdicts_in_order():
    report = parse_review_report(_SAMPLE)
    assert len(report.verdicts) == 2
    assert report.verdicts[0].pr_number == 42
    assert report.verdicts[0].verdict == "approve"
    assert report.verdicts[1].verdict == "request_changes"


def test_parses_findings_with_severity_and_optional_related_pr():
    report = parse_review_report(_SAMPLE)
    assert len(report.findings) == 2
    assert report.findings[0].severity == "minor"
    assert report.findings[0].related_pr is None
    assert report.findings[1].severity == "major"
    assert report.findings[1].related_pr == 43


def test_report_with_no_findings_parses_to_empty_list():
    text = """---
date: 2026-08-21
verdicts: []
findings: []
---

# Review report — 2026-08-21

Nothing to report today.
"""
    report = parse_review_report(text)
    assert report.verdicts == []
    assert report.findings == []


def test_missing_frontmatter_raises_a_clear_error():
    import pytest

    with pytest.raises(ValueError, match="no YAML frontmatter"):
        parse_review_report("# Just a heading, no frontmatter\n")
