"""Leadership-change detection.

Primary source: the Crunchbase ODM sample (leadership[].is_new_in_window).
Secondary sources (press, LinkedIn) are wired through the same interface
when available.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from agent.config import config


# Headline keyword → role enum, for parsing the `leadership_hire_events`
# press feed. Order matters: more specific phrases first.
_HEADLINE_ROLE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(head of (ai|ml)|chief ai officer|vp[, ]+ai)\b", re.I), "head_of_ai"),
    (re.compile(r"\b(chief data officer|cdo|head of data|vp[, ]+data)\b", re.I), "chief_data_officer"),
    (re.compile(r"\b(vp[, ]+engineering|svp[, ]+engineering)\b", re.I), "vp_engineering"),
    (re.compile(r"\b(cto|chief technology officer)\b", re.I), "cto"),
]

_INTERIM_RE = re.compile(r"\b(interim|acting)\b", re.I)
_TECH_ROLES = ("cto", "vp_engineering", "head_of_ai", "chief_data_officer")


def _detect_from_roster(record: dict[str, Any], window_days: int, today: dt.date) -> dict[str, Any] | None:
    """Walk leadership[] looking for a new technical leader within window."""
    for leader in record.get("leadership", []) or []:
        if leader.get("is_interim"):
            continue
        if leader.get("role") not in _TECH_ROLES:
            continue
        started_at_str = leader.get("started_at")
        if not started_at_str:
            continue
        try:
            started_at = dt.date.fromisoformat(started_at_str)
        except (ValueError, TypeError):
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


def _detect_from_press(record: dict[str, Any], window_days: int, today: dt.date) -> dict[str, Any] | None:
    """Walk leadership_hire_events[] (dated press headlines) for a fresh hire."""
    for ev in record.get("leadership_hire_events", []) or []:
        label = ev.get("label") or ""
        if _INTERIM_RE.search(label):
            continue
        role: str | None = None
        for pat, r in _HEADLINE_ROLE_RULES:
            if pat.search(label):
                role = r
                break
        if not role:
            continue
        date_str = ev.get("date")
        if not date_str:
            continue
        try:
            event_date = dt.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue
        if event_date > today or (today - event_date).days > window_days:
            continue
        return {
            "detected": True,
            "role": role,
            "new_leader_name": label,  # the headline is all we have
            "started_at": event_date,
            "source_url": ev.get("source_url"),
        }
    return None


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
    window_days = int(config.get("leadership.window_days", 3650))
    today = dt.date.today()

    # Roster (leadership[]) is preferred — it carries the canonical role enum.
    # Press feed is a fallback for sources that lack a started_at on the roster.
    return (
        _detect_from_roster(record, window_days, today)
        or _detect_from_press(record, window_days, today)
    )


def has_interim_current(record: dict[str, Any]) -> bool:
    """True if any current leadership entry is interim/acting."""
    for leader in record.get("leadership", []) or []:
        if leader.get("is_interim"):
            return True
    return False
