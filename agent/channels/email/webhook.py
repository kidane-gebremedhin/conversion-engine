"""Resend / MailerSend reply-webhook parser.

FastAPI sees the raw request; this module signature-verifies, parses, and
normalizes to `InboundEmail`. Routing to the reply handler happens in
agent/server.py so this stays transport-agnostic.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from agent.config import settings


@dataclass
class InboundEmail:
    from_address: str
    to_address: str
    subject: str
    body_text: str
    thread_id: str | None
    message_id: str
    headers: dict[str, str]


def verify_signature(raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 signature verification. Returns True iff valid."""
    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        return True  # dev mode; no secret configured
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def parse(payload: dict[str, Any]) -> InboundEmail:
    """Normalize a Resend/MailerSend webhook payload into `InboundEmail`.

    The exact JSON shape differs by provider; we accept a minimal common
    subset and pull by key with safe defaults.
    """
    data = payload.get("data", payload)
    return InboundEmail(
        from_address=str(data.get("from") or data.get("sender") or ""),
        to_address=str(data.get("to") or data.get("recipient") or ""),
        subject=str(data.get("subject") or ""),
        body_text=str(data.get("text") or data.get("body") or ""),
        thread_id=data.get("thread_id") or data.get("in_reply_to"),
        message_id=str(data.get("message_id") or data.get("id") or ""),
        headers=dict(data.get("headers") or {}),
    )
