"""SMS send — Africa's Talking primary, sink fallback.

160-char hard cap, sentence-boundary split for longer bodies. Every send
routes through the kill-switch.
"""
from __future__ import annotations

import json
import pathlib
import re
import time
from dataclasses import dataclass
from uuid import UUID

import httpx

from agent import tracing
from agent.integrations.killswitch import KillSwitch


_SINK = pathlib.Path("data/sink/sms.jsonl")
_SMS_MAX = 160


class SmsBodyTooLong(Exception):
    pass


@dataclass
class SmsResult:
    trace_id: str
    to_effective: str
    to_intended: str
    provider: str
    parts: list[str]
    draft: bool


class SmsSender:
    def __init__(
        self,
        *,
        killswitch: KillSwitch,
        provider: str = "sink",
        username: str = "sandbox",
        api_key: str | None = None,
        shortcode: str = "22222",
    ) -> None:
        self.killswitch = killswitch
        self.provider = provider if api_key and killswitch.enabled else "sink"
        self.username = username
        self.api_key = api_key
        self.shortcode = shortcode

    def send(self, *, to: str, body: str, trace_id: UUID | str, draft_approved: bool = False) -> SmsResult:
        tid = str(trace_id)
        effective_to = self.killswitch.route_sms(to, tid)
        is_draft = not (self.killswitch.enabled and draft_approved)
        prefix = "[DRAFT] " if is_draft else ""

        parts = _split_160(body, prefix=prefix)
        if any(len(p) > _SMS_MAX for p in parts):
            raise SmsBodyTooLong(f"part exceeds {_SMS_MAX} chars")

        with tracing.span("sms.send", provider=self.provider, trace_id=tid):
            time.sleep(0.06)
            if self.provider == "sink":
                self._write_sink(effective_to, to, parts, is_draft, tid)
            else:
                self._send_at(effective_to, parts)

        return SmsResult(
            trace_id=tid, to_effective=effective_to, to_intended=to,
            provider=self.provider, parts=parts, draft=is_draft,
        )

    def _write_sink(self, effective_to: str, intended_to: str, parts: list[str], draft: bool, tid: str) -> None:
        _SINK.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "channel": "sms",
            "to_effective": effective_to,
            "to_intended": intended_to,
            "shortcode": self.shortcode,
            "parts": parts,
            "draft": draft,
            "trace_id": tid,
            "sent_at": tracing._now_iso(),  # type: ignore[attr-defined]
        }
        with _SINK.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def _send_at(self, to: str, parts: list[str]) -> None:
        body = "\n".join(parts)
        with httpx.Client(timeout=30) as c:
            r = c.post(
                "https://api.sandbox.africastalking.com/version1/messaging",
                headers={"apiKey": self.api_key or "", "Accept": "application/json"},
                data={"username": self.username, "to": to, "message": body, "from": self.shortcode},
            )
            r.raise_for_status()


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_160(body: str, *, prefix: str = "") -> list[str]:
    """Split on sentence boundaries, then pack into ≤160-char parts with (i/n) markers."""
    body = body.strip()
    if len(prefix + body) <= _SMS_MAX:
        return [prefix + body]

    sentences = [s for s in _SENT_SPLIT.split(body) if s]
    chunks: list[str] = []
    cur = prefix
    for s in sentences:
        # Reserve ~7 chars for " (i/n)" marker.
        if len(cur) + len(s) + 8 <= _SMS_MAX:
            cur = (cur + " " + s).strip() if cur.strip() != prefix.strip() else prefix + s
        else:
            if cur.strip():
                chunks.append(cur.strip())
            cur = prefix + s
    if cur.strip():
        chunks.append(cur.strip())
    total = len(chunks)
    return [f"{c} ({i+1}/{total})" for i, c in enumerate(chunks)]
