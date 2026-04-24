"""HubSpot custom-property schema.

All custom properties are prefixed `tenacious_` so they are visible and
removable in one filter. Created idempotently on first boot.

See __specs/08-hubspot-integration.md § Custom properties.
"""
from __future__ import annotations

from typing import Any


CONTACT_PROPERTIES: list[dict[str, Any]] = [
    {"name": "tenacious_status", "type": "enumeration", "options": ["draft", "final", "opted_out"]},
    {"name": "tenacious_segment", "type": "enumeration", "options": [
        "segment_1_series_a_b",
        "segment_2_mid_market_restructure",
        "segment_3_leadership_transition",
        "segment_4_specialized_capability",
        "abstain",
    ]},
    {"name": "tenacious_segment_confidence", "type": "number"},
    {"name": "tenacious_ai_maturity_score", "type": "enumeration", "options": ["0", "1", "2", "3"]},
    {"name": "tenacious_ai_maturity_confidence", "type": "enumeration", "options": ["high", "medium", "low"]},
    {"name": "tenacious_outreach_status", "type": "enumeration", "options": [
        "never_contacted", "cold_1_sent", "cold_2_sent", "cold_3_sent",
        "warm_active", "booked", "opted_out", "parked",
    ]},
    {"name": "tenacious_last_brief_generated_at", "type": "datetime"},
    {"name": "tenacious_hiring_signal_brief_url", "type": "string"},
    {"name": "tenacious_competitor_gap_brief_url", "type": "string"},
    {"name": "tenacious_enrichment_sources_checked", "type": "string"},
    {"name": "tenacious_honesty_flags", "type": "enumeration",
     "options": ["weak_hiring_velocity_signal", "weak_ai_maturity_signal",
                 "conflicting_segment_signals", "layoff_overrides_funding",
                 "bench_gap_detected", "tech_stack_inferred_not_confirmed"]},
    {"name": "tenacious_bench_gap_detected", "type": "bool"},
    {"name": "tenacious_kill_switch_state", "type": "enumeration", "options": ["sink", "live"]},
    {"name": "tenacious_trace_id_latest", "type": "string"},
]

DEAL_PROPERTIES: list[dict[str, Any]] = [
    {"name": "tenacious_discovery_call_scheduled_at", "type": "datetime"},
    {"name": "tenacious_discovery_call_timezone_prospect", "type": "string"},
    {"name": "tenacious_delivery_lead_email", "type": "string"},
    {"name": "tenacious_context_brief_url", "type": "string"},
    {"name": "tenacious_segment_at_booking", "type": "string"},
    {"name": "tenacious_evidence_graph_id", "type": "string"},
]


def ensure_all(client: Any) -> list[str]:
    """Create any missing tenacious_* property. Returns list of created names."""
    created: list[str] = []
    for prop in CONTACT_PROPERTIES:
        if client.ensure_contact_property(**prop):
            created.append(prop["name"])
    for prop in DEAL_PROPERTIES:
        if client.ensure_deal_property(**prop):
            created.append(prop["name"])
    return created
