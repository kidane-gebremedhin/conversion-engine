"""SMS send adapter via Africa's Talking (sandbox).

Enforces: body ≤160 chars, ASCII-only (no emoji), no marketing language.
Falls back to a local JSONL sink when creds are absent.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from agent.config import settings
from agent.kill_switch import SmsPayload, PolicyViolation


MAX_BODY_CHARS = 160

_FORBIDDEN_WORDS = (
    "act now", "limited offer", "free gift", "click here", "congratulations",
    "best deal", "guaranteed",
)


def _validate_body(body: str) -> None:
    if len(body) > MAX_BODY_CHARS:
        raise PolicyViolation(
            f"SMS body length {len(body)} > {MAX_BODY_CHARS} char limit. "
            "SMS is warm-scheduling only; long-form content belongs in email."
        )
    if not body.isascii():
        raise PolicyViolation("SMS body must be ASCII (no emoji, no extended chars).")
    low = body.lower()
    for phrase in _FORBIDDEN_WORDS:
        if phrase in low:
            raise PolicyViolation(f"SMS body contains marketing language: {phrase!r}")


def send(to: str, payload: SmsPayload) -> tuple[str, str]:
    _validate_body(payload.body)
    if settings.AT_API_KEY and settings.AT_USERNAME:
        return _send_africas_talking(to, payload)
    return _send_local_sink(to, payload)


def _send_africas_talking(to: str, payload: SmsPayload) -> tuple[str, str]:
    import httpx

    data = {
        "username": settings.AT_USERNAME,
        "to": to,
        "message": payload.body,
    }
    if settings.AT_SHORT_CODE:
        data["from"] = settings.AT_SHORT_CODE
    headers = {
        "apiKey": settings.AT_API_KEY,
        "Accept": "application/json",
    }
    base = (
        "https://api.sandbox.africastalking.com/version1/messaging"
        if settings.AT_USERNAME == "sandbox"
        else "https://api.africastalking.com/version1/messaging"
    )
    r = httpx.post(base, data=data, headers=headers, timeout=30)
    r.raise_for_status()
    resp = r.json().get("SMSMessageData", {}).get("Recipients", [])
    mid = resp[0].get("messageId", "") if resp else ""
    return mid, "africas_talking"


def _send_local_sink(to: str, payload: SmsPayload) -> tuple[str, str]:
    path = Path(settings.LOCAL_SINK_DIR) / "sms.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    message_id = f"local-{uuid.uuid4().hex[:12]}"
    record: dict[str, Any] = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "message_id": message_id,
        "to": to,
        "from": settings.AT_SHORT_CODE,
        "body": payload.body,
        "thread_id": payload.thread_id,
        "trace_id": payload.trace_id,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return message_id, "local_sink"
