"""Leadership-change detection.

Primary source: the Crunchbase ODM sample (leadership[].is_new_in_window).
Secondary sources (press, LinkedIn) are wired through the same interface
when available.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from agent.config import config


def detect(record: dict[str, Any]) -> dict[str, Any] | None:
    """Return a new leadership-change event or None.

    Event shape:
        {
          "detected": True,
          "role": "cto" | "vp_engineering" | ...,
          "new_leader_name": str,
          "started_at": date,
          "source_url": str | None,
        }

    Returns None when no qualifying change is detected. Interim/acting leaders
    are excluded per the Segment 3 disqualifier in icp_definition.md.
    """
    window_days = int(config.get("leadership.window_days", 90))
    today = dt.date.today()

    for leader in record.get("leadership", []) or []:
        if leader.get("is_interim"):
            continue
        if leader.get("role") not in ("cto", "vp_engineering"):
            continue
        started_at_str = leader.get("started_at")
        if not started_at_str:
            continue
        try:
            started_at = dt.date.fromisoformat(started_at_str)
        except ValueError:
            continue
        if (today - started_at).days > window_days:
            continue
        return {
            "detected": True,
            "role": leader["role"],
            "new_leader_name": leader.get("name", "unknown"),
            "started_at": started_at,
            "source_url": None,
        }

    return None


def has_interim_current(record: dict[str, Any]) -> bool:
    """True if any current leadership entry is interim/acting."""
    for leader in record.get("leadership", []) or []:
        if leader.get("is_interim"):
            return True
    return False
