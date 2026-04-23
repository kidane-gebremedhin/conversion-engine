"""Channel-handoff policy — email → SMS → human handoff rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class HandoffDecision:
    next_channel: Literal["email", "sms", "human"]
    reason: str


def decide(
    *,
    current: str,
    reply_intent: str,
    preferred_channel: str | None,
    thread_age_hours: float,
    stage: str,
) -> HandoffDecision:
    # Email → SMS: only when prospect is warm AND explicitly asked OR stalled + opted-in
    if current == "email" and stage in ("QUALIFIED", "SCHEDULING"):
        if preferred_channel == "sms":
            return HandoffDecision("sms", "prospect asked for SMS scheduling")
        if thread_age_hours > 96 and preferred_channel == "sms":
            return HandoffDecision("sms", "stalled + opted-in for SMS")

    if reply_intent in ("pricing_question", "bench_question"):
        return HandoffDecision("human", f"reply intent {reply_intent} exceeds automated scope")

    if reply_intent == "unsubscribe":
        return HandoffDecision("human", "unsubscribe — stop automated outbound")

    return HandoffDecision(current, "no handoff needed")  # type: ignore[arg-type]
