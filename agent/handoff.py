"""Handoff gate — the five conditions that escalate a thread to a human.

From __specs/06-agent-design.md capability 4:
  1. Regulatory keyword (MSA/DPA/BAA/SOW/NDA/DPIA/GDPR/HIPAA).
  2. Pricing question beyond published bands.
  3. Bench over-commit risk (prospect asks for a stack with bench count = 0).
  4. Tone-check double failure.
  5. Discovery call booked (hand off the context brief).

The agent creates a HubSpot task, sends ONE acknowledgement email to the
prospect, and stops further autonomous messages on the thread.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any

from agent.config import config


@dataclass
class HandoffDecision:
    should_handoff: bool
    reason: str
    severity: str  # "hard" | "soft"


_REGULATORY_KEYWORDS = tuple(k.lower() for k in config.get("handoff.regulatory_keywords", [
    "MSA", "DPA", "BAA", "SOW", "NDA", "DPIA", "GDPR", "HIPAA",
]))


def should_handoff(
    *,
    reply_text: str | None,
    tone_double_failed: bool,
    bench_over_commit: bool,
    booking_created: bool,
    published_price_asked_out_of_band: bool,
) -> HandoffDecision:
    # Rule 1 — regulatory
    if reply_text:
        low = reply_text.lower()
        hit = next((k for k in _REGULATORY_KEYWORDS if re.search(rf"\b{re.escape(k)}\b", low)), None)
        if hit:
            return HandoffDecision(True, f"regulatory_keyword:{hit}", "hard")

    # Rule 2 — price out-of-band
    if published_price_asked_out_of_band:
        return HandoffDecision(True, "price_out_of_published_band", "hard")

    # Rule 3 — bench over-commit
    if bench_over_commit:
        return HandoffDecision(True, "bench_over_commit", "hard")

    # Rule 4 — tone double-fail
    if tone_double_failed:
        return HandoffDecision(True, "tone_double_failed", "soft")

    # Rule 5 — booking
    if booking_created:
        return HandoffDecision(True, "booking_created", "soft")

    return HandoffDecision(False, "no_trigger", "soft")


def make_hubspot_task(decision: HandoffDecision, *, prospect: dict[str, Any], thread_id: str, trace_url: str) -> dict[str, Any]:
    """Build a HubSpot task payload. Actual creation via agent.hubspot.events."""
    lead = config.get("handoff.default_lead_email", "arun@example.com")
    return {
        "ownerId": lead,
        "title": f"HANDOFF — {prospect.get('prospect_company', '?')}: {decision.reason}",
        "body": (
            f"Trace: {trace_url}\n"
            f"Thread: {thread_id}\n"
            f"Prospect: {prospect.get('prospect_name')} ({prospect.get('prospect_title')})\n"
            f"Reason: {decision.reason} [severity={decision.severity}]\n"
            f"Action: take over the thread; the agent has sent one acknowledgement and stopped.\n"
        ),
        "due_at": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)).isoformat(),
    }


def acknowledgement_message(decision: HandoffDecision, *, prospect: dict[str, Any]) -> dict[str, Any]:
    """Return the one human-handoff acknowledgement email payload fields."""
    lead_email = config.get("handoff.default_lead_email", "arun@example.com")
    tmpl = config.get("handoff.message_template", "Our delivery lead will follow up within 24 hours.")
    first = str(prospect.get("prospect_name", "")).split(" ", 1)[0]
    return {
        "subject": "Handoff: next message from our delivery lead",
        "body_text": (f"Hi {first}, {tmpl}\n\n"
                      f"They'll reach out from {lead_email}.\n\n"
                      f"— Tenacious research"),
    }
