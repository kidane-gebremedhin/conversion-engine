"""Agent orchestrator — state machine driving the COLD → BOOKED flow.

For the interim, the orchestrator works in two modes:

- **fixture mode** (default in the e2e demo): a synthetic prospect's reply is
  provided as a canned string from `tests/fixtures/synthetic_prospects.yaml`,
  so the machine runs end-to-end without live email round-trips.

- **webhook mode**: the FastAPI server feeds inbound replies in through
  `handle_email_reply` / `handle_sms_reply` and `handle_calcom_booked`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from agent import tracing
from agent.channels.email.render import render as render_email
from agent.channels.email.send import EmailSender
from agent.channels.sms.send import SmsSender
from agent.enrichment.pipeline import EnrichmentResult, enrich
from agent.integrations.calcom import CalcomClient, build_context_brief
from agent.integrations.hubspot_mcp import (
    CompanyUpsert,
    ContactUpsert,
    ConversationEvent,
    DealCreate,
    HubSpotClient,
)
from agent.llm.client import LlmClient
from agent.policies import bench, channel_handoff, confidence, tone
from agent.state import (
    EmailReplyIntent,
    Prospect,
    Stage,
    ThreadState,
    Variant,
)


_TENACIOUS_LEAD_EMAIL = "delivery-lead-a@tenacious-sandbox.invalid"

# ACV midpoints per segment (for Deal `amount`)
_ACV_MIDPOINTS = {1: 360_000, 2: 480_000, 3: 400_000, 4: 190_000, None: 240_000}


@dataclass
class OrchestratorDeps:
    llm: LlmClient
    email: EmailSender
    sms: SmsSender
    hubspot: HubSpotClient
    calcom: CalcomClient


class Orchestrator:
    def __init__(self, deps: OrchestratorDeps) -> None:
        self.deps = deps

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    def run_cold(self, prospect: Prospect) -> ThreadState:
        """Run enrichment + first outbound. Returns the thread in COLD (post-send)."""
        with tracing.trace(
            "agent.run_cold",
            tags={
                "thread_id": None,
                "crunchbase_uuid": prospect.uuid,
                "killswitch_enabled": self.deps.email.killswitch.enabled,
                "method_name": "day1_baseline",
            },
        ) as tr:
            result = enrich(prospect.uuid)
            state = ThreadState(
                prospect_uuid=prospect.uuid,
                contact_email=prospect.contact_email,
                segment=result.icp.segment,
                icp_mode=result.icp.mode,
                variant=Variant.SIGNAL_GROUNDED if result.icp.mode == "confident" else Variant.EXPLORATORY,
                preferred_channel=prospect.preferred_channel,
            )
            tr.tags["thread_id"] = str(state.thread_id)

            company_id = self._upsert_crm(prospect, result)
            contact_id = self.deps.hubspot.upsert_contact(
                ContactUpsert(
                    email=str(prospect.contact_email),
                    first_name=prospect.contact_first,
                    last_name=prospect.contact_last,
                    job_title=prospect.contact_role,
                    company_id=company_id,
                    preferred_channel=prospect.preferred_channel,
                    synthetic=prospect.synthetic,
                )
            )
            state.history.append({"hubspot_company_id": company_id, "hubspot_contact_id": contact_id})
            self._log_crm(state, contact_id, company_id, "segment_assigned", {
                "segment": result.icp.segment, "mode": result.icp.mode, "confidence": result.icp.confidence,
            })

            # Draft + gate + send
            self._send_outbound(state, prospect, result, template=_template_for_cold(state.variant))
            tracing.set_outcome(stage_final=state.stage.value, segment=state.segment, variant=state.variant.value)
            return state

    def handle_email_reply(
        self, state: ThreadState, prospect: Prospect, reply_body: str
    ) -> ThreadState:
        """Classify a reply and advance the state machine accordingly."""
        with tracing.trace(
            "agent.handle_reply",
            tags={
                "thread_id": str(state.thread_id),
                "crunchbase_uuid": prospect.uuid,
                "killswitch_enabled": self.deps.email.killswitch.enabled,
                "method_name": "day1_baseline",
            },
        ):
            intent = self._classify_reply(reply_body)
            state.push("prospect", reply_body, intent=intent.model_dump())
            result = enrich(prospect.uuid)

            # Policy: handoff first
            hand = channel_handoff.decide(
                current="email",
                reply_intent=intent.intent,
                preferred_channel=intent.extracted.get("preferred_channel"),
                thread_age_hours=_age_hours(state),
                stage=state.stage.value,
            )

            if intent.intent == "unsubscribe":
                state.stage = Stage.STOP
                tracing.set_outcome(stage_final=state.stage.value)
                return state

            if hand.next_channel == "human":
                state.stage = Stage.HUMAN_HANDOFF
                self._log_crm(state, None, None, "handoff_human", {"reason": hand.reason})
                tracing.set_outcome(stage_final=state.stage.value)
                return state

            if intent.intent == "interested" and intent.confidence >= 0.7:
                state.stage = Stage.QUALIFIED
                self._log_crm(state, None, None, "segment_assigned", {"qualified": True})
                # offer schedule
                return self._offer_scheduling(state, prospect, result)

            if intent.intent == "scheduling_question":
                state.stage = Stage.SCHEDULING
                return self._offer_scheduling(state, prospect, result)

            if intent.intent == "objection":
                state.stage = Stage.CLOSED_LOST
                tracing.set_outcome(stage_final=state.stage.value)
                return state

            # Everything else — stay warm, nurture
            state.stage = Stage.NURTURE_1
            tracing.set_outcome(stage_final=state.stage.value)
            return state

    def handle_calcom_booked(self, state: ThreadState, prospect: Prospect, booking: dict) -> ThreadState:
        state.stage = Stage.BOOKED
        state.push("system", "calcom.booked", booking=booking)
        self._log_crm(state, None, None, "call_booked", booking)
        self._send_post_book_confirmation(state, prospect, booking)
        state.stage = Stage.HANDED_OFF
        return state

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _upsert_crm(self, prospect: Prospect, result: EnrichmentResult) -> str:
        convergine = {
            "icp_segment": result.icp.segment or "",
            "icp_mode": result.icp.mode,
            "icp_confidence": result.icp.confidence,
            "ai_maturity_score": result.maturity.score,
            "ai_maturity_confidence": result.maturity.confidence,
            "enrichment_timestamp": result.brief.generated_at.isoformat(),
            "brief_url": f"data/briefs_cache/{prospect.uuid}/hiring_signal_brief.json",
            "gap_brief_url": f"data/briefs_cache/{prospect.uuid}/competitor_gap_brief.json",
        }
        return self.deps.hubspot.upsert_company(
            CompanyUpsert(
                crunchbase_uuid=prospect.uuid,
                name=prospect.company_name,
                domain=prospect.crunchbase.domain,
                industry=(prospect.crunchbase.industries or [None])[0],
                country=prospect.crunchbase.country,
                employees=prospect.crunchbase.employee_count_range,
                convergine=convergine,
            )
        )

    def _send_outbound(
        self,
        state: ThreadState,
        prospect: Prospect,
        result: EnrichmentResult,
        *,
        template: str,
    ) -> None:
        # Render template
        slot_sugg = _suggest_slot(prospect.contact_timezone)
        ctx = {
            "subject": _default_subject(state.variant),
            "prospect": prospect,
            "brief": result.brief,
            "signals": result.brief.signals,
            "gap_practices": [g.model_dump() for g in result.gap.gap_practices],
            "slot_suggestion": slot_sugg,
            "prior_subject": "Your recent hiring pace — a quick observation",
        }
        subject, body = render_email(template, **ctx)

        # Policy gates
        tone_res = tone.check(body, llm=self.deps.llm)
        bench_res = bench.check(body)
        conf_res = confidence.check(body, brief_signals=result.brief.signals)
        if not bench_res.passed:
            self._log_crm(state, None, None, "handoff_human", {
                "reason": "bench_overclaim", "flagged": bench_res.flagged
            })
            state.stage = Stage.HUMAN_HANDOFF
            return
        if not conf_res.passed:
            # Strip the offending phrase and retry once (simple mitigation).
            body = _strip_aggressive_hiring(body)

        draft_approved = False  # draft discipline: never approved in interim
        email_res = self.deps.email.send(
            to=str(prospect.contact_email),
            subject=subject,
            body_markdown=body,
            trace_id=state.thread_id,
            variant=state.variant.value,
            segment=state.segment if state.segment is not None else "abstain",
            draft_approved=draft_approved,
        )

        state.push("agent", body, subject=subject, email_result=email_res.__dict__)
        self._log_crm(state, None, None, "email_sent", {
            "subject": subject,
            "to_effective": email_res.to_effective,
            "variant": state.variant.value,
            "draft": email_res.draft,
            "tone_pass": tone_res.passed,
        })

    def _classify_reply(self, body: str) -> EmailReplyIntent:
        system = "You classify B2B outreach replies. Return JSON only."
        user = f"STAGE=classify_reply\nBODY:\n{body}"
        with tracing.span("agent.prompt.classify_reply", stage="classify_reply"):
            resp = self.deps.llm.complete(system=system, user=user, stage="classify_reply", response_format="json")
        try:
            data = json.loads(resp.text)
        except json.JSONDecodeError:
            return EmailReplyIntent(intent="off_topic", confidence=0.0, extracted={})
        return EmailReplyIntent(**data)

    def _offer_scheduling(self, state: ThreadState, prospect: Prospect, result: EnrichmentResult) -> ThreadState:
        slots = self.deps.calcom.available_slots(
            "discovery-30",
            from_=datetime.now(timezone.utc) + timedelta(days=1),
            to=datetime.now(timezone.utc) + timedelta(days=7),
            timezone_=prospect.contact_timezone,
        )
        slot_1 = slots[0].start.strftime("%A %Y-%m-%d %H:%M %Z") if slots else "TBD"
        slot_2 = slots[1].start.strftime("%A %Y-%m-%d %H:%M %Z") if len(slots) > 1 else "TBD"
        subject, body = render_email(
            "scheduling_offer.j2",
            subject="Re: scheduling",
            prior_subject="discovery call",
            prospect=prospect,
            calcom_url="http://localhost:3000/tenacious/discovery-30",
            slot_1=slot_1,
            slot_2=slot_2,
        )
        res = self.deps.email.send(
            to=str(prospect.contact_email),
            subject=subject,
            body_markdown=body,
            trace_id=state.thread_id,
            variant=state.variant.value,
            segment=state.segment if state.segment is not None else "abstain",
        )
        state.push("agent", body, subject=subject, email_result=res.__dict__)
        state.stage = Stage.SCHEDULING

        # Auto-book the first slot for the synthetic demo.
        if slots:
            brief_md = build_context_brief(
                prospect=prospect,
                brief=result.brief,
                maturity=result.maturity,
                gap=result.gap,
                icp=result.icp,
                bench_match=result.brief.signals.get("tech_stack", {}).get("bench_matches", []),
            )
            booking = self.deps.calcom.book(
                event_type_slug="discovery-30",
                start=slots[0].start,
                attendee_email=str(prospect.contact_email),
                attendee_name=f"{prospect.contact_first} {prospect.contact_last}",
                attendee_timezone=prospect.contact_timezone,
                metadata={
                    "crunchbase_uuid": prospect.uuid,
                    "thread_id": str(state.thread_id),
                    "trace_id": str(state.thread_id),
                    "segment": state.segment,
                    "variant": state.variant.value,
                    "draft": True,
                },
                context_brief_md=brief_md,
            )
            deal_id = self.deps.hubspot.create_deal(
                DealCreate(
                    company_id=prospect.uuid,  # local store keys companies by uuid
                    contact_id=str(prospect.contact_email).replace("@", "_at_"),
                    dealname=f"Convergine discovery – {prospect.company_name}",
                    amount=_ACV_MIDPOINTS.get(state.segment, _ACV_MIDPOINTS[None]),
                    convergine_segment=state.segment,
                    convergine_thread_id=str(state.thread_id),
                )
            )
            state.history.append({"hubspot_deal_id": deal_id})
            self.handle_calcom_booked(state, prospect, {
                "booking_id": booking.booking_id,
                "start": booking.start.isoformat(),
                "end": booking.end.isoformat(),
                "event_type_slug": booking.event_type_slug,
                "attendee_email": booking.attendee_email,
            })
        tracing.set_outcome(stage_final=state.stage.value)
        return state

    def _send_post_book_confirmation(self, state: ThreadState, prospect: Prospect, booking: dict) -> None:
        subject, body = render_email(
            "post_book_confirmation.j2",
            prospect=prospect,
            booking={"start_local": booking.get("start", "")},
        )
        self.deps.email.send(
            to=str(prospect.contact_email),
            subject=subject,
            body_markdown=body,
            trace_id=state.thread_id,
            variant=state.variant.value,
            segment=state.segment if state.segment is not None else "abstain",
        )
        state.push("agent", body, subject=subject)

    def _log_crm(
        self, state: ThreadState, contact_id: str | None, company_id: str | None,
        event_type: str, payload: dict[str, Any],
    ) -> None:
        self.deps.hubspot.log_event(
            ConversationEvent(
                event_id=str(uuid4()),
                contact_id=contact_id or "",
                company_id=company_id or "",
                event_type=event_type,
                channel="email",
                trace_id=str(state.thread_id),
                payload_json=payload,
                draft=True,
            )
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _age_hours(state: ThreadState) -> float:
    return (datetime.now(timezone.utc) - state.last_activity_at).total_seconds() / 3600.0


def _template_for_cold(variant: Variant) -> str:
    return "cold_signal_grounded.j2" if variant == Variant.SIGNAL_GROUNDED else "cold_exploratory.j2"


def _default_subject(variant: Variant) -> str:
    return (
        "Your recent hiring pace — a quick observation"
        if variant == Variant.SIGNAL_GROUNDED
        else "Brief note on sector benchmarks"
    )


def _suggest_slot(tz: str) -> str:
    # Next Thursday 14:00 in the prospect's TZ, as a string.
    now = datetime.now(timezone.utc)
    days_ahead = (3 - now.weekday()) % 7 or 7  # 3 = Thursday
    proposed = now + timedelta(days=days_ahead)
    return f"Thursday {proposed.date().isoformat()} at 14:00 {tz}"


def _strip_aggressive_hiring(body: str) -> str:
    import re as _re
    return _re.sub(r"(?i)aggressive\s+hiring", "expanding hiring", body)
