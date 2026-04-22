# 11 — τ²-Bench Harness

**Source:** Challenge document — "Act I — Baseline and Ground Truth", "Act IV — Mechanism Design", "Data Source 4 — τ²-Bench", baseline table ("Voice agent conversational pass@1 ceiling ~42 % τ²-Bench retail").

## 1. What τ²-Bench is

Sierra Research's dual-control conversational agent benchmark. Retail domain is the closest public analog to B2B qualification; telecom is used for secondary probes. Repo: `github.com/sierra-research/tau2-bench`.

## 2. Bench slices

| Slice | Size | Purpose | Access |
|-------|------|---------|--------|
| Dev | 30 tasks | Iteration during Days 1–4 | Open |
| Sealed held-out | 20 tasks | Act IV final scoring | Delivered by program staff; **not opened** until Day 5 |
| Telecom probes | ~10 tasks | Secondary probes in Act III | Open |

**Hard rule:** No Act IV mechanism may be tuned on the sealed held-out slice. Breaking this invalidates Delta A.

## 3. Pinning

Pin exact commits in `config.yaml`:

```yaml
eval:
  tau2_bench:
    repo: https://github.com/sierra-research/tau2-bench
    pinned_tag: v1.x.y                 # set at Day-0 kickoff
    domain_retail_version: v1.x.y
    domain_telecom_version: v1.x.y
    dev_tier_model: qwen3-next-80b-a3b-instruct
    eval_tier_model: claude-sonnet-4-6
    seed: 42
    trials_per_slice: 5
```

A change to any of these values requires a re-run and a diff entry in `eval/baseline.md`.

## 4. Harness wrapper

```python
# eval/harness.py

class Tau2BenchHarness:
    def __init__(self, cfg, llm_client, langfuse_client): ...

    def run_slice(self, slice_name: Literal["dev", "held_out", "telecom"],
                  trials: int,
                  method_name: str) -> SliceResult: ...

    def score(self, results: SliceResult) -> ScoreReport:
        """pass@1 mean, 95 % bootstrap CI (1000 resamples), cost per run, p50/p95 latency."""
```

Every run emits to:
- `eval/trace_log.jsonl` (full trajectories, one JSONL row per trace, format [10 §5](10-observability.md))
- `eval/score_log.json` (aggregate metrics, keyed by `(slice, method, model, timestamp)`)

Langfuse instrumentation wraps every task invocation; tags include `slice`, `task_id`, `method_name`, `trial`.

## 5. Baseline protocol (Act I — due Wed 22 Apr)

1. Clone + checkout pinned tag.
2. Run retail domain on the 30-task dev slice with the pinned dev-tier model.
3. 5 trials → compute pass@1 mean + 95 % CI.
4. Record cost per run, p50/p95 latency.
5. Write `eval/baseline.md` (max 400 words) covering: what was reproduced, confidence interval, cost per run, unexpected behaviour.
6. Report against the published τ²-Bench retail reference (~42 % ceiling noted in the challenge baseline table).

`score_log.json` must contain at least two entries by Wed 21:00 UTC:
- `slice=dev, method=day1_baseline, trials=5`
- `slice=dev, method=reproduction_check` — an independent re-run verifying the harness is deterministic under `seed=42`.

## 6. Act IV evaluation protocol (due Sat 25 Apr)

Three conditions, **all on the sealed held-out slice**, all with identical compute budget:

| Condition | Label |
|-----------|-------|
| Day-1 baseline (no mechanism) | `method=day1_baseline` |
| Automated-optimization baseline (GEPA **or** AutoAgent) | `method=auto_optim` |
| Your mechanism | `method=<chosen_mechanism>` |

### Deltas

- **Delta A** = `your_method − day1_baseline` on held-out. **Must be positive with 95 % CI separation. Must pass paired statistical test at p < 0.05.**
- **Delta B** = `your_method − auto_optim` on held-out. Failing Delta B does not fail the week; unexplained underperformance does.
- **Delta C** = `your_method − published τ²-Bench reference`. Informational only.

### Statistical test

`method/stat_test.py` implements:
- Paired bootstrap over per-task pass@1 (10 000 resamples).
- Report two-tailed p-value for `H0: your_method == day1_baseline`.
- Report Delta A point estimate + 95 % CI.

## 7. Cost envelope

Per the production-stack table:
- Days 1–4 (dev-tier, dev slice): target < $4 total LLM spend.
- Days 5–7 (eval-tier, held-out × 3 conditions × 5 trials): target < $12 total.

If projected cost to finish held-out exceeds $12, cut trials per condition from 5 → 3 (still within paper-style conventions) and note in `method.md`.

## 8. Outputs

| File | Act | Purpose |
|------|-----|---------|
| `eval/score_log.json` | I, IV | Aggregate metrics per run |
| `eval/trace_log.jsonl` | I, IV | Full trajectories |
| `eval/baseline.md` | I | ≤ 400-word Act I write-up |
| `method/held_out_traces.jsonl` | IV | Raw traces across the three held-out conditions |
| `method/ablation_results.json` | IV | pass@1, 95 % CI, cost-per-task, p95 latency for method + baseline + auto-optim |
| `method/method.md` | IV | Mechanism, rationale, hyperparameters, 3 ablation variants, statistical test |

## 9. Acceptance tests

- `make baseline` rerun with `seed=42` reproduces `score_log.json` within numerical tolerance.
- `score_log.json` entries all carry a non-null 95 % CI derived from the bootstrap.
- The 20-task sealed held-out file is not listed in any git-tracked training or tuning script — verified by `scripts/audit_seal.sh`.
- `stat_test.py` produces a non-null p-value < 0.05 when run against `method/held_out_traces.jsonl` for the final method vs. day-1 baseline.
