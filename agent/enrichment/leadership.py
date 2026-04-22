"""Leadership-change detection — Crunchbase key-people diff fixture.

For the interim, we read `data/leadership_events/<uuid>.json` if present.
Shape: `{"role": "CTO", "name": "...", "start_date": "2026-02-12", "source_url": "..."}`
or `null` if no change.
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timedelta

from pydantic import BaseModel


_DIR = pathlib.Path("data/leadership_events")


class LeadershipChange(BaseModel):
    role: str
    name: str
    start_date: date
    source_url: str | None = None


def detect(crunchbase_uuid: str, *, since_days: int = 90, today: date | None = None) -> LeadershipChange | None:
    p = _DIR / f"{crunchbase_uuid}.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    if not data:
        return None
    start = datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    today = today or date.today()
    if (today - start) > timedelta(days=since_days):
        return None
    return LeadershipChange(
        role=data["role"], name=data["name"], start_date=start, source_url=data.get("source_url")
    )
