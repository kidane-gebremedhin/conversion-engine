"""Resend / MailerSend reply-webhook parser.

FastAPI sees the raw request; this module signature-verifies, parses, and
normalizes to `InboundEmail`. Routing to the reply handler happens in
agent/server.py so this stays transport-agnostic.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

from agent.config import settings


# Reject Svix-signed webhooks whose timestamp is more than this many seconds
# off from now. Defends against captured-payload replay; matches Svix's
# default tolerance.
_SVIX_TIMESTAMP_TOLERANCE_SECS = 5 * 60


@dataclass
class InboundEmail:
    from_address: str
    to_address: str
    subject: str
    body_text: str
    thread_id: str | None
    message_id: str
    headers: dict[str, str]


def verify_signature(
    raw_body: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
) -> bool:
    """Verify a Resend webhook signature using the Svix scheme.

    Resend signs its webhooks via Svix. The signed payload is

        {svix_id}.{svix_timestamp}.{raw_body}

    HMAC-SHA256'd with the secret. The `svix-signature` header carries one
    or more `v<n>,<base64-sig>` entries separated by spaces; we accept the
    request if any v1 entry matches.

    The configured `RESEND_WEBHOOK_SECRET` typically begins with `whsec_`
    followed by base64-encoded key bytes (Svix convention). A bare-string
    secret is also accepted for environments that don't use the prefix.

    Returns True if no secret is configured (dev mode).
    """
    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        return True
    if not (svix_id and svix_timestamp and svix_signature):
        return False
    try:
        ts = int(svix_timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - ts) > _SVIX_TIMESTAMP_TOLERANCE_SECS:
        return False
    if secret.startswith("whsec_"):
        try:
            key = base64.b64decode(secret[len("whsec_"):])
        except (binascii.Error, ValueError):
            return False
    else:
        key = secret.encode()
    signed = f"{svix_id}.{svix_timestamp}.".encode() + raw_body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    for entry in svix_signature.split():
        if "," not in entry:
            continue
        version, sig = entry.split(",", 1)
        if version == "v1" and hmac.compare_digest(sig, expected):
            return True
    return False


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
