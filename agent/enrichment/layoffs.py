"""layoffs.fyi CSV adapter.

Matches company names tolerantly (lowercase + whitespace + remove legal suffixes)
and returns events within a rolling window.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
from functools import lru_cache
from pathlib import Path

from agent.config import settings


_LEGAL_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|ltd|limited|llc|corp|corporation|gmbh|s\.?a\.?|plc|bv|ag|sarl|co\.?|oy|aps|as)\.?$",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r"[^\w\s]", "", n)
    n = _LEGAL_SUFFIX_RE.sub("", n).strip()
    n = re.sub(r"\s+", " ", n)
    return n


@lru_cache(maxsize=1)
def _load() -> list[dict[str, str]]:
    path = Path(settings.LAYOFFS_FYI_LOCAL_PATH)
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def within_window(
    company_name: str, window_days: int = 120, today: dt.date | None = None
) -> dict[str, object] | None:
    """Return the most recent layoff event within `window_days` for the company."""
    today = today or dt.date.today()
    target = _normalize(company_name)
    best: dict[str, object] | None = None
    for row in _load():
        if _normalize(row.get("company", "")) != target:
            continue
        try:
            event_date = dt.date.fromisoformat(row["date"])
        except (ValueError, KeyError):
            continue
        delta = (today - event_date).days
        if 0 <= delta <= window_days:
            try:
                record: dict[str, object] = {
                    "date": event_date,
                    "headcount_reduction": int(row.get("headcount_reduction", "0") or 0),
                    "percentage_cut": float(row.get("percentage_cut", "0") or 0),
                    "source_url": row.get("source_url", ""),
                }
            except ValueError:
                continue
            if best is None or record["date"] > best["date"]:  # type: ignore[operator]
                best = record
    return best


def invalidate_cache() -> None:
    _load.cache_clear()
