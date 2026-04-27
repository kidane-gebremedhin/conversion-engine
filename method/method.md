# Method — Act IV

The Act IV mechanism applies one design principle — **abstain or verify
on uncertainty rather than over-claim** — across two domains:

1. **τ²-Bench retail** (the benchmark scoring surface): a hardened
   dual-control discipline layered on `llm_agent`, registered as
   `dual_control_agent`.
2. **Tenacious production stack** (where the system actually ships): a
   three-layer guard — confidence-gated ICP classifier → honesty flags
   into the composer → tone-preservation check.

The PDF requires Delta A on the sealed retail partition; the τ²-Bench
mechanism is what carries that test. The sales-side mechanism is what
ships and what the memo's Page 1 economic argument depends on. Same
design principle, different surfaces.

## τ²-Bench mechanism — `dual_control_agent`

### What it is

`agent/tau2_mechanism/dual_control_agent.py` subclasses tau2's
`LLMAgent` and replaces the system prompt with one that adds a
`<dual_control_discipline>` block beneath tau2's stock instructions and
the retail policy text. Five rules, ordered most→least impact:

| Rule | What it forces | Failure class it closes |
|---|---|---|
| R1. AUTHENTICATE FIRST | No tool calls (other than identity lookup) before user_id is obtained via email or name+zip | Wrong-user mutations |
| R2. CONFIRM BEFORE WRITE | Every `cancel`/`modify`/`return`/`exchange`/`update` call is preceded by a message naming the tool, listing every argument, ending with "Should I proceed? (yes/no)"; only an unambiguous "yes" proceeds | Unintended destructive writes; ambiguous-confirmation false positives |
| R3. ONE ACTION PER TURN | Never batch tool calls, never combine a tool call with a user-facing message in one turn | Policy-violating batched writes the orchestrator can't undo |
| R4. NEVER HALLUCINATE ARGUMENTS | No fabricated product/item/order/user IDs; if a search returns nothing, ask the user to disambiguate | "Product not found" infra errors from guessed IDs |
| R5. REFUSE OUT-OF-SCOPE | Explicit refusal with rule citation when a request is out-of-policy or missing prerequisite information | Out-of-scope actions; over-eager helpfulness |

Tau2's retail `policy.md` already mandates R1 and R2 in prose. Weaker
dev-tier models (DeepSeek V3.2, Qwen3-Next-80B-A3B) violate them
inconsistently — the augmentation makes the rules model-readable and
foregrounded above the rest of the policy text.

### Ablation variants

| Variant | Agent | Rules included | Why |
|---|---|---|---|
| **A — baseline** | `llm_agent` (stock) | none beyond stock retail policy | Day-1 control |
| **B — mechanism** | `dual_control_agent` | R1+R2+R3+R4+R5 | Primary claim |
| **C — ablation** | `dual_control_agent_lite` | R1+R2 only | Isolates whether R3+R4+R5 carry weight beyond R1+R2 |

### Hyperparameters

| Parameter | Where | Value |
|---|---|---|
| Agent registration | `agent/tau2_mechanism/dual_control_agent.py:register_with_tau2` | always-on at harness boot |
| Prompt template | `_SYSTEM_PROMPT_DUAL` | R1–R5 inlined, retail policy interpolated |
| Tier (mechanism) | `--tier` flag | `dev` for iteration, `eval` for sealed scoring |
| Tier (baseline) | `--baseline-tier` (defaults to mechanism tier; PDF spec uses `dev` for A even when B is `eval`) | `dev` |
| Trials | `--trials` | 5 (PDF default) |
| Bootstrap resamples | `--bootstrap-resamples` | 5000 |
| Max steps | `--max-steps` | 100 (tau2 default) |

### Statistical test for Delta A

Paired-task percentile bootstrap. For every task in the partition,
compute `pass_rate(B) − pass_rate(A)` across that task's trials, then
resample the per-task delta vector with replacement 5000 times for the
95% CI. Two-sided p-value via the same-size centered bootstrap. **Gate
per the PDF: Delta A > 0 AND p < 0.05.** Implementation:
[`method/run_ablations.py`](run_ablations.py).

The output `stat_test.md` reports the verdict; failing the gate means
the trainee must either revise the mechanism or honestly report the
null result in `memo.pdf` Page 2 ("One honest unresolved failure").

## Production-stack mechanism

The sales-side analog of "abstain or verify on uncertainty rather than
over-claim". Three layers, each addressing a class of probe failure:

- **Layer 1 — classifier abstention.** Rule-ordered ICP classifier with
  a `0.60` confidence threshold; below threshold the composer sends a
  generic exploratory email rather than a segment-specific pitch.
  Addresses ICP misclassification (probe category 1). Code:
  [`agent/classifier.py`](../agent/classifier.py).
- **Layer 2 — honesty flags consumed by the composer.** Flags
  `layoff_overrides_funding`, `bench_gap_detected`, `signal_grounded`
  flow from the enrichment pipeline into the composer prompt, forcing
  softer language even on correctly classified Segment 2 prospects.
  Addresses signal over-claiming and bench over-commitment.
- **Layer 3 — tone-preservation check.** A second LLM call scoring 1–5
  on each of the five Tenacious tone markers; any marker < 4 triggers
  regeneration (max 1 retry; second failure → human handoff).

The two mechanisms share the same shape: introduce explicit gates on
uncertainty, block downstream actions until the gate passes, refuse or
defer rather than over-claim. The retail mechanism is what carries
Delta A on the sealed partition; the sales-side mechanism is what ships
and what the memo's economic argument depends on.

## Hyperparameters (sales-side)

| Parameter | Config path | Value |
|---|---|---|
| Abstention threshold | `icp.abstain_threshold` | 0.60 |
| Layoff disqualifier ceiling | `icp.segment_2.disqualifier_layoff_pct_max` | 0.40 |
| Tone-check min per marker | `tone_check.per_marker_min_score` | 4 |
| Max regenerations | `tone_check.max_regenerations` | 1 |
| Tone-check LLM | `TONE_CHECK_MODEL` (falls back to `DEV_LLM_MODEL`) | dev-tier |

All dollars, model IDs, and thresholds come from `.env` or `config.yaml`.
None are hard-coded in source.

## Delta B — honesty against GEPA

GEPA (Gradient-free Evolution Prompt Adaptation) at the same compute
budget on the same partition. The ablation runner reserves a slot in
`ablation_results.json > automated_optimization_baseline` for the GEPA
numbers; trainee fills these in once GEPA is run. Per Act IV, **failing
Delta B does not fail the week** — but unexplained underperformance
must be addressed honestly in the memo.

## Delta C — published τ²-Bench reference

Informational. `score_log.json` records `published_reference_pass_at_1`
(0.42 per the Feb 2026 leaderboard) and the per-run reproduction delta;
the ablation summary inherits these.

## How to run

Cheap iteration on the dev partition, dev tier:

    make tau2-ablation
    # → 30 dev tasks × 5 trials × 3 conditions = 450 sims, ~$15-20 OpenRouter spend
    # → method/{ablation_results.json, held_out_traces.jsonl, stat_test.md}

Sealed final scoring (after dual guard is satisfied):

    make tau2-ablation \
        TAU2_ABLATION_PARTITION=retail_sealed_20 \
        TAU2_ABLATION_TIER=eval

Or call directly:

    PYTHONPATH=. python -m method.run_ablations \
        --partition retail_sealed_20 \
        --tier eval \
        --baseline-tier dev \
        --trials 5

`--baseline-tier dev` follows the PDF literally (Day-1 baseline is
dev-tier even when the mechanism is eval-tier). Drop the flag to run
both conditions on the same tier — useful for isolating mechanism
effect from tier effect.

## Production-stack evaluation (supplementary)

Beyond τ²-Bench, the sales-side mechanism is measured on production
traces:

- Reply-rate delta between A/B-tagged outbound (signal_grounded vs not).
- Stalled-thread rate vs the 30–40% manual baseline.
- Abstention rate at the 0.60 threshold and its effect on reply rate.
- Tone-check regenerate rate; do regens actually improve reply rate?

These are reported in the memo's Page 1 (decision) and Page 2
(Skeptic's Appendix).

## Evidence graph

Every numeric claim ties to a row in `held_out_traces.jsonl` (tau2 side)
or a Langfuse trace ID (production side). See
[`../memo/evidence_graph.json`](../memo/evidence_graph.json) for the
memo cross-reference.
