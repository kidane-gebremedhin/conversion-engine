"""Voice send adapter.

Bonus tier: if VOICE_RIG_BASE_URL is unset, every send is a local-sink no-op.
This keeps dev runs working without the shared rig provisioned.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

from agent.config import settings
from agent.kill_switch import VoicePayload


def send(to: str, payload: VoicePayload) -> tuple[str, str]:
    if not settings.VOICE_RIG_BASE_URL:
        return _send_local_sink(to, payload)
    return _send_rig(to, payload)


def _send_rig(to: str, payload: VoicePayload) -> tuple[str, str]:
    import httpx

    r = httpx.post(
        f"{settings.VOICE_RIG_BASE_URL.rstrip('/')}/calls",
        json={
            "to": to,
            "script": payload.script,
            "callback_url": payload.callback_url,
            "keyword_prefix": settings.VOICE_RIG_KEYWORD_PREFIX,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("call_id", ""), "voice_rig"


def _send_local_sink(to: str, payload: VoicePayload) -> tuple[str, str]:
    path = Path(settings.LOCAL_SINK_DIR) / "voice.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    call_id = f"local-{uuid.uuid4().hex[:12]}"
    record = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "call_id": call_id,
        "to": to,
        "script": payload.script,
        "callback_url": payload.callback_url,
        "trace_id": payload.trace_id,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return call_id, "local_sink"
