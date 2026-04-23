"""Tone policy — style-guide enforcement.

Cheap lexical check + optional LLM second-pass (dev-tier). Returns
`{pass, violations, suggestions}`.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from functools import lru_cache

from agent.llm.client import LlmClient


_STYLE_GUIDE = pathlib.Path("seed/style_guide.md")
_BANNED = ["offshore", "leverage", "synergy", "crush it"]


@dataclass
class ToneResult:
    passed: bool
    violations: list[str]
    suggestions: list[str]


@lru_cache(maxsize=1)
def _style_guide_text() -> str:
    if not _STYLE_GUIDE.exists():
        return ""
    return _STYLE_GUIDE.read_text()[:2000]


def check(draft_markdown: str, *, llm: LlmClient | None = None, stage: str = "cold") -> ToneResult:
    violations: list[str] = []
    suggestions: list[str] = []
    text_lower = draft_markdown.lower()
    for b in _BANNED:
        if b in text_lower:
            violations.append(f"banned phrase: '{b}'")
            suggestions.append(f"replace '{b}' with a concrete, observation-based phrasing")

    if llm is None:
        return ToneResult(passed=not violations, violations=violations, suggestions=suggestions)

    style = _style_guide_text()
    if not style:
        return ToneResult(passed=not violations, violations=violations, suggestions=suggestions)

    system = (
        "You are a tone/style reviewer for Tenacious Consulting. Given a style guide excerpt "
        "and a draft, return JSON with 'pass' (bool), 'violations' (list[str]), and 'suggestions' (list[str]). "
        "Be strict about first-person plural overuse, vagueness, and any marketing-superlative drift."
    )
    user = f"STAGE={stage}\nSTYLE_GUIDE:\n{style}\n\nDRAFT:\n{draft_markdown}"
    resp = llm.complete(system=system, user=user, stage="tone_check", response_format="json")
    try:
        data = json.loads(resp.text)
    except json.JSONDecodeError:
        return ToneResult(passed=not violations, violations=violations, suggestions=suggestions)
    violations += data.get("violations", [])
    suggestions += data.get("suggestions", [])
    return ToneResult(
        passed=bool(data.get("pass", True)) and not violations,
        violations=violations,
        suggestions=suggestions,
    )
