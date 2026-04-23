"""Dataclasses / pydantic models used across the agent.

Interim scope: only the structures touched by D0-D3 lanes. Probe/method structs
arrive in later acts.
"""
from __future__ import annotations

from datetime import date as _date, datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


# --------------------------------------------------------------------------- #
# Thread state machine
# --------------------------------------------------------------------------- #

class Stage(str, Enum):
    COLD = "COLD"
    NURTURE_1 = "NURTURE_1"
    NURTURE_2 = "NURTURE_2"
    NURTURE_3 = "NURTURE_3"
    QUALIFIED = "QUALIFIED"
    SCHEDULING = "SCHEDULING"
    SMS_SCHEDULING = "SMS_SCHEDULING"
    BOOKED = "BOOKED"
    HANDED_OFF = "HANDED_OFF"
    STALE = "STALE"
    STOP = "STOP"
    CLOSED_LOST = "CLOSED_LOST"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class Variant(str, Enum):
    SIGNAL_GROUNDED = "signal_grounded"
    EXPLORATORY = "exploratory"


# --------------------------------------------------------------------------- #
# Prospect
# --------------------------------------------------------------------------- #

class CrunchbaseRecord(BaseModel):
    uuid: str
    name: str
    domain: str | None = None
    country: str | None = None
    region: str | None = None
    industries: list[str] = Field(default_factory=list)
    founded_on: _date | None = None
    employee_count_range: str | None = None
    total_funding_usd: int | None = None
    last_funding_type: str | None = None
    last_funding_amount_usd: int | None = None
    last_funding_date: _date | None = None
    founders: list[str] = Field(default_factory=list)
    ceo: str | None = None
    linkedin_url: str | None = None
    crunchbase_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Prospect(BaseModel):
    """A synthetic prospect — Crunchbase firmographics + fabricated contact."""

    crunchbase: CrunchbaseRecord
    contact_email: str
    contact_first: str
    contact_last: str
    contact_role: str
    contact_timezone: str = "America/New_York"
    preferred_channel: Literal["email", "sms"] = "email"
    synthetic: bool = True

    @property
    def company_name(self) -> str:
        return self.crunchbase.name

    @property
    def uuid(self) -> str:
        return self.crunchbase.uuid


# --------------------------------------------------------------------------- #
# Signals / briefs
# --------------------------------------------------------------------------- #

class FundingSignal(BaseModel):
    latest_round: str | None = None
    amount_usd: int | None = None
    date: _date | None = None
    recency_days: int | None = None
    confidence: float = 0.0
    evidence: list[dict[str, str]] = Field(default_factory=list)


class VelocitySignal(BaseModel):
    open_roles_now: int = 0
    open_roles_60d_ago: int = 0
    ratio: float = 0.0
    ai_adjacent_fraction: float = 0.0
    confidence: float = 0.0
    qualifies_for_aggressive_hiring_claim: bool = False
    evidence: list[dict[str, str]] = Field(default_factory=list)


class LayoffSignal(BaseModel):
    detected: bool = False
    date: _date | None = None
    headcount: int | None = None
    percentage: float | None = None
    recency_days: int | None = None
    confidence: float = 0.0
    evidence: list[dict[str, str]] = Field(default_factory=list)


class LeadershipSignal(BaseModel):
    detected: bool = False
    role: str | None = None
    name: str | None = None
    recency_days: int | None = None
    confidence: float = 0.0
    evidence: list[dict[str, str]] = Field(default_factory=list)


class TechStackSignal(BaseModel):
    items: list[str] = Field(default_factory=list)
    bench_matches: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class HiringSignalBrief(BaseModel):
    version: str = "1.0"
    crunchbase_uuid: str
    company: dict[str, Any]
    signals: dict[str, Any]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AiMaturityJustification(BaseModel):
    signal: str
    weight: str
    evidence: str
    contribution: float
    caveat: str | None = None


class AiMaturityScore(BaseModel):
    version: str = "1.0"
    crunchbase_uuid: str
    score: int
    confidence: float
    confidence_band: Literal["low", "medium", "high"]
    justification: list[AiMaturityJustification]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GapPractice(BaseModel):
    practice: str
    peers_with: list[str]
    prospect_has: bool = False
    peer_evidence: list[dict[str, str]] = Field(default_factory=list)
    prospect_evidence: list[dict[str, str]] = Field(default_factory=list)
    confidence: float


class CompetitorGapBrief(BaseModel):
    version: str = "1.0"
    crunchbase_uuid: str
    sector: str
    size_band: str | None = None
    peers: list[dict[str, Any]]
    prospect_position: dict[str, Any]
    gap_practices: list[GapPractice]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IcpClassification(BaseModel):
    crunchbase_uuid: str
    segment: int | None = None
    mode: Literal["confident", "abstain"]
    confidence: float = 0.0
    margin: float = 0.0
    scores: dict[str, float] = Field(default_factory=dict)
    rationale: list[str] = Field(default_factory=list)
    reason: str | None = None


# --------------------------------------------------------------------------- #
# Conversation
# --------------------------------------------------------------------------- #

class EmailDraft(BaseModel):
    subject: str
    body_markdown: str
    signals_cited: list[str] = Field(default_factory=list)
    assertions_backed_by: list[str] = Field(default_factory=list)
    variant: Variant = Variant.SIGNAL_GROUNDED


class EmailReplyIntent(BaseModel):
    intent: Literal[
        "interested",
        "objection",
        "off_topic",
        "unsubscribe",
        "scheduling_question",
        "bench_question",
        "pricing_question",
    ]
    confidence: float = 0.0
    extracted: dict[str, Any] = Field(default_factory=dict)


class ThreadState(BaseModel):
    thread_id: UUID = Field(default_factory=uuid4)
    prospect_uuid: str
    contact_email: str
    stage: Stage = Stage.COLD
    segment: int | None = None
    icp_mode: Literal["confident", "abstain"] = "abstain"
    variant: Variant = Variant.EXPLORATORY
    history: list[dict[str, Any]] = Field(default_factory=list)
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    draft_approved: bool = False
    preferred_channel: Literal["email", "sms"] = "email"

    def push(self, role: str, body: str, **meta: Any) -> None:
        self.history.append(
            {
                "role": role,
                "body": body,
                "ts": datetime.now(timezone.utc).isoformat(),
                **meta,
            }
        )
        self.last_activity_at = datetime.now(timezone.utc)
