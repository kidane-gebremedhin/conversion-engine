"""Enrichment pipeline DAG — composes firmographics → signals → briefs.

One entry point: `enrich(domain)` → (HiringSignalBrief, CompetitorGapBrief|None).
Each adapter appends a DataSourceCheck to the brief's audit trail so the
evidence graph in the memo can trace every claim to a source.

See __specs/05-signal-enrichment-pipeline.md.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from agent.config import REPO_ROOT, config
from agent.enrichment import (
    ai_maturity,
    bench,
    competitor_gap,
    crunchbase,
    jobposts,
    layoffs,
    leadership,
    tech_stack,
)
from agent.enrichment.briefs import (
    AiMaturity,
    AiMaturityJustification,
    AiSignal,
    BenchToBriefMatch,
    BuyingWindowSignals,
    CompetitorGapBrief,
    Confidence,
    DataSourceCheck,
    FundingEvent,
    FundingStage,
    HiringSignalBrief,
    HiringVelocity,
    HonestyFlag,
    LayoffEvent,
    LeadershipChange,
    LeadershipRole,
    Segment,
    SourceStatus,
    VelocityLabel,
    Weight,
)
from agent.observability.langfuse import span, new_trace


class EnrichmentError(RuntimeError):
    """Raised when a domain is not in the Crunchbase allowlist."""


def enrich(
    domain: str,
    *,
    write_to: str | Path | None = None,
) -> tuple[HiringSignalBrief, CompetitorGapBrief | None]:
    """Run the full enrichment DAG for one prospect domain.

    If `write_to` is set, writes the briefs to
    `<write_to>/hiring_signal_brief.json` and `<write_to>/competitor_gap_brief.json`.
    """
    trace = new_trace(name="enrichment.run", attributes={"prospect.domain": domain})

    # ──────────────────────────────────────────────────────────────────────
    # Stage 1: firmographics (Crunchbase)
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.crunchbase_lookup", trace=trace) as s:
        record = crunchbase.lookup_by_domain(domain)
        s["present"] = bool(record)
    if not record:
        raise EnrichmentError(
            f"No Crunchbase record for domain {domain!r}. "
            "The pipeline refuses to outreach a domain without a firmographic anchor."
        )

    source_checks: list[DataSourceCheck] = [
        DataSourceCheck(
            source="crunchbase_odm",
            status=SourceStatus.SUCCESS,
            fetched_at=dt.datetime.now(dt.timezone.utc),
        )
    ]

    # ──────────────────────────────────────────────────────────────────────
    # Stage 2: hiring velocity (job posts)
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.jobposts", trace=trace) as s:
        today_count, ago_count = jobposts.open_roles_counts(domain)
        label, conf = jobposts.velocity_label_from_counts(today_count, ago_count)
        sources = jobposts.sources_used(domain)
        s["open_today"] = today_count
        s["open_60d_ago"] = ago_count
        s["label"] = label
    velocity = HiringVelocity(
        open_roles_today=today_count,
        open_roles_60_days_ago=ago_count,
        velocity_label=VelocityLabel(label),
        signal_confidence=conf,
        sources=sources,
    )
    source_checks.append(DataSourceCheck(
        source="job_posts_snapshot",
        status=SourceStatus.SUCCESS if today_count or ago_count else SourceStatus.NO_DATA,
        fetched_at=jobposts.last_fetched_at(),
    ))

    # ──────────────────────────────────────────────────────────────────────
    # Stage 3: layoffs
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.layoffs", trace=trace) as s:
        layoff = layoffs.within_window(record.get("name", ""), window_days=int(config.get("layoffs.window_days", 3650)))
        s["detected"] = bool(layoff)
    layoff_event = LayoffEvent(
        detected=bool(layoff),
        date=layoff["date"] if layoff else None,  # type: ignore[index]
        headcount_reduction=int(layoff["headcount_reduction"]) if layoff else None,  # type: ignore[index]
        percentage_cut=float(layoff["percentage_cut"]) if layoff else None,  # type: ignore[index]
        source_url=str(layoff["source_url"]) if layoff else None,  # type: ignore[index]
    )
    source_checks.append(DataSourceCheck(
        source="layoffs_fyi",
        status=SourceStatus.SUCCESS if layoff else SourceStatus.NO_DATA,
        fetched_at=dt.datetime.now(dt.timezone.utc),
    ))

    # ──────────────────────────────────────────────────────────────────────
    # Stage 4: leadership
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.leadership", trace=trace) as s:
        lead = leadership.detect(record)
        s["detected"] = bool(lead)
    leadership_change = LeadershipChange(
        detected=bool(lead),
        role=LeadershipRole(lead["role"]) if lead else None,
        new_leader_name=lead["new_leader_name"] if lead else None,
        started_at=lead["started_at"] if lead else None,
        source_url=lead["source_url"] if lead else None,
    )

    # ──────────────────────────────────────────────────────────────────────
    # Stage 5: AI-maturity scoring
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.ai_maturity", trace=trace) as s:
        mat = ai_maturity.score(record)
        s["score"] = mat["score"]
    justs: list[AiMaturityJustification] = []
    for j in mat["justifications"]:
        try:
            sig = AiSignal(j["signal"])
        except ValueError:
            continue
        try:
            w = Weight(j["weight"])
        except ValueError:
            w = Weight.LOW
        try:
            c = Confidence(j["confidence"])
        except ValueError:
            c = Confidence.LOW
        justs.append(AiMaturityJustification(
            signal=sig, status=j["status"], weight=w, confidence=c,
            source_url=j.get("source_url"),
        ))
    ai = AiMaturity(
        score=int(mat["score"]),
        confidence=float(mat["confidence"]),
        justifications=justs,
    )

    # ──────────────────────────────────────────────────────────────────────
    # Stage 6: tech stack + bench match
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.tech_stack", trace=trace) as s:
        tokens, stacks, inferred_not_confirmed = tech_stack.infer_stacks(record)
        s["stacks"] = stacks
    bench_match_d = bench.match(stacks)
    bench_match = BenchToBriefMatch(
        required_stacks=bench_match_d["required_stacks"],
        bench_available=bench_match_d["bench_available"],
        gaps=bench_match_d["gaps"],
    )

    # ──────────────────────────────────────────────────────────────────────
    # Stage 7: funding event
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.funding", trace=trace) as s:
        funding = crunchbase.recent_funding_event(record, window_days=int(config.get("funding.window_days", 3650)))
        s["detected"] = bool(funding)
    funding_event = FundingEvent(
        detected=bool(funding),
        stage=FundingStage(funding["stage"]) if funding else None,
        amount_usd=int(funding["amount_usd"]) if funding else None,
        closed_at=dt.date.fromisoformat(funding["closed_at"]) if funding else None,
        source_url=funding["source_url"] if funding else None,
    )

    # ──────────────────────────────────────────────────────────────────────
    # Stage 8: preliminary segment label (refined by classifier)
    # ──────────────────────────────────────────────────────────────────────
    buying = BuyingWindowSignals(
        funding_event=funding_event,
        layoff_event=layoff_event,
        leadership_change=leadership_change,
    )

    preliminary = HiringSignalBrief(
        prospect_domain=domain,
        prospect_name=record.get("name", domain),
        generated_at=dt.datetime.now(dt.timezone.utc),
        primary_segment_match=Segment.ABSTAIN,
        segment_confidence=0.0,
        ai_maturity=ai,
        hiring_velocity=velocity,
        buying_window_signals=buying,
        tech_stack=tokens,
        bench_to_brief_match=bench_match,
        data_sources_checked=source_checks,
        honesty_flags=[],
    )

    # Run the ICP classifier
    from agent.classifier import classify
    with span("enrichment.classify", trace=trace) as s:
        # mode='json' coerces enum values to their underlying strings; the
        # classifier does case-insensitive string comparison against config.
        result = classify(preliminary.model_dump(mode="json"))
        s["segment"] = result.segment
        s["confidence"] = result.confidence
    preliminary.primary_segment_match = Segment(result.segment) if result.segment != "abstain" else Segment.ABSTAIN
    preliminary.segment_confidence = result.confidence

    # ──────────────────────────────────────────────────────────────────────
    # Stage 9: honesty flags
    # ──────────────────────────────────────────────────────────────────────
    flags: list[HonestyFlag] = []
    if velocity.velocity_label.value == "insufficient_signal" or velocity.signal_confidence < 0.4:
        flags.append(HonestyFlag.WEAK_HIRING_VELOCITY_SIGNAL)
    if ai.confidence < 0.5:
        flags.append(HonestyFlag.WEAK_AI_MATURITY_SIGNAL)
    if layoff_event.detected and funding_event.detected:
        flags.append(HonestyFlag.LAYOFF_OVERRIDES_FUNDING)
    if bench_match.gaps:
        flags.append(HonestyFlag.BENCH_GAP_DETECTED)
    if inferred_not_confirmed:
        flags.append(HonestyFlag.TECH_STACK_INFERRED_NOT_CONFIRMED)
    if result.disqualifiers_hit:
        flags.append(HonestyFlag.CONFLICTING_SEGMENT_SIGNALS)
    preliminary.honesty_flags = flags

    # ──────────────────────────────────────────────────────────────────────
    # Stage 10: competitor-gap brief (only for Segment 4 or high AI maturity)
    # ──────────────────────────────────────────────────────────────────────
    with span("enrichment.competitor_gap", trace=trace) as s:
        gap_brief: CompetitorGapBrief | None = None
        if ai.score >= 2 or result.segment == "segment_4_specialized_capability":
            gap_brief = competitor_gap.generate(record, ai.score)
        s["generated"] = bool(gap_brief)

    # ──────────────────────────────────────────────────────────────────────
    # Stage 11: write
    # ──────────────────────────────────────────────────────────────────────
    if write_to is not None:
        _write_briefs(preliminary, gap_brief, write_to)

    return preliminary, gap_brief


def _write_briefs(
    hiring: HiringSignalBrief,
    gap: CompetitorGapBrief | None,
    target: str | Path,
) -> None:
    target = Path(target)
    if not target.is_absolute():
        target = REPO_ROOT / target
    target.mkdir(parents=True, exist_ok=True)
    (target / "hiring_signal_brief.json").write_text(
        hiring.model_dump_json(indent=2, exclude_none=True), encoding="utf-8"
    )
    if gap:
        (target / "competitor_gap_brief.json").write_text(
            gap.model_dump_json(indent=2, exclude_none=True), encoding="utf-8"
        )
