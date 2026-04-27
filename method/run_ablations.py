"""`python -m method.run_ablations` — Act IV ablation runner.

Three conditions on the τ²-Bench retail sealed held-out partition:

    A_baseline       — tau2 stock `llm_agent`           + dev-tier model.
                       The Day-1 baseline; what beats this with 95% CI
                       separation passes Delta A.
    B_mechanism      — `dual_control_agent` (full)      + dev-tier model
                       by default; pass --tier=eval for the spec-aligned
                       run on the eval-tier model.
    C_ablation       — `dual_control_agent_lite`        + same tier as B.
                       Drops rules R3+R4+R5; isolates whether the extra
                       discipline rules carry weight beyond R1+R2.

Pairs by task_id across conditions for a paired-task bootstrap CI on
Delta A = B − A. Two-sided p-value via centered bootstrap; p < 0.05 is
the gate per Act IV.

Outputs (under `method/`):
    ablation_results.json   — pass@1, 95% CI, cost-per-task, p95 latency
                              for all three conditions; Delta A + CI + p.
    held_out_traces.jsonl   — every simulation from every condition,
                              one JSON per sim, for the evidence graph.
    stat_test.md            — paired bootstrap math + interpretation.

Sealed partition is dual-guarded: TAU2_SEALED_ACCESS=1 + EVAL_TIER_ENABLED=1.
Use --partition=retail_dev_30 (and --skip-guard) for cheap iteration on the
mechanism design before burning the sealed budget.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import sys
from typing import Any

from agent.config import REPO_ROOT, config, settings
from eval.harness import run_partition


HELDOUT_TRACES = REPO_ROOT / "method" / "held_out_traces.jsonl"
ABLATION_RESULTS = REPO_ROOT / "method" / "ablation_results.json"
STAT_TEST = REPO_ROOT / "method" / "stat_test.md"
TRACE_LOG = REPO_ROOT / "eval" / "trace_log.jsonl"


CONDITIONS: list[dict[str, str]] = [
    {"name": "A_baseline", "agent": "llm_agent", "label": "Day-1 baseline (stock llm_agent)"},
    {"name": "B_mechanism", "agent": "dual_control_agent", "label": "Mechanism (full dual-control)"},
    {"name": "C_ablation", "agent": "dual_control_agent_lite", "label": "Ablation (R1+R2 only)"},
]


def _guard(partition: str, skip: bool) -> None:
    if partition == "retail_sealed_20" and not skip:
        if not (settings.TAU2_SEALED_ACCESS and settings.EVAL_TIER_ENABLED):
            print(
                "ERROR: sealed-slice access requires both TAU2_SEALED_ACCESS=1 "
                "and EVAL_TIER_ENABLED=1. Use --partition=retail_dev_30 for "
                "iteration, or --skip-guard if you know what you're doing.",
                file=sys.stderr,
            )
            raise SystemExit(2)


def _paired_bootstrap_ci(deltas: list[float], *, n_resamples: int, seed: int) -> tuple[float, float]:
    if not deltas:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(deltas)
    samples: list[float] = []
    for _ in range(n_resamples):
        resampled = [deltas[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(resampled) / n)
    samples.sort()
    lo = samples[int(math.floor(0.025 * n_resamples))]
    hi = samples[int(math.ceil(0.975 * n_resamples)) - 1]
    return lo, hi


def _paired_bootstrap_p(deltas: list[float], *, n_resamples: int, seed: int) -> float:
    """Two-sided p for H0: mean(delta) = 0. Centered bootstrap."""
    if not deltas:
        return 1.0
    n = len(deltas)
    observed = sum(deltas) / n
    centered = [d - observed for d in deltas]
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_resamples):
        sample_mean = sum(centered[rng.randrange(n)] for _ in range(n)) / n
        if abs(sample_mean) >= abs(observed):
            hits += 1
    return hits / n_resamples


def _harvest_sim_rows(run_id: str) -> list[dict[str, Any]]:
    """Pull rows belonging to `run_id` out of eval/trace_log.jsonl."""
    if not TRACE_LOG.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(TRACE_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("run_id") == run_id:
                rows.append(row)
    return rows


def _write_held_out_traces(per_condition_rows: dict[str, list[dict[str, Any]]]) -> None:
    """Write the paired held_out_traces.jsonl: one row per (condition, sim)."""
    HELDOUT_TRACES.parent.mkdir(parents=True, exist_ok=True)
    with open(HELDOUT_TRACES, "w", encoding="utf-8") as f:
        for cond, rows in per_condition_rows.items():
            for row in rows:
                out = {"condition": cond, **row}
                f.write(json.dumps(out, default=str) + "\n")


def _write_stat_test(out: dict[str, Any]) -> None:
    da = out["deltas"]["delta_a"]
    da_ci = out["deltas"]["delta_a_ci_95"]
    da_p = out["deltas"]["delta_a_p_value"]
    n_tasks = out["n_paired_tasks"]
    a = out["conditions"]["A_baseline"]["pass_at_1_mean"]
    b = out["conditions"]["B_mechanism"]["pass_at_1_mean"]
    verdict = "PASSES (Delta A > 0 with p < 0.05)" if (da > 0 and da_p < 0.05) else "DOES NOT PASS"

    body = f"""# Statistical test — Delta A

**Question.** Does the Act IV mechanism (full dual-control) outperform
the Day-1 baseline (stock `llm_agent`) on the same partition, paired by
task?

**Method.** Paired-task percentile bootstrap. For each task in the
partition, take pass-rate(B) − pass-rate(A) across that task's trials.
Resample the task-level delta vector with replacement {out['stat_test']['n_resamples']} times for the
CI; centered bootstrap of the same size for the p-value.

**Result.**

| Quantity | Value |
|---|---|
| Pass@1 — A (baseline)  | {a} |
| Pass@1 — B (mechanism) | {b} |
| Δ̂ A = B − A           | {da} |
| 95% CI on Δ̂ A         | [{da_ci[0]}, {da_ci[1]}] |
| Two-sided p-value      | {da_p} |
| Paired tasks (n)       | {n_tasks} |
| Resamples              | {out['stat_test']['n_resamples']} |

**Verdict.** **{verdict}.**

The Act IV gate is `Delta A > 0 AND p < 0.05`. Failing this means the
mechanism does not pass; the trainee must either revise the mechanism
or honestly report the null result in `memo.pdf` Page 2.

**Reproducibility.** Same partition, same trial count, same seed across
all conditions; tau2 SHA `{out['git_sha_tau2']}` pinned in
`config.yaml > tau2.pinned_sha`. Bootstrap RNG seed: {out['stat_test']['bootstrap_seed']}.
"""
    STAT_TEST.parent.mkdir(parents=True, exist_ok=True)
    STAT_TEST.write_text(body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partition", default="retail_sealed_20",
                    choices=["retail_sealed_20", "retail_dev_30"])
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--seed", type=int, default=300)
    ap.add_argument("--tier", default="dev", choices=["dev", "eval"],
                    help="dev-tier on both A and B keeps cost bounded; eval-tier "
                         "follows the PDF spec for sealed Act IV scoring.")
    ap.add_argument("--baseline-tier", default=None, choices=[None, "dev", "eval"],
                    help="Optionally pin the A-baseline tier independently of B (PDF default: dev).")
    ap.add_argument("--max-steps", type=int, default=100)
    ap.add_argument("--max-concurrency", type=int, default=4)
    ap.add_argument("--bootstrap-resamples", type=int, default=5000)
    ap.add_argument("--bootstrap-seed", type=int, default=0)
    ap.add_argument("--skip-guard", action="store_true",
                    help="Bypass the sealed-partition dual-guard (dev only).")
    args = ap.parse_args()

    _guard(args.partition, args.skip_guard)

    baseline_tier = args.baseline_tier or args.tier
    baseline_model = settings.DEV_LLM_MODEL if baseline_tier == "dev" else settings.EVAL_LLM_MODEL
    mechanism_model = settings.DEV_LLM_MODEL if args.tier == "dev" else settings.EVAL_LLM_MODEL

    # Run all three conditions back-to-back so the random / network state is
    # roughly comparable. Same trial seed, same task ordering.
    per_condition_score: dict[str, dict[str, Any]] = {}
    per_condition_rows: dict[str, list[dict[str, Any]]] = {}
    for cond in CONDITIONS:
        is_baseline = cond["name"] == "A_baseline"
        tier = baseline_tier if is_baseline else args.tier
        model = baseline_model if is_baseline else mechanism_model

        print(f"\n=== Running {cond['name']}: agent={cond['agent']}, tier={tier}, model={model} ===",
              file=sys.stderr)
        score = run_partition(
            partition=args.partition,
            model=model,
            trials=args.trials,
            seed=args.seed,
            tier=tier,
            max_steps=args.max_steps,
            max_concurrency=args.max_concurrency,
            agent=cond["agent"],
        )
        per_condition_score[cond["name"]] = score
        per_condition_rows[cond["name"]] = _harvest_sim_rows(score["run_id"])

    # Paired bootstrap on the per-task pass-rate vectors. Use the intersection
    # of task ids across A and B (in case a sim was lost to infra error in one
    # condition but not the other).
    a_tasks = per_condition_score["A_baseline"]["task_pass_rate"]
    b_tasks = per_condition_score["B_mechanism"]["task_pass_rate"]
    paired_ids = sorted(set(a_tasks) & set(b_tasks), key=lambda x: int(x) if str(x).isdigit() else x)
    deltas_ba = [b_tasks[t] - a_tasks[t] for t in paired_ids]
    mean_ba = sum(deltas_ba) / len(deltas_ba) if deltas_ba else 0.0
    lo_ba, hi_ba = _paired_bootstrap_ci(
        deltas_ba, n_resamples=args.bootstrap_resamples, seed=args.bootstrap_seed,
    )
    p_ba = _paired_bootstrap_p(
        deltas_ba, n_resamples=args.bootstrap_resamples, seed=args.bootstrap_seed,
    )

    out: dict[str, Any] = {
        "partition": args.partition,
        "trials": args.trials,
        "base_seed": args.seed,
        "tau2_pinned_sha": str(config.get("tau2.pinned_sha", "")),
        "git_sha_tau2": per_condition_score["A_baseline"].get("git_sha_tau2", ""),
        "git_sha_repo": per_condition_score["A_baseline"].get("git_sha_repo", ""),
        "n_paired_tasks": len(paired_ids),
        "conditions": {
            cond_name: {
                "agent": [c["agent"] for c in CONDITIONS if c["name"] == cond_name][0],
                "tier": s["tier"],
                "model": s["model"],
                "pass_at_1_mean": s["pass_at_1_mean"],
                "ci_95": s["ci_95"],
                "cost_total_usd": s["cost_total_usd"],
                "cost_per_task_usd": s["cost_per_task_usd"],
                "p50_latency_ms": s["p50_latency_ms"],
                "p95_latency_ms": s["p95_latency_ms"],
                "n_tasks": s["n_tasks"],
                "n_simulations": s["n_simulations"],
                "run_id": s["run_id"],
                "langfuse_trace_url": s["langfuse_trace_url"],
            }
            for cond_name, s in per_condition_score.items()
        },
        "automated_optimization_baseline": {
            "method": "GEPA (placeholder)",
            "compute_budget_usd": per_condition_score["B_mechanism"]["cost_total_usd"],
            "pass_at_1_mean": None,
            "ci_95": [None, None],
            "note": "Slot reserved per Act IV. Plug in numbers when GEPA is run on the same compute budget.",
        },
        "deltas": {
            "delta_a": round(mean_ba, 4),
            "delta_a_ci_95": [round(lo_ba, 4), round(hi_ba, 4)],
            "delta_a_p_value": round(p_ba, 4),
            "delta_a_passes_gate": (mean_ba > 0 and p_ba < 0.05),
            "note": "Delta A = B_mechanism − A_baseline, paired by task_id, "
                    "two-sided percentile bootstrap. Gate: > 0 AND p < 0.05.",
        },
        "stat_test": {
            "method": "paired_task_percentile_bootstrap",
            "n_resamples": args.bootstrap_resamples,
            "bootstrap_seed": args.bootstrap_seed,
        },
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    ABLATION_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    ABLATION_RESULTS.write_text(json.dumps(out, indent=2))
    _write_held_out_traces(per_condition_rows)
    _write_stat_test(out)

    print(json.dumps(out, indent=2))
    print(
        f"\nWrote: {ABLATION_RESULTS}\n"
        f"       {HELDOUT_TRACES}\n"
        f"       {STAT_TEST}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
