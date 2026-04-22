"""Tool schemas used by the orchestrator (and by probe fixtures later).

The orchestrator in the interim invokes these as plain Python calls — we keep
the schemas so Act IV / probe runs can enforce the same surface contract.
See __specs/06-agent-design.md §3.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class DraftEmailInput(BaseModel):
    prospect_uuid: str
    stage: Literal["cold", "nurture_1", "nurture_2", "nurture_3", "scheduling"]
    variant: Literal["signal_grounded", "exploratory"]


class SendEmailInput(BaseModel):
    to: EmailStr
    subject: str
    body_markdown: str
    trace_id: UUID
    draft_approved: bool = False


class SendSmsInput(BaseModel):
    to_shortcode: str
    body: str
    trace_id: UUID


class LogCrmInput(BaseModel):
    prospect_uuid: str
    event_type: Literal[
        "email_sent",
        "email_reply",
        "sms_sent",
        "sms_reply",
        "call_booked",
        "segment_assigned",
        "handoff_human",
    ]
    payload: dict


class BookCallInput(BaseModel):
    prospect_uuid: str
    slot_iso: datetime
    tenacious_lead_email: EmailStr
    context_brief_md: str


class ToneCheckInput(BaseModel):
    draft_markdown: str
    stage: str


class BenchCheckInput(BaseModel):
    draft_markdown: str


class HandoffHumanInput(BaseModel):
    reason: Literal[
        "prospect_asked_for_specific_pricing",
        "prospect_asked_bench_beyond_capacity",
        "prospect_explicit_objection",
        "unknown_policy_boundary",
    ]
    thread_summary_md: str
