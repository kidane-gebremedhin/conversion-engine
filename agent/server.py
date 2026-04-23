"""FastAPI server exposing healthz + inbound webhooks.

This is functional but optional for the interim e2e demo. The
`make run PROSPECT=...` path uses fixture replies; the server exists so
the Resend/AT/Cal.com sandbox webhooks can actually wire in when credentials
are present.
"""
from __future__ import annotations

from fastapi import FastAPI

from agent.config import load_config, load_secrets
from agent.channels.email.webhook import parse_resend_reply
from agent.channels.sms.webhook import parse_at_reply

app = FastAPI(title="convergine-agent", version="0.1.0-interim")


@app.get("/healthz")
def healthz() -> dict:
    cfg = load_config()
    secrets = load_secrets()
    return {
        "status": "ok",
        "killswitch_enabled": bool((cfg.get("killswitch") or {}).get("enabled")),
        "llm_mode": secrets.convergine_llm_mode,
        "env": secrets.convergine_env,
    }


@app.post("/webhooks/email/reply")
def email_reply(payload: dict) -> dict:
    reply = parse_resend_reply(payload)
    # Thread lookup would be via reply.in_reply_to / trace_id → state store.
    return {"received": True, "trace_id": reply.trace_id}


@app.post("/webhooks/sms/inbound")
def sms_inbound(payload: dict) -> dict:
    reply = parse_at_reply(payload)
    return {"received": True, "from": reply.from_number}


@app.post("/webhooks/calcom")
def calcom_hook(payload: dict) -> dict:
    return {"received": True, "type": payload.get("triggerEvent", "")}
