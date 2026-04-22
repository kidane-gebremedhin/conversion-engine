"""Inbound email reply webhook — normalises provider payloads to `EmailReply`.

Used by the FastAPI server (agent/server.py). For the interim we also allow
fixture-driven replay so the e2e synthetic prospect can be driven without
a real Resend webhook round-trip.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EmailReply:
    trace_id: str
    from_addr: str
    subject: str
    body: str
    in_reply_to: str | None = None
    references: list[str] | None = None
    provider_msg_id: str | None = None


def parse_resend_reply(payload: dict[str, Any]) -> EmailReply:
    """Best-effort parser matching Resend's inbound reply schema."""
    data = payload.get("data", payload)
    headers = {h["name"]: h["value"] for h in data.get("headers", [])}
    trace_id = headers.get("X-Convergine-Trace-Id") or data.get("x_convergine_trace_id") or ""
    return EmailReply(
        trace_id=trace_id,
        from_addr=data.get("from", ""),
        subject=data.get("subject", ""),
        body=data.get("text") or data.get("body_text") or "",
        in_reply_to=headers.get("In-Reply-To"),
        references=(headers.get("References") or "").split() or None,
        provider_msg_id=data.get("message_id"),
    )
