"""τ²-Bench harness wrapper — runs the real benchmark, no mocks.

`python -m eval.harness --partition retail_dev_30 --trials 5 --tier dev`

Drives the vendored τ²-Bench (`eval/tau2/`) with our dev-tier or eval-tier
LLM, captures every trial as a Langfuse generation (model + per-turn
trajectory + tokens + cost + latency), and writes:

  - eval/score_log.json   — one entry per run_id, appended
  - eval/trace_log.jsonl  — one JSON per simulation: full message trace
  - eval/runs/<run_id>/   — tau2's per-run logs

Partitions:
  retail_dev_30      first 30 task IDs from retail's `train` split (Act I).
  retail_sealed_20   first 20 task IDs from retail's `test` split (Act IV).
                     Dual-guarded by TAU2_SEALED_ACCESS=1 + EVAL_TIER_ENABLED=1.

Models pass through LiteLLM. OpenRouter slugs are auto-prefixed with
`openrouter/`; Anthropic slugs use `anthropic/...`; OpenAI slugs are
passed through as-is.

See __specs/11-tau2-bench-harness.md for the contract.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from agent.config import REPO_ROOT, config, settings
from agent.observability.cost import cost_usd
from agent.observability.langfuse import (
    _LF_INPUT,
    _LF_MODEL,
    _LF_OUTPUT,
    _LF_USAGE,
    flush,
    generation,
    new_trace,
    record_score,
    update_trace,
)


# ────────────────────────────────────────────────────────────────────────────
# tau2 import (vendored at eval/tau2/)
# ────────────────────────────────────────────────────────────────────────────


_TAU2_SRC = REPO_ROOT / "eval" / "tau2" / "src"
if str(_TAU2_SRC) not in sys.path:
    sys.path.insert(0, str(_TAU2_SRC))


def _import_tau2(*, agent_slug: str | None = None) -> Any:
    # Push provider keys into os.environ so LiteLLM (used by tau2) finds them.
    # pydantic-settings reads .env into `settings` but does not mirror to os.environ.
    # Skip values that look like dotenv comment placeholders (e.g. "# required for ...")
    # — LiteLLM would otherwise authenticate with the literal comment string and 401.
    for var, val in {
        "OPENROUTER_API_KEY": settings.OPENROUTER_API_KEY,
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
    }.items():
        if not _looks_like_real_key(val):
            continue
        if not os.environ.get(var):
            os.environ[var] = val

    _register_rate_cards_with_litellm()
    _silence_litellm_unmapped_warnings()
    _tolerate_empty_tool_call_args()
    if agent_slug:
        # tau2's evaluator + env-interface defaults are hard-coded to gpt-4.1,
        # which the NL-assertion judge calls on every task. Without aliasing,
        # those calls hit OpenAI even when only OPENROUTER_API_KEY is set.
        _route_tau2_internals_through(agent_slug)

    # Import from the new layered API (tau2.runner.batch); tau2.run.run_tasks is
    # a deprecated flat-arg shim and rejects the keyword-only `save_path`.
    from tau2.runner.batch import run_tasks
    from tau2.runner.helpers import get_tasks, load_task_splits
    from tau2.data_model.simulation import Results, TextRunConfig

    # Register the Act IV mechanism agents with tau2's registry so the harness
    # can select them via `--agent dual_control_agent[_lite]`.
    from agent.tau2_mechanism import register_with_tau2 as _register_mechanism
    _register_mechanism()

    return {
        "run_tasks": run_tasks,
        "get_tasks": get_tasks,
        "load_task_splits": load_task_splits,
        "TextRunConfig": TextRunConfig,
        "Results": Results,
    }


def _looks_like_real_key(val: str | None) -> bool:
    """Reject empty, comment-shaped, or whitespace-only env values."""
    if not val:
        return False
    stripped = val.strip()
    if not stripped:
        return False
    return not stripped.startswith("#")


def _register_rate_cards_with_litellm() -> None:
    """Mirror config.yaml > llm.rate_cards into LiteLLM's pricing catalog so
    tau2's `completion_cost` lookup succeeds for slugs that exactly match.
    For OpenRouter date-suffixed slugs that LiteLLM still won't recognise,
    the harness falls back to our config rate card downstream.
    """
    try:
        import litellm
    except ImportError:  # pragma: no cover
        return

    rate_cards = config.get("llm.rate_cards", {}) or {}
    if not isinstance(rate_cards, dict):
        return

    entries: dict[str, dict[str, Any]] = {}
    for model_id, card in rate_cards.items():
        if not isinstance(card, dict):
            continue
        inp = float(card.get("input_per_1m_usd", 0.0)) / 1_000_000.0
        out = float(card.get("output_per_1m_usd", 0.0)) / 1_000_000.0
        provider = (
            "anthropic" if model_id.startswith("anthropic/") or "claude" in model_id else
            "openai" if model_id.startswith("openai/") or model_id.startswith("gpt-") else
            "openrouter"
        )
        entry = {
            "input_cost_per_token": inp,
            "output_cost_per_token": out,
            "litellm_provider": provider,
            "mode": "chat",
        }
        entries[model_id] = entry
        if not model_id.startswith(("openrouter/", "anthropic/", "openai/")):
            entries[f"openrouter/{model_id}"] = entry

    if entries:
        try:
            litellm.register_model(entries)
        except Exception:  # noqa: BLE001 - best-effort
            pass


def _silence_litellm_unmapped_warnings() -> None:
    """tau2's `get_response_cost` logs ERROR every time LiteLLM doesn't know
    the served model slug — for OpenRouter, that fires on every date-stamped
    variant. The cost is 0 in that branch and we recover via the rate-card
    fallback in `_score()`, so the log noise is pure spam.
    """
    try:
        import tau2.utils.llm_utils as _llm_utils
        from litellm import completion_cost
    except ImportError:  # pragma: no cover
        return

    if getattr(_llm_utils.get_response_cost, "_quiet", False):
        return

    _parse = _llm_utils._parse_ft_model_name

    def _quiet_get_response_cost(response: Any) -> float:
        response.model = _parse(response.model)
        try:
            return completion_cost(completion_response=response)
        except Exception:  # noqa: BLE001 - LiteLLM raises NotFoundError for unmapped models
            return 0.0

    _quiet_get_response_cost._quiet = True  # type: ignore[attr-defined]
    _llm_utils.get_response_cost = _quiet_get_response_cost


def _tolerate_empty_tool_call_args() -> None:
    """Replace `json` inside two tau2 modules whose `json.loads` consumes raw
    LLM output, with a shim whose `loads` returns `{}` on empty / whitespace
    / unparseable strings (and tolerates ```json ...``` markdown wrappers).

    Failure paths this addresses:
      1. `tau2.utils.llm_utils:440` — tool-call argument parser.
         `json.loads(tool_call.function.arguments)` raises when the LLM emits
         a tool call with `arguments=""` (common on DeepSeek V3.2 / Qwen3-Next
         via OpenRouter). After tau2's 4-attempt retry, the task is marked
         INFRASTRUCTURE_ERROR and excluded from pass@1.
      2. `tau2.evaluator.evaluator_nl_assertions:127` — NL-assertion judge.
         `json.loads(assistant_message.content)` raises when the judge LLM
         wraps JSON in prose or markdown fences. Returning `{}` here makes
         `result_data.get("results", [])` evaluate to `[]` and the rest of
         the evaluator (env/action/communicate checks) still runs.
    """
    try:
        import tau2.utils.llm_utils as _llm_utils
        import tau2.evaluator.evaluator_nl_assertions as _nl_eval
    except ImportError:  # pragma: no cover
        return

    import json as _real_json
    import re as _re

    _MARKDOWN_FENCE = _re.compile(r"```(?:json)?\s*(.+?)\s*```", _re.DOTALL)

    class _JsonShim:
        JSONDecodeError = _real_json.JSONDecodeError
        dumps = staticmethod(_real_json.dumps)
        dump = staticmethod(_real_json.dump)
        load = staticmethod(_real_json.load)

        @staticmethod
        def loads(s: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(s, bytes):
                s = s.decode("utf-8", errors="replace")
            if not isinstance(s, str) or not s.strip():
                return {}
            try:
                return _real_json.loads(s, *args, **kwargs)
            except _real_json.JSONDecodeError:
                pass
            m = _MARKDOWN_FENCE.search(s)
            if m:
                try:
                    return _real_json.loads(m.group(1), *args, **kwargs)
                except _real_json.JSONDecodeError:
                    pass
            brace_start = s.find("{")
            brace_end = s.rfind("}")
            if 0 <= brace_start < brace_end:
                try:
                    return _real_json.loads(s[brace_start:brace_end + 1], *args, **kwargs)
                except _real_json.JSONDecodeError:
                    pass
            return {}

    for module in (_llm_utils, _nl_eval):
        if not getattr(module, "_tolerant_json_installed", False):
            module.json = _JsonShim
            module._tolerant_json_installed = True  # type: ignore[attr-defined]


def _route_tau2_internals_through(slug: str) -> None:
    """Make tau2's hard-coded `gpt-4.1` / `claude-opus-4-5` evaluator and
    env-interface defaults route through the agent's provider via LiteLLM's
    `model_alias_map`. Aliasing at the LiteLLM call site is robust to tau2
    capturing the constants via `from tau2.config import …`.
    """
    try:
        import litellm
    except ImportError:  # pragma: no cover
        return

    aliases = dict(getattr(litellm, "model_alias_map", {}) or {})
    aliases.update({
        "gpt-4.1-2025-04-14": slug,
        "gpt-4.1": slug,
        "claude-opus-4-5": slug,
    })
    litellm.model_alias_map = aliases


# ────────────────────────────────────────────────────────────────────────────
# Paths
# ────────────────────────────────────────────────────────────────────────────


DEV_SLICE_PATH = REPO_ROOT / "eval" / "dev_slice.json"
SCORE_LOG_PATH = REPO_ROOT / "eval" / "score_log.json"
TRACE_LOG_PATH = REPO_ROOT / "eval" / "trace_log.jsonl"
RUNS_DIR = REPO_ROOT / "eval" / "runs"
PASS_THRESHOLD = 1.0 - 1e-9


# ────────────────────────────────────────────────────────────────────────────
# Model id mapping → LiteLLM slug
# ────────────────────────────────────────────────────────────────────────────


def _to_litellm_slug(model: str) -> str:
    """Translate our config model id to a LiteLLM slug.

    Examples:
        qwen/qwen3-next-80b-a3b              → openrouter/qwen/qwen3-next-80b-a3b
        deepseek/deepseek-v3.2               → openrouter/deepseek/deepseek-v3.2
        anthropic/claude-sonnet-4.6          → anthropic/claude-sonnet-4-6
        openai/gpt-5                         → openai/gpt-5
        openrouter/qwen/qwen3-next-80b-a3b   → openrouter/qwen/qwen3-next-80b-a3b
    """
    if model.startswith(("openrouter/", "anthropic/", "openai/", "azure/", "bedrock/", "vertex_ai/")):
        return model
    # Anthropic LiteLLM slugs use hyphenated patch versions; tolerate both.
    if model.startswith("claude") or "claude-" in model:
        return f"anthropic/{model}"
    if model.startswith("gpt-"):
        return f"openai/{model}"
    # Default: route through OpenRouter.
    return f"openrouter/{model}"


def _provider_tier(slug: str) -> str:
    """Map a LiteLLM slug back to our tier ('dev' / 'eval')."""
    return "dev" if slug.startswith("openrouter/") else "eval"


# ────────────────────────────────────────────────────────────────────────────
# Partition runner
# ────────────────────────────────────────────────────────────────────────────


def _load_dev_task_ids() -> list[str]:
    """Authoritative list of 30 retail task IDs that constitute the dev slice.

    Source of truth: eval/dev_slice.json (committed). Falls back to the first
    30 ids from retail's `train` split if the file is missing — this lets a
    fresh repo bootstrap without a pre-committed slice.
    """
    if DEV_SLICE_PATH.exists():
        body = json.loads(DEV_SLICE_PATH.read_text())
        ids = [str(t["task_id"]) for t in body.get("tasks", [])]
        if ids:
            return ids
    splits = _import_tau2()["load_task_splits"]("retail") or {}
    return list(splits.get("train", []))[:30]


def _load_sealed_task_ids() -> list[str]:
    """First 20 retail `test` task ids — used as the sealed held-out partition.

    A program-delivered sealed file at TAU2_HELDOUT_PATH overrides this when
    present (final-week scoring path).
    """
    sealed_path = Path(settings.TAU2_HELDOUT_PATH).expanduser()
    if sealed_path.exists() and sealed_path.is_file():
        body = json.loads(sealed_path.read_text())
        return [str(t["task_id"]) for t in body.get("tasks", [])]
    splits = _import_tau2()["load_task_splits"]("retail") or {}
    return list(splits.get("test", []))[:20]


def run_partition(
    *,
    partition: str,
    model: str,
    trials: int,
    seed: int,
    tier: str,
    user_model: str | None = None,
    max_steps: int = 100,
    max_concurrency: int = 4,
    agent: str = "llm_agent",
) -> dict[str, Any]:
    """Run τ²-Bench retail on one partition. Returns the score dict."""
    if partition == "retail_sealed_20":
        if not (settings.TAU2_SEALED_ACCESS and settings.EVAL_TIER_ENABLED):
            raise RuntimeError(
                "Sealed held-out partition requires both TAU2_SEALED_ACCESS=1 and EVAL_TIER_ENABLED=1. "
                "Refusing."
            )

    agent_slug = _to_litellm_slug(model)
    user_slug = _to_litellm_slug(user_model or model)
    tau2 = _import_tau2(agent_slug=agent_slug)

    task_ids = _load_dev_task_ids() if partition == "retail_dev_30" else _load_sealed_task_ids()
    if not task_ids:
        raise RuntimeError(f"Partition {partition!r} resolved to zero task ids — check dev_slice.json / TAU2_HELDOUT_PATH.")
    tasks = tau2["get_tasks"]("retail", task_ids=task_ids)

    run_id = f"act1_baseline_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    trace = new_trace(
        f"tau2.{partition}",
        attributes={
            "tau2.partition": partition,
            "tier": tier,
            "tau2.model": agent_slug,
            "tau2.agent": agent,
        },
    )

    cfg = tau2["TextRunConfig"](
        domain="retail",
        agent=agent,
        user="user_simulator",
        llm_agent=agent_slug,
        llm_user=user_slug,
        llm_args_agent={"temperature": 0.0},
        llm_args_user={"temperature": 0.0},
        num_trials=trials,
        max_steps=max_steps,
        max_errors=10,
        seed=seed,
        max_concurrency=max_concurrency,
        log_level="WARNING",
    )

    save_path = run_dir / "tau2_results.json"
    results = tau2["run_tasks"](
        cfg, tasks,
        save_path=save_path,
        save_dir=run_dir,
        console_display=False,
    )

    score = _score(results, model=agent_slug, partition=partition, tier=tier, trials=trials, seed=seed, run_id=run_id)

    # Per-trial Langfuse generation: turn trajectory as input/output, model,
    # token usage, cost, latency, reward all visible per-task.
    for sim in results.simulations:
        _emit_trial_generation(sim, trace=trace, model_slug=agent_slug, partition=partition, tier=tier)

    # Trace-level rollup so cost-per-task / pass@1 show on the parent trace.
    update_trace(
        trace,
        **{
            "trace.total_cost_usd": score["cost_total_usd"],
            "tau2.cost_total_usd": score["cost_total_usd"],
            "tau2.cost_per_task_usd": round(score["cost_total_usd"] / max(score["n_tasks"], 1), 6),
            "tau2.pass_at_1_mean": score["pass_at_1_mean"],
            "tau2.n_tasks": score["n_tasks"],
            "tau2.model": agent_slug,
        },
    )
    record_score(trace, name="pass_at_1", value=score["pass_at_1_mean"], comment=f"τ²-Bench {partition}")
    score["langfuse_trace_url"] = trace.url()
    score["langfuse_trace_id"] = trace.trace_id
    score["save_path"] = str(save_path)

    # Append to score_log.json
    prev: dict[str, Any] = {"runs": []}
    if SCORE_LOG_PATH.exists():
        try:
            prev = json.loads(SCORE_LOG_PATH.read_text())
        except json.JSONDecodeError:
            prev = {"runs": []}
    prev.setdefault("runs", []).append(score)
    SCORE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORE_LOG_PATH.write_text(json.dumps(prev, indent=2))

    # Append per-simulation rows to trace_log.jsonl (full turn-by-turn, no PII risk
    # — these are τ²-Bench synthetic prospects, not real customers).
    with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
        for sim in results.simulations:
            f.write(json.dumps(_serialize_sim(sim, run_id=run_id), default=str) + "\n")

    return score


def _aggregate_usage(messages: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    """Sum (prompt_tokens, completion_tokens) by role across the trace.

    Returns (agent_pt, agent_ct, user_pt, user_ct). tau2 stamps usage on each
    message; the agent's cost should attribute to assistant rows, the user
    simulator's cost to user rows.
    """
    a_pt = a_ct = u_pt = u_ct = 0
    for m in messages:
        usage = m.get("usage") or {}
        if not isinstance(usage, dict):
            continue
        pt = int(usage.get("prompt_tokens") or 0)
        ct = int(usage.get("completion_tokens") or 0)
        if m.get("role") == "assistant":
            a_pt += pt
            a_ct += ct
        elif m.get("role") == "user":
            u_pt += pt
            u_ct += ct
    return a_pt, a_ct, u_pt, u_ct


def _resolve_rate_card_model(slug: str) -> str:
    """Strip the LiteLLM provider prefix and any date suffix so the slug
    matches a rate-card key in config.yaml > llm.rate_cards.

    `openrouter/deepseek/deepseek-v3.2-20251201` → `deepseek/deepseek-v3.2`
    """
    base = slug.split("/", 1)[1] if "/" in slug and slug.split("/", 1)[0] in (
        "openrouter", "anthropic", "openai", "azure", "bedrock", "vertex_ai",
    ) else slug
    rate_cards = config.get("llm.rate_cards", {}) or {}
    if base in rate_cards:
        return base
    # Try trimming a trailing date stamp like `-20251201`.
    parts = base.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 8 and parts[0] in rate_cards:
        return parts[0]
    return base


def _emit_trial_generation(sim: Any, *, trace: Any, model_slug: str, partition: str, tier: str) -> None:
    messages = [m.model_dump(mode="json") for m in (sim.get_messages() or [])]
    reward = sim.reward_info.reward if sim.reward_info else None
    passed = bool(reward is not None and reward >= PASS_THRESHOLD)
    cost_litellm = float(sim.agent_cost or 0.0)

    a_pt, a_ct, _u_pt, _u_ct = _aggregate_usage(messages)
    rate_card_model = _resolve_rate_card_model(model_slug)
    cost_local = cost_usd(rate_card_model, a_pt, a_ct)
    # Use LiteLLM's number when present (it knows about its own price catalog);
    # otherwise fall back to our config rate card.
    cost = cost_litellm if cost_litellm > 0 else cost_local

    with generation(
        "tau2.trial",
        trace=trace,
        **{
            "tau2.partition": partition,
            "tau2.task_id": str(sim.task_id),
            "tau2.seed": sim.seed,
            "tau2.trial": sim.trial,
            "tau2.passed": passed,
            "tau2.reward": reward,
            "tau2.termination_reason": str(sim.termination_reason),
            "tier": tier,
            "cost.usd": round(cost, 6),
        },
    ) as s:
        s[_LF_MODEL] = model_slug
        first_user = next((m for m in messages if m.get("role") == "user"), None)
        s[_LF_INPUT] = {
            "task_id": sim.task_id,
            "first_user_message": (first_user or {}).get("content"),
            "messages": messages,
        }
        last_assistant = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
        s[_LF_OUTPUT] = {
            "passed": passed,
            "reward": reward,
            "termination_reason": str(sim.termination_reason),
            "final_assistant_message": (last_assistant or {}).get("content"),
            "messages": messages,
        }
        s[_LF_USAGE] = {
            "input": a_pt,
            "output": a_ct,
            "total": a_pt + a_ct,
            "unit": "TOKENS",
            "input_cost": cost_usd(rate_card_model, a_pt, 0),
            "output_cost": cost_usd(rate_card_model, 0, a_ct),
            "total_cost": cost,
        }


def _serialize_sim(sim: Any, *, run_id: str) -> dict[str, Any]:
    reward = sim.reward_info.reward if sim.reward_info else None
    return {
        "run_id": run_id,
        "sim_id": sim.id,
        "task_id": sim.task_id,
        "trial": sim.trial,
        "seed": sim.seed,
        "reward": reward,
        "passed": bool(reward is not None and reward >= PASS_THRESHOLD),
        "agent_cost_usd": sim.agent_cost,
        "user_cost_usd": sim.user_cost,
        "duration_s": sim.duration,
        "termination_reason": str(sim.termination_reason),
        "messages": [m.model_dump(mode="json") for m in (sim.get_messages() or [])],
    }


# ────────────────────────────────────────────────────────────────────────────
# Scoring (pass@1, bootstrap CI, cost, latency)
# ────────────────────────────────────────────────────────────────────────────


def _score(
    results: Any, *, model: str, partition: str, tier: str,
    trials: int, seed: int, run_id: str,
) -> dict[str, Any]:
    sims = list(results.simulations)
    if not sims:
        raise RuntimeError("τ²-Bench returned zero simulations — see eval/runs/<run_id>/ for tau2 logs.")

    # Bucket rewards by task_id to enable a task-clustered bootstrap.
    by_task: dict[str, list[float]] = {}
    durations_s: list[float] = []
    total_cost = 0.0
    rate_card_model = _resolve_rate_card_model(model)
    for sim in sims:
        rid = str(sim.task_id)
        r = sim.reward_info.reward if sim.reward_info else 0.0
        by_task.setdefault(rid, []).append(1.0 if r >= PASS_THRESHOLD else 0.0)
        durations_s.append(sim.duration or 0.0)
        c = float(sim.agent_cost or 0.0)
        if c <= 0.0:
            messages = [m.model_dump(mode="json") for m in (sim.get_messages() or [])]
            a_pt, a_ct, _, _ = _aggregate_usage(messages)
            c = cost_usd(rate_card_model, a_pt, a_ct)
        total_cost += c

    task_means = [sum(v) / len(v) for v in by_task.values()]
    n_tasks = len(by_task)
    mean = sum(task_means) / n_tasks if n_tasks else 0.0

    ci_low, ci_high = _bootstrap_ci(task_means, n_resamples=2000, alpha=0.05, seed=seed)

    # Latency: per-simulation wall time. p50 / p95 across all sims.
    wall_ms_sorted = sorted(int(d * 1000) for d in durations_s)
    p50 = wall_ms_sorted[len(wall_ms_sorted) // 2] if wall_ms_sorted else 0
    p95 = (
        wall_ms_sorted[max(0, int(math.ceil(0.95 * len(wall_ms_sorted))) - 1)]
        if len(wall_ms_sorted) >= 20
        else (wall_ms_sorted[-1] if wall_ms_sorted else 0)
    )

    cost_per_run = total_cost / max(trials, 1)
    cost_per_task = total_cost / max(n_tasks, 1)

    published_ref = float(config.get("tenacious.conversions.tau2_retail_ceiling", 0.42))
    delta = round(mean - published_ref, 3)
    overlaps = (ci_low <= published_ref <= ci_high)

    # task_pass_rate: {task_id: mean reward across that task's trials}, used by
    # the ablation runner to pair across conditions for the Delta-A bootstrap.
    task_pass_rate = {tid: sum(v) / len(v) for tid, v in by_task.items()}

    return {
        "run_id": run_id,
        "partition": partition,
        "model": model,
        "tier": tier,
        "trials": trials,
        "seed": seed,
        "pass_at_1_mean": round(mean, 3),
        "ci_95": [round(ci_low, 3), round(ci_high, 3)],
        "ci_method": "task_clustered_percentile_bootstrap",
        "cost_total_usd": round(total_cost, 4),
        "cost_per_run_usd": round(cost_per_run, 4),
        "cost_per_task_usd": round(cost_per_task, 6),
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "git_sha_repo": _git_sha(),
        "git_sha_tau2": _tau2_git_sha(),
        "published_reference_pass_at_1": published_ref,
        "reproduction_delta": delta,
        "reproduction_ci_overlaps_published": overlaps,
        "n_tasks": n_tasks,
        "n_simulations": len(sims),
        "task_pass_rate": task_pass_rate,
    }


def _bootstrap_ci(values: list[float], *, n_resamples: int, alpha: float, seed: int) -> tuple[float, float]:
    """Percentile bootstrap CI over per-task pass rates."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    samples: list[float] = []
    for _ in range(n_resamples):
        resampled = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(resampled) / n)
    samples.sort()
    lo_idx = int(math.floor((alpha / 2) * n_resamples))
    hi_idx = int(math.ceil((1 - alpha / 2) * n_resamples)) - 1
    return samples[lo_idx], samples[hi_idx]


def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _tau2_git_sha() -> str:
    """Read the actual tau2 working-tree SHA so reproducibility checks against
    config.yaml > tau2.pinned_sha catch drift."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT / "eval" / "tau2"), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--partition", default="retail_dev_30", choices=["retail_dev_30", "retail_sealed_20"])
    p.add_argument("--model", default=settings.DEV_LLM_MODEL)
    p.add_argument("--user-model", default=None,
                   help="Model for the τ² user simulator. Defaults to --model to keep cost bounded.")
    p.add_argument("--trials", type=int, default=5)
    p.add_argument("--seed", type=int, default=300, help="Base seed; tau2 derives per-trial seeds.")
    p.add_argument("--tier", default="dev", choices=["dev", "eval"])
    p.add_argument("--max-steps", type=int, default=100)
    p.add_argument("--max-concurrency", type=int, default=4)
    p.add_argument("--agent", default="llm_agent",
                   help="tau2 agent name. `llm_agent` is the Day-1 baseline; "
                        "`dual_control_agent[_lite]` are the Act IV mechanism variants.")
    args = p.parse_args()

    if args.tier == "eval" and not settings.EVAL_TIER_ENABLED:
        print("ERROR: EVAL_TIER_ENABLED unset. Refusing.", file=sys.stderr)
        return 2

    score = run_partition(
        partition=args.partition, model=args.model,
        trials=args.trials, seed=args.seed, tier=args.tier,
        user_model=args.user_model,
        max_steps=args.max_steps, max_concurrency=args.max_concurrency,
        agent=args.agent,
    )
    print(json.dumps(score, indent=2))
    flush()
    print(
        f"\nτ²-Bench {args.partition} score: pass@1={score['pass_at_1_mean']} "
        f"(95% CI {score['ci_95']}), cost/task=${score['cost_per_task_usd']:.4f}, "
        f"p50={score['p50_latency_ms']}ms, p95={score['p95_latency_ms']}ms\n"
        f"Langfuse trace: {score['langfuse_trace_url']}\n"
        f"Per-run logs:   {score['save_path']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
