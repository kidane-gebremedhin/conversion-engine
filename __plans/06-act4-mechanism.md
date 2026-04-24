# 06 — Act IV: Mechanism Design and Sealed Held-Out Evaluation

## Goal

Implement an original mechanism that addresses the target failure mode named in Act III. Evaluate it on the 20-task sealed held-out τ²-Bench retail partition. Beat the Day-1 baseline with 95% CI separation (Delta A) and honestly compare against an automated-optimization baseline (Delta B). Report the deltas with a p < 0.05 statistical test.

## Spec references

- [`__specs/13-mechanism-design.md`](../__specs/13-mechanism-design.md)
- [`__specs/11-tau2-bench-harness.md`](../__specs/11-tau2-bench-harness.md) — sealed-partition access rules.
- [`__specs/10-observability.md`](../__specs/10-observability.md) — tier attribution and cost.

## Dependencies

- [`05-act3-probes.md`](05-act3-probes.md) closed; `probes/target_failure_mode.md` names the mechanism target.
- Sealed partition available at `$TAU2_HELDOUT_PATH` (outside the repo tree).
- Eval-tier LLM budget intact (`budgets.eval_llm_max_usd`).

## Tasks

### 6.1 Guard the eval budget

1. Confirm `TAU2_SEALED_ACCESS` and `EVAL_TIER_ENABLED` are **unset** until this phase starts. The harness refuses to touch the sealed partition otherwise.
2. Confirm the sealed partition checksum matches the program-provided value.
3. Decide the mechanism and ablation variants on paper first; any half-baked mechanism that runs against the sealed slice burns budget and cannot be un-run.

### 6.2 Mechanism implementation

The mechanism implementation depends on the target failure mode. Pick **one** direction from the spec (not all):

| Target failure | Mechanism candidate |
|---|---|
| Signal over-claiming | Signal-confidence-aware phrasing: the composer reads per-input confidence and softens verbs. |
| Bench over-commitment | Bench-gated commitment policy: hard constraint with handoff when bench count < stated need. |
| ICP misclassification | ICP classifier with explicit abstention threshold + exploratory-email fallback. |
| Tone drift | Tone-preservation check (second LLM call with regeneration). |
| Channel misuse | Multi-channel handoff policy: explicit rules for email→SMS→voice transitions. |
| Multi-thread leakage | Thread isolation keyed by prospect email, not company domain. |

The chosen mechanism is documented in `method/method.md` with:

- Name and one-sentence description.
- Design rationale citing the probe evidence.
- Hyperparameters (all referenced to `config.yaml`).
- Three ablation variants (variant A = mechanism off / Day-1 baseline, B = mechanism with chosen setting, C = mechanism with a different setting, e.g., threshold).

### 6.3 Automated-optimization baseline

1. Pick one of GEPA (gradient-free prompt evolution) or AutoAgent.
2. Configure it to optimize the **same prompt target** as the mechanism.
3. Budget it the **same compute cost** as the mechanism (dollars, not tokens).
4. Record the resulting pass@1 and cost-per-task for comparison.

### 6.4 Sealed held-out run

This is the single largest budget expenditure of the project.

1. Enable the dual guards: `TAU2_SEALED_ACCESS=1`, `EVAL_TIER_ENABLED=1`.
2. Run `python -m eval.harness --partition retail_sealed_20 --model $EVAL_LLM_MODEL --trials 5 --seeds 42,43,44,45,46 --tier eval --variant <A|B|C>` for each of the three variants (your mechanism, your Day-1 baseline, automated-optimization baseline).
3. Each variant's traces land in `method/held_out_traces.jsonl` with the `condition` attribute set.
4. Total expected cost: the sum of three `eval-tier × 20 tasks × 5 trials` runs. Budget in `budgets.eval_llm_max_usd`. Do not exceed.

### 6.5 Statistical test

1. Implement `method/stat_test.py`:
   - Paired bootstrap over 20 tasks, 10,000 resamples.
   - Two-sided test.
   - Output `p_value_delta_a`, `p_value_delta_b`, `ci_95_delta_a`, `ci_95_delta_b`.
2. Write `method/stat_test.md`: test statistic, p-value, CI, discussion.
3. If `p_value_delta_a >= 0.05`, the mechanism has not beaten the baseline. Options:
   - Accept failure and write it honestly in `method.md` and the memo (this costs fewer points than fabricating).
   - Reconfigure the mechanism's hyperparameter (variant C vs variant B) and re-run — **only if budget allows**.

### 6.6 Ablation results JSON

Emit `method/ablation_results.json` per the schema in [spec 13](../__specs/13-mechanism-design.md#ablation-variants-required).

### 6.7 Method memo

Write `method/method.md` covering:

- The target failure mode it addresses (cross-ref `probes/target_failure_mode.md`).
- Design rationale — why this mechanism fits the failure mode.
- Hyperparameters and their justifications.
- Ablations A / B / C with the observed effect of each variant.
- Statistical test outcome.
- Known limitations (one probe from the library that this mechanism does **not** resolve — used in the memo Skeptic's Appendix).

### 6.8 Production-stack supplementary measurement

Beyond the sealed τ²-Bench slice, measure the mechanism's effect on the production-stack data:

1. A/B tag outbound variants in Langfuse (`signal_grounded=True` vs `False`).
2. Compute reply-rate delta, stalled-thread-rate delta, tone-check-regenerate-rate.
3. Feed these numbers into the memo (Page 1) with trace IDs.

## Acceptance criteria

- [ ] `method/method.md` present with name, rationale, hyperparameters, three ablations.
- [ ] `method/ablation_results.json` present, all three variants populated, GEPA baseline included.
- [ ] `method/held_out_traces.jsonl` contains traces for all three conditions across 20 tasks × 5 trials (= 300 per condition, 900 total).
- [ ] `method/stat_test.md` shows **Delta A positive with p < 0.05**, OR explains why it failed and what this means for the memo.
- [ ] Eval-tier LLM total spend ≤ `budgets.eval_llm_max_usd`.
- [ ] Dev-tier budget still has headroom for Act V (memo composition uses dev-tier).

## Submission gate

**Final**: `method/` artifacts are part of the Saturday submission. The memo cites these traces.

## Exit risks

- **Delta A fails (p ≥ 0.05)**: the mechanism did not beat the baseline. Mitigation: honest reporting is better than fabrication. The Skeptic's Appendix absorbs the failure; probe-originality credit may carry the submission.
- **Eval-tier overrun**: running three variants on 20 tasks × 5 trials can exceed the $12 cap if the eval-tier model is GPT-5-class. Mitigation: before running, estimate cost per trial from the Act I dev-tier numbers scaled by the price ratio; if the projection exceeds budget, drop one variant or trial count (documented in `method.md`).
- **GEPA setup friction**: installing GEPA with a working optimizer is non-trivial. Mitigation: if GEPA does not install within a reasonable effort, substitute a simple automated prompt-rewriter as the baseline and document the swap honestly. Note that Delta B is informational, not required.
- **Sealed partition contamination**: accidentally using the sealed partition for iteration rather than final eval invalidates the deltas. Mitigation: the harness's dual-guard assertion prevents this. Do not iterate on sealed; iterate on dev slice with a proxy of the target failure.
