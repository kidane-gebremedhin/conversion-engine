"""SMS inbound webhook parser with a tiny three-intent classifier.

Africa's Talking posts form-encoded payloads; we accept JSON too for test
fixtures. The classifier lives here because the rule set is small.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class InboundSms:
    from_number: str
    to_number: str
    body: str
    message_id: str


_CONFIRM_PATTERNS = (r"\byes\b", r"\bconfirm\b", r"\bworks\b", r"\bgood\b", r"\bok\b", r"\bsounds good\b")
_RESCHEDULE_PATTERNS = (r"\breschedul", r"\bmove\b", r"\bchange\b", r"\bdifferent time", r"\blater\b", r"\bearlier\b")
_ESCALATE_PATTERNS = (r"\bstop\b", r"\bunsubscribe\b", r"\bopt.?out\b", r"\bnot interested\b", r"\btake me off\b")


def classify_intent(body: str) -> str:
    low = (body or "").lower()
    if any(re.search(p, low) for p in _ESCALATE_PATTERNS):
        return "escalate_or_optout"
    if any(re.search(p, low) for p in _RESCHEDULE_PATTERNS):
        return "reschedule"
    if any(re.search(p, low) for p in _CONFIRM_PATTERNS):
        return "confirm"
    return "ambiguous"


def parse(payload: dict[str, Any]) -> InboundSms:
    return InboundSms(
        from_number=str(payload.get("from") or payload.get("From") or ""),
        to_number=str(payload.get("to") or payload.get("To") or ""),
        body=str(payload.get("text") or payload.get("body") or payload.get("Body") or ""),
        message_id=str(payload.get("id") or payload.get("messageId") or ""),
    )
