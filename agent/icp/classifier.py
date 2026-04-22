"""Rules-based ICP classifier with abstention.

See __specs/03-icp-and-segments.md. Four fixed segments. Outputs
`IcpClassification`; below threshold → mode=abstain + exploratory variant.
"""
from __future__ import annotations

import pathlib
from functools import lru_cache

import yaml

from agent.state import AiMaturityScore, HiringSignalBrief, IcpClassification

_SEGMENTS_PATH = pathlib.Path("agent/icp/segments.yaml")

# Defaults from config.example.yaml; callers can override via cfg.
_CONFIDENCE_THRESHOLD = 0.55
_MARGIN_THRESHOLD = 0.10
_SEGMENT_4_MATURITY_GATE = 2

_EMP_BANDS = {
    "1-10": 5, "11-50": 30, "51-100": 75, "101-250": 175,
    "251-500": 375, "501-1000": 750, "1001-5000": 3000, "5000+": 6000,
}


@lru_cache(maxsize=1)
def _segments() -> list[dict]:
    return yaml.safe_load(_SEGMENTS_PATH.read_text())["segments"]


def _headcount(band: str | None) -> int:
    return _EMP_BANDS.get(band or "", 0)


def _score_seg1(brief: HiringSignalBrief, maturity: AiMaturityScore) -> tuple[float, list[str]]:
    s = 0.0
    rat: list[str] = []
    f = brief.signals.get("funding", {}) or {}
    amt = f.get("amount_usd") or 0
    rec = f.get("recency_days")
    round_ = f.get("latest_round")
    if round_ in ("Series A", "Series B") and 5_000_000 <= amt <= 30_000_000 and rec is not None and rec <= 180:
        s += 0.45
        rat.append(f"{round_} ${amt/1e6:.1f}M {rec} d ago — +0.45 to seg 1")
    hc = _headcount(brief.company.get("employee_count_range"))
    if 15 <= hc <= 80:
        s += 0.20
        rat.append(f"headcount {hc} in 15–80 band — +0.20")
    v = brief.signals.get("job_post_velocity", {}) or {}
    if v.get("qualifies_for_aggressive_hiring_claim"):
        s += 0.15
        rat.append("aggressive hiring gate passes — +0.15")
    ly = brief.signals.get("layoff", {}) or {}
    if ly.get("detected") and (ly.get("recency_days") or 999) <= 120:
        s -= 0.30
        rat.append("recent layoff — penalty −0.30 (pushes toward seg 2)")
    return max(0.0, min(1.0, s)), rat


def _score_seg2(brief: HiringSignalBrief, maturity: AiMaturityScore) -> tuple[float, list[str]]:
    s = 0.0
    rat: list[str] = []
    hc = _headcount(brief.company.get("employee_count_range"))
    if 200 <= hc <= 2000:
        s += 0.15
        rat.append(f"headcount {hc} in 200–2000 — +0.15")
    ly = brief.signals.get("layoff", {}) or {}
    if ly.get("detected") and (ly.get("recency_days") or 999) <= 120:
        s += 0.40
        rat.append(f"layoff {ly.get('recency_days')} d ago — +0.40")
    # Prefer non-Series A/B stage as signal
    f = brief.signals.get("funding", {}) or {}
    if (f.get("latest_round") or "") not in ("Series A", "Series B"):
        s += 0.10
    return max(0.0, min(1.0, s)), rat


def _score_seg3(brief: HiringSignalBrief, maturity: AiMaturityScore) -> tuple[float, list[str]]:
    s = 0.0
    rat: list[str] = []
    lc = brief.signals.get("leadership_change", {}) or {}
    role = (lc.get("role") or "").lower()
    if lc.get("detected") and (lc.get("recency_days") or 999) <= 90 and any(
        k in role for k in ("cto", "vp eng", "svp eng", "head of engineering")
    ):
        s += 0.60
        rat.append(f"new {lc.get('role')} {lc.get('recency_days')} d ago — +0.60")
    return max(0.0, min(1.0, s)), rat


def _score_seg4(brief: HiringSignalBrief, maturity: AiMaturityScore) -> tuple[float, list[str]]:
    s = 0.0
    rat: list[str] = []
    v = brief.signals.get("job_post_velocity", {}) or {}
    if v.get("ai_adjacent_fraction", 0.0) >= 0.3 and maturity.score >= _SEGMENT_4_MATURITY_GATE:
        s += 0.55
        rat.append(f"AI-adjacent role fraction {v.get('ai_adjacent_fraction')} + maturity {maturity.score} — +0.55")
    if maturity.score < _SEGMENT_4_MATURITY_GATE:
        s = 0.0  # hard gate
        rat.append(f"maturity {maturity.score} < {_SEGMENT_4_MATURITY_GATE} — seg 4 gated to 0")
    return max(0.0, min(1.0, s)), rat


def classify(brief: HiringSignalBrief, *, maturity: AiMaturityScore,
             confidence_threshold: float = _CONFIDENCE_THRESHOLD,
             margin_threshold: float = _MARGIN_THRESHOLD) -> IcpClassification:
    scorers = {1: _score_seg1, 2: _score_seg2, 3: _score_seg3, 4: _score_seg4}
    scores: dict[int, float] = {}
    rationale: list[str] = []
    for sid, fn in scorers.items():
        sc, rat = fn(brief, maturity)
        scores[sid] = sc
        rationale.extend(rat)

    # Tie-break: prefer segment 3 over 1 when both qualify (leadership > fresh funding per docs).
    if scores[3] >= confidence_threshold and scores[1] >= confidence_threshold and scores[3] >= scores[1] - 0.05:
        scores[1] = max(0.0, scores[1] - 0.1)
        rationale.append("seg 3 tiebreak applied: leadership transition preferred over seg 1 overlap")

    top_id = max(scores, key=lambda k: scores[k])
    top_score = scores[top_id]
    ordered = sorted(scores.values(), reverse=True)
    second = ordered[1] if len(ordered) > 1 else 0.0
    margin = top_score - second

    out = IcpClassification(
        crunchbase_uuid=brief.crunchbase_uuid,
        segment=top_id,
        mode="confident",
        confidence=round(top_score, 2),
        margin=round(margin, 2),
        scores={str(k): round(v, 2) for k, v in scores.items()},
        rationale=rationale,
    )

    if top_score < confidence_threshold:
        out.mode = "abstain"
        out.segment = None
        out.reason = f"top score {top_score:.2f} below threshold {confidence_threshold:.2f}"
        return out
    if margin < margin_threshold:
        out.mode = "abstain"
        out.segment = None
        out.reason = f"ambiguous — margin {margin:.2f} below {margin_threshold:.2f}"
        return out
    if top_id == 4 and maturity.score < _SEGMENT_4_MATURITY_GATE:
        out.mode = "abstain"
        out.segment = None
        out.reason = f"segment 4 gated below AI-maturity {_SEGMENT_4_MATURITY_GATE}"
        return out

    return out
