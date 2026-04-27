"""Rule-based ICP classifier.

Ordered rules, first match wins. Abstention threshold 0.6 by default, read
from config.yaml > icp.abstain_threshold.

See __specs/03-icp-and-segments.md.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from agent.config import config


@dataclass
class ClassificationResult:
    segment: str              # e.g. "segment_1_series_a_b" | "abstain"
    confidence: float         # [0.0, 1.0]
    rule_fired: str           # which ordered rule matched
    filter_evidence: dict[str, Any] = field(default_factory=dict)
    disqualifiers_hit: list[str] = field(default_factory=list)


class SegmentMismatch(ValueError):
    """Raised when a composer tries to render Segment 4 for an AI-maturity <2 prospect."""


def _days_between(a: dt.date | None, b: dt.date) -> int | None:
    if a is None:
        return None
    return (b - a).days


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def classify(brief: dict[str, Any] | Any) -> ClassificationResult:
    """Classify a hiring-signal-brief-like dict into one of 4 segments + abstain.

    Accepts either a dict (e.g. `HiringSignalBrief.model_dump()`) or the
    Pydantic model directly.
    """
    b = brief.model_dump() if hasattr(brief, "model_dump") else brief
    today = _today()

    funding = b.get("buying_window_signals", {}).get("funding_event") or {}
    layoff = b.get("buying_window_signals", {}).get("layoff_event") or {}
    leadership = b.get("buying_window_signals", {}).get("leadership_change") or {}
    ai = b.get("ai_maturity") or {}
    velocity = b.get("hiring_velocity") or {}
    honesty = b.get("honesty_flags") or []

    layoff_days = _days_between(_parse_date(layoff.get("date")), today)
    funding_days = _days_between(_parse_date(funding.get("closed_at")), today)
    leadership_days = _days_between(_parse_date(leadership.get("started_at")), today)

    s1 = config.get("icp.segment_1", {})
    s2 = config.get("icp.segment_2", {})
    s3 = config.get("icp.segment_3", {})
    s4 = config.get("icp.segment_4", {})
    abstain_threshold = float(config.get("icp.abstain_threshold", 0.6))

    def _as_dict(node: Any) -> dict[str, Any]:
        if hasattr(node, "as_dict"):
            return node.as_dict()
        return dict(node) if node else {}

    s1 = _as_dict(s1); s2 = _as_dict(s2); s3 = _as_dict(s3); s4 = _as_dict(s4)

    disqualifiers: list[str] = []

    # ──────────────────────────────────────────────────────────────────────
    # Ordered rules
    # ──────────────────────────────────────────────────────────────────────

    # Rule 1: layoff + funding → Segment 2
    layoff_recent = layoff.get("detected") and layoff_days is not None and layoff_days <= int(s2.get("layoff_window_days", 3650))
    funding_recent = funding.get("detected") and funding_days is not None and funding_days <= int(s1.get("funding_window_days", 3650))
    if layoff_recent and funding_recent:
        pct = layoff.get("percentage_cut") or 0.0
        if pct > float(s2.get("disqualifier_layoff_pct_max", 0.40)):
            disqualifiers.append("layoff_pct_too_high")
            # Fall through to abstain (no Segment 2 when layoff too deep)
        else:
            return ClassificationResult(
                segment="segment_2_mid_market_restructure",
                confidence=_confidence_segment_2(b, s2),
                rule_fired="rule_1_layoff_plus_funding",
                filter_evidence={"layoff_days": layoff_days, "funding_days": funding_days, "pct_cut": pct},
                disqualifiers_hit=disqualifiers,
            )

    # Rule 2: new CTO/VP Eng in last 90d → Segment 3
    if leadership.get("detected") and leadership_days is not None and leadership_days <= int(s3.get("leadership_change_window_days", 3650)):
        role = leadership.get("role")
        allowed_roles = s3.get("roles") or ["cto", "vp_engineering"]
        if role and str(role).lower() in [str(r).lower() for r in allowed_roles]:
            if _is_interim(leadership.get("new_leader_name") or ""):
                disqualifiers.append("interim_or_acting")
            else:
                return ClassificationResult(
                    segment="segment_3_leadership_transition",
                    confidence=_confidence_segment_3(b, s3),
                    rule_fired="rule_2_leadership_transition",
                    filter_evidence={"leadership_days": leadership_days, "role": role},
                    disqualifiers_hit=disqualifiers,
                )

    # Rule 3: specialized-capability + AI-maturity ≥ 2 → Segment 4
    score = int(ai.get("score", 0))
    ai_min = int(s4.get("ai_maturity_min_required", 2))
    min_days_open = int(s4.get("specialist_req_min_days_open", 60))
    tech_stack = b.get("tech_stack") or []
    required_stacks = b.get("bench_to_brief_match", {}).get("required_stacks", [])
    stalled = any(_stuck_stacks(required_stacks)) if required_stacks else False
    if score >= ai_min and (stalled or _stale_velocity(velocity, min_days_open)):
        return ClassificationResult(
            segment="segment_4_specialized_capability",
            confidence=_confidence_segment_4(b, s4),
            rule_fired="rule_3_specialized_capability",
            filter_evidence={"ai_score": score, "stalled_role": stalled},
            disqualifiers_hit=disqualifiers,
        )

    # Rule 4: fresh funding (no layoff, no leadership change) → Segment 1
    if funding_recent and not layoff_recent and not leadership.get("detected"):
        open_roles = int(velocity.get("open_roles_today", 0))
        min_open = int(s1.get("min_open_eng_roles", 5))
        if open_roles >= min_open:
            amt = funding.get("amount_usd") or 0
            if int(s1.get("funding_min_usd", 5_000_000)) <= amt <= int(s1.get("funding_max_usd", 30_000_000)):
                return ClassificationResult(
                    segment="segment_1_series_a_b",
                    confidence=_confidence_segment_1(b, s1),
                    rule_fired="rule_4_funding",
                    filter_evidence={"funding_days": funding_days, "open_roles": open_roles, "amount_usd": amt},
                    disqualifiers_hit=disqualifiers,
                )

    # Rule 5: abstain
    return ClassificationResult(
        segment="abstain",
        confidence=max(0.0, min(abstain_threshold - 0.05, 0.5)),
        rule_fired="rule_5_default_abstain",
        filter_evidence={},
        disqualifiers_hit=disqualifiers,
    )


# ────────────────────────────────────────────────────────────────────────────
# Confidence scoring (per-segment, weighted by filter fires)
# ────────────────────────────────────────────────────────────────────────────


def _score_filters(fires: list[tuple[str, bool, float]]) -> float:
    total_w = sum(w for _, _, w in fires) or 1.0
    met_w = sum(w for _, hit, w in fires if hit)
    return round(met_w / total_w, 3)


def _confidence_segment_1(b: dict[str, Any], s1: dict[str, Any]) -> float:
    funding = b.get("buying_window_signals", {}).get("funding_event", {})
    velocity = b.get("hiring_velocity", {})
    amt = funding.get("amount_usd") or 0
    fires = [
        ("funding_recent", bool(funding.get("detected")), 0.30),
        ("funding_amount_band", int(s1.get("funding_min_usd", 5_000_000)) <= amt <= int(s1.get("funding_max_usd", 30_000_000)), 0.25),
        ("open_roles_ok", int(velocity.get("open_roles_today", 0)) >= int(s1.get("min_open_eng_roles", 5)), 0.25),
        ("velocity_label_ok", str(velocity.get("velocity_label", "")) not in ("flat", "declined", "insufficient_signal"), 0.20),
    ]
    return _score_filters(fires)


def _confidence_segment_2(b: dict[str, Any], s2: dict[str, Any]) -> float:
    layoff = b.get("buying_window_signals", {}).get("layoff_event", {})
    velocity = b.get("hiring_velocity", {})
    fires = [
        ("layoff_detected", bool(layoff.get("detected")), 0.45),
        ("pct_under_ceiling", (layoff.get("percentage_cut") or 0.0) <= float(s2.get("disqualifier_layoff_pct_max", 0.40)), 0.25),
        ("roles_post_event", int(velocity.get("open_roles_today", 0)) >= int(s2.get("min_open_eng_roles_post_event", 3)), 0.30),
    ]
    return _score_filters(fires)


def _confidence_segment_3(b: dict[str, Any], s3: dict[str, Any]) -> float:
    leadership = b.get("buying_window_signals", {}).get("leadership_change", {})
    fires = [
        ("leadership_detected", bool(leadership.get("detected")), 0.50),
        ("role_in_allowed", str(leadership.get("role", "")).lower() in [r.lower() for r in (s3.get("roles") or [])], 0.30),
        ("not_interim", not _is_interim(leadership.get("new_leader_name") or ""), 0.20),
    ]
    return _score_filters(fires)


def _confidence_segment_4(b: dict[str, Any], s4: dict[str, Any]) -> float:
    ai = b.get("ai_maturity", {})
    gap = b.get("bench_to_brief_match", {})
    fires = [
        ("ai_score_ok", int(ai.get("score", 0)) >= int(s4.get("ai_maturity_min_required", 2)), 0.50),
        ("ai_confidence_ok", float(ai.get("confidence", 0.0)) >= 0.5, 0.25),
        ("stacks_identified", bool(gap.get("required_stacks")), 0.25),
    ]
    return _score_filters(fires)


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _parse_date(val: Any) -> dt.date | None:
    if val is None or val == "":
        return None
    if isinstance(val, dt.date) and not isinstance(val, dt.datetime):
        return val
    if isinstance(val, dt.datetime):
        return val.date()
    try:
        return dt.date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def _is_interim(name: str) -> bool:
    if not name:
        return False
    low = name.lower()
    return any(t in low for t in ("interim", "acting"))


def _stuck_stacks(stacks: list[str]) -> list[bool]:
    # Placeholder: the enrichment pipeline populates a richer stalled-role signal;
    # here we treat any declared required-stack as a mild positive signal.
    return [bool(s) for s in stacks]


def _stale_velocity(velocity: dict[str, Any], min_days_open: int) -> bool:
    """Rough stand-in: flat or declined velocity on a company with ≥ some
    openings is a proxy for 'specialist req open ≥N days'."""
    label = str(velocity.get("velocity_label", ""))
    return label in ("flat", "declined") and int(velocity.get("open_roles_today", 0)) > 0
