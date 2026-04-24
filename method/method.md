# Method — Act IV

## Mechanism

**Grounded classifier → honesty-flag prompt injection → tone-preservation check.**

A three-layer guard against the target failure from
[`probes/target_failure_mode.md`](../probes/target_failure_mode.md) —
layoff + funding misclassification that routes a post-restructure CFO
into a fresh-budget pitch.

## Design rationale

The failure survives any single layer:

- **Layer 1 — classifier abstention.** Rule-ordered classifier with a
  `0.60` abstention threshold. Addresses probe category 1 (ICP
  misclassification). Code: [`agent/classifier.py`](../agent/classifier.py).
- **Layer 2 — honesty flags consumed by the composer.** Flags
  `layoff_overrides_funding` and `bench_gap_detected` flow from the
  enrichment pipeline into the composer prompt, forcing softer language
  even on correctly classified Segment 2 prospects. Addresses category 2
  (signal over-claiming).
- **Layer 3 — tone-preservation check.** A second LLM call scoring 1–5
  on each of the five Tenacious tone markers. Any marker < 4 triggers
  regeneration (max 1 retry; second failure → human handoff).

Removing any single layer reopens a failure class the others cannot
fully compensate for. The ablation variants are chosen to isolate each.

## Hyperparameters

| Parameter | Config path | Value |
|---|---|---|
| Abstention threshold | `icp.abstain_threshold` | 0.60 |
| Layoff disqualifier ceiling | `icp.segment_2.disqualifier_layoff_pct_max` | 0.40 |
| Tone-check min per marker | `tone_check.per_marker_min_score` | 4 |
| Max regenerations | `tone_check.max_regenerations` | 1 |
| Tone-check LLM | `TONE_CHECK_MODEL` (falls back to `DEV_LLM_MODEL`) | dev-tier |

All dollars, model IDs, and thresholds come from `.env` or `config.yaml`.
None are hard-coded in source.

## Ablation variants

| Variant | Setting | Rationale |
|---|---|---|
| **A — baseline** | all three layers OFF; equivalent to Day-1 | control |
| **B — mechanism** | all three layers ON at spec defaults | primary claim |
| **C — ablation** | classifier only; flags + tone check OFF | isolate layers 2+3 contribution |

Additional exploratory: ablating layer-2 only, ablating layer-3 only.
These are not required for Delta A but they sharpen the memo argument.

## Statistical test

Paired bootstrap across the 20 sealed held-out tasks, same five seeds
(`[42, 43, 44, 45, 46]`). Two-sided p-value. **Required: p < 0.05 for
Delta A (B > A).**

## Delta B — honesty against GEPA

GEPA (Gradient-free Evolution Prompt Adaptation) is run at the same
compute budget (dollars) on the same 20 tasks. Delta B = B − GEPA.
Per spec 13, a losing Delta B does **not** fail the challenge week —
but it must be discussed honestly in the memo.

## Production-stack evaluation (supplementary)

Beyond τ²-Bench, the mechanism is measured on production traces:

- Reply-rate delta between A/B-tagged outbound (signal_grounded vs. not).
- Stalled-thread rate vs. the 30–40% manual baseline.
- Abstention rate at the 0.60 threshold and its effect on reply rate.
- Tone-check regenerate rate; do regens actually improve reply rate?

These are reported in the memo's Page 1 (decision) and Page 2
(Skeptic's Appendix).

## Evidence graph

Every claim in this file ties to a trace in `method/held_out_traces.jsonl`.
See [`../memo/evidence_graph.json`](../memo/evidence_graph.json) for the
memo cross-reference.
