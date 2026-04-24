# τ²-Bench retail baseline — dev slice

> Populated by `make tau2-baseline`. This is the Act I deliverable.

## What reproduced

- Partition: `retail_dev_30`, 30 tasks.
- Trials per run: 5, seeds `[42, 43, 44, 45, 46]`.
- Model: `DEV_LLM_MODEL` (OpenRouter dev-tier).
- See `eval/score_log.json` for the latest `pass_at_1_mean`, 95% CI, cost per
  run, and p50/p95 latency.

## Published reference and delta

- Feb 2026 τ²-Bench retail leaderboard ceiling: ~42%.
- Dev-tier reproduction is expected to sit 3–10 points below on first run.
- `reproduction_ci_overlaps_published` in `score_log.json` flags when the
  reproduction CI fails to bracket the published reference — that's a harness
  or LLM-calibration issue, investigate before closing Act I.

## Unexpected behavior

> Note surprising task-level patterns here after the run. Keep it to
> 1–2 sentences. One or two task IDs is enough.

## Headroom for mechanism

The Act III probe library will hunt the obvious dev-tier failure modes in
this domain:

- Dual-control coordination on refund-threshold tasks.
- Tool-sequencing errors under interleaved inventory + shipping operations.
- Missing-input tolerance on ambiguous address / payment inputs.

These preview the target failure mode candidate for Act IV.

---

*This file is strictly ≤400 words. CI enforces the wordcount in
`scripts/final_check.py`.*
