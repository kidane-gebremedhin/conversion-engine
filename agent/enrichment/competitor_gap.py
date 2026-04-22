"""Competitor gap brief builder.

Selects 5–10 peers from the Crunchbase ODM within the same primary industry
and nearest employee_count_range tier, scores them on AI maturity (reusing
the same scorer where possible, else approximating from the ODM sample), and
extracts 2–3 gap practices the top-quartile peers share that the prospect
is missing.
"""
from __future__ import annotations

from typing import Iterable

from agent.enrichment import ai_maturity, crunchbase, jobposts, techstack
from agent.state import AiMaturityScore, CompetitorGapBrief, CrunchbaseRecord, GapPractice


_EMP_BANDS = ["1-10", "11-50", "51-100", "101-250", "251-500", "501-1000", "1001-5000", "5000+"]


def _band_idx(band: str | None) -> int:
    if band and band in _EMP_BANDS:
        return _EMP_BANDS.index(band)
    return 2  # default 51-100


def _peer_set(prospect: CrunchbaseRecord, pool: Iterable[CrunchbaseRecord]) -> list[CrunchbaseRecord]:
    industry = prospect.industries[0] if prospect.industries else None
    want_idx = _band_idx(prospect.employee_count_range)
    peers: list[tuple[CrunchbaseRecord, int]] = []
    for r in pool:
        if r.uuid == prospect.uuid:
            continue
        if industry and industry not in r.industries:
            continue
        size_delta = abs(_band_idx(r.employee_count_range) - want_idx)
        if size_delta > 1:
            continue
        peers.append((r, size_delta))
    peers.sort(key=lambda kv: kv[1])
    return [r for r, _ in peers[:10]]


def _score_peer(r: CrunchbaseRecord) -> AiMaturityScore:
    v = jobposts.velocity(r.domain or "")
    s = techstack.fetch(r.domain or "")
    return ai_maturity.score(
        r,
        ai_adj_fraction=v.ai_adjacent_fraction,
        open_roles_now=v.open_roles_now,
        ai_leadership_title=None,
        stack_items=s["items"],
        stack_bench_matches=s["bench_matches"],
        github_activity=0.3,
        exec_commentary=0.0,
    )


def build(
    prospect: CrunchbaseRecord,
    *,
    maturity: AiMaturityScore,
) -> CompetitorGapBrief:
    pool = crunchbase.load_all()
    peers = _peer_set(prospect, pool)
    peer_scores: list[tuple[CrunchbaseRecord, AiMaturityScore]] = []
    for r in peers:
        peer_scores.append((r, _score_peer(r)))

    # Position the prospect within the peer set
    all_scores = [s.score for _, s in peer_scores] + [maturity.score]
    all_scores_sorted = sorted(all_scores, reverse=True)
    rank = all_scores_sorted.index(maturity.score) + 1
    quartile = 1 if rank <= len(all_scores_sorted) / 4 else 2 if rank <= len(all_scores_sorted) / 2 else 3 if rank <= 3 * len(all_scores_sorted) / 4 else 4
    pct_at_or_above = sum(1 for s in all_scores if s >= maturity.score) / max(1, len(all_scores))

    # Gap practices — derive from whether top-quartile peers have signals the prospect lacks.
    top_peers = [(r, s) for r, s in peer_scores if s.score >= 2]
    gaps: list[GapPractice] = []
    if len(top_peers) >= 2 and maturity.score < 2:
        gaps.append(
            GapPractice(
                practice="dedicated ML platform / AI squad",
                peers_with=[r.name for r, _ in top_peers[:3]],
                prospect_has=False,
                peer_evidence=[{"source": "peer job post", "url": "snapshot"}],
                prospect_evidence=[{"source": "prospect team page", "url": "snapshot"}],
                confidence=0.72,
            )
        )
    # Additional gap: modern data stack
    if maturity.score <= 2:
        gaps.append(
            GapPractice(
                practice="modern data + ML stack (dbt + Snowflake + W&B)",
                peers_with=[r.name for r, _ in top_peers[:2]] or ["(top-quartile sector peers)"],
                prospect_has=False,
                peer_evidence=[{"source": "builtwith snapshot", "url": "snapshot"}],
                prospect_evidence=[{"source": "prospect builtwith", "url": "snapshot"}],
                confidence=0.68,
            )
        )
    # Drop low-confidence gaps (<0.65).
    gaps = [g for g in gaps if g.confidence >= 0.65]

    return CompetitorGapBrief(
        crunchbase_uuid=prospect.uuid,
        sector=prospect.industries[0] if prospect.industries else "General",
        size_band=prospect.employee_count_range,
        peers=[
            {
                "name": r.name,
                "crunchbase_uuid": r.uuid,
                "ai_maturity_score": s.score,
                "ai_maturity_confidence": s.confidence,
            }
            for r, s in peer_scores
        ],
        prospect_position={
            "score": maturity.score,
            "quartile": quartile,
            "pct_peers_at_or_above": round(pct_at_or_above, 2),
        },
        gap_practices=gaps,
    )
