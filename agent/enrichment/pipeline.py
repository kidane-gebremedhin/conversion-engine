"""Enrichment pipeline orchestrator — emits the three JSON artifacts.

Outputs to `data/briefs_cache/<crunchbase_uuid>/`:
  - hiring_signal_brief.json
  - ai_maturity_score.json
  - competitor_gap_brief.json

Also emits `icp_classification.json` via the classifier (kept in this module
so the artifact bundle per prospect is one-shot).
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from agent import tracing
from agent.enrichment import (
    ai_maturity as ai_maturity_mod,
    competitor_gap,
    crunchbase,
    jobposts,
    layoffs,
    leadership,
    techstack,
)
from agent.state import (
    AiMaturityScore,
    CompetitorGapBrief,
    CrunchbaseRecord,
    HiringSignalBrief,
    IcpClassification,
)


_CACHE = pathlib.Path("data/briefs_cache")
_TTL_SECONDS = 24 * 3600


@dataclass
class EnrichmentResult:
    brief: HiringSignalBrief
    maturity: AiMaturityScore
    gap: CompetitorGapBrief
    icp: IcpClassification


def enrich(crunchbase_uuid: str, *, force: bool = False, today: date | None = None) -> EnrichmentResult:
    from agent.icp.classifier import classify

    cache_dir = _CACHE / crunchbase_uuid
    if not force and _cache_fresh(cache_dir):
        with tracing.span("enrich.cache_hit", crunchbase_uuid=crunchbase_uuid):
            return _from_cache(cache_dir)

    with tracing.span("enrich.full", crunchbase_uuid=crunchbase_uuid):
        record = crunchbase.by_uuid(crunchbase_uuid)
        if record is None:
            raise KeyError(f"crunchbase_uuid not found: {crunchbase_uuid}")

        today = today or date.today()

        with tracing.span("enrich.funding"):
            funding_events = crunchbase.funding_events(crunchbase_uuid, today=today)
        with tracing.span("enrich.jobposts"):
            velocity = jobposts.velocity(record.domain or "")
        with tracing.span("enrich.layoffs"):
            layoff_events = layoffs.find_by_company(record.name, today=today)
        with tracing.span("enrich.leadership"):
            lead = leadership.detect(crunchbase_uuid, today=today)
        with tracing.span("enrich.techstack"):
            stack = techstack.fetch(record.domain or "")
        with tracing.span("enrich.ai_maturity"):
            maturity = ai_maturity_mod.score(
                record,
                ai_adj_fraction=velocity.ai_adjacent_fraction,
                open_roles_now=velocity.open_roles_now,
                ai_leadership_title=(lead.role if lead and "AI" in lead.role else None),
                stack_items=stack["items"],
                stack_bench_matches=stack["bench_matches"],
                github_activity=0.3,
                exec_commentary=0.0,
            )
        with tracing.span("enrich.competitor_gap"):
            gap = competitor_gap.build(record, maturity=maturity)

        brief = _build_brief(
            record,
            funding_events=funding_events,
            velocity=velocity,
            layoff_events=layoff_events,
            leadership_change=lead,
            stack=stack,
            today=today,
        )
        icp = classify(brief, maturity=maturity)

        _write_cache(cache_dir, brief=brief, maturity=maturity, gap=gap, icp=icp)

        return EnrichmentResult(brief=brief, maturity=maturity, gap=gap, icp=icp)


# --------------------------------------------------------------------------- #

def _build_brief(
    record: CrunchbaseRecord,
    *,
    funding_events,
    velocity,
    layoff_events,
    leadership_change,
    stack,
    today: date,
) -> HiringSignalBrief:
    funding_block: dict[str, Any] = {"confidence": 0.0, "evidence": []}
    if funding_events:
        f = funding_events[0]
        funding_block = {
            "latest_round": f.round_type,
            "amount_usd": f.amount_usd,
            "date": f.announced_on.isoformat(),
            "recency_days": (today - f.announced_on).days,
            "confidence": 0.9,
            "evidence": [{"source": "crunchbase", "url": f.source_url or ""}],
        }

    layoff_block: dict[str, Any]
    if layoff_events:
        ly = layoff_events[0]
        layoff_block = {
            "detected": True,
            "date": ly.date.isoformat(),
            "headcount": ly.headcount,
            "percentage": ly.percentage,
            "recency_days": (today - ly.date).days,
            "confidence": 0.85,
            "evidence": [{"source": "layoffs.fyi", "url": ly.source_url or ""}],
        }
    else:
        layoff_block = {"detected": False, "confidence": 0.9, "evidence": []}

    leadership_block: dict[str, Any]
    if leadership_change:
        leadership_block = {
            "detected": True,
            "role": leadership_change.role,
            "name": leadership_change.name,
            "recency_days": (today - leadership_change.start_date).days,
            "confidence": 0.8,
            "evidence": [{"source": "press", "url": leadership_change.source_url or ""}],
        }
    else:
        leadership_block = {"detected": False, "confidence": 0.7, "evidence": []}

    return HiringSignalBrief(
        crunchbase_uuid=record.uuid,
        company={
            "name": record.name,
            "domain": record.domain,
            "country": record.country,
            "industries": record.industries,
            "employee_count_range": record.employee_count_range,
            "founded": record.founded_on.year if record.founded_on else None,
        },
        signals={
            "funding": funding_block,
            "job_post_velocity": velocity.model_dump(),
            "layoff": layoff_block,
            "leadership_change": leadership_block,
            "tech_stack": stack,
        },
    )


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def _cache_fresh(cache_dir: pathlib.Path) -> bool:
    mark = cache_dir / "hiring_signal_brief.json"
    if not mark.exists():
        return False
    return (time.time() - mark.stat().st_mtime) < _TTL_SECONDS


def _write_cache(
    cache_dir: pathlib.Path,
    *,
    brief: HiringSignalBrief,
    maturity: AiMaturityScore,
    gap: CompetitorGapBrief,
    icp: IcpClassification,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "hiring_signal_brief.json").write_text(brief.model_dump_json(indent=2))
    (cache_dir / "ai_maturity_score.json").write_text(maturity.model_dump_json(indent=2))
    (cache_dir / "competitor_gap_brief.json").write_text(gap.model_dump_json(indent=2))
    (cache_dir / "icp_classification.json").write_text(icp.model_dump_json(indent=2))


def _from_cache(cache_dir: pathlib.Path) -> EnrichmentResult:
    brief = HiringSignalBrief.model_validate_json((cache_dir / "hiring_signal_brief.json").read_text())
    maturity = AiMaturityScore.model_validate_json((cache_dir / "ai_maturity_score.json").read_text())
    gap = CompetitorGapBrief.model_validate_json((cache_dir / "competitor_gap_brief.json").read_text())
    icp = IcpClassification.model_validate_json((cache_dir / "icp_classification.json").read_text())
    return EnrichmentResult(brief=brief, maturity=maturity, gap=gap, icp=icp)
