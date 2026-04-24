"""Handoff rule tests — the five conditions from spec 06."""
from __future__ import annotations

from agent.handoff import should_handoff


def test_regulatory_keyword_triggers():
    d = should_handoff(
        reply_text="we'll need an MSA before we can sign", tone_double_failed=False,
        bench_over_commit=False, booking_created=False, published_price_asked_out_of_band=False,
    )
    assert d.should_handoff and d.reason.startswith("regulatory_keyword")


def test_price_out_of_band_triggers():
    d = should_handoff(
        reply_text="what's your ACV range?", tone_double_failed=False,
        bench_over_commit=False, booking_created=False, published_price_asked_out_of_band=True,
    )
    assert d.should_handoff and d.reason == "price_out_of_published_band"


def test_bench_over_commit_triggers():
    d = should_handoff(
        reply_text="can you ship 10 Rust engineers this week?", tone_double_failed=False,
        bench_over_commit=True, booking_created=False, published_price_asked_out_of_band=False,
    )
    assert d.should_handoff and d.reason == "bench_over_commit"


def test_booking_triggers_soft_handoff():
    d = should_handoff(
        reply_text=None, tone_double_failed=False, bench_over_commit=False,
        booking_created=True, published_price_asked_out_of_band=False,
    )
    assert d.should_handoff and d.severity == "soft"


def test_no_trigger():
    d = should_handoff(
        reply_text="thanks, will look", tone_double_failed=False,
        bench_over_commit=False, booking_created=False, published_price_asked_out_of_band=False,
    )
    assert not d.should_handoff
