"""Crunchbase ODM sample loader.

For the interim we load from `data/crunchbase_odm/companies.json` — the
Luminati public sample shape — and expose by_domain / by_uuid / funding_events.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timedelta
from functools import lru_cache

from pydantic import BaseModel

from agent.state import CrunchbaseRecord


_ODM_PATH = pathlib.Path("data/crunchbase_odm/companies.json")


class FundingEvent(BaseModel):
    round_type: str
    amount_usd: int | None = None
    announced_on: date
    investors: list[str] = []
    source_url: str | None = None


@lru_cache(maxsize=1)
def load_all() -> list[CrunchbaseRecord]:
    if not _ODM_PATH.exists():
        return []
    data = json.loads(_ODM_PATH.read_text())
    out: list[CrunchbaseRecord] = []
    for row in data:
        out.append(_coerce(row))
    return out


def _coerce(row: dict) -> CrunchbaseRecord:
    return CrunchbaseRecord(
        uuid=row["uuid"],
        name=row["name"],
        domain=row.get("domain"),
        country=row.get("country"),
        region=row.get("region"),
        industries=row.get("industries", []),
        founded_on=_date(row.get("founded_on")),
        employee_count_range=row.get("employee_count_range"),
        total_funding_usd=row.get("total_funding_usd"),
        last_funding_type=row.get("last_funding_type"),
        last_funding_amount_usd=row.get("last_funding_amount_usd"),
        last_funding_date=_date(row.get("last_funding_date")),
        founders=row.get("founders", []),
        ceo=row.get("ceo"),
        linkedin_url=row.get("linkedin_url"),
        crunchbase_url=row.get("crunchbase_url"),
        raw=row,
    )


def _date(s: str | None) -> date | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def by_uuid(uuid: str) -> CrunchbaseRecord | None:
    for r in load_all():
        if r.uuid == uuid:
            return r
    return None


def by_domain(domain: str) -> CrunchbaseRecord | None:
    d = domain.lower().strip()
    for r in load_all():
        if r.domain and r.domain.lower() == d:
            return r
    return None


def funding_events(uuid: str, *, since_days: int = 180, today: date | None = None) -> list[FundingEvent]:
    r = by_uuid(uuid)
    if not r or not r.last_funding_date:
        return []
    today = today or date.today()
    if (today - r.last_funding_date) > timedelta(days=since_days):
        return []
    return [
        FundingEvent(
            round_type=r.last_funding_type or "Unknown",
            amount_usd=r.last_funding_amount_usd,
            announced_on=r.last_funding_date,
            investors=r.raw.get("last_funding_investors", []) if r.raw else [],
            source_url=r.crunchbase_url,
        )
    ]
