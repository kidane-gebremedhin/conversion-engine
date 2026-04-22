"""layoffs.fyi snapshot loader + per-company match.

Load from `data/layoffs_fyi/layoffs.csv`. Matching: normalised exact name
primary, alias table fallback (`data/layoffs_fyi/aliases.yaml`), no fuzzy.
"""
from __future__ import annotations

import csv
import pathlib
import re
from datetime import date, datetime, timedelta
from functools import lru_cache

import yaml
from pydantic import BaseModel


_CSV = pathlib.Path("data/layoffs_fyi/layoffs.csv")
_ALIASES = pathlib.Path("data/layoffs_fyi/aliases.yaml")


class LayoffEvent(BaseModel):
    company_name: str
    date: date
    headcount: int | None = None
    percentage: float | None = None
    source_url: str | None = None


@lru_cache(maxsize=1)
def load_snapshot() -> list[LayoffEvent]:
    if not _CSV.exists():
        return []
    out: list[LayoffEvent] = []
    with _CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                out.append(
                    LayoffEvent(
                        company_name=row["company"].strip(),
                        date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                        headcount=_int(row.get("headcount")),
                        percentage=_float(row.get("percentage")),
                        source_url=row.get("source") or None,
                    )
                )
            except (KeyError, ValueError):
                continue
    return out


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    if not _ALIASES.exists():
        return {}
    data = yaml.safe_load(_ALIASES.read_text()) or {}
    return {k.lower(): v.lower() for k, v in data.items()}


def _norm(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\b(inc|incorporated|corp|corporation|ltd|llc|limited|co)\.?\b", "", name)
    return re.sub(r"[^a-z0-9]+", "", name)


def find_by_company(name: str, *, since_days: int = 120, today: date | None = None) -> list[LayoffEvent]:
    today = today or date.today()
    target = _norm(name)
    alias_hit = _aliases().get(name.lower())
    alias_norm = _norm(alias_hit) if alias_hit else None
    out: list[LayoffEvent] = []
    for ev in load_snapshot():
        if (today - ev.date) > timedelta(days=since_days):
            continue
        n = _norm(ev.company_name)
        if n == target or (alias_norm and n == alias_norm):
            out.append(ev)
    return out


def _int(x: str | None) -> int | None:
    try:
        return int(x) if x not in (None, "", "N/A") else None
    except ValueError:
        return None


def _float(x: str | None) -> float | None:
    try:
        if not x or x in ("", "N/A"):
            return None
        return float(x.rstrip("%")) / (100.0 if x.endswith("%") else 1.0)
    except ValueError:
        return None
