"""Unified LLM client over dev-tier (OpenRouter) and eval-tier (Anthropic/OpenAI).

Public API:
    call(prompt, *, tier="dev", model=None, system=None, temperature=0.0,
         max_tokens=1024, json_mode=False) -> LlmCall

Graceful degradation: if no API key is set, the client returns a deterministic
stub response so the rest of the pipeline can be developed and tested offline.
Stub mode is opt-out via the `LLM_STUB` env var (default on when no key set).

See __specs/06-agent-design.md, __specs/18-configuration.md.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any

from agent.config import settings, config
from agent.observability.cost import cost_usd


@dataclass
class LlmCall:
    text: str
    model: str
    tier: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)

    def json(self) -> Any:
        """Parse the response text as JSON (strict)."""
        return json.loads(self.text)


class EvalTierGateError(RuntimeError):
    """Raised if an eval-tier call is attempted without EVAL_TIER_ENABLED=1."""


def _pick_model(tier: str, override: str | None) -> str:
    if override:
        return override
    if tier == "dev":
        return settings.DEV_LLM_MODEL
    if tier == "eval":
        return settings.EVAL_LLM_MODEL
    raise ValueError(f"Unknown tier: {tier!r}")


def _stub_text(prompt: str, system: str | None, json_mode: bool) -> str:
    """Deterministic stub when no API key is available.

    Returns a JSON-looking response when json_mode=True so callers that parse
    JSON (classifier, tone-check, reply classifier) don't crash. Otherwise
    returns a short fixed string.
    """
    digest = hashlib.sha256((prompt + (system or "")).encode("utf-8")).hexdigest()[:12]
    if json_mode:
        # Heuristic stubs for the most common JSON-returning callers.
        pl = prompt.lower()
        if "tone" in pl and ("marker" in pl or "direct" in pl):
            return json.dumps({
                "direct": 4, "grounded": 4, "honest": 5, "professional": 5,
                "non_condescending": 5, "overall_ok": True, "flags": [],
            })
        if "reply" in pl and "class" in pl:
            return json.dumps({"class": "ambiguous", "confidence": 0.5, "rationale": "stub"})
        return json.dumps({"stub": True, "digest": digest})
    return f"[llm-stub {digest}] (offline mode — no OPENROUTER_API_KEY set)"


def _is_stub_mode(tier: str) -> bool:
    force = os.environ.get("LLM_STUB", "").lower() in ("1", "true", "yes")
    if force:
        return True
    if tier == "dev":
        return not settings.OPENROUTER_API_KEY
    if tier == "eval":
        if settings.EVAL_LLM_PROVIDER == "anthropic":
            return not settings.ANTHROPIC_API_KEY
        return not settings.OPENAI_API_KEY
    return True


def call(
    prompt: str,
    *,
    tier: str = "dev",
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    json_mode: bool = False,
    seed: int | None = None,
) -> LlmCall:
    # Eval-tier guard
    if tier == "eval" and not settings.EVAL_TIER_ENABLED:
        raise EvalTierGateError(
            "Eval-tier LLM call attempted with EVAL_TIER_ENABLED unset. "
            "Set it deliberately; do not let a dev run leak into the eval budget."
        )

    model_id = _pick_model(tier, model)

    if _is_stub_mode(tier):
        text = _stub_text(prompt, system, json_mode)
        return LlmCall(text=text, model=model_id, tier=tier, cost_usd=0.0, finish_reason="stub")

    # Real providers. All calls use the OpenAI-compatible REST shape where possible.
    if tier == "dev":
        return _call_openrouter(prompt, model_id, system, temperature, max_tokens, json_mode, seed)
    provider = settings.EVAL_LLM_PROVIDER
    if provider == "anthropic":
        return _call_anthropic(prompt, model_id, system, temperature, max_tokens, json_mode)
    return _call_openai(prompt, model_id, system, temperature, max_tokens, json_mode, seed)


def _call_openrouter(
    prompt: str, model: str, system: str | None, temperature: float,
    max_tokens: int, json_mode: bool, seed: int | None,
) -> LlmCall:
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    kwargs: dict[str, Any] = dict(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    if seed is not None:
        kwargs["seed"] = seed
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    usage = getattr(resp, "usage", None)
    pt = getattr(usage, "prompt_tokens", 0) if usage else 0
    ct = getattr(usage, "completion_tokens", 0) if usage else 0
    return LlmCall(
        text=choice.message.content or "",
        model=model, tier="dev",
        prompt_tokens=pt, completion_tokens=ct,
        cost_usd=cost_usd(model, pt, ct),
        finish_reason=choice.finish_reason or "stop",
        raw={"id": resp.id},
    )


def _call_anthropic(
    prompt: str, model: str, system: str | None, temperature: float,
    max_tokens: int, json_mode: bool,
) -> LlmCall:
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    sys_text = system or ""
    if json_mode:
        sys_text = (sys_text + "\n\nReturn only valid JSON. No prose.").strip()
    resp = client.messages.create(
        model=model,
        system=sys_text or None,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature, max_tokens=max_tokens,
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    pt = resp.usage.input_tokens
    ct = resp.usage.output_tokens
    return LlmCall(
        text=text, model=model, tier="eval",
        prompt_tokens=pt, completion_tokens=ct,
        cost_usd=cost_usd(model, pt, ct),
        finish_reason=resp.stop_reason or "stop",
        raw={"id": resp.id},
    )


def _call_openai(
    prompt: str, model: str, system: str | None, temperature: float,
    max_tokens: int, json_mode: bool, seed: int | None,
) -> LlmCall:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    kwargs: dict[str, Any] = dict(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    if seed is not None:
        kwargs["seed"] = seed
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    pt = resp.usage.prompt_tokens
    ct = resp.usage.completion_tokens
    return LlmCall(
        text=choice.message.content or "",
        model=model, tier="eval",
        prompt_tokens=pt, completion_tokens=ct,
        cost_usd=cost_usd(model, pt, ct),
        finish_reason=choice.finish_reason or "stop",
        raw={"id": resp.id},
    )


def load_prompt(prompt_id: str) -> str:
    """Load a prompt file by its config.yaml > prompts.<id> path."""
    from pathlib import Path

    rel = config.get(f"prompts.{prompt_id}")
    if not rel:
        raise KeyError(f"No prompts.{prompt_id} in config.yaml")
    path = Path(rel)
    if not path.is_absolute():
        from agent.config import REPO_ROOT
        path = REPO_ROOT / path
    return path.read_text(encoding="utf-8")
