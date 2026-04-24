"""Pydantic models mirroring tenacious_sales_data/schemas/*.schema.json.

These models validate briefs at write time. A CI test (tests/test_schema_conformance.py)
cross-validates serialized instances against the source JSON Schema so drift is caught.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, ConfigDict


# ────────────────────────────────────────────────────────────────────────────
# Shared enums
# ────────────────────────────────────────────────────────────────────────────


class Segment(str, Enum):
    SEGMENT_1 = "segment_1_series_a_b"
    SEGMENT_2 = "segment_2_mid_market_restructure"
    SEGMENT_3 = "segment_3_leadership_transition"
    SEGMENT_4 = "segment_4_specialized_capability"
    ABSTAIN = "abstain"


class AiSignal(str, Enum):
    AI_ADJACENT_OPEN_ROLES = "ai_adjacent_open_roles"
    NAMED_AI_ML_LEADERSHIP = "named_ai_ml_leadership"
    GITHUB_ORG_ACTIVITY = "github_org_activity"
    EXECUTIVE_COMMENTARY = "executive_commentary"
    MODERN_DATA_ML_STACK = "modern_data_ml_stack"
    STRATEGIC_COMMUNICATIONS = "strategic_communications"


class Weight(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VelocityLabel(str, Enum):
    TRIPLED_OR_MORE = "tripled_or_more"
    DOUBLED = "doubled"
    INCREASED_MODESTLY = "increased_modestly"
    FLAT = "flat"
    DECLINED = "declined"
    INSUFFICIENT_SIGNAL = "insufficient_signal"


class FundingStage(str, Enum):
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    SERIES_D_PLUS = "series_d_plus"
    DEBT = "debt"
    OTHER = "other"
    NONE = "none"


class LeadershipRole(str, Enum):
    CTO = "cto"
    VP_ENGINEERING = "vp_engineering"
    CIO = "cio"
    CHIEF_DATA_OFFICER = "chief_data_officer"
    HEAD_OF_AI = "head_of_ai"
    OTHER = "other"
    NONE = "none"


class SourceStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NO_DATA = "no_data"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class HeadcountBand(str, Enum):
    HC_15_80 = "15_to_80"
    HC_80_200 = "80_to_200"
    HC_200_500 = "200_to_500"
    HC_500_2000 = "500_to_2000"
    HC_2000_PLUS = "2000_plus"


class HonestyFlag(str, Enum):
    WEAK_HIRING_VELOCITY_SIGNAL = "weak_hiring_velocity_signal"
    WEAK_AI_MATURITY_SIGNAL = "weak_ai_maturity_signal"
    CONFLICTING_SEGMENT_SIGNALS = "conflicting_segment_signals"
    LAYOFF_OVERRIDES_FUNDING = "layoff_overrides_funding"
    BENCH_GAP_DETECTED = "bench_gap_detected"
    TECH_STACK_INFERRED_NOT_CONFIRMED = "tech_stack_inferred_not_confirmed"


# ────────────────────────────────────────────────────────────────────────────
# Hiring Signal Brief
# ────────────────────────────────────────────────────────────────────────────


class AiMaturityJustification(BaseModel):
    signal: AiSignal
    status: str
    weight: Weight
    confidence: Confidence
    source_url: str | None = None


class AiMaturity(BaseModel):
    score: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    justifications: list[AiMaturityJustification] = Field(default_factory=list)


class HiringVelocity(BaseModel):
    open_roles_today: int = Field(ge=0)
    open_roles_60_days_ago: int = Field(ge=0)
    velocity_label: VelocityLabel
    signal_confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class FundingEvent(BaseModel):
    detected: bool = False
    stage: FundingStage | None = None
    amount_usd: int | None = None
    closed_at: dt.date | None = None
    source_url: str | None = None


class LayoffEvent(BaseModel):
    detected: bool = False
    date: dt.date | None = None
    headcount_reduction: int | None = None
    percentage_cut: float | None = None
    source_url: str | None = None


class LeadershipChange(BaseModel):
    detected: bool = False
    role: LeadershipRole | None = None
    new_leader_name: str | None = None
    started_at: dt.date | None = None
    source_url: str | None = None


class BuyingWindowSignals(BaseModel):
    funding_event: FundingEvent = Field(default_factory=FundingEvent)
    layoff_event: LayoffEvent = Field(default_factory=LayoffEvent)
    leadership_change: LeadershipChange = Field(default_factory=LeadershipChange)


class BenchToBriefMatch(BaseModel):
    required_stacks: list[str] = Field(default_factory=list)
    bench_available: bool = True
    gaps: list[str] = Field(default_factory=list)


class DataSourceCheck(BaseModel):
    source: str
    status: SourceStatus
    error_message: str | None = None
    fetched_at: dt.datetime | None = None


class HiringSignalBrief(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    prospect_domain: str
    prospect_name: str
    generated_at: dt.datetime
    primary_segment_match: Segment
    segment_confidence: float = Field(ge=0.0, le=1.0)
    ai_maturity: AiMaturity
    hiring_velocity: HiringVelocity
    buying_window_signals: BuyingWindowSignals = Field(default_factory=BuyingWindowSignals)
    tech_stack: list[str] = Field(default_factory=list)
    bench_to_brief_match: BenchToBriefMatch = Field(default_factory=BenchToBriefMatch)
    data_sources_checked: list[DataSourceCheck] = Field(default_factory=list)
    honesty_flags: list[HonestyFlag] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────
# Competitor Gap Brief
# ────────────────────────────────────────────────────────────────────────────


class CompetitorEntry(BaseModel):
    name: str
    domain: str
    ai_maturity_score: int = Field(ge=0, le=3)
    ai_maturity_justification: list[str] = Field(default_factory=list)
    headcount_band: HeadcountBand
    top_quartile: bool = False
    sources_checked: list[str] = Field(default_factory=list)


class PeerEvidence(BaseModel):
    competitor_name: str
    evidence: str
    source_url: str


class GapFinding(BaseModel):
    practice: str
    peer_evidence: list[PeerEvidence] = Field(min_length=2)
    prospect_state: str
    confidence: Confidence
    segment_relevance: list[Segment] = Field(default_factory=list)


class GapQualitySelfCheck(BaseModel):
    all_peer_evidence_has_source_url: bool
    at_least_one_gap_high_confidence: bool
    prospect_silent_but_sophisticated_risk: bool = False


class CompetitorGapBrief(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    prospect_domain: str
    prospect_sector: str
    prospect_sub_niche: str | None = None
    generated_at: dt.datetime
    prospect_ai_maturity_score: int = Field(ge=0, le=3)
    sector_top_quartile_benchmark: float = Field(ge=0.0, le=3.0)
    competitors_analyzed: list[CompetitorEntry] = Field(min_length=5, max_length=10)
    gap_findings: list[GapFinding] = Field(min_length=1, max_length=3)
    suggested_pitch_shift: str | None = None
    gap_quality_self_check: GapQualitySelfCheck | None = None


# ────────────────────────────────────────────────────────────────────────────
# Discovery Call Context Brief (rendered as markdown; model here for type safety)
# ────────────────────────────────────────────────────────────────────────────


class DiscoveryCallContext(BaseModel):
    """A structured representation; the final deliverable is a markdown render."""

    prospect_name: str
    prospect_title: str
    prospect_company: str
    call_datetime_utc: dt.datetime
    call_datetime_prospect_tz: str
    tenacious_lead_name: str
    duration_minutes: int
    thread_start_date: dt.date
    original_subject: str
    langfuse_trace_url: str

    segment_name: str
    segment_confidence: float
    segment_rationale: str
    abstention_risk: str

    hiring_signal_summary: str  # rendered bullet list
    gap_findings_high_conf: list[str] = Field(default_factory=list)
    gap_findings_low_conf: list[str] = Field(default_factory=list)

    required_stacks: list[str] = Field(default_factory=list)
    bench_availability: str  # rendered table as markdown
    bench_gaps: list[str] = Field(default_factory=list)
    staffing_promises_flag: str

    thread_summary_bullets: list[str] = Field(default_factory=list)
    objections_table: list[dict[str, str]] = Field(default_factory=list)

    price_bands_quoted: str
    prospect_asked_tcv: str
    vendor_comparison: str
    urgency_quotes: str

    suggested_opening: str
    suggested_qualifying_q: str
    suggested_capability_discussion: str
    suggested_commercial_framing: str
    suggested_next_step: str

    do_not_do: list[str] = Field(default_factory=list)

    confident_facts: str
    uncertain_facts: str
    missing_facts: str
    overall_confidence: float

    trace_id: str
    generation_timestamp_utc: dt.datetime
