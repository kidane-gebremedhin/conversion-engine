# 13 — Mechanism Design (Act IV)

Act IV takes the target failure mode identified in Act III and addresses it with an original mechanism. The mechanism must beat the Day-1 baseline on the sealed held-out slice with 95% CI separation.

## Input

- `probes/target_failure_mode.md` from Act III — the single highest-ROI failure, with business-cost derivation in Tenacious terms.
- Day-1 baseline score from Act I on the dev slice.
- The 20-task sealed held-out partition (access via `TAU2_SEALED_ACCESS=1` + `EVAL_TIER_ENABLED=1`).

## Mechanism directions worth considering

These are **suggestions** from the challenge brief. The trainee may implement one, two, or a novel combination. Every direction listed here addresses a specific probe category:

| Direction | Failure it addresses | Expected delta |
|---|---|---|
| **Signal-confidence-aware phrasing** | Signal over-claiming (cat 2), gap over-claiming (cat 10) | Reply rate up, brand risk down |
| **Bench-gated commitment policy** | Bench over-commitment (cat 3) | Handoff rate up, wrong-commitment rate down |
| **ICP classifier with abstention** | ICP misclassification (cat 1) | Abstention rate up, wrong-segment rate down |
| **Tone-preservation check (second model call)** | Tone drift (cat 4) | Tone-score regenerate rate ~10–20%, brand risk down |
| **Multi-channel handoff policy** | Scheduling edge cases (cat 8), channel misuse | SMS-to-email handoff tested |
| **Multi-thread isolation (key by email)** | Multi-thread leakage (cat 5) | Leakage probe trigger rate → 0 |

Implementing a tone-preservation check costs one extra LLM call per message — a design trade-off. The rate-card math for that call is in [spec 10](10-observability.md).

## Method.md contract

`method/method.md` documents:

- **Mechanism name and one-sentence description.**
- **Design rationale** — why this mechanism addresses the target failure mode, grounded in probe-library evidence.
- **Hyperparameters** — thresholds, regeneration counts, model IDs, tier. All derived from or cross-referenced against `config.yaml`.
- **Three ablation variants** — e.g., (a) mechanism off, (b) mechanism with threshold X, (c) mechanism with threshold 2X. Ablations are graded for discipline and isolation.
- **Statistical test** — paired bootstrap across the 20 sealed tasks; two-sided, **p < 0.05 required for Delta A**.

## Ablation variants (required)

Three variants are mandatory. Example for a tone-preservation check:

| Variant | Setting | Expected effect |
|---|---|---|
| A | Tone check off (= Day-1 baseline) | Baseline pass@1 |
| B | Tone check on, threshold 4/5 | Mechanism |
| C | Tone check on, threshold 3/5 | Ablation — too permissive |

All three variants must run on the same sealed held-out slice with the same seeds. Results in `method/ablation_results.json`:

```json
{
  "sealed_partition_sha": "<20-task-checksum>",
  "seeds": [42, 43, 44, 45, 46],
  "variants": {
    "A_baseline": { "pass_at_1_mean": 0.42, "ci_95": [0.35, 0.49], "cost_per_task_usd": 0.08, "p95_latency_ms": 4200 },
    "B_mechanism": { "pass_at_1_mean": 0.55, "ci_95": [0.48, 0.62], "cost_per_task_usd": 0.11, "p95_latency_ms": 5400 },
    "C_ablation": { "pass_at_1_mean": 0.50, "ci_95": [0.43, 0.57], "cost_per_task_usd": 0.10, "p95_latency_ms": 5300 }
  },
  "automated_optimization_baseline": {
    "method": "GEPA",
    "compute_budget_usd": 0.11,
    "pass_at_1_mean": 0.48,
    "ci_95": [0.41, 0.55]
  },
  "deltas": {
    "delta_a": 0.13,
    "delta_a_p_value": 0.008,
    "delta_b": 0.07,
    "delta_b_p_value": 0.04,
    "delta_c_informational": "+0.13 vs τ²-Bench Feb 2026 retail leaderboard (~0.42)"
  }
}
```

## Honest reporting against GEPA / AutoAgent

Delta B compares the mechanism against an automated-optimization baseline at the same compute budget. GEPA (Gradient-free Evolution Prompt Adaptation) or AutoAgent variants are the typical comparators.

Rules:

- Same compute budget (dollars, not tokens — the GEPA and human-designed mechanism may use different tiers).
- Same seeds.
- Same sealed partition.
- **Failing Delta B does not fail the challenge week.** Unexplained underperformance does. If GEPA wins, `method.md` must honestly discuss why.

## Traces (required)

`method/held_out_traces.jsonl` contains raw traces from all three conditions (your mechanism, Day-1 baseline, automated-optimization baseline) on the sealed partition. Every trace carries:

- `condition` — `your_method`, `day1_baseline`, or `automated_optimization`.
- `task_id`, `seed`.
- `cost_usd`, `wall_time_ms`.
- `pass` — boolean.

The memo's `evidence_graph.json` cites these trace IDs for any claim involving the mechanism or its deltas.

## Mechanism evaluation on production-stack data (supplementary)

Beyond τ²-Bench, the mechanism is also measured on synthetic-prospect data from [spec 10](10-observability.md):

- **Reply-rate delta** between `signal_grounded=True` and `signal_grounded=False` outbound variants (A/B tagged in HubSpot).
- **Stalled-thread-rate delta** vs. the 30–40% Tenacious manual baseline.
- **Abstention-rate** at the configured threshold (and its effect on reply rate).
- **Tone-check regenerate rate** and whether regenerations actually improve reply rate.

These measurements feed the memo's Page 1 (the decision) and Page 2 (the Skeptic's Appendix).

## What the mechanism must NOT do

- Be a generic prompt-engineering trick that happens to improve τ²-Bench retail but has no Tenacious mapping. The mechanism must address a specific probe-library category.
- Use a different dev-tier model at evaluation time vs. Day-1 baseline time. The comparison is invalid if the substrate differs.
- Report Delta A without a p-value and a 95% CI on the delta itself (not just on the pass@1 means).
- Claim Delta B success without running GEPA (or an equivalent automated optimizer) on the same budget.
