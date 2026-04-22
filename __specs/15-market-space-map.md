# 15 — Market Space Mapping (Distinguished-Tier Stretch)

**Source:** Challenge document — "Market Space Mapping" section.

## 1. Status

**Optional stretch.** The five-act deliverables are the floor. This deliverable is only attempted if the core five acts are fully in hand — a superficial market map is worse than no map at all because it misdirects strategy with false confidence.

Recommended attempt window: **Day 6 only**. Do not let the stretch compromise Acts III–V.

## 2. Goal

Apply the per-lead AI-maturity scoring built in Acts II + IV at the **population level**. Produce a table that tells the Tenacious executive team which (sector × company-size × AI-readiness) cells contain the most outbound oxygen — funded, hiring, AI-open, bench-matched.

The finding is **strategic, not tactical**. It answers where to point the system, not how well the system performs on arbitrary input.

## 3. Inputs

- Full Crunchbase ODM sample (1 001 records).
- `agent/enrichment/ai_maturity.py` scorer (applied to every company).
- `seed/bench_summary.yaml` for bench-match scoring.

## 4. Outputs

### `market_space.csv`
One row per `(sector, company_size_band, ai_readiness_band)` cell.

| Column | Type |
|--------|------|
| sector | string |
| size_band | enum (`1-10`, `11-50`, `51-100`, `101-500`, `501-2000`, `2000+`) |
| ai_readiness_band | int 0–3 |
| cell_population | int (# companies in the ODM sample in this cell) |
| avg_funding_last_12mo_usd | float |
| avg_hiring_velocity_ratio | float (derived on the sampled subset) |
| bench_match_score | float 0–1 (see §5) |
| combined_score | float — ranked field |

### `top_cells.md`
Three-to-five highest-`combined_score` cells, each with:
- Cell id and profile (one paragraph — who they are, why they qualify).
- Recommended outbound allocation (e.g., "40 % of weekly outbound for the first 2 weeks of pilot").
- Known risks of targeting this cell (e.g., "most cells of this shape are Series B with weak bench match on infra").

### `methodology.md`
- Sector definition (primary Crunchbase industry, with a mapping for top-15 sectors).
- Size-band definition and edge cases.
- AI-readiness-band computation and validation against a **hand-labelled sample of ≥ 30 companies**.
- Precision / recall of AI-maturity scoring on the hand-labelled sample, with a confusion matrix and error bars.
- Known false positives and false negatives (links to the lossiness modes in [05 §7](05-signal-enrichment-pipeline.md)).

## 5. Bench-match score

```
bench_match_score(cell) = 
  sum over bench_stack s in bench_summary.yaml:
    w(s) * likelihood(cell needs s | cell's public signals)
```

Where `likelihood` is estimated from the cell's typical AI-adjacent role mix + tech stack. Normalise to [0, 1].

## 6. Combined score

```
combined_score = 
  0.40 * normalised(avg_funding_last_12mo_usd)
+ 0.25 * normalised(avg_hiring_velocity_ratio)
+ 0.20 * bench_match_score
+ 0.15 * ai_readiness_signal_strength     # favours bands 1–2 where Tenacious can add most
```

Weights are set in `config.yaml` under `market_space.weights` so they can be re-tuned.

## 7. Honesty bar

Doing this honestly requires validation the challenge week does **not** naturally provide:
- Hand-label ≥ 30 companies across ≥ 5 sectors.
- Compute precision and recall of AI-maturity scoring.
- Publish error bars on every cell-level metric.

A market map without these is **worse than none** — it misdirects strategy with false confidence. Do not submit a superficial map.

## 8. Grading credit

A map that would change how Tenacious allocates outbound effort earns:
- **Distinguished rating on the Cost-Quality Pareto observable.**
- **Originality credit on Probe Originality.**

## 9. Acceptance tests

- `market_space.csv` contains ≥ one row per distinct `(sector, size_band, ai_readiness_band)` triple observed in the Crunchbase ODM sample.
- `methodology.md` reports precision + recall with confusion matrix over ≥ 30 hand-labelled rows.
- `top_cells.md` lists 3–5 cells with specific allocation recommendations and enumerated risks.
- Every cell metric traces back to code in `market_space/` that can be re-run from the raw Crunchbase ODM.
