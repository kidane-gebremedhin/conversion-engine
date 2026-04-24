# 11 — τ²-Bench Harness

τ²-Bench is the non-substitutable benchmark anchor for the challenge. It grounds the Day-1 baseline, provides the retail-domain analog for B2B qualification conversation, and supplies the sealed held-out slice on which Act IV mechanisms are honestly evaluated.

## Provider

- **Repo**: `github.com/sierra-research/tau2-bench` (configurable via `TAU2_BENCH_REPO_URL`).
- **Pinned SHA**: stored in `config.yaml > tau2.pinned_sha` for reproducibility; never advanced mid-week.
- **Domains**:
  - **Retail** (primary) — closest public analog to B2B qualification conversation; this is where the baseline and mechanism are evaluated.
  - **Telecom** (secondary) — supplies probe signal for time-zone confusion, escalation phrasing.

## Partitions

| Partition | Size | Source | Use |
|---|---|---|---|
| Retail dev slice | 30 tasks | Ships with τ²-Bench | Act I baseline reproduction, Acts II/III iteration |
| Retail sealed held-out | 20 tasks | Program staff, delivered after policy acknowledgement is signed | Act IV mechanism evaluation **only** |

**The sealed partition is stored outside the repo.** `TAU2_HELDOUT_PATH` points to a location outside the git tree; loading it in dev-iteration code is a policy violation.

## Harness contract

`eval/harness.py` wraps τ²-Bench so that every run:

1. Writes a canonical `score_log.json` with `mean`, `95% CI`, `cost_per_run_usd`, `p50_latency_ms`, `p95_latency_ms`.
2. Writes `trace_log.jsonl` — one JSON object per trial, with full turn-by-turn trajectories.
3. Emits a Langfuse trace per trial with the attributes in [spec 10](10-observability.md).
4. Refuses to run the sealed partition unless `TAU2_SEALED_ACCESS=1` **and** `EVAL_TIER_ENABLED=1` are both set (guard against accidental burn of the 20-task budget on dev-tier models).
5. Refuses to run any partition without a pinned model ID from `config.yaml > llm.models.<tier>`.

## Model tiers

| Tier | Purpose | Candidates | Budget |
|---|---|---|---|
| **Dev** | Development, probing, mechanism prototyping; all dev-slice runs | Qwen3-Next-80B-A3B, DeepSeek V3.2 (via OpenRouter) | `budgets.dev_llm_max_usd` (target under $4, Days 1–4) |
| **Eval** | Sealed held-out scoring only | Claude Sonnet 4.6, GPT-5 class | `budgets.eval_llm_max_usd` (target under $12, Days 5–7) |

Model IDs, base URLs, and API keys are in env vars (never hard-coded). See [spec 18](18-configuration.md).

## Act I — Baseline and ground truth

**Goal**: reproduce the published τ²-Bench retail baseline within a 95% CI.

Process:

1. Clone τ²-Bench at pinned SHA into `eval/tau2/`.
2. Run `eval/harness.py --partition retail_dev_30 --model <dev_tier_model> --trials 5 --seed <seed>` (5-trial pass@1 on the full 30-task dev slice).
3. Record mean, 95% CI, cost per run, p50/p95 latency into `score_log.json`.
4. Write `trace_log.jsonl` — full trajectories across all dev trials.
5. Write `baseline.md` (≤400 words) describing what reproduced, the CI, the cost, and any unexpected behavior.

**Interim-submission requirement**: `score_log.json` + `trace_log.jsonl` + `baseline.md` committed to `eval/`.

The published τ²-Bench retail pass@1 ceiling is **~42%** per the leaderboard (Feb 2026). Reproducing within 95% CI is the gate for Acts II–IV; failure to reproduce means the dev-tier model or the harness is miscalibrated and must be fixed before mechanism work.

## Act II — Production stack use of τ²-Bench

The τ²-Bench harness is also used in the interim submission to show the baseline score alongside p50/p95 latency from real email/SMS interactions. The two measurements are distinct:

- τ²-Bench is a **benchmark** — clean, controlled, no human in the loop.
- The production-stack latency metrics come from synthetic-prospect interactions against the live email and SMS channels.

Both appear in the interim PDF report.

## Act IV — Mechanism evaluation

Three conditions evaluated on the sealed held-out 20 tasks:

| Condition | Model | Cost source |
|---|---|---|
| **Your Day-1 baseline** | Pinned dev-tier | `budgets.dev_llm_max_usd` |
| **Your mechanism** | Eval-tier | `budgets.eval_llm_max_usd` |
| **Automated-optimization baseline** (GEPA or AutoAgent) | Same compute budget as mechanism | Shared eval budget |

Three deltas:

- **Delta A** = `your_method - your_day1_baseline`. Must be positive with 95% CI separation. This is the primary grading metric.
- **Delta B** = `your_method - automated-optimization baseline` on the same compute budget. Failing Delta B does not fail the week; unexplained underperformance does.
- **Delta C** = `your_method - published τ²-Bench reference`. Informational only.

Statistical test for Delta A: paired bootstrap over the 20 held-out tasks, two-sided, **p < 0.05** required.

Artifacts:

- `method/ablation_results.json` — pass@1, 95% CI, cost-per-task, p95 latency for all three conditions.
- `method/held_out_traces.jsonl` — raw traces from all three conditions.
- `method/stat_test.md` — test statistic, p-value, discussion.

## Retail domain probes (linked to Act III)

The retail domain is instrumented with a subset of the probe library (see [spec 12](12-probe-library.md)). Specifically, τ²-Bench retail supplies native signal for:

- **Dual-control coordination** — retail's central failure mode (agent proceeds vs. waits for the user).
- **Tone drift** across 3–4 turns.
- **Time-zone confusion** (the telecom domain is the stronger source).
- **Cost pathology** — prompts that cause runaway token usage.

Tenacious-specific probes (ICP misclassification, bench over-commitment, gap over-claiming) are **not** native to τ²-Bench. They run as separate probe-library tests in `probes/runs/`.

## Reproducibility requirements

Every τ²-Bench run records:

- Git SHA of `eval/tau2/` (checked against pinned SHA; fails hard on drift).
- Git SHA of this repo at run time.
- Model ID, temperature, seed, max-tokens.
- Full hyperparameter snapshot.
- UTC timestamp start and end.

## What the τ²-Bench integration must NOT do

- Run the sealed partition with a dev-tier model (cheaper but defeats the purpose).
- Run the sealed partition without the dual-guard `TAU2_SEALED_ACCESS=1` AND `EVAL_TIER_ENABLED=1`.
- Use a model other than the pinned dev-tier for Acts I–III or a non-eval-tier model for Act IV.
- Modify the sealed held-out tasks in any way. Anomaly detection in the harness flags diffs against the program-delivered checksum.
- Skip the 5-trial pass@1 on the dev slice. Pass@1 with fewer trials inflates the CI artificially.
