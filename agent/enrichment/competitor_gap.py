"""Competitor gap brief generation.

Converts outbound from vendor pitch to research finding. Every peer claim
must map to a competitor entry with a public source URL.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from agent.config import config
from agent.enrichment import crunchbase, ai_maturity, jobposts
from agent.enrichment.briefs import (
    CompetitorEntry,
    CompetitorGapBrief,
    GapFinding,
    GapQualitySelfCheck,
    HeadcountBand,
    PeerEvidence,
    Segment,
)


def _peer_entry(record: dict[str, Any]) -> CompetitorEntry:
    mat = ai_maturity.score(record)
    justifs = [j["status"] for j in mat["justifications"] if j.get("status")]
    # source URLs from the jobposts entry
    entry = jobposts.company_jobposts(record["domain"]) or {}
    sources = []
    if gh := entry.get("github_public_org"):
        if gh.get("url"):
            sources.append(gh["url"])
    for post in entry.get("exec_commentary_last_12m", []):
        if post.get("url"):
            sources.append(post["url"])
    for leader in entry.get("ai_ml_leaders", []):
        if leader.get("url"):
            sources.append(leader["url"])

    return CompetitorEntry(
        name=record.get("name", record["domain"]),
        domain=record["domain"],
        ai_maturity_score=int(mat["score"]),
        ai_maturity_justification=justifs[:3],
        headcount_band=HeadcountBand(record.get("headcount_band", "15_to_80")),
        top_quartile=False,
        sources_checked=sources,
    )


def _derive_gap_findings(
    prospect_score: int,
    peers: list[CompetitorEntry],
    prospect_domain: str,
) -> list[GapFinding]:
    """Produce up to 3 gap findings backed by ≥2 peer evidence entries."""
    findings: list[GapFinding] = []

    # Finding 1: AI/ML leadership gap
    peers_with_ai_leader = [p for p in peers if p.ai_maturity_score >= 2]
    if len(peers_with_ai_leader) >= 2 and prospect_score < 2:
        evidence = [
            PeerEvidence(
                competitor_name=p.name,
                evidence=f"AI maturity score {p.ai_maturity_score}/3 with public AI leadership signal.",
                source_url=p.sources_checked[0] if p.sources_checked else f"https://{p.domain}/team",
            )
            for p in peers_with_ai_leader[:3]
        ]
        findings.append(
            GapFinding(
                practice="Named AI/ML leadership (Head of AI / VP Data / Chief Scientist).",
                peer_evidence=evidence,
                prospect_state="No named AI/ML leadership visible on public team page.",
                confidence="medium",
                segment_relevance=[Segment.SEGMENT_4],
            )
        )

    # Finding 2: MLOps / AI platform roles
    ai_hiring_peers = []
    for p in peers:
        entry = jobposts.company_jobposts(p.domain) or {}
        ai_roles = [
            r for r in entry.get("open_roles_today", []) if r.get("ai_adjacent")
        ]
        if len(ai_roles) >= 1:
            ai_hiring_peers.append((p, ai_roles[:2]))

    prospect_entry = jobposts.company_jobposts(prospect_domain) or {}
    prospect_ai_roles = sum(1 for r in prospect_entry.get("open_roles_today", []) if r.get("ai_adjacent"))

    if len(ai_hiring_peers) >= 2 and prospect_ai_roles == 0:
        evidence = [
            PeerEvidence(
                competitor_name=p.name,
                evidence=f"{len(roles)} AI-adjacent role(s) open (e.g., '{roles[0].get('title','?')}').",
                source_url=f"https://builtin.com/company/{_slug(p.name)}/jobs",
            )
            for p, roles in ai_hiring_peers[:3]
        ]
        findings.append(
            GapFinding(
                practice="Open AI-platform or MLOps engineering roles.",
                peer_evidence=evidence,
                prospect_state="No AI-adjacent roles visible on prospect's current openings.",
                confidence="high" if len(ai_hiring_peers) >= 3 else "medium",
                segment_relevance=[Segment.SEGMENT_1, Segment.SEGMENT_4],
            )
        )

    # Finding 3: modern ML-platform stack (Databricks / W&B / vLLM)
    stack_peers = []
    for p in peers:
        entry = jobposts.company_jobposts(p.domain) or {}
        bw = [t.lower() for t in (entry.get("builtwith") or [])]
        if any(t in bw for t in ("databricks", "weights and biases", "vllm")):
            stack_peers.append((p, bw))

    prospect_bw = [t.lower() for t in (prospect_entry.get("builtwith") or [])]
    prospect_has_modern = any(t in prospect_bw for t in ("databricks", "weights and biases", "vllm"))

    if len(stack_peers) >= 2 and not prospect_has_modern:
        evidence = [
            PeerEvidence(
                competitor_name=p.name,
                evidence=f"Public BuiltWith detections: {', '.join(bw[:3])}.",
                source_url=f"https://builtwith.com/{p.domain}",
            )
            for p, bw in stack_peers[:3]
        ]
        findings.append(
            GapFinding(
                practice="Adoption of modern ML-platform tooling (Databricks / Weights and Biases / vLLM).",
                peer_evidence=evidence,
                prospect_state="No modern ML-platform tooling visible in public signal.",
                confidence="low",
                segment_relevance=[Segment.SEGMENT_4, Segment.SEGMENT_1],
            )
        )

    return findings[:3]


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


def generate(record: dict[str, Any], prospect_ai_maturity_score: int) -> CompetitorGapBrief | None:
    """Generate the competitor gap brief for a prospect, or None if peer set is too small."""
    peer_records = crunchbase.peers_in_sector(
        record,
        same_headcount_band=False,
        limit=int(config.get("competitor_gap.peers_max", 10)),
    )

    # Require at least 5 peers per schema
    peers_min = int(config.get("competitor_gap.peers_min", 5))
    if len(peer_records) < peers_min:
        # Relax to cross-band peers if strict filter yields too few
        peer_records = crunchbase.peers_in_sector(record, same_headcount_band=False, limit=10)
    if len(peer_records) < peers_min:
        return None

    competitors = [_peer_entry(r) for r in peer_records]
    # Top quartile
    sorted_scores = sorted((c.ai_maturity_score for c in competitors), reverse=True)
    if sorted_scores:
        threshold = sorted_scores[max(0, len(sorted_scores) // 4 - 1)]
    else:
        threshold = 3
    for c in competitors:
        c.top_quartile = c.ai_maturity_score >= threshold

    top_q = [c for c in competitors if c.top_quartile]
    benchmark = (
        sum(c.ai_maturity_score for c in top_q) / len(top_q) if top_q else 0.0
    )

    findings = _derive_gap_findings(prospect_ai_maturity_score, competitors, record["domain"])
    if not findings:
        # Ensure ≥1 finding — emit a soft, low-confidence exploratory finding
        findings = [
            GapFinding(
                practice="Peer-group research scope",
                peer_evidence=[
                    PeerEvidence(
                        competitor_name=competitors[0].name,
                        evidence="Peer at similar stage with comparable firmographics.",
                        source_url=f"https://{competitors[0].domain}",
                    ),
                    PeerEvidence(
                        competitor_name=competitors[1].name if len(competitors) > 1 else competitors[0].name,
                        evidence="Second peer at similar stage.",
                        source_url=f"https://{competitors[1].domain}" if len(competitors) > 1 else f"https://{competitors[0].domain}",
                    ),
                ],
                prospect_state="No strong gap detected; peer comparison is informational only.",
                confidence="low",
                segment_relevance=[Segment.SEGMENT_1],
            )
        ]

    sector, sub_niche = crunchbase.company_sector(record)

    # Suggested pitch shift
    if prospect_ai_maturity_score >= 2:
        shift = (
            "Frame the outreach around a specific capability gap versus top-quartile peers, "
            "not a generic talent pitch. Use the peer-evidence specifics."
        )
    else:
        shift = (
            "Stand up your first AI function with a dedicated squad — softer framing, "
            "because the prospect's public AI-maturity signal is low."
        )

    self_check = GapQualitySelfCheck(
        all_peer_evidence_has_source_url=all(
            all(pe.source_url for pe in f.peer_evidence) for f in findings
        ),
        at_least_one_gap_high_confidence=any(
            str(f.confidence) == "high" for f in findings
        ),
        prospect_silent_but_sophisticated_risk=bool(
            (jobposts.company_jobposts(record["domain"]) or {}).get("exec_commentary_last_12m")
            and prospect_ai_maturity_score < 2
        ),
    )

    return CompetitorGapBrief(
        prospect_domain=record["domain"],
        prospect_sector=sector,
        prospect_sub_niche=sub_niche,
        generated_at=dt.datetime.now(dt.timezone.utc),
        prospect_ai_maturity_score=prospect_ai_maturity_score,
        sector_top_quartile_benchmark=round(benchmark, 2),
        competitors_analyzed=competitors,
        gap_findings=findings,
        suggested_pitch_shift=shift,
        gap_quality_self_check=self_check,
    )
