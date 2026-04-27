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

# Email engagements (HubSpot object type "emails") — written by
# events.record_outbound and events.record_inbound.
EMAIL_PROPERTIES: list[dict[str, Any]] = [
    {"name": "tenacious_trace_id", "type": "string"},
    {"name": "tenacious_provider_message_id", "type": "string"},
    {"name": "tenacious_tone_scores", "type": "string"},
    {"name": "tenacious_draft_flag", "type": "string"},
    {"name": "tenacious_reply_class", "type": "string"},
    {"name": "tenacious_reply_confidence", "type": "number"},
    {"name": "tenacious_reply_rationale", "type": "string"},
]

# Meeting engagements (object type "meetings") — written by events.record_booking.
MEETING_PROPERTIES: list[dict[str, Any]] = [
    {"name": "tenacious_cal_booking_id", "type": "string"},
]

# Task engagements (object type "tasks") — written by events.create_handoff_task.
# Tasks go through the legacy create-engagement API but the modern object type
# is `tasks`; properties created here apply to the v3 object representation.
TASK_PROPERTIES: list[dict[str, Any]] = [
    {"name": "tenacious_trace_id", "type": "string"},
    {"name": "tenacious_handoff_reason", "type": "string"},
]


def ensure_all(client: Any) -> list[str]:
    """Create any missing tenacious_* property. Returns list of created names."""
    created: list[str] = []
    plan: list[tuple[str, list[dict[str, Any]]]] = [
        ("contacts", CONTACT_PROPERTIES),
        ("deals", DEAL_PROPERTIES),
        ("emails", EMAIL_PROPERTIES),
        ("meetings", MEETING_PROPERTIES),
        ("tasks", TASK_PROPERTIES),
    ]
    for object_type, props in plan:
        for prop in props:
            if client.ensure_property(object_type, **prop):
                created.append(f"{object_type}.{prop['name']}")
    return created
