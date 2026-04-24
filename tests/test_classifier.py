"""ICP classifier rule-firing tests — the ordered rules from spec 03."""
from __future__ import annotations

import datetime as dt

from agent.classifier import classify


_TODAY = dt.date.today()


def _base() -> dict:
    return {
        "buying_window_signals": {
            "funding_event": {"detected": False},
            "layoff_event": {"detected": False},
            "leadership_change": {"detected": False},
        },
        "ai_maturity": {"score": 0, "confidence": 0.5},
        "hiring_velocity": {"open_roles_today": 0, "open_roles_60_days_ago": 0, "velocity_label": "insufficient_signal", "signal_confidence": 0.3},
        "tech_stack": [],
        "bench_to_brief_match": {"required_stacks": [], "bench_available": True, "gaps": []},
    }


def test_layoff_plus_funding_wins_segment_2():
    b = _base()
    b["buying_window_signals"]["funding_event"] = {"detected": True, "closed_at": (_TODAY - dt.timedelta(days=30)).isoformat(), "amount_usd": 10_000_000, "stage": "series_b"}
    b["buying_window_signals"]["layoff_event"] = {"detected": True, "date": (_TODAY - dt.timedelta(days=60)).isoformat(), "percentage_cut": 0.12}
    b["hiring_velocity"]["open_roles_today"] = 4
    r = classify(b)
    assert r.segment == "segment_2_mid_market_restructure"
    assert r.rule_fired == "rule_1_layoff_plus_funding"


def test_layoff_above_ceiling_abstains():
    b = _base()
    b["buying_window_signals"]["funding_event"] = {"detected": True, "closed_at": (_TODAY - dt.timedelta(days=30)).isoformat(), "amount_usd": 10_000_000, "stage": "series_b"}
    b["buying_window_signals"]["layoff_event"] = {"detected": True, "date": (_TODAY - dt.timedelta(days=60)).isoformat(), "percentage_cut": 0.50}
    r = classify(b)
    assert r.segment == "abstain"


def test_new_cto_wins_segment_3():
    b = _base()
    b["buying_window_signals"]["leadership_change"] = {
        "detected": True, "role": "cto", "new_leader_name": "Alex Chen",
        "started_at": (_TODAY - dt.timedelta(days=45)).isoformat(),
    }
    r = classify(b)
    assert r.segment == "segment_3_leadership_transition"


def test_interim_cto_is_disqualified():
    b = _base()
    b["buying_window_signals"]["leadership_change"] = {
        "detected": True, "role": "cto", "new_leader_name": "Interim CTO Jane",
        "started_at": (_TODAY - dt.timedelta(days=10)).isoformat(),
    }
    r = classify(b)
    # Should not land Segment 3; falls through to abstain
    assert r.segment != "segment_3_leadership_transition"


def test_segment_4_requires_ai_maturity_2():
    b = _base()
    b["ai_maturity"] = {"score": 1, "confidence": 0.8}
    b["bench_to_brief_match"]["required_stacks"] = ["python", "data"]
    b["hiring_velocity"] = {"open_roles_today": 3, "open_roles_60_days_ago": 3, "velocity_label": "flat", "signal_confidence": 0.7}
    r = classify(b)
    assert r.segment != "segment_4_specialized_capability"


def test_pure_funding_wins_segment_1():
    b = _base()
    b["buying_window_signals"]["funding_event"] = {
        "detected": True, "closed_at": (_TODAY - dt.timedelta(days=30)).isoformat(),
        "amount_usd": 14_000_000, "stage": "series_b",
    }
    b["hiring_velocity"] = {"open_roles_today": 11, "open_roles_60_days_ago": 4, "velocity_label": "doubled", "signal_confidence": 0.85}
    r = classify(b)
    assert r.segment == "segment_1_series_a_b"
    assert r.confidence >= 0.6


def test_no_signals_abstain():
    r = classify(_base())
    assert r.segment == "abstain"
