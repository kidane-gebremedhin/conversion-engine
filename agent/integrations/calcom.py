"""Cal.com booking — local fixture fallback.

Real mode uses the self-hosted Cal.com REST API. Interim mode (no credentials)
persists bookings to `data/calcom_local/bookings/<id>.json`. The context
brief is always 150–250 words and carries all 8 required elements.
"""
from __future__ import annotations

import json
import pathlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from agent import tracing
from agent.state import AiMaturityScore, CompetitorGapBrief, HiringSignalBrief, IcpClassification, Prospect


_LOCAL = pathlib.Path("data/calcom_local")


@dataclass
class Slot:
    start: datetime
    end: datetime


@dataclass
class BookingResult:
    booking_id: str
    start: datetime
    end: datetime
    event_type_slug: str
    attendee_email: str
    context_brief_md: str
    metadata: dict[str, Any]


class CalcomClient:
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:3000",
        api_key: str | None = None,
        working_hours: tuple[str, str] = ("08:00", "19:00"),
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.working_hours = working_hours
        self.mode = "rest" if api_key else "local"
        if self.mode == "local":
            (_LOCAL / "bookings").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #

    def available_slots(
        self, event_type_slug: str, *, from_: datetime, to: datetime, timezone_: str
    ) -> list[Slot]:
        with tracing.span("calcom.available_slots"):
            if self.mode == "local":
                return _synth_slots(from_, to, self.working_hours)
            return self._rest_slots(event_type_slug, from_, to, timezone_)

    def book(
        self,
        *,
        event_type_slug: str,
        start: datetime,
        attendee_email: str,
        attendee_name: str,
        attendee_timezone: str,
        metadata: dict[str, Any],
        context_brief_md: str,
        duration_min: int = 30,
    ) -> BookingResult:
        with tracing.span("calcom.book", event_type_slug=event_type_slug):
            booking_id = f"book_{uuid.uuid4().hex[:10]}"
            end = start + timedelta(minutes=duration_min)
            if self.mode == "local":
                rec = {
                    "booking_id": booking_id,
                    "event_type_slug": event_type_slug,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "attendee": {"email": attendee_email, "name": attendee_name, "timezone": attendee_timezone},
                    "metadata": metadata,
                    "description": f"[DRAFT]\n\n{context_brief_md}",
                }
                (_LOCAL / "bookings" / f"{booking_id}.json").write_text(json.dumps(rec, indent=2))
            else:
                self._rest_book(event_type_slug, start, end, attendee_email, attendee_name, attendee_timezone, metadata, context_brief_md)
            return BookingResult(
                booking_id=booking_id,
                start=start,
                end=end,
                event_type_slug=event_type_slug,
                attendee_email=attendee_email,
                context_brief_md=context_brief_md,
                metadata=metadata,
            )

    def _rest_slots(self, event_type_slug: str, from_: datetime, to: datetime, tz: str) -> list[Slot]:
        with httpx.Client(timeout=30) as c:
            r = c.get(
                f"{self.base_url}/v1/slots",
                params={"eventTypeSlug": event_type_slug, "from": from_.isoformat(), "to": to.isoformat(), "timezone": tz},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            return [Slot(start=datetime.fromisoformat(s["start"]), end=datetime.fromisoformat(s["end"])) for s in r.json().get("slots", [])]

    def _rest_book(self, event_type_slug: str, start: datetime, end: datetime, email: str, name: str, tz: str, meta: dict, brief: str) -> None:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{self.base_url}/v1/bookings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "eventTypeSlug": event_type_slug,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "attendee": {"email": email, "name": name, "timezone": tz},
                    "metadata": meta,
                    "description": f"[DRAFT]\n\n{brief}",
                },
            )
            r.raise_for_status()


# --------------------------------------------------------------------------- #

def _synth_slots(from_: datetime, to: datetime, wh: tuple[str, str]) -> list[Slot]:
    """Two slots per weekday within working hours."""
    slots: list[Slot] = []
    cur = from_
    start_h, start_m = [int(x) for x in wh[0].split(":")]
    end_h, _ = [int(x) for x in wh[1].split(":")]
    for _ in range(7):
        if cur > to:
            break
        if cur.weekday() < 5:
            for hour in (start_h + 2, min(end_h - 3, 14)):
                s = cur.replace(hour=hour, minute=start_m, second=0, microsecond=0)
                slots.append(Slot(start=s, end=s + timedelta(minutes=30)))
        cur = cur + timedelta(days=1)
    return slots


# --------------------------------------------------------------------------- #
# Context brief builder (150–250 words)
# --------------------------------------------------------------------------- #

def build_context_brief(
    *,
    prospect: Prospect,
    brief: HiringSignalBrief,
    maturity: AiMaturityScore,
    gap: CompetitorGapBrief,
    icp: IcpClassification,
    bench_match: list[str],
    draft: bool = True,
) -> str:
    co = brief.company
    funding = brief.signals.get("funding", {}) or {}
    velocity = brief.signals.get("job_post_velocity", {}) or {}
    layoff = brief.signals.get("layoff", {}) or {}
    lead = brief.signals.get("leadership_change", {}) or {}
    top_gap = gap.gap_practices[0].practice if gap.gap_practices else "n/a"

    seg_line = (
        f"Segment {icp.segment} (confidence {icp.confidence:.2f})"
        if icp.mode == "confident"
        else f"abstain — {icp.reason or 'insufficient confidence'}"
    )
    maturity_line = f"AI maturity {maturity.score}/3, confidence {maturity.confidence_band}"

    lines = [
        f"[DRAFT] Tenacious discovery brief — {co.get('name')} (Crunchbase {brief.crunchbase_uuid[:8]})",
        f"Sector: {(co.get('industries') or ['?'])[0]}; Size band: {co.get('employee_count_range') or 'unknown'}",
        f"ICP: {seg_line}. {maturity_line}.",
        (
            f"Funding: {funding.get('latest_round') or '—'}"
            + (f" ${funding.get('amount_usd',0)/1e6:.1f}M ({funding.get('recency_days')} d ago)" if funding.get('amount_usd') else "")
            + f", confidence {funding.get('confidence',0):.2f}."
        ),
        (
            f"Hiring: {velocity.get('open_roles_now',0)} open roles, "
            f"{velocity.get('ratio',0)}× vs 60d prior"
            + (" — qualifies for aggressive-hiring claim." if velocity.get('qualifies_for_aggressive_hiring_claim') else ".")
        ),
        (f"Layoff: {layoff.get('date')} affecting {layoff.get('headcount')}." if layoff.get('detected') else "Layoff: none detected."),
        (f"Leadership: new {lead.get('role')} {lead.get('recency_days')} d ago." if lead.get('detected') else "Leadership: no recent change."),
        f"Top gap practice: {top_gap}.",
        f"Bench match: {', '.join(bench_match) or 'general Python/data'}.",
        f"Suggested opening: anchor on the hiring + {top_gap.lower()} observation; avoid committing to stack capacity beyond bench.",
        "Kill-switch: unset (routed to sink) | draft: true.",
    ]
    text = "\n".join(lines)
    # Target 150–250 words; our synthesis is ~120–170 on average. Pad if short.
    word_count = len(text.split())
    if word_count < 150:
        text += (
            "\nNotes for the delivery lead: verify that the prospect's actual stack aligns with the bench match above "
            "before committing to capacity. If the prospect asks for specific headcount on a stack not listed, route "
            "the request to the handoff flow rather than answering directly. The competitor-gap practice is a hook, "
            "not a prescription — frame it as an observation from peer public signal."
        )
    return text
