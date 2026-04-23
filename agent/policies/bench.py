r"""Bench policy — hard gate on capacity claims.

Parses `seed/bench_summary.yaml` for `{stack: count}` availability. Scans the
draft for regex patterns like `\b(\d+)\s+(engineers|developers|...)\b` with
a nearby stack word. If a claim exceeds the bench, the send is BLOCKED.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from functools import lru_cache

import yaml


_BENCH_PATH = pathlib.Path("seed/bench_summary.yaml")

_CAPACITY_RE = re.compile(
    r"\b(\d+)\s+(?:senior\s+)?(?:python|go|golang|rust|java|kotlin|scala|ruby|data|ml|ai|infra|platform)\s+(?:engineers?|developers?|scientists?|data scientists?)\b",
    re.IGNORECASE,
)

_STACK_NORM = {
    "python": "python",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "java": "java",
    "kotlin": "kotlin",
    "scala": "scala",
    "ruby": "ruby",
    "data": "data",
    "ml": "ml",
    "ai": "ml",
    "infra": "infra",
    "platform": "infra",
}


@dataclass
class BenchResult:
    passed: bool
    flagged: list[str]


@lru_cache(maxsize=1)
def _bench_counts() -> dict[str, int]:
    if not _BENCH_PATH.exists():
        return {}
    data = yaml.safe_load(_BENCH_PATH.read_text()) or {}
    raw = data.get("available", data)
    return {k.lower(): int(v) for k, v in raw.items()}


def check(draft_markdown: str) -> BenchResult:
    flagged: list[str] = []
    for m in _CAPACITY_RE.finditer(draft_markdown):
        n = int(m.group(1))
        phrase = m.group(0)
        # Pull stack key out of the phrase
        stack_match = re.search(r"(python|go|golang|rust|java|kotlin|scala|ruby|data|ml|ai|infra|platform)", phrase, re.IGNORECASE)
        if not stack_match:
            continue
        stack = _STACK_NORM[stack_match.group(1).lower()]
        avail = _bench_counts().get(stack, 0)
        if n > avail:
            flagged.append(f"claim '{phrase}' exceeds bench availability ({stack}: {avail})")
    return BenchResult(passed=not flagged, flagged=flagged)
