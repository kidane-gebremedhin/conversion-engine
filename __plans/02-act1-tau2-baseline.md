# 02 — Act I: τ²-Bench Retail Baseline

## Goal

Reproduce the τ²-Bench retail baseline on the 30-task dev slice with the pinned dev-tier model, record a 5-trial pass@1 with 95% CI, log cost and latency, and produce `baseline.md` (≤400 words). This establishes the ground-truth anchor the rest of the project compares against.

## Spec references

- [`__specs/11-tau2-bench-harness.md`](../__specs/11-tau2-bench-harness.md)
- [`__specs/10-observability.md`](../__specs/10-observability.md) — trace attributes for τ²-Bench spans.
- [`__specs/18-configuration.md`](../__specs/18-configuration.md) — model-ID and rate-card config.

## Dependencies

- [`01-preflight.md`](01-preflight.md) complete (accounts, smoke test green, τ²-Bench clone present at pinned SHA).
- `DEV_LLM_MODEL` set in `.env`.
- `budgets.dev_llm_max_usd` in `config.yaml` with at least $2 headroom reserved for this phase.

## Tasks

### 2.1 Harness wrapper

1. Implement `eval/harness.py` that wraps τ²-Bench retail runs with:
   - A `run_partition(partition, model, trials, seeds, tier)` entrypoint.
   - Langfuse span emission per trial with all required attributes from [spec 10](../__specs/10-observability.md).
   - Cost attribution via the rate card in `config.yaml > llm.rate_cards`.
   - Wall-time capture for p50/p95 latency.
   - A dual-guard assertion: `sealed` partition requires `TAU2_SEALED_ACCESS=1` **and** `EVAL_TIER_ENABLED=1`; otherwise raises.
2. Add a `--trials`, `--seeds`, `--partition retail_dev_30 | retail_sealed_20`, `--model` CLI.

### 2.2 Reproduction run

1. Run: `python -m eval.harness --partition retail_dev_30 --model $DEV_LLM_MODEL --trials 5 --seeds 42,43,44,45,46 --tier dev`.
2. Expected ceiling per τ²-Bench Feb 2026 leaderboard: **~42% retail pass@1**. Dev-tier reproduction is expected to sit 3–10 points below on first run.
3. Watch total cost stay under `budgets.dev_llm_max_usd * 0.5` (this is one of several dev-tier workloads).

### 2.3 Score log

1. Emit `eval/score_log.json` with:

```json
{
  "run_id": "act1_baseline_<timestamp>",
  "partition": "retail_dev_30",
  "model": "<DEV_LLM_MODEL>",
  "tier": "dev",
  "trials": 5,
  "seeds": [42, 43, 44, 45, 46],
  "pass_at_1_mean": 0.38,
  "ci_95": [0.30, 0.46],
  "cost_total_usd": 1.42,
  "cost_per_run_usd": 0.284,
  "p50_latency_ms": 3100,
  "p95_latency_ms": 5800,
  "git_sha_repo": "<repo-sha>",
  "git_sha_tau2": "<pinned-tau2-sha>",
  "published_reference_pass_at_1": 0.42,
  "reproduction_delta": -0.04,
  "reproduction_ci_overlaps_published": true
}
```

2. If `reproduction_ci_overlaps_published` is `false`, investigate — the dev-tier model or the harness is miscalibrated.

### 2.4 Trace log

1. Emit `eval/trace_log.jsonl` — one JSON object per trial, with full turn-by-turn trajectory.
2. Each line includes `task_id`, `seed`, `pass`, `turns[]`, `total_tokens`, `cost_usd`, `wall_time_ms`.
3. Verify via `jq length eval/trace_log.jsonl` that the line count equals `len(tasks) × trials = 30 × 5 = 150`.

### 2.5 Baseline memo

Write `eval/baseline.md` (≤400 words, enforced by wordcount in CI). Sections:

1. **What reproduced**: headline pass@1, 95% CI, cost per run, p50/p95 latency.
2. **Published reference and delta**: the ~42% Feb 2026 retail ceiling; our delta with explanation if negative.
3. **Unexpected behavior**: any task where the dev-tier model behaved qualitatively differently from expectation. One or two sentences is enough.
4. **Headroom for mechanism**: where the obvious failure modes are (dual-control coordination, tool-sequencing errors, etc.) — preview for Act III probes.

### 2.6 Reproduction check (sanity)

1. Re-run the Act I baseline **once more** with a different seed set `[100, 101, 102, 103, 104]`.
2. Confirm `pass_at_1_mean` falls within the 95% CI from the original run.
3. If it doesn't, the harness has a source of non-determinism beyond LLM sampling — investigate (likely candidates: environment temperature, missing seed on tool calls).

## Acceptance criteria

- [ ] `eval/score_log.json` present with all fields populated.
- [ ] `eval/trace_log.jsonl` has 150 lines (5 trials × 30 tasks).
- [ ] `eval/baseline.md` is ≤400 words.
- [ ] Reproduction CI overlaps the published reference, **or** the delta is ≥95% CI and explained in `baseline.md`.
- [ ] Total cost ≤ 50% of `budgets.dev_llm_max_usd`.
- [ ] `git rev-parse HEAD:eval/tau2` matches `config.yaml > tau2.pinned_sha`.
- [ ] Langfuse shows 150 τ²-Bench trace entries with `tier=dev`.

## Submission gate

**Interim**: `eval/score_log.json` + `eval/trace_log.jsonl` + `eval/baseline.md` are part of the Wednesday submission. They are the Act I deliverables.

## Exit risks

- **Pass@1 collapse** (≤20%): dev-tier model is miscalibrated or the harness is broken. Mitigation: run one task by hand with `--trials 1 --verbose` and inspect the trajectory; check temperature, max-tokens, and system prompt.
- **Cost blowout**: 5 trials × 30 tasks with a chatty model can go over budget. Mitigation: set `max_tokens` per turn conservatively in `config.yaml`; the retail domain's mean trajectory length is ~8 turns.
- **Non-determinism beyond LLM sampling**: if reproduction check fails, suspect random IDs in the τ²-Bench setup, cache state, or tool-call ordering. Mitigation: pin every random seed the harness can reach.
- **Eval-tier leakage**: if `EVAL_TIER_ENABLED=1` was accidentally set, the dev run burns the sealed-partition budget. Mitigation: harness refuses to run `dev` tier with an eval-tier model ID (catches the mistake at setup time).
