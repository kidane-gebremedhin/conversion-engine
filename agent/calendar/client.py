"""Cal.com client — event-type setup, slot discovery, booking lookup.

Local-file fallback when CALCOM_API_KEY unset. See __specs/09-calendar-booking.md.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from agent.config import settings


class CalComClient:
    def __init__(self) -> None:
        self.api_key = settings.CALCOM_API_KEY
        self.base_url = settings.CALCOM_BASE_URL.rstrip("/")
        self.mode = "rest" if self.api_key else "local"
        if self.mode == "local":
            self._local_dir = Path("data/calcom_local")
            self._local_dir.mkdir(parents=True, exist_ok=True)

    def healthcheck(self) -> bool:
        if self.mode == "local":
            return True
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/api/v1/me", headers=self._headers(), timeout=15)
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def ensure_event_type(self, slug: str, duration_minutes: int) -> str:
        if self.mode == "local":
            path = self._local_dir / "event_types.json"
            existing = json.loads(path.read_text()) if path.exists() else []
            if any(e.get("slug") == slug for e in existing):
                return next(e["id"] for e in existing if e["slug"] == slug)
            eid = f"et-{uuid.uuid4().hex[:12]}"
            existing.append({"id": eid, "slug": slug, "duration_minutes": duration_minutes})
            path.write_text(json.dumps(existing, indent=2))
            return eid
        # REST: Cal.com v1 event-types POST
        import httpx
        r = httpx.post(
            f"{self.base_url}/api/v1/event-types",
            headers=self._headers(),
            json={"slug": slug, "length": duration_minutes, "title": slug.replace("-", " ").title()},
            timeout=15,
        )
        if r.status_code == 200 or r.status_code == 201:
            return str(r.json().get("event_type", {}).get("id", ""))
        return ""

    def free_slots(self, slug: str, *, tz: str, start: dt.date, end: dt.date) -> list[dict[str, Any]]:
        if self.mode == "local":
            # Produce deterministic 09:00 + 14:00 slots in prospect TZ for the next 5 weekdays
            slots: list[dict[str, Any]] = []
            d = start
            while d <= end and len(slots) < 10:
                if d.weekday() < 5:
                    for h in (9, 14):
                        start_ts = dt.datetime.combine(d, dt.time(h, 0))
                        slots.append({"start_local": start_ts.isoformat(), "timezone": tz})
                d += dt.timedelta(days=1)
            return slots
        import httpx
        r = httpx.get(
            f"{self.base_url}/api/v1/slots",
            headers=self._headers(),
            params={"eventTypeSlug": slug, "startTime": start.isoformat(), "endTime": end.isoformat(), "timeZone": tz},
            timeout=15,
        )
        return r.json().get("slots", [])

    def create_booking(self, slug: str, *, prospect_email: str, start_iso: str, duration_minutes: int, prospect_name: str, prospect_timezone: str) -> dict[str, Any]:
        if self.mode == "local":
            b = {
                "booking_id": f"bk-{uuid.uuid4().hex[:12]}",
                "slug": slug,
                "prospect_email": prospect_email,
                "prospect_name": prospect_name,
                "prospect_timezone": prospect_timezone,
                "start_time_utc": start_iso,
                "end_time_utc": (dt.datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                                 + dt.timedelta(minutes=duration_minutes)).isoformat(),
                "lead_email": settings.CALCOM_DEFAULT_DELIVERY_LEAD,
                "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            path = self._local_dir / "bookings.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(b) + "\n")
            return b
        import httpx
        r = httpx.post(
            f"{self.base_url}/api/v1/bookings",
            headers=self._headers(),
            json={
                "eventTypeSlug": slug, "start": start_iso, "timeZone": prospect_timezone,
                "responses": {"email": prospect_email, "name": prospect_name},
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def booking(self, booking_id: str) -> dict[str, Any] | None:
        if self.mode == "local":
            path = self._local_dir / "bookings.jsonl"
            if not path.exists():
                return None
            with open(path, encoding="utf-8") as f:
                for line in f:
                    b = json.loads(line)
                    if b.get("booking_id") == booking_id:
                        return b
            return None
        import httpx
        r = httpx.get(f"{self.base_url}/api/v1/bookings/{booking_id}", headers=self._headers(), timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
