# 15 — Market-Space Map (Distinguished-Tier Stretch)

This deliverable is **optional**. The five-act deliverables are the floor; the market-space map is the only ceiling-bump available. Attempting it carelessly is worse than not attempting it — a superficial map misdirects strategy with false confidence.

## Why this is a stretch

The underlying capability — scoring AI maturity from public signal — is already built in Acts II and IV for the per-lead use case. Extending it to the population is leverage, not new engineering.

But doing it **honestly** requires validation effort the challenge week will not naturally provide:

- A hand-labeled sample of companies for precision/recall measurement.
- Explicit error-bar reporting.
- Discussion of known false-positive and false-negative modes.

A superficial market-space map — "here are 50 companies ranked by AI maturity" with no validation — is worse than none.

## The work

1. **Load the full Crunchbase ODM sample** (1,001 records).
2. **Segment by sector × company-size band**:
   - Sector: Crunchbase `categories` field, narrowed to a sub-niche where sensible.
   - Company-size band: from the schema's headcount enum (15–80, 80–200, 200–500, 500–2000, 2000+).
3. **Apply AI-maturity scoring to every company** using the same rubric from [spec 05](05-signal-enrichment-pipeline.md).
4. **Cluster into subsector × readiness cells**.
5. **Compute per-cell metrics**:
   - Cell population (number of companies).
   - Average funding in the last 12 months.
   - Average hiring velocity.
   - Bench-match score against `seed/bench_summary.json`.
   - Combined "outbound oxygen" score (weighted sum, weights configurable).
6. **Rank cells** by combined score.
7. **Validate**: hand-label a stratified sample of 30–50 companies. Compute precision and recall of the AI-maturity classifier on this sample.

## Deliverables

`market_space/market_space.csv` — one row per `(sector, company_size_band, ai_readiness_band)` cell:

| Column | Type | Notes |
|---|---|---|
| `sector` | str | Crunchbase category, normalized |
| `sub_niche` | str | Optional finer-grained |
| `company_size_band` | enum | `15_to_80`, `80_to_200`, `200_to_500`, `500_to_2000`, `2000_plus` |
| `ai_readiness_band` | enum | `0`, `1`, `2`, `3` |
| `cell_population` | int | Companies in this cell |
| `avg_funding_12mo_usd` | int | Mean funding in last 12 months |
| `avg_hiring_velocity_ratio` | float | `open_today / open_60d_ago` |
| `bench_match_score` | float | 0–1; fraction of likely-needed stacks covered by bench |
| `combined_oxygen_score` | float | Weighted sum |

`market_space/top_cells.md` — the 3–5 highest-scoring cells, each with:

- A one-paragraph profile (who's in it, what they're hiring for, why they match).
- A specific outbound-allocation recommendation (e.g., "allocate 40% of Segment 1 outbound to Series B cloud-infrastructure 80–200-person US cluster").

`market_space/methodology.md` — documents:

- How sectors were defined and normalized.
- How AI-maturity scoring was validated against the hand-labeled sample.
- What false positives and false negatives are **known** to exist in the map.
- Sample sizes and confidence intervals.

`market_space/validation_sample.csv` — the hand-labeled sample (30–50 rows) with:

- `company_domain`
- `ai_maturity_predicted` (0–3)
- `ai_maturity_ground_truth` (0–3, labeled by you)
- `confidence_notes` (why you labeled it that way)

Precision / recall reported per readiness band in `methodology.md`.

## Grading implications

A market-space map that would **change how Tenacious allocates outbound effort** earns:

- **Distinguished rating** on the Cost-Quality Pareto observable.
- **Originality credit** on Probe Originality.

A shallow map earns neither. The burden of validation is real. Budget Day 6 carefully; **the stretch must not compromise the five-act core deliverables**.

## Configuration

All weights, thresholds, and sub-niche overrides live in `config.yaml > market_space`. Defaults:

```yaml
market_space:
  enabled: false                        # Explicit opt-in; distinguished-tier only
  oxygen_score_weights:
    funding_12mo: 0.3
    hiring_velocity: 0.3
    ai_readiness: 0.2
    bench_match: 0.2
  validation_sample_size: 40
  sub_niche_overrides:
    advertising: [adtech_ssp, adtech_dsp, adtech_verification]
    fintech: [lending, payments, infra]
```

## What the market-space map must NOT do

- Publish precision/recall without an explicit sample size and label noise estimate.
- Recommend an outbound allocation the bench cannot sustain (bench-match score must be the gating filter).
- Invent companies not in the Crunchbase ODM sample.
- Include a cell with fewer than 5 companies — single-company outliers should not drive strategy.
- Compromise the core five-act deliverables. If Day 6 runs long, **cut this first**.
