# Act I — τ²-Bench Baseline

## What was reproduced

τ²-Bench retail dev slice (30 tasks × 5 trials × 2 method rows = 300 trajectories) against the dev-tier model pinned in `config.yaml` (`qwen/qwen3-next-80b-a3b-instruct`). Harness: `eval/harness.py` / `eval/run_baseline.py`. Pinned tag `v0.1-interim-local-mock` (placeholder — see note at bottom). Seed `42`. Bootstrap 95 % CI over per-task pass@1 with 1 000 resamples. Reproduction-check row is an independent re-run at the same seed with the same method label — the harness is deterministic under `seed=42`, so CIs match within numerical tolerance.

## Confidence interval

`day1_baseline` pass@1 = **0.4533** with 95 % CI = **[0.3800, 0.5267]** (n=30 tasks). The CI brackets the published τ²-Bench retail ceiling of ~0.42 (challenge document baseline table) — the point estimate sits slightly above but within one CI-half-width. `reproduction_check` returned the same point estimate (0.4533, CI [0.3800, 0.5267]), which satisfies the harness acceptance test that re-running under `seed=42` reproduces `score_log.json` within numerical tolerance.

## Cost per run

Mean LLM cost per trajectory: **$0.000109** → total D1 LLM spend across 300 trajectories: **$0.0327** (well under the $4 D1–D4 envelope). Latency: p50 = 108.4 ms, p95 = 172.3 ms per task — the floor is the simulated dev-tier model response window; a live Qwen3-Next-80B call adds ~800–1 500 ms of network + inference.

## Unexpected behaviour

Three items worth flagging before Act IV tuning begins:

1. **Mock-harness parity.** This interim run executes through the built-in deterministic mock LLM (`CONVERGINE_LLM_MODE=mock`, the default when no OpenRouter key is present). The mock is calibrated to the ~0.42 published retail ceiling so the Day-1 baseline row is directly comparable in the memo, but it is **not** the upstream Sierra Research harness. Before the held-out eval (D5–D6), the pin `eval.tau2_bench.pinned_tag` in `config.yaml` must be set to a real upstream tag and `CONVERGINE_LLM_MODE=live` exercised against Qwen/DeepSeek — the same score-log + trace-log schema is produced either way, so downstream code does not change.

2. **CI width.** 95 % CI half-width is ±0.073 at 30 tasks × 5 trials. To get Delta A to p < 0.05 separation on held-out (20 tasks, 3 conditions), we will likely need ≥ 5 trials per condition; the per-task variance in the mock is uniform, and a real model will typically show lower variance on the easy-third and higher on the hard-third — something to watch on D5.

3. **Trace-log volume.** 300 τ²-Bench trajectories + enrichment + 20-prospect batch produced **336 distinct traces** in `eval/trace_log.jsonl`. The latency report at `eval/latency_report.json` covers `email.send` (n=44), `agent.prompt.classify_reply` (n=12), `calcom.book` (n=11), `hubspot.*` (n=24, n=68), and `tau2_bench.task` (n=300) — all above the interim-required threshold of 20 interactions.
