"""Inbound SMS webhook — Africa's Talking sandbox schema → `SmsReply`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SmsReply:
    from_number: str
    shortcode: str
    body: str
    provider_msg_id: str | None = None


def parse_at_reply(payload: dict[str, Any]) -> SmsReply:
    return SmsReply(
        from_number=payload.get("from") or "",
        shortcode=payload.get("to") or "",
        body=payload.get("text", ""),
        provider_msg_id=payload.get("id"),
    )
