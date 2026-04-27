"""Dual-control agent — Act IV mechanism for τ²-Bench retail.

Subclasses tau2's `LLMAgent` and replaces the system prompt with one that
hardens the existing retail-policy dual-control rules ("get explicit
confirmation before any database write", "one tool call per turn") with
explicit, model-readable instructions that weaker dev-tier models often
violate.

Two variants registered:
  - dual_control_agent       — full mechanism (5 rules)
  - dual_control_agent_lite  — ablation: rules 1+2 only (drops the
                               single-action / refusal / no-assumption
                               reinforcers)

Design rationale: see `method/method.md` § "τ²-Bench mechanism".
"""
from __future__ import annotations

from typing import List

from tau2.agent.llm_agent import (
    AGENT_INSTRUCTION,
    LLMAgent,
    LLMAgentState,
)
from tau2.environment.tool import Tool


# ────────────────────────────────────────────────────────────────────────────
# System-prompt augmentation
# ────────────────────────────────────────────────────────────────────────────

# Five rules, ordered most→least impact based on the failure modes observed
# in the Day-1 baseline traces (eval/runs/act1_baseline_*/tau2_results.json).
# Removing any rule reopens a failure class the others don't fully catch:
#   R1: identity-authentication skips → wrong-user mutations.
#   R2: confirmation-skip → unintended destructive writes.
#   R3: tool-call batching → policy violations the orchestrator can't undo.
#   R4: hallucinated arguments → "missing product/order" infra errors.
#   R5: ambiguous user replies → false-positive proceed.

_DUAL_CONTROL_FULL = """
<dual_control_discipline>
You are operating under a hardened dual-control discipline. The retail
policy already requires explicit user confirmation before any database
mutation; the rules below add the structure weaker models miss.

R1. AUTHENTICATE FIRST. Before any tool call other than identity lookup,
    you must have already obtained the user_id via `find_user_id_by_email`
    or `find_user_id_by_name_zip`. If the conversation has not authenticated
    the user yet, your only valid actions are to (a) ask for identity
    information, or (b) call an identity-lookup tool. Do not look up orders
    or products on behalf of an unauthenticated user.

R2. CONFIRM BEFORE WRITE. For every tool that modifies state — anything
    whose name contains `cancel`, `modify`, `return`, `exchange`, or
    `update` — you must FIRST send a message that:
       (a) names the tool you will call,
       (b) lists every argument you will pass with its exact value, and
       (c) ends with the literal question "Should I proceed? (yes/no)".
    Only after the user replies with "yes" (or an unambiguous synonym:
    "confirmed", "proceed", "go ahead", "do it") may you call the tool.
    If the user replies with anything ambiguous ("sure I guess", "maybe",
    "ok if you think so"), ask the confirmation question again.

R3. ONE ACTION PER TURN. Never batch multiple tool calls in a single
    response. Never combine a tool call with a user-facing message in
    the same turn. If you have a tool call to make, that is the entire
    turn. If you have a message to send, that is the entire turn.

R4. NEVER HALLUCINATE ARGUMENTS. If you don't have an exact product_id,
    item_id, order_id, or user_id, look it up first via the appropriate
    search tool. Never construct an id from a name, never guess at
    options or quantities. If a search returns no result, tell the user
    plainly and ask them to disambiguate — do not retry with a fabricated
    id.

R5. REFUSE OUT-OF-SCOPE. If the user requests an action this policy does
    not authorise (acting on another user's data, granting refunds outside
    policy, providing recommendations or comments), refuse explicitly and
    cite the rule. If the request is in-scope but missing prerequisite
    information, ask for it — do not proceed on assumptions.
</dual_control_discipline>
""".strip()


# Ablation variant: keep only R1 (authenticate) and R2 (confirm before write).
# This isolates the contribution of R3+R4+R5 — the "discipline" rules that
# don't directly mirror the retail policy text but address weaker-model
# behaviour on top of it.
_DUAL_CONTROL_LITE = """
<dual_control_discipline>
You are operating under a hardened dual-control discipline. Two rules in
addition to the retail policy:

R1. AUTHENTICATE FIRST. Before any tool call other than identity lookup,
    obtain user_id via `find_user_id_by_email` or `find_user_id_by_name_zip`.
    Do not look up orders or products on behalf of an unauthenticated user.

R2. CONFIRM BEFORE WRITE. For every tool whose name contains `cancel`,
    `modify`, `return`, `exchange`, or `update`, first send a message
    listing the tool name, every argument and value, and ending with
    "Should I proceed? (yes/no)". Only call the tool after an unambiguous
    "yes".
</dual_control_discipline>
""".strip()


_SYSTEM_PROMPT_DUAL = """
<instructions>
{agent_instruction}
</instructions>
<policy>
{domain_policy}
</policy>
{discipline}
""".strip()


# ────────────────────────────────────────────────────────────────────────────
# Agent classes
# ────────────────────────────────────────────────────────────────────────────


class DualControlAgent(LLMAgent[LLMAgentState]):
    """Full mechanism — five rules."""

    _DISCIPLINE = _DUAL_CONTROL_FULL

    @property
    def system_prompt(self) -> str:  # type: ignore[override]
        return _SYSTEM_PROMPT_DUAL.format(
            agent_instruction=AGENT_INSTRUCTION,
            domain_policy=self.domain_policy,
            discipline=self._DISCIPLINE,
        )


class DualControlAgentLite(DualControlAgent):
    """Ablation — rules R1 + R2 only."""

    _DISCIPLINE = _DUAL_CONTROL_LITE


# ────────────────────────────────────────────────────────────────────────────
# Factories + registry hook
# ────────────────────────────────────────────────────────────────────────────


def _create_dual_control_agent(
    tools: List[Tool], domain_policy: str, **kwargs
) -> DualControlAgent:
    return DualControlAgent(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
    )


def _create_dual_control_agent_lite(
    tools: List[Tool], domain_policy: str, **kwargs
) -> DualControlAgentLite:
    return DualControlAgentLite(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
    )


_REGISTERED = False


def register_with_tau2() -> None:
    """Register both variants with tau2's agent registry. Idempotent."""
    global _REGISTERED
    if _REGISTERED:
        return
    from tau2.registry import registry

    # tau2's registry raises if a name is already registered, so check first.
    if registry.get_agent_factory("dual_control_agent") is None:
        registry.register_agent_factory(
            _create_dual_control_agent,
            "dual_control_agent",
            metadata={"mechanism": "dual_control_full", "act": "IV"},
        )
    if registry.get_agent_factory("dual_control_agent_lite") is None:
        registry.register_agent_factory(
            _create_dual_control_agent_lite,
            "dual_control_agent_lite",
            metadata={"mechanism": "dual_control_lite", "act": "IV", "ablation": True},
        )
    _REGISTERED = True


__all__ = [
    "DualControlAgent",
    "DualControlAgentLite",
    "register_with_tau2",
]
