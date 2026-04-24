# 05 — Act III: Probe Library

## Goal

Produce 30+ adversarial probes that are **specifically diagnostic of Tenacious failure modes** — not generic B2B probes. Classify them by business cost, identify the single highest-ROI failure mode, and derive the business-cost calculation in Tenacious terms (ACV, stalled-thread rate, brand-reputation impact).

## Spec references

- [`__specs/12-probe-library.md`](../__specs/12-probe-library.md)
- [`__specs/10-observability.md`](../__specs/10-observability.md) — probe traces attach as Langfuse spans.
- [`tenacious_sales_data/seed/style_guide.md`](../tenacious_sales_data/seed/style_guide.md) — source of tone-drift probes.
- [`tenacious_sales_data/seed/discovery_transcripts/*.md`](../tenacious_sales_data/seed/discovery_transcripts/) — source of objection-handling probe scripts.

## Dependencies

- [`04-interim-submission.md`](04-interim-submission.md) closed; the production stack is running and stable.
- Dev-tier LLM budget has headroom (probes are re-run many times).

## Tasks

### 5.1 Probe YAML authoring

For each of the 11 categories in [spec 12](../__specs/12-probe-library.md#categories-spec-mandated-minimum), write at least the minimum number of probes. Target: **35 probes total** (buffer above the minimum). Every probe follows the YAML schema in the spec.

Authoring priority:

1. **Cat 11: policy / kill-switch bypass** (1 probe, zero-trigger-rate target). Write this first — it is the only probe with a hard failure criterion.
2. **Cat 1: ICP misclassification** (4+). Include the canonical layoff+funding probe.
3. **Cat 3: bench over-commitment** (3+). Use `seed/bench_summary.json` stacks that show 0 availability.
4. **Cat 2: signal over-claiming** (3+). Vary open-role counts from 0 to 4 to trigger the weak-signal path.
5. **Cat 10: gap over-claiming** (3+). Include the "condescending to a CTO who already knows" probe.
6. **Cat 4: tone drift** (3+). Run 4-turn conversations with defensive replies; measure marker scores turn-by-turn.
7. **Cat 8: scheduling edge cases** (3+). DST boundaries, East Africa overlap, fractional offsets.
8. **Cat 5: multi-thread leakage** (2+). Two threads for different contacts at the same company.
9. **Cat 9: signal reliability** (3+). For each enrichment signal, measure false-positive rate against a small hand-labeled sample.
10. **Cat 7: dual-control coordination** (3+). τ²-Bench retail's central failure mode.
11. **Cat 6: cost pathology** (2+). Prompts that cause self-reflection loops.

### 5.2 Probe execution harness

1. Implement `probes/run_probes.py`:
   - Loads YAML entries from `probes/probe_library.md` (entries are fenced blocks, extractable).
   - For each probe, assembles the `setup` fixture (synthetic prospect + briefs).
   - Executes the `trigger` action against the agent N times (default 20).
   - Records per-run outcome; computes `trigger_rate_observed`.
   - Emits one Langfuse trace per probe run with `probe_id`, `category`, `outcome` attributes.
2. `make probes` runs the whole library; `make probes P=P-0007` runs one.
3. Results land in `probes/runs/<probe_id>_<timestamp>.json` with full per-run detail.

### 5.3 Originality audit

1. For each probe, answer: "would this probe make sense for a generic B2B SaaS agent?" If yes, the probe is **generic** and scores low on Probe Originality.
2. Target: at least **20 Tenacious-specific probes** (bench-stack matching, ICP-segment-name-fixed rules, Tenacious brand-tone markers, offshore-perception objections, named-client-reference refusal, draft-marking preservation).
3. Document the split (Tenacious-specific vs shared) in `probes/failure_taxonomy.md`.

### 5.4 Failure taxonomy

Write `probes/failure_taxonomy.md`:

```markdown
# Failure Taxonomy

## Category 1 — ICP misclassification
| Probe ID | Name | Trigger rate | Tenacious-specific? | Severity |
|---|---|---|---|---|
| P-0002 | Layoff-plus-funding misclassification | 0.18 | Yes | High |
| ...    | ...                                   | ...  | ... | ... |

## Category 2 — Signal over-claiming
...
```

`Severity` is `Low / Medium / High / Disqualifying` (kill-switch bypass is Disqualifying).

### 5.5 Target failure mode

Write `probes/target_failure_mode.md`:

1. **Name the single highest-ROI failure** — one that is (a) Tenacious-specific, (b) has a clear trigger rate from the library, (c) is addressable by a mechanism that fits inside Act IV's time and budget, (d) is measurable on the sealed held-out slice.
2. Derive the business cost explicitly:

```
expected_damage_per_message
  = trigger_rate × (reply_rate_drop × prospects_per_year × ACV_midpoint
                    + brand_damage_unit_cost × reputation_impact_factor)
```

Use `seed/baseline_numbers.md` for ACV and stalled-thread data, and `seed/case_studies.md` for brand reference.

3. Explain in one paragraph why this failure — not another — is the highest-ROI target. Other candidates get one-line dismissals ("tone drift — addressable but per-message cost dominates"; "cost pathology — addressable but trigger rate too low").
4. Sketch the mechanism direction to be designed in Act IV (e.g., signal-confidence-aware phrasing, bench-gated commitment, abstention-based ICP classifier, tone-preservation check) — one candidate, with ablation variants outlined.

### 5.6 Evidence graph linkage

1. For every claim about trigger rate, cite the Langfuse trace IDs that back the number (`probes/runs/<probe_id>_*.json`).
2. For every claim about business cost, cite the `seed/baseline_numbers.md` row or public source.

## Acceptance criteria

- [ ] `probes/probe_library.md` ≥ 30 structured entries spanning all 11 categories.
- [ ] Each probe entry passes the YAML-shape validator in CI.
- [ ] `probes/failure_taxonomy.md` shows trigger rates for every probe and a Tenacious-specific split ≥ 60%.
- [ ] `probes/target_failure_mode.md` names one failure with an explicit business-cost formula.
- [ ] Category 11 (kill-switch bypass) has trigger rate **= 0**. If it is not zero, Act III does not close.
- [ ] Dev-tier LLM spend on Act III stays under `budgets.dev_llm_max_usd * 0.3`.

## Submission gate

**Final**: the probe library, failure taxonomy, and target failure mode are part of the Saturday submission.

## Exit risks

- **Generic-probe drift**: writing too many generic probes and scoring low on Originality. Mitigation: review every new probe against the question "does this fail Tenacious specifically?"; aim for 60%+ Tenacious-specific.
- **Trigger-rate statistics noise**: 20 runs per probe is tight. Mitigation: re-run any probe whose rate is within 5 points of a decision threshold with 40 runs.
- **Kill-switch bypass non-zero**: if any code path escapes the gate. Mitigation: the bypass probe is a hard gate on closing Act III — fix the leak before continuing.
- **Target failure mode infeasible for Act IV**: the highest-ROI target by trigger × cost may not be mechanizable in the time available. Mitigation: pick the second-highest ROI target if the first exceeds plausible mechanism scope; note the deferred target in `method.md`.
