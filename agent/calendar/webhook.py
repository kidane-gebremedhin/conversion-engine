"""Cal.com webhook parser + signature verification."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from agent.config import settings


@dataclass
class CalBookingEvent:
    event_type: str
    booking_id: str
    start_time_utc: str
    end_time_utc: str
    prospect_email: str
    prospect_name: str
    prospect_timezone: str
    title: str


def verify_signature(raw_body: bytes, signature: str) -> bool:
    secret = settings.CALCOM_WEBHOOK_SECRET
    if not secret:
        return True
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def parse(payload: dict[str, Any]) -> CalBookingEvent:
    data = payload.get("payload", payload)
    attendees = data.get("attendees") or [{}]
    a0 = attendees[0] if attendees else {}
    return CalBookingEvent(
        event_type=str(payload.get("triggerEvent") or payload.get("event") or "BOOKING_CREATED"),
        booking_id=str(data.get("id") or data.get("uid") or ""),
        start_time_utc=str(data.get("startTime") or data.get("start") or ""),
        end_time_utc=str(data.get("endTime") or data.get("end") or ""),
        prospect_email=str(a0.get("email") or ""),
        prospect_name=str(a0.get("name") or ""),
        prospect_timezone=str(a0.get("timeZone") or data.get("organizer", {}).get("timeZone") or "UTC"),
        title=str(data.get("title") or "Discovery call"),
    )
