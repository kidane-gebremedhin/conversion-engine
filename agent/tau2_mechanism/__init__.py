"""τ²-Bench-side Act IV mechanism.

Extends tau2's stock `llm_agent` with the same "abstain on uncertainty,
verify before destructive action" principle that the sales-side mechanism
uses (see [`method/method.md`](../../method/method.md)). Tau2's retail
benchmark is the closest public analog to B2B qualification conversation,
and dual-control coordination is τ²-Bench retail's central failure mode
per the PDF — both make this the right place to port the abstention
principle.

Public surface:
    register_with_tau2()    — idempotent; safe to call from harness boot.

Variants (registered as separate agent names so the ablation harness can
select them):
    dual_control_agent       — full mechanism: pre-action verification +
                               single-tool-call discipline + identity
                               authentication reminder + refusal language.
    dual_control_agent_lite  — ablation: pre-action verification only,
                               drops the single-tool-call and refusal
                               reminders.

See `dual_control_agent.py` for the system-prompt augmentation itself.
"""
from __future__ import annotations

from .dual_control_agent import register_with_tau2  # re-export

__all__ = ["register_with_tau2"]
