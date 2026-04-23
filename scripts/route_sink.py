"""Tiny FastAPI app that receives sink email/SMS webhooks — used for demo screenshots.

Optional. The main orchestrator writes directly to `data/sink/*.jsonl` without
needing this app to be running. This exists so the challenge-prescribed
"staff-controlled sink" exists as an addressable service during the week.
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="convergine-sink", version="0.1.0-interim")


@app.post("/sink/email")
def sink_email(payload: dict) -> dict:
    return {"received": True, "channel": "email", "to": payload.get("to")}


@app.post("/sink/sms")
def sink_sms(payload: dict) -> dict:
    return {"received": True, "channel": "sms", "to": payload.get("to")}
