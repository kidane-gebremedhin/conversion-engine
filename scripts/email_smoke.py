"""Day-0 email proof: send one test email via Resend (or MailerSend).

This bypasses agent.kill_switch.deliver() on purpose — it's a provider
readiness check, not an agent-policy check. It confirms:
  1. RESEND_API_KEY (or MAILERSEND_API_KEY) is valid.
  2. RESEND_FROM_ADDRESS resolves to a verified sender domain.
  3. The target inbox receives the message.

Usage:
    PYTHONPATH=. python3 scripts/email_smoke.py --to you@example.com
    make day0-email TO=you@example.com
"""
from __future__ import annotations

import argparse
import sys

import httpx

from agent.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a one-shot test email via Resend/MailerSend.")
    parser.add_argument(
        "--to",
        default=settings.EMAIL_SINK_ADDRESS,
        help="Recipient address (default: EMAIL_SINK_ADDRESS).",
    )
    args = parser.parse_args()

    provider = settings.EMAIL_PROVIDER.lower()
    if provider == "resend":
        return _send_resend(args.to)
    if provider == "mailersend":
        return _send_mailersend(args.to)
    print(f"ERROR: EMAIL_PROVIDER={provider!r} is not supported by this smoke.", file=sys.stderr)
    return 2


def _send_resend(to: str) -> int:
    if not settings.RESEND_API_KEY:
        print("ERROR: RESEND_API_KEY is unset. Fill .env first.", file=sys.stderr)
        return 2
    body = {
        "from": settings.RESEND_FROM_ADDRESS,
        "to": [to],
        "subject": "Conversion Engine — Day-0 smoke",
        "text": (
            "If you can read this, the Resend API key works and the sender "
            "domain is verified.\n\nThis is a provider readiness check; the "
            "agent's kill switch is unaffected."
        ),
    }
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post("https://api.resend.com/emails", json=body, headers=headers, timeout=30)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"ERROR: Resend API returned {e.response.status_code}: {e.response.text}", file=sys.stderr)
        return 3
    except httpx.HTTPError as e:
        print(f"ERROR: HTTP error talking to Resend: {e}", file=sys.stderr)
        return 3
    mid = r.json().get("id", "")
    print(f"✓ sent: id={mid!r} from={settings.RESEND_FROM_ADDRESS} to={to}")
    return 0


def _send_mailersend(to: str) -> int:
    if not settings.MAILERSEND_API_KEY:
        print("ERROR: MAILERSEND_API_KEY is unset. Fill .env first.", file=sys.stderr)
        return 2
    body = {
        "from": {"email": settings.RESEND_FROM_ADDRESS},
        "to": [{"email": to}],
        "subject": "Conversion Engine — Day-0 smoke",
        "text": (
            "If you can read this, the MailerSend API key works and the sender "
            "domain is verified."
        ),
    }
    headers = {
        "Authorization": f"Bearer {settings.MAILERSEND_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post("https://api.mailersend.com/v1/email", json=body, headers=headers, timeout=30)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"ERROR: MailerSend API returned {e.response.status_code}: {e.response.text}", file=sys.stderr)
        return 3
    except httpx.HTTPError as e:
        print(f"ERROR: HTTP error talking to MailerSend: {e}", file=sys.stderr)
        return 3
    mid = r.headers.get("x-message-id", "")
    print(f"✓ sent: id={mid!r} from={settings.RESEND_FROM_ADDRESS} to={to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
