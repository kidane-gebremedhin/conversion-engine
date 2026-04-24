"""Job-post velocity from the frozen April 2026 snapshot.

Live scraping would use Playwright with the policy-compliant rate limiter.
During the challenge week the frozen snapshot is primary; a small live crawl
of ≤200 companies is permitted but is not the default path. We omit the
live path here to keep the flow deterministic for tests; the live adapter
can be added behind this interface without changing callers.
"""
from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from agent.config import config, settings


@lru_cache(maxsize=1)
def _load_snapshot() -> dict[str, Any]:
    path = Path(settings.JOB_POSTS_SNAPSHOT_PATH)
    if not path.exists():
        return {"companies": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def company_jobposts(domain: str) -> dict[str, Any] | None:
    """Return the snapshot entry for a domain, or None."""
    data = _load_snapshot().get("companies", {})
    return data.get(domain.lower())


def open_roles_counts(domain: str) -> tuple[int, int]:
    """Return (open_today, open_60d_ago)."""
    entry = company_jobposts(domain)
    if not entry:
        return 0, 0
    today = len(entry.get("open_roles_today", []))
    ago = int(entry.get("open_roles_60d_ago_count", 0))
    return today, ago


def velocity_label_from_counts(today: int, ago: int) -> tuple[str, float]:
    """Return (velocity_label, signal_confidence) given role counts."""
    thresholds = config.get("jobposts.velocity_thresholds", {})
    min_valid = int(config.get("jobposts.min_roles_for_valid_signal", 5))

    if today < min_valid:
        return "insufficient_signal", 0.3

    ratio = today / ago if ago > 0 else float("inf")

    if ratio >= float(thresholds.get("tripled_or_more", 3.0)):
        label = "tripled_or_more"
    elif ratio >= float(thresholds.get("doubled", 2.0)):
        label = "doubled"
    elif ratio >= float(thresholds.get("increased_modestly", 1.25)):
        label = "increased_modestly"
    elif ratio >= float(thresholds.get("flat_low", 0.8)):
        label = "flat"
    else:
        label = "declined"

    # higher confidence when both values are large enough to be stable
    confidence = 0.85 if (today >= 8 and ago >= 3) else 0.65
    return label, confidence


def ai_adjacent_ratio(domain: str) -> float:
    entry = company_jobposts(domain)
    if not entry:
        return 0.0
    roles = entry.get("open_roles_today", [])
    if not roles:
        return 0.0
    adjacent = sum(1 for r in roles if r.get("ai_adjacent"))
    return adjacent / len(roles)


def sources_used(domain: str) -> list[str]:
    entry = company_jobposts(domain)
    if not entry:
        return []
    srcs = {r.get("source") for r in entry.get("open_roles_today", [])}
    return sorted(s for s in srcs if s)


def last_fetched_at() -> dt.datetime:
    data = _load_snapshot()
    snapshot_date = data.get("snapshot_date", "2026-04-01")
    return dt.datetime.fromisoformat(f"{snapshot_date}T00:00:00+00:00")


def invalidate_cache() -> None:
    _load_snapshot.cache_clear()
