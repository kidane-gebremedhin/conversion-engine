"""Day-0 Cal.com proof: end-to-end test booking against the self-hosted instance.

Steps:
  1. Ensure the `discovery-15` event type exists (idempotent).
  2. List available slots for the next 7 days.
  3. Create one booking for a synthetic prospect at the first slot.
  4. Read the booking back by id; print the confirmation.

When CALCOM_API_KEY is unset, the script runs against the local-file
fallback in agent/calendar/client.py so the Day-0 loop works offline.
Flip to the real server by bringing up `docker compose -f infra/docker-compose.yml up`
and setting CALCOM_API_KEY + CALCOM_USERNAME.
"""
from __future__ import annotations

import datetime as dt
import sys

from agent.calendar.client import CalComClient
from agent.config import settings


def main() -> int:
    client = CalComClient()
    slug = settings.CALCOM_EVENT_TYPE_DISCOVERY_15
    duration = settings.CALCOM_DEFAULT_DURATION_MINUTES

    event_type_id = client.ensure_event_type(slug, duration)
    print(f"→ event type {slug!r} id={event_type_id} ({client.mode})")

    today = dt.date.today()
    slots = client.free_slots(slug, tz="America/New_York", start=today, end=today + dt.timedelta(days=7))
    if not slots:
        print("! no free slots; aborting", file=sys.stderr)
        return 2
    first = slots[0]
    start_iso = first.get("start_local") or first.get("time") or first.get("start")
    print(f"→ first slot: {start_iso}")

    booking = client.create_booking(
        slug,
        prospect_email="daytest@trp1-sink.example",
        start_iso=start_iso,
        duration_minutes=duration,
        prospect_name="Day0 Test",
        prospect_timezone="America/New_York",
    )
    bid = booking.get("booking_id") or booking.get("uid") or ""
    print(f"✓ booked: id={bid}")

    confirmed = client.booking(bid)
    if not confirmed:
        print("! could not read booking back", file=sys.stderr)
        return 3
    print(f"✓ confirmed readback: start_time_utc={confirmed.get('start_time_utc')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
