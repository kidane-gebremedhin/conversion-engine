"""Email send adapter.

Invoked only by agent.kill_switch.deliver() — this is the thin provider edge.
On missing provider credentials, writes to a local JSONL sink so the agent
runs end-to-end in offline dev. The kill switch has already asserted the
recipient allowlist and the draft header before this is called.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from agent.config import settings
from agent.kill_switch import EmailPayload


def send(to: str, payload: EmailPayload) -> tuple[str, str]:
    """Send an email. Returns (message_id, provider)."""
    provider = settings.EMAIL_PROVIDER.lower()
    if provider == "resend" and settings.RESEND_API_KEY:
        return _send_resend(to, payload)
    if provider == "mailersend" and settings.MAILERSEND_API_KEY:
        return _send_mailersend(to, payload)
    return _send_local_sink(to, payload)


def _send_resend(to: str, payload: EmailPayload) -> tuple[str, str]:
    import httpx

    body = {
        "from": settings.RESEND_FROM_ADDRESS,
        "to": [to],
        "subject": payload.subject,
        "text": payload.body_text,
        "headers": dict(payload.headers),
    }
    if payload.body_html:
        body["html"] = payload.body_html
    if payload.reply_to:
        body["reply_to"] = payload.reply_to
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    r = httpx.post("https://api.resend.com/emails", json=body, headers=headers, timeout=30)
    if r.status_code >= 400:
        # Surface Resend's response body — httpx's default error swallows it.
        raise RuntimeError(
            f"Resend rejected the request ({r.status_code}): {r.text} "
            f"(from={settings.RESEND_FROM_ADDRESS!r}, to={to!r})"
        )
    return r.json().get("id", ""), "resend"


def _send_mailersend(to: str, payload: EmailPayload) -> tuple[str, str]:
    import httpx

    body = {
        "from": {"email": settings.RESEND_FROM_ADDRESS},
        "to": [{"email": to}],
        "subject": payload.subject,
        "text": payload.body_text,
        "headers": [{"name": k, "value": v} for k, v in payload.headers.items()],
    }
    if payload.body_html:
        body["html"] = payload.body_html
    headers = {
        "Authorization": f"Bearer {settings.MAILERSEND_API_KEY}",
        "Content-Type": "application/json",
    }
    r = httpx.post("https://api.mailersend.com/v1/email", json=body, headers=headers, timeout=30)
    r.raise_for_status()
    mid = r.headers.get("x-message-id", "")
    return mid, "mailersend"


def _send_local_sink(to: str, payload: EmailPayload) -> tuple[str, str]:
    path = Path(settings.LOCAL_SINK_DIR) / "email.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    message_id = f"local-{uuid.uuid4().hex[:12]}"
    record: dict[str, Any] = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "message_id": message_id,
        "to": to,
        "from": settings.RESEND_FROM_ADDRESS,
        "subject": payload.subject,
        "body_text": payload.body_text,
        "headers": dict(payload.headers),
        "thread_id": payload.thread_id,
        "trace_id": payload.trace_id,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return message_id, "local_sink"
