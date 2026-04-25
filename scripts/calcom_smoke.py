"""Day-0 Cal.com proof: webhook-only readiness (no API access required).

Self-hosted Cal.com gates API keys behind a commercial license, so this
project's Cal.com integration is webhook-only:
  - Outbound: emails embed a public booking link (cal_link).
  - Inbound:  Cal.com posts BOOKING_CREATED to /webhook/cal.

This script verifies that surface:
  1. CALCOM_USERNAME is set (else the booking link in emails resolves nowhere).
  2. CALCOM_BASE_URL is reachable.
  3. Both event-type booking pages (discovery-15, discovery-30) resolve —
     i.e., they were created in the UI and are publicly bookable.
  4. CALCOM_WEBHOOK_URL + CALCOM_WEBHOOK_SECRET are configured.

It does NOT programmatically create a booking — that requires the
commercial API. To prove the webhook actually fires, the script prints a
short manual confirmation step at the end.
"""
from __future__ import annotations

import sys

import httpx

from agent.config import settings


def _check_reachable(base: str) -> bool:
    try:
        r = httpx.get(base, timeout=10, follow_redirects=True)
    except httpx.HTTPError as e:
        print(
            f"ERROR: Cal.com unreachable at {base}: {e}. "
            "Is `docker compose -f infra/docker-compose.yml up` running?",
            file=sys.stderr,
        )
        return False
    if r.status_code >= 500:
        print(
            f"ERROR: Cal.com at {base} returned HTTP {r.status_code}.",
            file=sys.stderr,
        )
        return False
    print(f"→ Cal.com reachable at {base} (HTTP {r.status_code})")
    return True


def _check_event_type_page(base: str, username: str, slug: str) -> bool:
    url = f"{base}/{username}/{slug}"
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
    except httpx.HTTPError as e:
        print(f"ERROR: cannot fetch {url}: {e}", file=sys.stderr)
        return False
    if r.status_code == 200:
        print(f"✓ booking page resolves: {url}")
        return True
    print(
        f"ERROR: booking page {url} returned HTTP {r.status_code}. "
        f"Create the {slug!r} event type at {base}/event-types and try again.",
        file=sys.stderr,
    )
    return False


def main() -> int:
    failures: list[str] = []

    if not settings.CALCOM_USERNAME:
        failures.append(
            "CALCOM_USERNAME is unset. The booking link in outbound emails "
            "would resolve to a non-existent profile."
        )

    base = settings.CALCOM_BASE_URL.rstrip("/")
    if not _check_reachable(base):
        return 2

    if settings.CALCOM_USERNAME:
        for slug in (
            settings.CALCOM_EVENT_TYPE_DISCOVERY_15,
            settings.CALCOM_EVENT_TYPE_DISCOVERY_30,
        ):
            if not _check_event_type_page(base, settings.CALCOM_USERNAME, slug):
                failures.append(f"event type {slug!r} not bookable")

    if not settings.CALCOM_WEBHOOK_URL:
        failures.append(
            "CALCOM_WEBHOOK_URL is unset. Register a public URL with Cal.com "
            "(Settings → Developer → Webhooks → BOOKING_CREATED) and paste "
            "it in .env."
        )
    else:
        print(f"→ webhook URL configured: {settings.CALCOM_WEBHOOK_URL}")

    if not settings.CALCOM_WEBHOOK_SECRET:
        failures.append(
            "CALCOM_WEBHOOK_SECRET is unset. Cal.com signs webhooks; without "
            "the shared secret /webhook/cal will reject every payload."
        )

    if failures:
        print("", file=sys.stderr)
        for msg in failures:
            print(f"ERROR: {msg}", file=sys.stderr)
        return 3

    print(
        "\nManual confirmation (the webhook fire cannot be verified "
        "programmatically without API access):"
    )
    booking_url = (
        f"{base}/{settings.CALCOM_USERNAME}/{settings.CALCOM_EVENT_TYPE_DISCOVERY_15}"
    )
    print(f"  1. Open {booking_url}")
    print("  2. Book any slot using a sandbox email.")
    print(
        "  3. Confirm 'POST /webhook/cal HTTP/1.1 200 OK' shows in the "
        "FastAPI log."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
