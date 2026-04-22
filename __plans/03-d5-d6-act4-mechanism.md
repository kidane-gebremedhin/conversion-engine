# 03 — Days 5–6: Act IV Mechanism + Held-Out Evaluation

**Purpose:** Design and implement one original mechanism that addresses the D4-picked target failure family, beat the D1 baseline on the sealed τ²-Bench held-out slice with Delta A positive at p < 0.05, and report honestly against an automated-optimization baseline (Delta B).

**Reference specs:** [__specs/11](/home/kg/Projects/10Academy/conversion-engine/__specs/11-tau2-bench-harness.md), [__specs/13](/home/kg/Projects/10Academy/conversion-engine/__specs/13-mechanism-design.md), [__specs/06 §7](/home/kg/Projects/10Academy/conversion-engine/__specs/06-agent-design.md).

**Entry gate:** [02-d4-act3-probes.md §9](02-d4-act3-probes.md) complete. `probes/target_failure_mode.md` in hand. O4 closed.

**Exit gate:** `method/ablation_results.json` and `method/stat_test_output.json` show Delta A > 0, CI > 0, p < 0.05 on held-out.

---

## Day 5 — Mechanism implementation + auto-optim baseline (≈ 10 h)

### D5.1 — Close remaining open decisions (30 min)

- **O3** — eval-tier model. Run one dry task with both Claude Sonnet 4.6 and the GPT-5-class alternative. Pick the one projecting into budget for 300 task-runs. Update [00-decisions.md](00-decisions.md).
- **O6** — auto-optim framework. Default GEPA. Confirm it can be configured to match our compute budget (same dev-tier model, same trials, same slice) with < 2 h integration work. If not, swap to AutoAgent.

### D5.2 — Seal audit (15 min, before any held-out invocation)

```
scripts/audit_seal.sh
```

Must exit 0. Any hit indicates someone imported or referenced `held_out_slice.json` outside `eval/harness.py` or `method/stat_test.py`. Fix before proceeding. Human sign-off commit: `held-out-run: approved-by=<name>`.

### D5.3 — Mechanism implementation (4 h)

Follow `target_failure_mode.md` to pick the corresponding candidate from [__specs/13 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/13-mechanism-design.md):

| Target family (from D4) | Mechanism candidate | Policy module | Primary surface |
|-------------------------|---------------------|---------------|-----------------|
| Signal over-claiming (default) | A — signal-confidence-aware phrasing | `agent/policies/confidence.py` | `hiring_signal_brief.signals[*].confidence` |
| Bench over-commitment | B — bench-gated commitment policy | `agent/policies/bench.py` | `bench_summary.yaml` cross-check |
| ICP misclassification | C — ICP classifier with abstention | `agent/icp/classifier.py` | segment scores + thresholds |
| Tone drift | D — tone-preservation check | `agent/policies/tone.py` | second-model validator call |
| Scheduling / channel | E — multi-channel handoff policy | `agent/policies/channel_handoff.py` | rules from trace data |

Implementation pattern regardless of candidate:

1. Fill out `method/mechanism.py` that wraps the chosen policy module in the `Mechanism` protocol from [__specs/06 §7](/home/kg/Projects/10Academy/conversion-engine/__specs/06-agent-design.md):
   ```python
   class ChosenMechanism:
       name: str
       def wrap_draft(self, brief, draft) -> str: ...
       def gate_send(self, draft) -> GateDecision: ...
       def post_reply(self, reply, thread) -> ReplyUpdate: ...
   ```
2. Wire `cfg.method.name` in `agent/orchestrator.py` so `"day1_baseline"` produces the untouched behavior and `"<chosen>"` invokes `ChosenMechanism`.
3. Add hyperparameters to `config.yaml` under `method.hyperparameters`.

### D5.4 — Auto-optim baseline implementation (2 h)

- Clone the chosen framework (GEPA or AutoAgent).
- Configure to run against the τ²-Bench retail dev slice (not held-out) with our dev-tier model.
- Give it the same compute budget — same number of trials, same task count, same seed.
- Emit the same `trace_log.jsonl` format so the downstream stat test can ingest it uniformly.
- Capture outcome artifacts under `method/auto_optim/` for transparency.

### D5.5 — Dry run on dev slice (1.5 h)

Before held-out, run all three conditions (`day1_baseline`, `auto_optim`, `<chosen>`) on the 30-task dev slice × 3 trials. Purpose:

- Catch integration bugs in `method/mechanism.py`.
- Verify harness emits uniformly-shaped traces for all three.
- Sanity-check Delta A direction on dev (no guarantee of held-out, but a negative dev delta is a strong warning).

### D5.6 — Ablation variant definitions (30 min)

Per [__specs/13 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/13-mechanism-design.md) and `config.example.yaml` under `method.ablations`:

- **3a** — no regeneration loop (`max_retries = 0`).
- **3b** — tighter thresholds (e.g., 0.40 / 0.65 instead of 0.50 / 0.75).
- **3c** — eval-tier validator (more expensive, stronger; also R4 fallback).

Each ablation is a config overlay; `method.name` does not change, only hyperparameters.

### D5.7 — Budget check-in

Projected cost to complete D6 held-out run: (1 + 3 ablations) × 3 conditions × 5 trials × 20 tasks. Compare to the $12 envelope. If projected > $10, apply R3 mitigation: drop trials 5 → 3 now, before committing.

### D5 exit gate

- [ ] `method/mechanism.py` implements the Mechanism protocol; unit test passes.
- [ ] Orchestrator selects mechanism via `cfg.method.name`.
- [ ] Auto-optim baseline runs end-to-end on dev slice.
- [ ] All three conditions emit identically-shaped traces.
- [ ] O3 and O6 closed in [00-decisions.md](00-decisions.md).
- [ ] Seal audit green; human sign-off recorded.

---

## Day 6 — Held-out evaluation + ablations + stat test (≈ 8 h)

### D6.1 — Held-out run (4 h wall clock, monitored)

```
CONVERGINE_ENV=eval make held-out
```

Runs 3 conditions × 5 trials × 20 tasks × (possibly + 3 ablations × reduced trials) = ~300–450 task-runs at eval-tier prices.

**Monitoring:**
- Langfuse cost dashboard open throughout; refresh every 30 min.
- If projected > $10 with 100 runs remaining: **trials 5 → 3** (R3 mitigation).
- If projected > $12 with 60 runs remaining: **abort + switch eval-tier model** (R3 ladder step 2) + resume from checkpoint.
- If projected > $15: **stop**; document partial results; memo reports what landed.

**Resumability:** harness checkpoints per-task. Resuming after an outage (R9) re-uses the completed portion.

### D6.2 — Collect outputs (30 min)

- `method/held_out_traces.jsonl` — one JSONL per `(method, trial, task_id)`.
- `method/ablation_results.json` — pass@1 + 95 % CI + cost/task + p95 latency per method × ablation.
- Re-run probes with `method_name=<chosen>` to emit the post-mechanism trigger-rate column in `probes/failure_taxonomy.md` (per D4 §6 deferral).

### D6.3 — Statistical test (1 h)

```
python method/stat_test.py --method=<chosen> --baseline=day1_baseline
```

Implements paired bootstrap per [__specs/13 §6](/home/kg/Projects/10Academy/conversion-engine/__specs/13-mechanism-design.md):

1. Pair per-task pass@1 between method and baseline.
2. 10 000 bootstrap resamples over the paired differences.
3. Delta A point = mean(diffs). 95 % CI = [p2.5, p97.5].
4. Two-tailed p-value from the null hypothesis `H0: Delta A == 0`.

Emit `method/stat_test_output.json`:

```json
{
  "method": "<chosen>",
  "baseline": "day1_baseline",
  "delta_a": 0.073,
  "ci_95": [0.031, 0.116],
  "p_value": 0.004,
  "n_paired_tasks": 20,
  "resamples": 10000,
  "seed": 42
}
```

### D6.4 — Delta B analysis (1 h)

Compare our method to auto-optim on the same held-out slice. Possible outcomes:

- **We win Delta B.** Note in `method.md` with 100–200 words of why the structured mechanism found something the auto-optim missed.
- **We tie.** Discuss the Pareto position — ours may be cheaper or more interpretable.
- **We lose Delta B.** Per [__specs/13 §5](/home/kg/Projects/10Academy/conversion-engine/__specs/13-mechanism-design.md), "failing Delta B does not fail the week; unexplained underperformance does." Write 150–250 words covering:
  - Why auto-optim found a better solution.
  - Whether the auto-optim solution generalises (honest assessment).
  - What our method retains (interpretability, latency, cost-per-task, or probe-family specificity).

### D6.5 — R4 contingency — Delta A fails (if applicable)

If `p_value ≥ 0.05` or `ci_95.lower ≤ 0`, execute R4's ladder:

1. Per-task inspection: restrict Delta A to tasks the mechanism was designed to affect. Document restriction in `method.md`.
2. Swap to ablation 3c (eval-tier validator). Re-run only that variant on held-out (if budget permits).
3. If still failing, write honest memo language per [04-d7-act5-memo-demo.md](04-d7-act5-memo-demo.md). **Never fabricate.**

### D6.6 — `method.md` authoring (1.5 h)

Contents per [__specs/13 §3](/home/kg/Projects/10Academy/conversion-engine/__specs/13-mechanism-design.md):

- Mechanism description (what it does, why, the single paragraph that would appear on a whiteboard).
- Design rationale grounded in `target_failure_mode.md`.
- Hyperparameters with the chosen values and why.
- 3 ablation variants with rows in `ablation_results.json`.
- Delta A with 95 % CI and p-value from `stat_test_output.json`.
- Delta B with honest narrative per D6.4.
- Delta C — point vs. published τ²-Bench retail reference (~42 %) — informational.

### D6 exit gate

- [ ] `method/mechanism.py`, `method.md`, `ablation_results.json`, `held_out_traces.jsonl`, `stat_test_output.json` all present.
- [ ] Delta A > 0, CI > 0, p < 0.05 **OR** honest R4 fallback narrative captured.
- [ ] Eval-tier spend ≤ $12 cumulative; overall week spend ≤ $20.
- [ ] `probes/failure_taxonomy.md` updated with post-mechanism column.
- [ ] Sealed slice not re-opened outside `eval/harness.py` or `method/stat_test.py`.
- [ ] `scripts/audit_seal.sh` re-run after the held-out sessions — still green.

---

## Anti-patterns to avoid

1. **Tuning on held-out.** Never. Inspection is allowed after Delta A is recorded; tuning after inspection is a disqualifying methodology error.
2. **Silent retries that change temperature mid-trial.** If a run fails, resume from checkpoint at the same trial/task with the same seed. Do not substitute a different model call.
3. **Moving goalposts between D5 dry run and D6 held-out.** The dry run informs debugging, not hyperparameter choice. Tune on the dev slice, freeze, then run held-out.
4. **"Just one more trial."** 5 trials is the budget. 3 is the fallback. Not 4, not 6.
5. **Merging auto-optim's output into `method.name=<chosen>`.** They are independent conditions; blending the two is scientifically uninterpretable.

## Budget summary

| Phase | Budget | Notes |
|-------|--------|-------|
| D5 dry run + mechanism dev | $2 dev-tier | Already within D1–D4 envelope |
| D6 held-out (3 conditions × 5 trials × 20) | $8 eval-tier | Worst case with Claude Sonnet 4.6 |
| D6 ablations (3 × 3 trials × 20) | $3 eval-tier | Can share fixtures |
| D6 stat test + prose | < $0.20 dev-tier | |
| **Total week** | **≤ $20** | Includes buffer for R3 / R9 |
