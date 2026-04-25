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
from urllib.parse import parse_qs

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
    svix_id: str | None = Header(default=None, alias="svix-id"),
    svix_timestamp: str | None = Header(default=None, alias="svix-timestamp"),
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
) -> dict[str, object]:
    print("email webhook callback")
    raw = await request.body()
    print(raw)
    if not email_webhook.verify_signature(
        raw, svix_id or "", svix_timestamp or "", svix_signature or ""
    ):
        raise HTTPException(status_code=401, detail="signature verification failed")
    payload = json.loads(raw.decode("utf-8")) if raw else {}
    inbound = email_webhook.parse(payload)
    # Resend posts outbound telemetry (email.sent, email.delivered, email.bounced,
    # email.opened, ...) and inbound replies to the same webhook URL. Only inbound
    # events carry a body; everything else is delivery telemetry we just ack.
    event_type = str(payload.get("type") or "")
    if not inbound.body_text:
        return {"status": "noted", "type": event_type or "unknown"}
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
    print("SMS Callback")
    body = await request.body()
    print(body)
    # Africa's Talking posts form-encoded; JSON is accepted for test fixtures.
    content_type = request.headers.get("content-type", "").lower()
    if "application/x-www-form-urlencoded" in content_type:
        qs = parse_qs(body.decode("utf-8"))
        data = {k: v[0] for k, v in qs.items()}
    else:
        data = json.loads(body.decode("utf-8") or "{}") if body else {}
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
    print('resultresultresultresultresult')
    print(result)
    return {"status": "replied", "intent": intent, "message_id": result.message_id, "trace_id": trace.trace_id}


@app.post("/webhook/voice")
async def webhook_voice(request: Request) -> dict[str, object]:
    return {"status": "not_implemented"}


@app.post("/webhook/cal")
async def webhook_cal(
    request: Request,
    x_cal_signature_256: str | None = Header(default=None),
) -> dict[str, object]:
    print("Cal webhook callback")
    raw = await request.body()
    print(raw)
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
