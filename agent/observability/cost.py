"""Per-call cost attribution from the rate card in config.yaml > llm.rate_cards.

Every LLM call returns (prompt_tokens, completion_tokens); this module turns
that into a USD cost attached to the enclosing Langfuse span.
"""
from __future__ import annotations

from agent.config import config


def cost_usd(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return USD cost for one LLM call at the rate card.

    Unknown models cost zero and emit no warning — the caller is expected to
    surface unknowns via a missing-rate-card alert if it cares.
    """
    card = config.get(f"llm.rate_cards.{model_id}", None)
    if not card:
        return 0.0
    inp = card.get("input_per_1m_usd", 0.0) if isinstance(card, dict) else card.input_per_1m_usd
    out = card.get("output_per_1m_usd", 0.0) if isinstance(card, dict) else card.output_per_1m_usd
    return round((prompt_tokens * inp + completion_tokens * out) / 1_000_000.0, 6)
