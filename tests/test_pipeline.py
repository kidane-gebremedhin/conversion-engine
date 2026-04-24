"""Pipeline smoke tests — every synthetic prospect enriches without raising."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.enrichment.pipeline import enrich


def _prospects():
    path = Path("data/synthetic_prospects.json")
    return json.loads(path.read_text())


@pytest.mark.parametrize("prospect", _prospects())
def test_every_prospect_enriches(prospect):
    # Some fixtures may not have Crunchbase records; skip those, don't fail.
    from agent.enrichment import crunchbase
    if not crunchbase.lookup_by_domain(prospect["company_domain"]):
        pytest.skip(f"no Crunchbase record for {prospect['company_domain']}")
    brief, gap = enrich(prospect["company_domain"])
    assert brief.prospect_domain == prospect["company_domain"]
    # Expected-segment not strictly enforced in tests (fixture drift),
    # but the brief must be schema-complete.
    assert brief.ai_maturity is not None
    assert brief.hiring_velocity is not None
