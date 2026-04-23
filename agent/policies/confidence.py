"""Confidence policy — signal-confidence-aware phrasing.

Verifies that assertions in the draft are backed by signals at the required
band. Key hard rule: "aggressive hiring" (and close synonyms) only when
`qualifies_for_aggressive_hiring_claim == true`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_AGGRESSIVE_HIRING_RE = re.compile(
    r"\b(aggressive(ly)?\s+hir|mass\s+hir|hiring\s+spree|ramping\s+(up\s+)?hiring)\b",
    re.IGNORECASE,
)

_FUNDING_ASSERT_RE = re.compile(r"\$\s*\d+(\.\d+)?\s*[mb]\b", re.IGNORECASE)


@dataclass
class ConfidenceResult:
    passed: bool
    violations: list[str]


def check(draft_markdown: str, *, brief_signals: dict) -> ConfidenceResult:
    v: list[str] = []
    velocity = brief_signals.get("job_post_velocity", {}) or {}
    funding = brief_signals.get("funding", {}) or {}

    if _AGGRESSIVE_HIRING_RE.search(draft_markdown) and not velocity.get("qualifies_for_aggressive_hiring_claim"):
        v.append("asserts 'aggressive hiring' but qualifies_for_aggressive_hiring_claim=false")

    if _FUNDING_ASSERT_RE.search(draft_markdown):
        conf = funding.get("confidence", 0.0)
        if conf < 0.75:
            v.append(f"asserts a funding number but funding confidence={conf:.2f} < 0.75")

    return ConfidenceResult(passed=not v, violations=v)
