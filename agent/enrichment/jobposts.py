"""Job-post snapshot reader + velocity metric.

Reads the early-April 2026 snapshot under `data/jobposts_snapshot/`. Each
company directory has `now.json` + `prior.json` (60-day prior baseline).
"""
from __future__ import annotations

import json
import pathlib
import re
from datetime import date
from functools import lru_cache

from pydantic import BaseModel


_SNAP = pathlib.Path("data/jobposts_snapshot")

_AI_ADJ_RE = re.compile(
    r"\b(machine learning|ml engineer|applied scientist|research scientist|llm|ai engineer|"
    r"ai product|data platform|data engineer.*(ml|ai)|mlops|vector|rag|genai)\b",
    re.IGNORECASE,
)


class JobPost(BaseModel):
    company_domain: str
    title: str
    posted_at: date | None = None
    location: str | None = None
    department: str | None = None
    role_category: str = "other"
    url: str | None = None


class VelocityReport(BaseModel):
    open_roles_now: int
    open_roles_60d_ago: int
    ratio: float
    ai_adjacent_fraction: float
    qualifies_for_aggressive_hiring_claim: bool
    confidence: float


def _slug(domain: str) -> str:
    return domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]


def _load(company_dir: pathlib.Path, which: str) -> list[JobPost]:
    p = company_dir / f"{which}.json"
    if not p.exists():
        return []
    rows = json.loads(p.read_text())
    out: list[JobPost] = []
    for r in rows:
        out.append(
            JobPost(
                company_domain=r.get("company_domain", ""),
                title=r["title"],
                posted_at=_date(r.get("posted_at")),
                location=r.get("location"),
                department=r.get("department"),
                role_category=r.get("role_category", "other"),
                url=r.get("url"),
            )
        )
    return out


def _date(s: str | None) -> date | None:
    if not s:
        return None
    from datetime import datetime

    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


@lru_cache(maxsize=256)
def _posts(domain: str) -> tuple[list[JobPost], list[JobPost]]:
    d = _SNAP / _slug(domain)
    if not d.exists():
        return [], []
    return _load(d, "now"), _load(d, "prior")


def crawl(company_domain: str) -> list[JobPost]:
    now, _ = _posts(company_domain)
    return now


def velocity(company_domain: str) -> VelocityReport:
    now, prior = _posts(company_domain)
    n, p = len(now), max(1, len(prior))  # avoid /0
    ratio = n / p
    ai_count = sum(1 for j in now if _AI_ADJ_RE.search(j.title) or _AI_ADJ_RE.search(j.department or ""))
    ai_frac = (ai_count / n) if n else 0.0
    qualifies = n >= 5 and ratio >= 2.0
    # Confidence — data present on both windows + reasonable absolute volume.
    conf = 0.0
    if now:
        conf += 0.45
    if prior:
        conf += 0.25
    if n >= 10:
        conf += 0.15
    if n >= 5:
        conf += 0.08
    conf = min(conf, 0.95)
    return VelocityReport(
        open_roles_now=n,
        open_roles_60d_ago=len(prior),
        ratio=round(ratio, 2),
        ai_adjacent_fraction=round(ai_frac, 2),
        qualifies_for_aggressive_hiring_claim=qualifies,
        confidence=round(conf, 2),
    )
