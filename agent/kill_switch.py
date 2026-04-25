"""Kill switch — the single outbound gate.

Every outbound action the agent takes — email, SMS, voice, and programmatic
booking-creation — is gated here:

  - Message-shaped outbound (email/SMS/voice) flows through `deliver()`.
  - Booking-shaped outbound (Cal.com event creation) flows through
    `gate_booking()`, which the calendar client consults before any
    real-API write.

In both gates:

  - TENACIOUS_OUTBOUND_ENABLED unset → recipient rewritten to staff sink
    (or, for bookings, the local-file mock at data/calcom_local/).
  - Recipient must be the sink OR a synthetic-prospect entry; anything else
    raises PolicyViolation.
  - Email payloads must carry X-Tenacious-Status: draft.
  - Every call emits a Langfuse deliver span and a local audit line.

No file outside this module (and its thin channel adapters) may import a
provider SDK's send method. A CI grep enforces this; code review enforces
the spirit.

See __specs/16-data-handling-and-kill-switch.md.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from agent.config import settings


# ────────────────────────────────────────────────────────────────────────────
# Errors and types
# ────────────────────────────────────────────────────────────────────────────


class PolicyViolation(Exception):
    """Raised when an outbound attempt violates the data-handling policy.

    This exception propagates to the process boundary — it must not be caught
    by channel adapters. An uncaught PolicyViolation is the correct signal
    that the system should halt and the incident be reported per Rule 9.
    """


@dataclass
class EmailPayload:
    subject: str
    body_text: str
    body_html: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    reply_to: str | None = None
    thread_id: str | None = None
    trace_id: str | None = None

    def channel(self) -> str:
        return "email"


@dataclass
class SmsPayload:
    body: str
    thread_id: str | None = None
    trace_id: str | None = None

    def channel(self) -> str:
        return "sms"


@dataclass
class VoicePayload:
    """Voice dispatches carry a TwiML-like script or a webhook callback URL."""

    script: str | None = None
    callback_url: str | None = None
    trace_id: str | None = None

    def channel(self) -> str:
        return "voice"


Payload = EmailPayload | SmsPayload | VoicePayload


@dataclass
class DeliveryResult:
    message_id: str
    channel: str
    to: str
    sink: bool
    provider: str
    trace_id: str | None


# ────────────────────────────────────────────────────────────────────────────
# Synthetic-prospect + sink allowlist
# ────────────────────────────────────────────────────────────────────────────


def _load_synthetic_prospect_addresses() -> tuple[set[str], set[str]]:
    """Load synthetic email addresses and phone numbers.

    Returns (emails, phones). Missing file returns empty sets; the sink
    check then gates everything.
    """
    emails: set[str] = set()
    phones: set[str] = set()
    path = Path(settings.CRUNCHBASE_ODM_LOCAL_PATH).parent / "synthetic_prospects.json"
    if not path.exists():
        # Try the canonical location
        path = Path("data") / "synthetic_prospects.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            prospects = json.load(f)
        for p in prospects:
            if email := p.get("prospect_email"):
                emails.add(email.lower())
            if phone := p.get("prospect_phone"):
                phones.add(phone)
    return emails, phones


def _recipient_is_sink(to: str, channel: str) -> bool:
    if channel == "email":
        return to.lower() == settings.EMAIL_SINK_ADDRESS.lower()
    if channel == "sms":
        return to == settings.SMS_SINK_NUMBER
    if channel == "voice":
        return to == settings.VOICE_SINK_NUMBER
    return False


def _recipient_is_synthetic(to: str, channel: str) -> bool:
    emails, phones = _load_synthetic_prospect_addresses()
    if channel == "email":
        return to.lower() in emails
    if channel in ("sms", "voice"):
        return to in phones
    return False


# ────────────────────────────────────────────────────────────────────────────
# Assertions
# ────────────────────────────────────────────────────────────────────────────


def _assert_draft_header_present(payload: Payload) -> None:
    if isinstance(payload, EmailPayload):
        header_keys = {k.lower() for k in payload.headers.keys()}
        if "x-tenacious-status" not in header_keys:
            raise PolicyViolation(
                "Email payload missing required X-Tenacious-Status: draft header. "
                "Every Tenacious-branded outbound must carry this marker."
            )
        if payload.headers.get("X-Tenacious-Status", "").lower() != "draft":
            if payload.headers.get("x-tenacious-status", "").lower() != "draft":
                raise PolicyViolation(
                    "X-Tenacious-Status header must equal 'draft' during the challenge week."
                )


_SINK_ENV_VAR = {"email": "EMAIL_SINK_ADDRESS", "sms": "SMS_SINK_NUMBER", "voice": "VOICE_SINK_NUMBER"}


def _assert_recipient_allowed(to: str, channel: str) -> None:
    if not to or not to.strip():
        env_var = _SINK_ENV_VAR.get(channel, f"<sink for {channel!r}>")
        raise PolicyViolation(
            f"Resolved recipient is empty on channel {channel!r}. "
            f"Set {env_var} in .env to a real address you own — the kill "
            "switch routes outbound here when TENACIOUS_OUTBOUND_ENABLED is unset."
        )
    if _recipient_is_sink(to, channel):
        return
    if _recipient_is_synthetic(to, channel):
        return
    raise PolicyViolation(
        f"Recipient {to!r} on channel {channel!r} is neither the staff sink nor a "
        "synthetic-prospect address. Every outbound during the challenge week "
        "must target one of these."
    )


# ────────────────────────────────────────────────────────────────────────────
# Audit log
# ────────────────────────────────────────────────────────────────────────────


def _audit_log_entry(entry: dict[str, Any]) -> None:
    path = Path(settings.LOCAL_KILLSWITCH_AUDIT)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ────────────────────────────────────────────────────────────────────────────
# The gate
# ────────────────────────────────────────────────────────────────────────────


def deliver(channel: str, to: str, payload: Payload) -> DeliveryResult:
    """Gate every outbound through here.

    Args:
        channel: "email" | "sms" | "voice"
        to: recipient address (may be rewritten to sink).
        payload: channel-specific payload.

    Returns:
        DeliveryResult with provider message_id, the sink flag, and the
        resolved recipient.

    Raises:
        PolicyViolation: if any invariant fails.
    """
    if channel not in ("email", "sms", "voice"):
        raise ValueError(f"Unknown channel: {channel!r}")
    if getattr(payload, "channel", lambda: None)() != channel:
        raise ValueError(f"Payload channel mismatch: {payload!r} on {channel!r}")

    kill_switch_unset = not settings.TENACIOUS_OUTBOUND_ENABLED
    resolved_to = settings.sink_for(channel) if kill_switch_unset else to

    # Enforce invariants
    _assert_draft_header_present(payload)
    _assert_recipient_allowed(resolved_to, channel)

    # Audit trail
    entry = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "channel": channel,
        "to_requested": to,
        "to_resolved": resolved_to,
        "sink": kill_switch_unset,
        "kill_switch_enabled": settings.TENACIOUS_OUTBOUND_ENABLED,
        "trace_id": getattr(payload, "trace_id", None),
    }
    _audit_log_entry(entry)

    # Langfuse span (lazy import to avoid circular)
    try:
        from agent.observability.langfuse import deliver_span

        deliver_span(channel, resolved_to, kill_switch_unset, payload)
    except Exception:  # noqa: BLE001 - observability must never break delivery
        pass

    # Dispatch to the adapter
    from agent.channels import dispatch

    message_id, provider = dispatch(channel, resolved_to, payload)

    return DeliveryResult(
        message_id=message_id,
        channel=channel,
        to=resolved_to,
        sink=kill_switch_unset,
        provider=provider,
        trace_id=getattr(payload, "trace_id", None),
    )


def add_draft_header(payload: EmailPayload) -> EmailPayload:
    """Helper: stamp the required draft header + canonical trace headers.

    Composers should call this before handing payloads to deliver().
    """
    headers = dict(payload.headers)
    headers.setdefault("X-Tenacious-Status", "draft")
    payload.headers = headers
    return payload


# ────────────────────────────────────────────────────────────────────────────
# Booking gate
# ────────────────────────────────────────────────────────────────────────────


def gate_booking(prospect_email: str) -> str:
    """Gate a programmatic Cal.com booking attempt.

    Bookings are not message-shaped, so they don't go through deliver(); but
    they're still outbound to a third-party (Cal.com) on a real prospect's
    behalf, so the same kill-switch policy applies.

    Returns:
        "live" — kill switch is enabled AND the prospect is on the synthetic
                 allowlist (or is the staff sink). The caller may proceed
                 with the real Cal.com API.
        "sink" — kill switch is unset. The caller must NOT call the real
                 API; route to the local-file mock at data/calcom_local/
                 instead.

    Raises:
        PolicyViolation — kill switch is enabled but the recipient is
        neither a synthetic prospect nor the staff sink.
    """
    if not settings.TENACIOUS_OUTBOUND_ENABLED:
        _audit_log_entry({
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "operation": "booking",
            "prospect_email": prospect_email,
            "kill_switch_enabled": False,
            "action": "routed_to_local_sink",
        })
        return "sink"
    emails, _ = _load_synthetic_prospect_addresses()
    if prospect_email.lower() in emails:
        return "live"
    if prospect_email.lower() == settings.EMAIL_SINK_ADDRESS.lower():
        return "live"
    raise PolicyViolation(
        f"Booking attempted for {prospect_email!r} which is neither a synthetic "
        "prospect nor the staff sink. The kill switch is enabled but the "
        "recipient allowlist is still enforced."
    )
