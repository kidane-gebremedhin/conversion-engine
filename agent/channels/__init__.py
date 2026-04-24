"""Channel adapters — email, SMS, voice.

Only `agent.kill_switch.deliver()` imports from this package; no upstream code
path may construct and send its own payload. The dispatch() fan-out lives
here to keep the kill-switch module thin.
"""
from __future__ import annotations

from typing import Any

from agent.kill_switch import EmailPayload, SmsPayload, VoicePayload


def dispatch(channel: str, to: str, payload: Any) -> tuple[str, str]:
    """Route a payload to the correct channel adapter.

    Returns (message_id, provider).
    """
    if channel == "email":
        from agent.channels.email.send import send as email_send

        return email_send(to, payload)
    if channel == "sms":
        from agent.channels.sms.send import send as sms_send

        return sms_send(to, payload)
    if channel == "voice":
        from agent.channels.voice.send import send as voice_send

        return voice_send(to, payload)
    raise ValueError(f"Unknown channel: {channel!r}")
