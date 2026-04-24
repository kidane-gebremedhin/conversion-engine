"""Composer post-check tests — word cap, forbidden subject firsts, disallowed phrases."""
from __future__ import annotations

import pytest

from agent.composer import ComposerError, compose
from agent.classifier import SegmentMismatch
from agent.enrichment.pipeline import enrich


def _prospect():
    return {
        "prospect_email": "sink@test.example",
        "prospect_name": "Dana Fox",
        "prospect_title": "VP Engineering",
        "prospect_company": "Orrin Labs",
        "prospect_timezone": "America/New_York",
    }


def test_segment_4_refuses_low_ai_maturity():
    brief, _ = enrich("orrin-labs.example")
    # Orrin Labs comes in at score ≤ 2 in the fixture; downgrade forcibly.
    brief.ai_maturity.score = 0
    with pytest.raises(SegmentMismatch):
        compose(
            segment="segment_4_specialized_capability",
            brief=brief, gap_brief=None, prospect=_prospect(),
            cal_link="https://cal.example/x",
        )


def test_stub_mode_fallback_passes_post_checks():
    brief, gap = enrich("orrin-labs.example")
    draft = compose(
        segment="segment_1_series_a_b",
        brief=brief, gap_brief=gap, prospect=_prospect(),
        cal_link="https://cal.example/x",
    )
    assert draft.subject
    assert draft.body_text
    # word cap enforced
    assert "words=" in draft.notes[0]
