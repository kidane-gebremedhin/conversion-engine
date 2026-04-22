# 02 — Day 4: Act III Probe Library

**Purpose:** Build the probe library — ≥ 30 entries across 10 Tenacious-specific categories — and emerge with a ranked `target_failure_mode.md` that mechanism design on D5–D6 can bind to.

**Reference specs:** [__specs/12](/home/kg/Projects/10Academy/conversion-engine/__specs/12-probe-library.md).

**Entry gate:** [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md) §D3 exit complete. Repo tagged `interim-D3`.

**Exit gate:** probe taxonomy in hand; O4 (mechanism candidate) closed in [00-decisions.md](00-decisions.md).

---

## 1. Schedule for D4 (≈ 8 h)

| Block | Wall clock | Output |
|-------|-----------|--------|
| D4 AM-1 (2 h) | Author probe YAMLs — ICP misclass + signal over-claim + bench over-commit (10 probes) | 10 `probes/probes/*.yaml` files |
| D4 AM-2 (2 h) | Author probe YAMLs — tone drift + multi-thread leak + cost pathology + dual-control (10 probes) | 10 more YAMLs |
| D4 PM-1 (2 h) | Author probe YAMLs — scheduling TZ + signal reliability + gap over-claim (12 probes) | 12 more YAMLs |
| D4 PM-2 (1 h) | Run `make probe` → `failure_taxonomy.md` | Per-category pre-mechanism trigger rates |
| D4 PM-3 (1 h) | Rank + pick target failure mode; close O4 | `target_failure_mode.md`, `probe_library.md` assembled |

Total ≥ 32 probes is the target; 30 is the floor.

## 2. Category by category

| # | Category | Probe count target | Estimated per-probe authoring time |
|---|----------|---------------------|-------------------------------------|
| 1 | ICP misclassification | 4 | 20 min |
| 2 | Signal over-claiming | 4 | 20 min |
| 3 | Bench over-commitment | 3 | 25 min |
| 4 | Tone drift | 4 | 25 min |
| 5 | Multi-thread leakage | 2 | 30 min |
| 6 | Cost pathology | 2 | 20 min |
| 7 | Dual-control coordination | 3 | 30 min |
| 8 | Scheduling edge cases (TZ) | 3 | 25 min |
| 9 | Signal reliability (FPR/FNR) | 3 | 30 min |
| 10 | Gap over-claiming | 3 | 25 min |
| **Total** | | **31** | |

Full manifest of probe names is in [__specs/12 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/12-probe-library.md). This plan does not duplicate it; instead, it assigns authoring order.

## 3. Fixture economy

Authoring 31 probes from 31 one-off fixtures is wasteful. Instead:

- **8 synthetic prospects** cover ≥ 90 % of cases via signal overrides.
  - `fixture-seg1-strong-signals` — Segment 1, high AI-maturity, bench-matched.
  - `fixture-seg1-weak-signals` — Segment 1, low AI-maturity, few open roles.
  - `fixture-seg2-post-layoff` — Segment 2, layoff 90 d ago, no fresh raise.
  - `fixture-seg2-layoff-plus-bridge` — Segment 2/1 overlap trap.
  - `fixture-seg3-new-cto` — Segment 3, leadership change in last 60 d.
  - `fixture-seg4-ml-rfp-high-maturity` — Segment 4, maturity 3.
  - `fixture-seg4-ml-rfp-low-maturity` — Segment 4 gate trap: maturity 1.
  - `fixture-abstain` — ambiguous, high-abstention signal.
- Each probe's `fixture.overrides` block tweaks just the field under test; otherwise the prospect is drawn from this pool.
- One shared helper, `probes/fixtures/load.py`, loads a base prospect and applies overrides before the agent runs.

Generator: `scripts/seed_synthetic_prospects.py` from D2 Lane A extended on D4 AM to produce the 8 canonical prospects. ~30 min work.

## 4. Probe YAML authoring conventions

Each file follows the schema in [__specs/12 §3](/home/kg/Projects/10Academy/conversion-engine/__specs/12-probe-library.md). Conventions this plan adds:

- **`tenacious_specificity: high`** is the default. Only drop to `medium` / `low` with an inline comment explaining what makes it generic.
- **`business_cost.estimate_usd_per_incident`** is grounded in one of: stalled-thread rate × ACV, published B2B reply-rate baseline × outbound volume, Tenacious-interview-derived brand incident cost (stated as an assumption).
- **`detection.method`** prefers `regex_and_llm_judge` — regex catches obvious cases fast; LLM judge handles ambiguous ones. Cost: two extra LLM calls per probe run, ≤ $0.003 each.
- **`expected_trigger_rate_pre_mechanism`** is the engineer's prior before running. Populated from gut; overwritten by the actual run in `failure_taxonomy.md`.

## 5. Authoring-time parallelization

Solo engineer walks the categories top-to-bottom in 10. Pairs split:

- **Engineer 1:** Categories 1–4 (ICP + signal + bench + tone). Total ~3.5 h.
- **Engineer 2:** Categories 5–10 (threading + cost + dual-control + scheduling + reliability + gap). Total ~4 h.

They converge at D4 PM-2 for the `run_probes.py` wiring and taxonomy emission.

## 6. `run_probes.py` execution

Reference: [__specs/12 §5](/home/kg/Projects/10Academy/conversion-engine/__specs/12-probe-library.md).

```python
# probes/run_probes.py
for probe in load_all_probes():
    pre_result = run_under_variant(probe, method_name="day1_baseline")
    taxonomy.record(probe, pre_result)
taxonomy.write("probes/failure_taxonomy.md")
```

D4 runs only the `pre_result`. The `post_result` (under the chosen Act IV mechanism) is run on D6 when the mechanism exists. `failure_taxonomy.md` is re-written on D6 with both columns.

Cost: 31 probes × ~3 LLM calls each = ~93 calls, ≤ $0.20 total at dev-tier.

## 7. Ranking + `target_failure_mode.md`

### 7.1 Rank criterion

```
score(probe) = business_cost.estimate_usd_per_incident 
             × observed_trigger_rate_pre_mechanism
             × tenacious_specificity_weight
```

Where `tenacious_specificity_weight ∈ {1.5: high, 1.0: medium, 0.5: low}`.

### 7.2 Pick target family, not single probe

The mechanism will attack a **family** of probes sharing a category, not a single probe. The mechanism design on D5 binds to the highest-scored category mean.

### 7.3 Default target

Per [00-decisions.md §2 O4](00-decisions.md), the default pick is **signal over-claiming** family. Override only if another category has a category-mean score ≥ 1.3× the signal-over-claiming mean in `failure_taxonomy.md`.

### 7.4 `target_failure_mode.md` contents

Mandatory sections (≤ 500 words):

1. Category name and the probe-family summary.
2. Top 3 probes by score, with their `business_cost` derivations.
3. Business-cost derivation at the **category** level — ACV at risk, stalled-thread delta the mechanism could address, brand-reputation envelope.
4. Mechanism success criterion the D5–D6 mechanism must satisfy (e.g., "reduce per-family pre-mechanism trigger rate from X % to ≤ Y %").
5. Criterion for mechanism abandonment on D6 (e.g., "if the mechanism introduces a new probe-family failure with trigger rate > Z %, revert and report honestly").

## 8. Cut-list for D4

Apply in sequence if behind schedule:

1. **Ship 30 probes, not 32.** Drop the 4th entry in the largest categories. Taxonomy quality (per-category observations) matters more than raw count.
2. **Regex-only detection on categories 6 + 8.** Cost pathology and scheduling TZ are easier to detect than tone; skip the LLM judge to save run time.
3. **Defer the `post_result` column in `failure_taxonomy.md` to D6.** It is only populated after the mechanism exists anyway; no interim loss.
4. **Fold signal reliability (#9) into signal over-claiming (#2).** They overlap. One less category, same ≥ 30 probe count.

**Never cut:**
- Coverage of all 4 ICP segments in the fixture pool.
- Coverage of the bench over-commitment category (HubSpot-to-bench-summary check is a core Tenacious guardrail).
- `target_failure_mode.md` derivation — without it, the D5 mechanism is underspecified.

## 9. D4 exit gate

Before starting D5:

- [ ] `probes/probe_library.md` catalogs ≥ 30 structured entries; each has a non-null `tenacious_specificity` and `business_cost.estimate_usd_per_incident`.
- [ ] `probes/failure_taxonomy.md` exists and contains per-category pre-mechanism trigger rates.
- [ ] `probes/target_failure_mode.md` names a specific probe-family and a testable mechanism success criterion.
- [ ] Every probe yaml parses, loads its fixture, and runs end-to-end via `make probe`.
- [ ] O4 in [00-decisions.md](00-decisions.md) is closed (mechanism candidate picked, rationale logged).
- [ ] D4 LLM spend ≤ $0.30 cumulative; cumulative D1–D4 ≤ $4.
- [ ] `probes/` directory layout matches [__specs/02 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/02-repo-structure.md).

## 10. Handoff to D5

`target_failure_mode.md` should be concrete enough that D5 engineers can start implementation immediately without re-reading probe yamls. Specifically, it must identify:

- The one `agent/policies/*.py` module that owns the mitigation (likely `confidence.py` if category 2 is the winner; `bench.py` if category 3; `tone.py` if category 4).
- The specific `hiring_signal_brief.json` fields the mechanism reads.
- The exact regex or tool-call-gate the mechanism inserts or tightens.

This is the deliverable that unblocks [03-d5-d6-act4-mechanism.md](03-d5-d6-act4-mechanism.md).
