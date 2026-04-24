# 08 — Stretch: Market-Space Map (Distinguished-Tier, Optional)

## Goal

If — and only if — the five-act core deliverables are secure, produce a market-space map that scores every company in the Crunchbase ODM sample and ranks sector × company-size × AI-readiness cells by combined outbound-oxygen score. Validate against a hand-labeled sample and publish precision/recall error bars. A market-space map that would change how Tenacious allocates outbound effort earns distinguished-tier credit; a superficial one misdirects strategy and is worse than none.

## Spec references

- [`__specs/15-market-space-map.md`](../__specs/15-market-space-map.md)

## Dependencies

- All of [`02`](02-act1-tau2-baseline.md), [`03`](03-act2-production-stack.md), [`04`](04-interim-submission.md), [`05`](05-act3-probes.md), [`06`](06-act4-mechanism.md), [`07`](07-act5-memo-demo.md) **effectively complete** — memo drafted, evidence graph validated, demo video recorded.
- Dev-tier LLM budget remaining after mechanism prototyping; eval-tier budget untouched by this phase.
- Explicit opt-in: `market_space.enabled: true` in `config.yaml`.

## Hard gate — don't start this without confirmation

If any of the following is **not** true, **skip this plan** and spend the time polishing Act V:

- [ ] `memo/memo.pdf` is final and validated against the evidence graph.
- [ ] Demo video is recorded and uploaded.
- [ ] `method/ablation_results.json` shows Delta A with p < 0.05 (or is honestly reported otherwise).
- [ ] `infra/smoke_test.sh` is still green.
- [ ] At least 30% of the available budget remains for unexpected memo revisions.

## Tasks

### 8.1 Scoring at population scale

1. Implement `market_space/score_population.py` that:
   - Loads all 1,001 Crunchbase ODM records.
   - For each, runs the AI-maturity scorer in "public-only" mode (no live scraping — only data already fetched during Acts II and III is permissible; the 200-company crawl cap does **not** reset for the stretch).
   - Produces a DataFrame of `(domain, sector, sub_niche, headcount_band, ai_readiness_band, avg_funding_12mo_usd, hiring_velocity_ratio, bench_match_score)` rows.
2. Cluster into cells by `(sector, company_size_band, ai_readiness_band)`.

### 8.2 Hand-labeled validation sample

1. Draw a stratified random sample of 40 companies (weights in `config.yaml > market_space.validation_sample_size`).
2. For each, manually review public signal and label `ai_maturity_ground_truth` on 0–3.
3. Record labels in `market_space/validation_sample.csv`.
4. Compute precision and recall per readiness band.
5. Document known false-positive and false-negative modes in `market_space/methodology.md`.

### 8.3 Combined oxygen score

1. Compute the combined score per cell:

```
oxygen_score = Σ w_i × normalized_metric_i
  weights from config.yaml > market_space.oxygen_score_weights
```

2. Rank cells; pick the top 3–5 by score.

### 8.4 Deliverables

Write to `market_space/`:

- `market_space.csv` — all cells with per-cell metrics.
- `top_cells.md` — profile paragraphs + outbound-allocation recommendations for the top 3–5.
- `methodology.md` — how sectors were defined, how scoring was validated, precision/recall per band, known error modes, sample sizes, CIs.
- `validation_sample.csv` — the hand-labeled sample with predicted and ground-truth scores.

### 8.5 Memo integration (optional, one paragraph only)

If there is a half-page of headroom on memo Page 1, add a one-paragraph "Market-Space Finding" section that names the top cell and the specific outbound reallocation recommendation. **Do not** expand the memo to three pages.

### 8.6 Evidence graph update

Add claims from the market-space map to `evidence_graph.json` with `source_type: market_space_map` and references to the CSVs.

## Acceptance criteria

- [ ] `market_space/market_space.csv` has rows for every cell with population ≥ 5.
- [ ] `market_space/validation_sample.csv` has 30–50 hand-labeled rows.
- [ ] `market_space/methodology.md` reports precision and recall per readiness band with explicit CIs.
- [ ] `market_space/top_cells.md` names 3–5 cells with concrete outbound-allocation recommendations.
- [ ] Every recommendation's bench-match score is >0 (don't recommend a cell the bench cannot staff).
- [ ] No fabricated company; every entry resolves to a Crunchbase ODM record.
- [ ] Zero incremental LLM spend on the eval-tier model.

## Submission gate

**Optional** — this is distinguished-tier credit only. It must not displace or delay final submission.

## Exit risks

- **Hand-labeling drift**: labeling 40 companies by hand is time-consuming. If it takes longer than two hours, cut the sample to 30 and note the reduced statistical power.
- **Weak validation numbers**: precision or recall < 0.6 is distinguishing-tier-disqualifying. Mitigation: publish the numbers honestly rather than silently inflating them; the memo's Skeptic's Appendix handles weak validation with a business-impact note.
- **Act-V regression**: the stretch tempted you to re-open the memo. Mitigation: treat Act V as frozen before starting this plan.
- **Scope creep into new data sources**: the temptation to add BuiltWith/Wappalyzer for every company at population scale blows the scraping cap. Mitigation: only use signals already resolved in the per-lead enrichment runs.
