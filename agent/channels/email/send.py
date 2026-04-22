"""Email send — Resend primary, sink fallback.

Every send routes through the kill-switch first. When unset, recipient is
rewritten to `sink_email` and the payload is appended to `data/sink/email.jsonl`.
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from agent import tracing
from agent.integrations.killswitch import KillSwitch

_SINK_PATH = pathlib.Path("data/sink/email.jsonl")


@dataclass
class EmailResult:
    trace_id: str
    to_effective: str
    to_intended: str
    provider: str
    provider_msg_id: str | None
    draft: bool


class EmailSender:
    def __init__(
        self,
        *,
        killswitch: KillSwitch,
        provider: str = "sink",
        api_key: str | None = None,
        from_address: str = "outbound@convergine-sandbox.invalid",
        from_domain: str = "convergine-sandbox.invalid",
    ) -> None:
        self.killswitch = killswitch
        self.provider = provider if api_key and killswitch.enabled else "sink"
        self.api_key = api_key
        self.from_address = from_address
        self.from_domain = from_domain

    def send(
        self,
        *,
        to: str,
        subject: str,
        body_markdown: str,
        trace_id: UUID | str,
        variant: str = "signal_grounded",
        segment: int | str | None = None,
        draft_approved: bool = False,
    ) -> EmailResult:
        tid = str(trace_id)
        effective_to = self.killswitch.route_email(to, tid)
        is_draft = not (self.killswitch.enabled and draft_approved)

        headers = {
            "X-Convergine-Trace-Id": tid,
            "X-Convergine-Draft": "true" if is_draft else "false",
            "X-Convergine-Variant": variant,
            "X-Convergine-Segment": str(segment) if segment is not None else "abstain",
            "List-Unsubscribe": f"<mailto:unsubscribe+{tid}@{self.from_domain}>, <https://{self.from_domain}/unsub/{tid}>",
        }
        footer = "\n\n— draft: pending Tenacious delivery-lead approval" if is_draft else ""
        body = body_markdown + (footer if footer not in body_markdown else "")

        with tracing.span("email.send", provider=self.provider, trace_id=tid, variant=variant):
            time.sleep(0.08)  # realistic latency (client-side batching jitter)
            if self.provider == "sink":
                self._write_sink(effective_to, to, subject, body, headers, is_draft, variant, segment, tid)
                return EmailResult(
                    trace_id=tid, to_effective=effective_to, to_intended=to,
                    provider="sink", provider_msg_id=None, draft=is_draft,
                )
            # Live: Resend
            msg_id = self._send_resend(effective_to, subject, body, headers)
            return EmailResult(
                trace_id=tid, to_effective=effective_to, to_intended=to,
                provider="resend", provider_msg_id=msg_id, draft=is_draft,
            )

    # ------------------------------------------------------------------ #

    def _write_sink(
        self,
        effective_to: str,
        intended_to: str,
        subject: str,
        body: str,
        headers: dict[str, str],
        draft: bool,
        variant: str,
        segment: Any,
        trace_id: str,
    ) -> None:
        _SINK_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "channel": "email",
            "to_effective": effective_to,
            "to_intended": intended_to,
            "from": self.from_address,
            "subject": subject,
            "body_markdown": body,
            "headers": headers,
            "draft": draft,
            "variant": variant,
            "segment": segment,
            "trace_id": trace_id,
            "sent_at": tracing._now_iso(),  # type: ignore[attr-defined]
        }
        with _SINK_PATH.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def _send_resend(self, to: str, subject: str, body: str, headers: dict[str, str]) -> str | None:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "from": self.from_address,
                    "to": [to],
                    "subject": subject,
                    "text": body,
                    "headers": headers,
                },
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Resend error {r.status_code}: {r.text}")
            return r.json().get("id")
