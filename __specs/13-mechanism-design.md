# 13 — Mechanism Design (Act IV)

**Source:** Challenge document — "Act IV — Mechanism Design", "Mechanism attribution" (grading row).

## 1. Objective

Design one original mechanism that targets the highest-ROI failure mode from [12 §6](12-probe-library.md) and beats the Day-1 baseline on the sealed τ²-Bench held-out slice with 95 % CI separation and p < 0.05.

## 2. Candidate mechanisms

Pick one. Others become ablation comparisons.

### Candidate A — Signal-confidence-aware phrasing (recommended default)

**Target failure modes:** signal over-claiming (§2 in probe library), gap over-claiming, tone drift.

**Mechanism.** Every outbound draft is pre-processed against `hiring_signal_brief.signals[*].confidence`. For each cited signal, the generator emits one of three phrasings — assert / soften / ask — keyed by confidence band. A second validator call (<200 completion tokens) verifies the draft matches the expected phrasing for each cited signal. If it doesn't, regenerate up to 2× then `handoff_human`.

**Why it wins on Tenacious.** It directly addresses brand-reputation risk, the highest-cost axis in the challenge. The mechanism is composable with `tone_check` and `bench_check`.

**Hyperparameters.** Band thresholds (0.50, 0.75). Regeneration limit (2). Validator model (cheap dev-tier).

### Candidate B — Bench-gated commitment policy

**Target failure modes:** bench over-commitment; deal-stall risk in proposal stage.

**Mechanism.** Hard parser over every draft that extracts capacity claims (regex + LLM extractor), cross-checks against `bench_summary.yaml`, blocks send on mismatch, and forces `handoff_human(reason=prospect_asked_bench_beyond_capacity)` for prospect-initiated asks. The policy is **non-negotiable** — there is no "soften" branch.

**Why it might win.** Zero-tolerance policies are easy to validate statistically and reduce variance in held-out scoring.

### Candidate C — ICP classifier with abstention

**Target failure modes:** ICP misclassification.

**Mechanism.** Lightweight classifier (logistic regression on hand-labelled Crunchbase features, trained on 30–50 labelled prospects from the dev pool) with thresholded abstention. Below threshold → `exploratory` variant.

**Why it might win.** Upgrades the naive rule-based classifier in [03](03-icp-and-segments.md) into a learned one.

### Candidate D — Tone-preservation check (second-call guard)

**Target failure modes:** tone drift.

**Mechanism.** Second, cheap model call scores style-guide adherence per draft; regenerate if below threshold. Cost is an explicit ablation axis.

### Candidate E — Multi-channel handoff policy

**Target failure modes:** scheduling stalls; channel mismatch.

**Mechanism.** Data-driven rules (trained on probe runs + τ²-Bench retail traces) for when to switch email → SMS → human.

## 3. Required artifacts

| File | Contents |
|------|----------|
| `method/method.md` | Mechanism description, design rationale, hyperparameters, 3 ablation variants, statistical-test summary, Deltas A/B/C |
| `method/ablation_results.json` | pass@1, 95 % CI, cost-per-task, p95 latency for method + day1_baseline + auto-optim on held-out |
| `method/held_out_traces.jsonl` | Raw traces for each of the 3 held-out conditions |
| `method/mechanism.py` | Implementation (uses the `Mechanism` protocol from [06 §7](06-agent-design.md)) |
| `method/stat_test.py` | Paired bootstrap; outputs Delta A + p-value |

## 4. Ablation plan

Three ablation variants, each controlled independently:

| Variant | Hyperparameter swept | Expected direction |
|---------|----------------------|--------------------|
| 3a | No regeneration loop (max_retries = 0) | Higher failure rate on held-out |
| 3b | Different thresholds (e.g., 0.40 / 0.65 instead of 0.50 / 0.75) | Sensitivity curve |
| 3c | Dev-tier validator replaced with eval-tier | Cost up, marginal quality gain |

Each variant's pass@1, CI, and cost are reported side-by-side in `ablation_results.json`.

## 5. Automated-optimization comparison (Delta B)

Pick **one** of:
- GEPA (Generative Evolutionary Prompt Automation)
- AutoAgent

Run it on the same compute budget as our method (same trials, same eval-tier model, same slice).

**Failing Delta B does not fail the week.** Unexplained underperformance does. If our method underperforms auto-optim, `method.md` must include a 150–250-word analysis covering:
- Why auto-optim found a better solution
- Whether the auto-optim solution generalises (honest assessment)
- What our method retains as an advantage (interpretability? latency? cost?)

## 6. Statistical test

```python
# method/stat_test.py
def delta_a_bootstrap(method_traces, baseline_traces, resamples=10_000) -> Result:
    paired = pair_by_task(method_traces, baseline_traces)
    diffs = [m.pass_at_1 - b.pass_at_1 for m, b in paired]
    deltas = [mean(random_choice(diffs, n=len(diffs), replace=True)) for _ in range(resamples)]
    delta_point = mean(diffs)
    ci_low, ci_high = percentiles(deltas, [2.5, 97.5])
    p_value = 2 * min(sum(d <= 0 for d in deltas), sum(d >= 0 for d in deltas)) / resamples
    return Result(delta_point, (ci_low, ci_high), p_value)
```

**Acceptance**: Delta A point > 0, CI strictly above 0, `p_value < 0.05`.

## 7. Cost budgeting

Held-out eval of 3 conditions × 5 trials × 20 tasks = **300 task-runs**.

- Dev-tier (Days 1–4): not used on held-out. Baseline + mechanism development only.
- Eval-tier (Days 5–7): target ≤ $12. If projected overrun, reduce trials from 5 → 3 and note in `method.md`.

Track per-trial cost in Langfuse; abort eval if projected spend exceeds the envelope.

## 8. Evidence-graph mapping

Every claim about Delta A / B / C in the memo has a matching `evidence_graph.json` entry:

```json
{
  "claim_id": "memo.page1.deltaA",
  "statement": "Our method beats the Day-1 baseline by +7.3 pts pass@1 (95% CI: +3.1, +11.6; p = 0.004) on the sealed held-out slice.",
  "sources": [
    {"type": "ablation_results", "path": "method/ablation_results.json", "selector": "$.held_out.method.pass_at_1"},
    {"type": "ablation_results", "path": "method/ablation_results.json", "selector": "$.held_out.day1_baseline.pass_at_1"},
    {"type": "stat_test", "path": "method/stat_test_output.json"}
  ]
}
```

## 9. Acceptance tests

- `method.md` contains: mechanism description, rationale, hyperparameters, 3 ablations, Delta A with CI and p-value, Delta B with explanation, Delta C informational note.
- `ablation_results.json` schema validates and contains 3 variants + 3 conditions.
- `held_out_traces.jsonl` contains traces for all 3 held-out conditions × ≥ 3 trials × 20 tasks.
- `stat_test.py` run on held-out traces returns Delta A > 0, CI above 0, p < 0.05.
- `method/mechanism.py` implements the `Mechanism` protocol and is wired into `agent/orchestrator.py` behind the `method_name` config switch.
