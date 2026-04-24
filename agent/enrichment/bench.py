"""Bench loader. The single source of truth for staffing capacity claims.

The agent may NEVER claim capacity the seed bench summary does not show.
See __specs/05-signal-enrichment-pipeline.md (bench gate) and the style
guide rule "never over-commit bench capacity."
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from agent.config import SEED_DIR, config


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    path = Path(config.get("bench.summary_source", "tenacious_sales_data/seed/bench_summary.json"))
    if not path.is_absolute():
        # Try seed dir first, then repo root
        candidates = [SEED_DIR.parent / path.name, SEED_DIR / path.name, path]
        for c in candidates:
            if c.exists():
                path = c
                break
    if not path.exists():
        return {"as_of": "", "stacks": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def available(stack: str) -> int:
    """Engineers available on the bench for a stack, or 0 if unknown."""
    data = _load().get("stacks", {}).get(stack, {})
    return int(data.get("available_engineers", 0))


def match(required_stacks: list[str]) -> dict[str, Any]:
    """Return a bench-to-brief match summary.

    Output:
        {
          "required_stacks": [...],
          "bench_available": bool,      # True if ALL required stacks have ≥1
          "gaps": [...],                # stacks with zero available engineers
          "counts": {stack: int},
        }
    """
    counts: dict[str, int] = {s: available(s) for s in required_stacks}
    gaps = [s for s, n in counts.items() if n == 0]
    return {
        "required_stacks": list(required_stacks),
        "bench_available": len(gaps) == 0,
        "gaps": gaps,
        "counts": counts,
    }


def snapshot_as_of() -> str:
    return str(_load().get("as_of", ""))


def all_stacks() -> list[str]:
    return list(_load().get("stacks", {}).keys())


def invalidate_cache() -> None:
    _load.cache_clear()
