"""Kill-switch invariants — the one load-bearing policy gate.

Covers:
  1. Unset kill switch → routes to sink.
  2. Missing draft header → PolicyViolation.
  3. Non-sink, non-synthetic recipient → PolicyViolation.
  4. All three channels dispatch through deliver().
"""
from __future__ import annotations

import pytest

from agent.kill_switch import (
    PolicyViolation, EmailPayload, SmsPayload, VoicePayload,
    deliver, add_draft_header, gate_booking,
)
from agent.config import settings


def _email(**kw) -> EmailPayload:
    return add_draft_header(EmailPayload(
        subject=kw.pop("subject", "smoke"),
        body_text=kw.pop("body_text", "hello"),
        **kw,
    ))


def test_email_routes_to_sink_when_kill_switch_unset():
    assert not settings.TENACIOUS_OUTBOUND_ENABLED
    r = deliver("email", settings.EMAIL_SINK_ADDRESS, _email())
    assert r.sink is True
    assert r.channel == "email"
    assert r.to == settings.EMAIL_SINK_ADDRESS


def test_email_missing_draft_header_raises():
    bad = EmailPayload(subject="x", body_text="hello")
    with pytest.raises(PolicyViolation):
        deliver("email", settings.EMAIL_SINK_ADDRESS, bad)


def test_recipient_not_sink_not_synthetic_raises(monkeypatch):
    # Force kill switch live so the allowlist is checked on the original 'to'
    monkeypatch.setattr(settings, "TENACIOUS_OUTBOUND_ENABLED", True)
    with pytest.raises(PolicyViolation):
        deliver("email", "someone@real-customer.com", _email())


def test_sms_routes_to_sink():
    r = deliver("sms", settings.SMS_SINK_NUMBER, SmsPayload(body="test"))
    assert r.sink is True
    assert r.channel == "sms"


def test_voice_routes_to_sink():
    r = deliver("voice", settings.VOICE_SINK_NUMBER, VoicePayload(script="test"))
    assert r.sink is True
    assert r.channel == "voice"


def test_sms_over_length_is_rejected(monkeypatch):
    # The kill switch accepts; the adapter enforces SMS body-length policy.
    monkeypatch.setattr(settings, "TENACIOUS_OUTBOUND_ENABLED", False)
    long = "x" * 200
    with pytest.raises(PolicyViolation):
        deliver("sms", settings.SMS_SINK_NUMBER, SmsPayload(body=long))


def test_gate_booking_returns_sink_when_kill_switch_unset():
    assert not settings.TENACIOUS_OUTBOUND_ENABLED
    # Kill switch unset → "sink" regardless of recipient (even unknown ones).
    assert gate_booking("anyone@example.com") == "sink"


def test_gate_booking_returns_live_for_synthetic_recipient(monkeypatch):
    monkeypatch.setattr(settings, "TENACIOUS_OUTBOUND_ENABLED", True)
    # First entry in data/synthetic_prospects.json
    assert gate_booking("elena.romero@delamode-group.com") == "live"


def test_gate_booking_returns_live_for_sink_address(monkeypatch):
    monkeypatch.setattr(settings, "TENACIOUS_OUTBOUND_ENABLED", True)
    assert gate_booking(settings.EMAIL_SINK_ADDRESS) == "live"


def test_gate_booking_raises_for_unknown_recipient(monkeypatch):
    monkeypatch.setattr(settings, "TENACIOUS_OUTBOUND_ENABLED", True)
    with pytest.raises(PolicyViolation):
        gate_booking("real-customer@real-company.com")
