"""Conversation-event writers.

Every send / receive / booking / handoff funnels through one function here.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any

from agent.hubspot.client import HubSpotClient


_client: HubSpotClient | None = None


def _c() -> HubSpotClient:
    global _client
    if _client is None:
        _client = HubSpotClient()
    return _client


def upsert_contact(prospect: dict[str, Any], *, brief: Any, classification: Any, trace_id: str, kill_switch_sink: bool) -> str:
    b = brief.model_dump() if hasattr(brief, "model_dump") else brief
    properties: dict[str, Any] = {
        "email": prospect["prospect_email"],
        "firstname": str(prospect.get("prospect_name", "")).split(" ", 1)[0],
        "lastname": " ".join(str(prospect.get("prospect_name", "")).split(" ")[1:]) or "",
        "company": prospect.get("prospect_company", ""),
        "tenacious_status": "draft",
        "tenacious_segment": str(classification.segment),
        "tenacious_segment_confidence": float(classification.confidence),
        "tenacious_ai_maturity_score": str(b.get("ai_maturity", {}).get("score", 0)),
        "tenacious_ai_maturity_confidence": _conf_bucket(b.get("ai_maturity", {}).get("confidence", 0.0)),
        "tenacious_outreach_status": "never_contacted",
        "tenacious_last_brief_generated_at": str(b.get("generated_at", dt.datetime.now(dt.timezone.utc).isoformat())),
        "tenacious_hiring_signal_brief_url": f"eval/briefs/{prospect['company_domain']}/hiring_signal_brief.json",
        "tenacious_enrichment_sources_checked": json.dumps([
            {"source": s["source"] if isinstance(s, dict) else s.source, "status": str(s.get("status") if isinstance(s, dict) else s.status)}
            for s in b.get("data_sources_checked", [])
        ])[:3000],
        "tenacious_honesty_flags": ",".join(str(f) for f in b.get("honesty_flags", [])),
        "tenacious_bench_gap_detected": not b.get("bench_to_brief_match", {}).get("bench_available", True),
        "tenacious_kill_switch_state": "sink" if kill_switch_sink else "live",
        "tenacious_trace_id_latest": trace_id or "",
    }
    return _c().upsert_contact(properties, email=prospect["prospect_email"])


def _conf_bucket(f: float) -> str:
    if f >= 0.75:
        return "high"
    if f >= 0.5:
        return "medium"
    return "low"


def attach_brief(contact_id: str, *, brief_type: str, brief_json: dict[str, Any], brief_url: str) -> str:
    body = {
        "hs_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hs_note_body": f"Brief attached: {brief_type}\nURL: {brief_url}\n\n" + json.dumps(brief_json, indent=2, default=str)[:5000],
    }
    return _c().create_engagement("note", body, associations=[{"to_id": contact_id, "type": "contact_to_note"}])


def record_outbound(contact_id: str, draft: dict[str, Any], *, provider_message_id: str, trace_id: str, tone_scores: dict[str, int] | None = None) -> str:
    body = {
        "hs_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hs_email_subject": draft.get("subject", ""),
        "hs_email_text": draft.get("body_text", ""),
        "hs_email_direction": "EMAIL",
        "hs_email_status": "SENT",
        "tenacious_provider_message_id": provider_message_id,
        "tenacious_trace_id": trace_id,
        "tenacious_tone_scores": json.dumps(tone_scores or {}),
        "tenacious_draft_flag": "true",
    }
    return _c().create_engagement("email", body, associations=[{"to_id": contact_id, "type": "contact_to_email"}])


def record_inbound(contact_id: str, reply: dict[str, Any], *, classification: Any, trace_id: str) -> str:
    body = {
        "hs_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hs_email_subject": reply.get("subject", ""),
        "hs_email_text": reply.get("body_text", ""),
        "hs_email_direction": "INCOMING_EMAIL",
        "hs_email_status": "RECEIVED",
        "tenacious_reply_class": getattr(classification, "class_", ""),
        "tenacious_reply_confidence": getattr(classification, "confidence", 0.0),
        "tenacious_reply_rationale": getattr(classification, "rationale", ""),
        "tenacious_trace_id": trace_id,
    }
    return _c().create_engagement("email", body, associations=[{"to_id": contact_id, "type": "contact_to_email"}])


def create_handoff_task(contact_id: str, *, reason: str, delivery_lead_email: str, context_brief_md: str, trace_id: str) -> str:
    body = {
        "hs_timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hs_task_subject": f"HANDOFF — {reason}",
        "hs_task_body": context_brief_md[:5000],
        "hs_task_status": "NOT_STARTED",
        "hs_task_priority": "HIGH",
        "hubspot_owner_id": delivery_lead_email,
        "tenacious_handoff_reason": reason,
        "tenacious_trace_id": trace_id,
    }
    return _c().create_engagement("task", body, associations=[{"to_id": contact_id, "type": "contact_to_task"}])


def record_booking(contact_id: str, cal_booking: dict[str, Any], *, segment_at_booking: str, context_brief_url: str, evidence_graph_id: str) -> tuple[str, str]:
    # Meeting engagement
    meeting = {
        "hs_timestamp": cal_booking.get("start_time_utc", dt.datetime.now(dt.timezone.utc).isoformat()),
        "hs_meeting_title": cal_booking.get("title", "Discovery call"),
        "hs_meeting_start_time": cal_booking.get("start_time_utc"),
        "hs_meeting_end_time": cal_booking.get("end_time_utc"),
        "tenacious_cal_booking_id": cal_booking.get("booking_id", ""),
    }
    meeting_id = _c().create_engagement("meeting", meeting, associations=[{"to_id": contact_id, "type": "contact_to_meeting"}])
    # Deal
    deal = _c().create_deal({
        "dealname": f"Discovery — {cal_booking.get('prospect_company','?')}",
        "tenacious_discovery_call_scheduled_at": cal_booking.get("start_time_utc"),
        "tenacious_discovery_call_timezone_prospect": cal_booking.get("prospect_timezone", ""),
        "tenacious_delivery_lead_email": cal_booking.get("lead_email", ""),
        "tenacious_context_brief_url": context_brief_url,
        "tenacious_segment_at_booking": segment_at_booking,
        "tenacious_evidence_graph_id": evidence_graph_id,
    }, contact_id=contact_id)
    return meeting_id, deal


def mark_opted_out(contact_id: str, *, reason: str) -> None:
    _c().upsert_contact({
        "tenacious_status": "opted_out",
        "tenacious_outreach_status": "opted_out",
        "tenacious_opt_out_reason": reason,
    }, email=contact_id)
