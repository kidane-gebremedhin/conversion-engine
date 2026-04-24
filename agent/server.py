"""FastAPI inbound server.

Endpoints:
  GET  /health
  POST /webhook/email  (Resend / MailerSend)
  POST /webhook/sms    (Africa's Talking)
  POST /webhook/voice  (Shared Voice Rig)
  POST /webhook/cal    (Cal.com booking.created)

All bodies are signature-verified where a secret is configured. Routes
normalize inbound payloads and hand off to the reply / booking handlers.
Every response is kill-switch gated.
"""
from __future__ import annotations

import datetime as dt
import json

from fastapi import FastAPI, HTTPException, Request, Header

from agent.channels.email import webhook as email_webhook
from agent.channels.sms import webhook as sms_webhook
from agent.calendar import webhook as cal_webhook
from agent.config import settings
from agent.observability.langfuse import new_trace, span
from agent.reply_handler import classify_reply, compose_warm_reply
from agent.kill_switch import deliver, EmailPayload, SmsPayload, add_draft_header


app = FastAPI(title="Conversion Engine")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "env": settings.ENV,
        "kill_switch": "sink" if not settings.TENACIOUS_OUTBOUND_ENABLED else "live",
        "eval_tier_enabled": settings.EVAL_TIER_ENABLED,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@app.post("/webhook/email")
async def webhook_email(
    request: Request,
    x_resend_signature: str | None = Header(default=None),
) -> dict[str, object]:
    raw = await request.body()
    if not email_webhook.verify_signature(raw, x_resend_signature or ""):
        raise HTTPException(status_code=401, detail="signature verification failed")
    payload = json.loads(raw.decode("utf-8")) if raw else {}
    inbound = email_webhook.parse(payload)
    trace = new_trace("reply.email", attributes={"prospect.email": inbound.from_address})
    with span("reply.classify", trace=trace) as s:
        cl = classify_reply(inbound.body_text)
        s["class"] = cl.class_
        s["confidence"] = cl.confidence
    if cl.suggested_action in ("handoff", "suppress"):
        return {"status": "no_reply", "action": cl.suggested_action, "class": cl.class_, "trace_id": trace.trace_id}
    prospect = {"prospect_email": inbound.from_address, "prospect_name": inbound.from_address, "prospect_timezone": "UTC"}
    reply = compose_warm_reply(
        classification=cl, reply_text=inbound.body_text, prospect=prospect,
        cal_link=f"{settings.CALCOM_BASE_URL}/{settings.CALCOM_USERNAME or 'tenacious'}/{settings.CALCOM_EVENT_TYPE_DISCOVERY_15}",
    )
    payload_out = add_draft_header(EmailPayload(
        subject=str(reply["subject"]),
        body_text=str(reply["body_text"]),
        thread_id=inbound.thread_id,
        trace_id=trace.trace_id,
    ))
    result = deliver("email", inbound.from_address, payload_out)
    return {"status": "replied", "class": cl.class_, "message_id": result.message_id, "trace_id": trace.trace_id}


@app.post("/webhook/sms")
async def webhook_sms(request: Request) -> dict[str, object]:
    print("Webhook callback")
    body = await request.body()
    print(body)
    # Africa's Talking posts form-encoded; accept JSON too.
    try:
        data = json.loads(body.decode("utf-8") or "{}")
        print(f"Callback received")
    except json.JSONDecodeError as e:
        print("Parse error", e)
        from urllib.parse import parse_qs
        qs = parse_qs(body.decode("utf-8"))
        data = {k: v[0] for k, v in qs.items()}
    inbound = sms_webhook.parse(data)
    intent = sms_webhook.classify_intent(inbound.body)
    trace = new_trace("reply.sms", attributes={"prospect.phone": inbound.from_number})
    if intent == "confirm":
        payload = SmsPayload(body="Confirmed. Calendar invite coming by email.", trace_id=trace.trace_id)
    elif intent == "reschedule":
        payload = SmsPayload(body="Happy to move it. Reply with a day or use the Cal link in email.", trace_id=trace.trace_id)
    else:
        # escalate / opt-out / ambiguous
        return {"status": "handoff", "intent": intent, "trace_id": trace.trace_id}
    result = deliver("sms", inbound.from_number, payload)
    return {"status": "replied", "intent": intent, "message_id": result.message_id, "trace_id": trace.trace_id}


@app.post("/webhook/voice")
async def webhook_voice(request: Request) -> dict[str, object]:
    return {"status": "not_implemented"}


@app.post("/webhook/cal")
async def webhook_cal(
    request: Request,
    x_cal_signature_256: str | None = Header(default=None),
) -> dict[str, object]:
    raw = await request.body()
    if not cal_webhook.verify_signature(raw, x_cal_signature_256 or ""):
        raise HTTPException(status_code=401, detail="signature verification failed")
    payload = json.loads(raw.decode("utf-8")) if raw else {}
    evt = cal_webhook.parse(payload)
    trace = new_trace("cal.booking", attributes={"prospect.email": evt.prospect_email})
    # On booking.created we'd synthesize the context brief and attach to the Deal.
    # The real orchestration lives in scripts/compose_and_send.py; this is the
    # webhook surface that a user-facing boot would complete.
    return {
        "status": "received",
        "trigger": evt.event_type,
        "booking_id": evt.booking_id,
        "trace_id": trace.trace_id,
    }
