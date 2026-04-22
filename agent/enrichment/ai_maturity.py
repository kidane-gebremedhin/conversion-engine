"""AI-maturity scorer (0–3) with per-signal justification.

Deterministic, signal-weighted — see __specs/05 §5 for weights. The optional
LLM call is used only for the justification paragraph, via the dev-tier model
(cheap); we skip it here and produce structured justifications from the inputs.
"""
from __future__ import annotations

from statistics import pstdev

from agent.state import AiMaturityJustification, AiMaturityScore, CrunchbaseRecord


_WEIGHTS = {
    "ai_adjacent_open_roles": 1.0,
    "named_ai_leadership": 1.0,
    "github_activity": 0.6,
    "executive_ai_commentary": 0.6,
    "modern_data_ml_stack": 0.3,
    "strategic_communications": 0.3,
}
_NORM = sum(_WEIGHTS.values())  # 3.8


def score(
    record: CrunchbaseRecord,
    *,
    ai_adj_fraction: float,
    open_roles_now: int,
    ai_leadership_title: str | None,
    stack_items: list[str],
    stack_bench_matches: list[str],
    github_activity: float = 0.0,
    exec_commentary: float = 0.0,
) -> AiMaturityScore:
    contrib: dict[str, float] = {}
    evidence: dict[str, str] = {}

    # 1. AI-adjacent open roles
    adj = min(1.0, ai_adj_fraction * 1.5 + (0.2 if open_roles_now >= 8 else 0.0))
    contrib["ai_adjacent_open_roles"] = adj
    evidence["ai_adjacent_open_roles"] = (
        f"{int(ai_adj_fraction * open_roles_now)} of {open_roles_now} open roles are AI-adjacent "
        f"({int(ai_adj_fraction * 100)}%)"
    )

    # 2. Named AI leadership
    if ai_leadership_title:
        contrib["named_ai_leadership"] = 0.95
        evidence["named_ai_leadership"] = f"public role: {ai_leadership_title}"
    else:
        contrib["named_ai_leadership"] = 0.0
        evidence["named_ai_leadership"] = "no public AI leadership role detected"

    # 3. GitHub activity
    contrib["github_activity"] = github_activity
    evidence["github_activity"] = (
        "active public AI/ML repos" if github_activity > 0.5 else "no public AI repos found"
    )

    # 4. Executive commentary
    contrib["executive_ai_commentary"] = exec_commentary
    evidence["executive_ai_commentary"] = (
        "recent executive AI commentary in public press" if exec_commentary > 0.5 else "no recent AI commentary"
    )

    # 5. Modern data/ml stack
    stack_hit = min(1.0, 0.25 * len({m for m in stack_bench_matches if m in ("data", "ml")}) + 0.05 * len(stack_items))
    contrib["modern_data_ml_stack"] = stack_hit
    evidence["modern_data_ml_stack"] = (
        f"stack items include: {', '.join(stack_items[:3])}" if stack_items else "no public stack signal"
    )

    # 6. Strategic communications — skip, rarely available
    contrib["strategic_communications"] = 0.0
    evidence["strategic_communications"] = "not evaluated in interim"

    # raw = Σ (weight_i × evidence_strength_i)
    weighted = {k: _WEIGHTS[k] * v for k, v in contrib.items()}
    raw = sum(weighted.values())
    max_possible = _NORM
    # Score: map raw/max onto 0..3
    score_int = max(0, min(3, round((raw / max_possible) * 3)))

    # Confidence: 1 - stdev(weighted)/max_possible — shrinks when signals disagree strongly.
    if len(weighted) >= 2:
        conf = 1 - (pstdev(list(weighted.values())) / max_possible)
    else:
        conf = 0.5
    conf = max(0.2, min(0.95, conf))

    band = "low" if conf < 0.5 else "medium" if conf < 0.75 else "high"

    justification = [
        AiMaturityJustification(
            signal=k,
            weight=("high" if _WEIGHTS[k] >= 1.0 else "medium" if _WEIGHTS[k] >= 0.6 else "low"),
            evidence=evidence[k],
            contribution=round(contrib[k], 2),
            caveat=None if contrib[k] > 0 else "absence of public signal is not absence of activity",
        )
        for k in _WEIGHTS
    ]

    return AiMaturityScore(
        crunchbase_uuid=record.uuid,
        score=score_int,
        confidence=round(conf, 2),
        confidence_band=band,
        justification=justification,
    )
