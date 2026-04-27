"""Crunchbase ODM sample loader.

Every HubSpot lead object must reference a Crunchbase record (per the
challenge brief). This module is the gate: lookup_by_domain() either
returns a CompanyRecord or None. The pipeline refuses to outreach a
domain with no Crunchbase match.
"""
from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from agent.config import settings


def _crunchbase_path() -> Path:
    return Path(settings.CRUNCHBASE_ODM_LOCAL_PATH)


@lru_cache(maxsize=1)
def _load() -> list[dict[str, Any]]:
    path = _crunchbase_path()
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def _normalize_domain(domain: str) -> str:
    d = domain.lower().strip()
    if d.startswith("http://"):
        d = d[7:]
    if d.startswith("https://"):
        d = d[8:]
    if d.startswith("www."):
        d = d[4:]
    return d.split("/")[0]


def lookup_by_domain(domain: str) -> dict[str, Any] | None:
    """Return the Crunchbase record for a domain, or None if not in the sample."""
    target = _normalize_domain(domain)
    for record in _load():
        if _normalize_domain(record.get("domain", "")) == target:
            return record
    return None


def recent_funding_event(record: dict[str, Any], window_days: int = 3650) -> dict[str, Any] | None:
    """Return the most recent funding round within `window_days`, or None."""
    today = dt.date.today()
    best: dict[str, Any] | None = None
    for round_ in record.get("funding_rounds", []) or []:
        closed_at_str = round_.get("closed_at")
        if not closed_at_str:
            continue
        try:
            closed_at = dt.date.fromisoformat(closed_at_str)
        except ValueError:
            continue
        delta = (today - closed_at).days
        if 0 <= delta <= window_days:
            if best is None or dt.date.fromisoformat(best["closed_at"]) < closed_at:
                best = round_
    return best


def new_leadership_in_window(
    record: dict[str, Any], window_days: int = 3650, roles: tuple[str, ...] = ("cto", "vp_engineering")
) -> dict[str, Any] | None:
    """Return a leadership entry newly appointed within `window_days`, matching a role."""
    today = dt.date.today()
    for leader in record.get("leadership", []) or []:
        if leader.get("role") not in roles:
            continue
        if leader.get("is_interim"):
            continue
        started_at_str = leader.get("started_at")
        if not started_at_str:
            continue
        try:
            started_at = dt.date.fromisoformat(started_at_str)
        except ValueError:
            continue
        if 0 <= (today - started_at).days <= window_days:
            return leader
    return None


def company_sector(record: dict[str, Any]) -> tuple[str, str | None]:
    """Return (sector, sub_niche) from the record."""
    categories = record.get("categories", []) or []
    sector = categories[0] if categories else "software"
    sub_niche = record.get("sub_niche")
    return sector, sub_niche


def peers_in_sector(
    record: dict[str, Any],
    same_headcount_band: bool = True,
    limit: int = 10,
    exclude_domains: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return peer records for competitor-gap analysis."""
    exclude_domains = exclude_domains or set()
    exclude_domains.add(_normalize_domain(record["domain"]))
    sector, sub_niche = company_sector(record)
    target_band = record.get("headcount_band")
    peers: list[dict[str, Any]] = []
    for candidate in _load():
        domain = _normalize_domain(candidate.get("domain", ""))
        if domain in exclude_domains:
            continue
        cat = candidate.get("categories", []) or []
        cand_sub = candidate.get("sub_niche")
        # match on shared categories OR sub_niche
        if sub_niche and cand_sub == sub_niche:
            pass
        elif any(c in cat for c in (record.get("categories", []) or [])):
            pass
        else:
            continue
        if same_headcount_band and candidate.get("headcount_band") != target_band:
            continue
        if candidate.get("listed_as_competitor_client"):
            continue
        peers.append(candidate)
    # rank by rank_score desc
    peers.sort(key=lambda c: c.get("rank_score", 0.0), reverse=True)
    return peers[:limit]


def invalidate_cache() -> None:
    _load.cache_clear()
