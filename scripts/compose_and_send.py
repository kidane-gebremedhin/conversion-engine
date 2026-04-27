"""`make compose-and-send DOMAIN=<domain>` — end-to-end one synthetic prospect.

  1. Enrich → briefs
  2. Compose draft via composer (segment-specific prompt)
  3. Tone check; regenerate ≤1 time on failure
  4. Kill-switch-gated delivery to the sink
  5. HubSpot writes (contact, outbound engagement, brief NOTE)
  6. Langfuse trace links everything

See __specs/06-agent-design.md and __specs/08-hubspot-integration.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent.composer import compose, ComposerError
from agent.config import settings
from agent.enrichment.pipeline import enrich
from agent.hubspot import events as hevents
from agent.hubspot.client import HubSpotClient
from agent.hubspot.schema import ensure_all
from agent.kill_switch import deliver, EmailPayload, add_draft_header
from agent.observability.langfuse import new_trace, span, verify_trace
from agent.tone_check import check as tone_check, log_flagged


PROSPECTS = "data/synthetic_prospects.json"


def load_prospects() -> list[dict[str, object]]:
    p = Path(PROSPECTS)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def find_prospect(domain: str) -> dict[str, object] | None:
    for p in load_prospects():
        if str(p.get("company_domain", "")).lower() == domain.lower():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    args = ap.parse_args()

    prospect = find_prospect(args.domain)
    if not prospect:
        print(f"ERROR: {args.domain!r} not in {PROSPECTS}", file=sys.stderr)
        return 2

    trace = new_trace("compose_and_send", attributes={"prospect.domain": args.domain})

    # ─── enrich ─────────────────────────────────────────────────────────
    out_dir = f"eval/briefs/{args.domain}"
    with span("enrichment", trace=trace):
        brief, gap_brief = enrich(args.domain, write_to=out_dir)

    # ─── compose ─────────────────────────────────────────────────────────
    cal_link = f"{settings.CALCOM_BASE_URL}/{settings.CALCOM_USERNAME or 'tenacious'}/{settings.CALCOM_EVENT_TYPE_DISCOVERY_15}"
    seg = str(brief.primary_segment_match.value if hasattr(brief.primary_segment_match, "value") else brief.primary_segment_match)
    with span("composer", trace=trace) as s:
        try:
            draft = compose(
                segment=seg, brief=brief, gap_brief=gap_brief, prospect=prospect,
                cal_link=cal_link, sequence_position="cold_1",
            )
            s["subject"] = draft.subject
        except ComposerError as e:
            print(f"ERROR: composer failed: {e}", file=sys.stderr)
            return 3

    # ─── tone check ─────────────────────────────────────────────────────
    with span("tone_check", trace=trace) as s:
        result = tone_check(draft.subject, draft.body_text, brief_summary=json.dumps(brief.model_dump(), default=str)[:1200])
        s["scores"] = result.scores
        s["overall_ok"] = result.overall_ok
        if not result.overall_ok:
            # Regenerate once, passing the tone-checker's rewrite_hint so the
            # LLM knows which areas to address (e.g. "soften urgency in opener",
            # "remove fabricated metric in line 3").
            s["rewrite_hint"] = result.rewrite_hint
            draft = compose(
                segment=seg, brief=brief, gap_brief=gap_brief, prospect=prospect,
                cal_link=cal_link, sequence_position="cold_1",
                rewrite_hint=result.rewrite_hint,
            )
            result = tone_check(draft.subject, draft.body_text, brief_summary=json.dumps(brief.model_dump(), default=str)[:1200], regen_count=1)
            if not result.overall_ok:
                log_flagged({"subject": draft.subject, "body_text": draft.body_text, "segment": seg}, result, trace_id=trace.trace_id)
                # Human handoff path — do not send.
                print(f"✗ tone double-fail; logged to eval/runs/tone_flagged.jsonl. No send.")
                return 4

    # ─── HubSpot (idempotent) ───────────────────────────────────────────
    hs_client = HubSpotClient()
    ensure_all(hs_client)

    class _Cl:
        segment = seg
        confidence = brief.segment_confidence

    contact_id = hevents.upsert_contact(
        prospect, brief=brief, classification=_Cl(),
        trace_id=trace.trace_id, kill_switch_sink=not settings.TENACIOUS_OUTBOUND_ENABLED,
    )
    hevents.attach_brief(contact_id, brief_type="hiring_signal", brief_json=brief.model_dump(), brief_url=f"{out_dir}/hiring_signal_brief.json")
    if gap_brief:
        hevents.attach_brief(contact_id, brief_type="competitor_gap", brief_json=gap_brief.model_dump(), brief_url=f"{out_dir}/competitor_gap_brief.json")

    # ─── deliver (kill-switch gate) ─────────────────────────────────────
    payload = add_draft_header(EmailPayload(
        subject=draft.subject,
        body_text=draft.body_text,
        trace_id=trace.trace_id,
    ))
    with span("deliver", trace=trace):
        delivery = deliver("email", str(prospect["prospect_email"]), payload)
    hevents.record_outbound(
        contact_id, {"subject": draft.subject, "body_text": draft.body_text},
        provider_message_id=delivery.message_id, trace_id=trace.trace_id,
        tone_scores=result.scores,
    )

    # Flush the Langfuse queue and trust the SDK's POST result — see
    # agent.observability.langfuse.verify_trace for why we don't poll.
    pushed = verify_trace(trace.trace_id)

    print(f"✓ sent draft for {args.domain}")
    print(f"  subject: {draft.subject}")
    print(f"  words:   {draft.notes}")
    print(f"  sink:    {delivery.sink} ({delivery.provider})")
    print(f"  message: {delivery.message_id}")
    print(f"  trace:   {trace.url()}")
    if pushed:
        print(f"  langfuse: pushed (visible in UI in ~10–15s)")
    else:
        print(f"  langfuse: disabled — see warning above for cause")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
