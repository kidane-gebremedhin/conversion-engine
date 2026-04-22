# 04 — Day 7: Act V Memo, Demo Video, Final Submission

**Purpose:** Land the **final submission** — memo (exactly 2 pages), evidence graph, demo video (≤ 8 min, public, no-login), repo with probes + method artifacts — by D7 21:00 local. Optionally, land the market-space stretch.

**Reference specs:** [__specs/14](/home/kg/Projects/10Academy/conversion-engine/__specs/14-memo-specification.md), [__specs/15](/home/kg/Projects/10Academy/conversion-engine/__specs/15-market-space-map.md), [__specs/17 §B](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md).

**Entry gate:** [03-d5-d6-act4-mechanism.md §D6 exit](03-d5-d6-act4-mechanism.md) complete. `method/` + `probes/` + `eval/` artifacts in place.

---

## D7 morning (08:00–14:00) — Memo assembly

### D7.1 — Close O5 (pilot segment) (30 min)

Review traces tagged by `outbound_variant` across the four segments. Pick the segment with the **largest signal-grounded-vs-exploratory reply-rate delta** and the cleanest bench match. Update [00-decisions.md](00-decisions.md) O5.

If the corpus is too thin to distinguish segments (common — ~50–100 outbound during the week), default to **Segment 1** per fallback. Document in memo Page 1 §2.7 why the choice was made and the sample-size caveat.

### D7.2 — Invoice summary (30 min)

Export from Langfuse → `memo/invoice_summary.json` per [__specs/10 §3](/home/kg/Projects/10Academy/conversion-engine/__specs/10-observability.md).

Validate:
```
jq '.totals.usd' memo/invoice_summary.json
```

and cross-check against sum over `eval/trace_log.jsonl`'s `cost_usd` column (± $0.05). Any mismatch → investigate before any memo number is written.

### D7.3 — Evidence-graph-first (2 h)

This is the single most important discipline of D7. **Every memo claim's source exists before any prose.**

Build `memo/evidence_graph.json` with one `claim_id` per numeric statement that will appear in the memo. For each, populate `sources[]` with:

- `type: trace_count` + `path: eval/trace_log.jsonl` + `filter: <jq-style>`
- `type: ablation_results` + `path: method/ablation_results.json` + `selector: <JSONPath>`
- `type: stat_test` + `path: method/stat_test_output.json`
- `type: invoice_line` + `path: memo/invoice_summary.json` + `selector: ...`
- `type: published` + `citation: <exact source>`
- `type: tenacious_provided` + `source: seed/bench_summary.yaml | seed/pricing.yaml | Tenacious executive interview (seed materials)`

Required claim ids (minimum — add as needed):

| Claim id | Page | Source types used |
|----------|------|-------------------|
| `memo.page1.executive_summary.headline` | 1 | ablation_results, stat_test |
| `memo.page1.tau2_bench.published_reference` | 1 | published (τ²-Bench retail ~42 %) |
| `memo.page1.tau2_bench.day1_baseline` | 1 | ablation_results |
| `memo.page1.tau2_bench.our_method` | 1 | ablation_results, stat_test |
| `memo.page1.cost_per_qualified_lead` | 1 | invoice_line, trace_count |
| `memo.page1.stalled_thread_tenacious_manual` | 1 | tenacious_provided (executive interview) |
| `memo.page1.stalled_thread_our_system` | 1 | trace_count |
| `memo.page1.competitive_gap_fraction` | 1 | trace_count (variant tag) |
| `memo.page1.competitive_gap_reply_delta` | 1 | trace_count (variant tag) |
| `memo.page1.scenario_1_segment` | 1 | trace_count, tenacious_provided |
| `memo.page1.scenario_2_segments` | 1 | trace_count, tenacious_provided |
| `memo.page1.scenario_4_segments` | 1 | trace_count, tenacious_provided |
| `memo.page1.pilot.segment` | 1 | decision log |
| `memo.page1.pilot.lead_volume` | 1 | derivation (documented) |
| `memo.page1.pilot.budget` | 1 | invoice_line extrapolation |
| `memo.page1.pilot.success_criterion` | 1 | derivation (documented) |
| `memo.page2.failure_mode_1..4` | 2 | probe references |
| `memo.page2.signal_lossiness_quiet` | 2 | probe reference |
| `memo.page2.signal_lossiness_loud` | 2 | probe reference |
| `memo.page2.gap_risk_1..N` | 2 | example from traces |
| `memo.page2.brand_reputation.1000_emails` | 2 | stated assumption + unit-econ derivation |
| `memo.page2.brand_reputation.break_even` | 2 | derivation |
| `memo.page2.unresolved_failure` | 2 | probe id |
| `memo.page2.killswitch_trigger` | 2 | decision-log thresholds |

### D7.4 — Memo prose (2 h)

Author `memo/memo.md` following [__specs/14 §2, §3](/home/kg/Projects/10Academy/conversion-engine/__specs/14-memo-specification.md). Every number already exists in `evidence_graph.json`; the prose only **references** the graph.

**Page 1 order (mandatory):**
1. Executive summary — 3 sentences (what was built, headline number, recommendation).
2. τ²-Bench pass@1 table (published reference / Day-1 / our method, with CIs).
3. Cost per qualified lead.
4. Speed-to-lead delta (Tenacious manual 30–40 % vs. measured).
5. Competitive-gap outbound performance (signal-grounded vs. exploratory reply-rate delta).
6. Annualised dollar impact at 3 adoption scenarios.
7. Pilot scope (one segment, one volume, one budget, one success criterion).

**Page 2 order (mandatory):**
1. Four failure modes τ²-Bench does not capture — must be Tenacious-specific.
2. Public-signal lossiness (quiet-sophisticated / loud-shallow).
3. Gap-analysis risks.
4. Brand-reputation unit economics (1 000 emails × 5 % wrong-signal).
5. One honest unresolved failure.
6. Kill-switch clause (trigger metric + threshold + rollback).

### D7.5 — Render + lint (30 min)

```
make memo
```

Internally:
1. Pandoc renders `memo/memo.md` via `memo/template.tex` to `memo/memo.pdf`.
2. `scripts/lint_memo.py memo/memo.md memo/evidence_graph.json memo/memo.pdf` must exit 0:
   - Every regex-matched number in `memo.md` has a matching `evidence_graph.json` claim whose `statement_preview` contains it.
   - `pdfinfo memo/memo.pdf | grep Pages` returns `2`.
   - Every `evidence_graph.json` source path exists; JSONPath selectors resolve.

Any linter failure → fix before the demo recording. Do not let PDF rendering become a D7 afternoon blocker.

---

## D7 afternoon (14:00–18:00) — Demo video

### D7.6 — Storyboard (30 min)

8 scenes × ~1 min each, mapping 1:1 to [__specs/17 §B.3](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md):

| # | Scene | Duration | Content |
|---|-------|----------|---------|
| 1 | Live email conversation end-to-end | 90 s | Signal-grounded cold email → reply → qualify → discovery call booked (record as one take if possible) |
| 2 | Hiring signal brief + competitor gap brief | 45 s | Terminal view of the two JSON artifacts, with per-signal confidence scores highlighted |
| 3 | HubSpot contact populating live | 45 s | Browser shows all `convergine_*` custom properties non-null + enrichment timestamp current |
| 4 | Email-to-SMS handoff for warm lead | 45 s | Existing email thread + prospect asks "can you text me?" → SMS send → scheduling via SMS |
| 5 | Grounded-honesty refusal | 45 s | Trigger a low-velocity fixture; show the agent refusing the "aggressive hiring" phrasing |
| 6 | Segment-classification trap | 60 s | Post-layoff-plus-bridge fixture → classifier picks Segment 2, not 1; narrate the rationale |
| 7 | τ²-Bench harness run | 30 s | `make baseline` excerpt; score_log.json + query trace visible in Langfuse |
| 8 | Probe walkthrough → concrete fix | 60 s | Show a probe YAML, its pre-mechanism trigger rate, its post-mechanism ≤ 1 % trigger rate |

Optional 9th scene (bonus): one real voice call end-to-end through the Shared Voice Rig if [00-decisions.md §3](00-decisions.md) unlocks it. **Only** if D7 schedule is ahead.

### D7.7 — Record (2 h)

- Record each scene as one take when possible; re-take only on fatal bloopers.
- No editing beyond scene concatenation + intro title card (name, repo URL, challenge name).
- Resolution 1080p minimum; audio clean (use a headset).
- Host on YouTube **unlisted** OR Google Drive with public-no-login sharing. Do not put it behind a login.

### D7.8 — Demo smoke check (15 min)

Open the video link from an incognito window without any authentication. Verify playback works end-to-end. This catches privacy/sharing misconfigurations that would cost points.

---

## D7 evening (18:00–21:00) — Final packaging + submit

### D7.9 — Optional stretch: market-space map (only if all green by 14:00)

If by 14:00 local the memo is drafted + demo storyboarded + no red risks open, attempt the market-space stretch per [__specs/15](/home/kg/Projects/10Academy/conversion-engine/__specs/15-market-space-map.md).

**Scope gate:** you need a hand-labelled sample of ≥ 30 companies across ≥ 5 sectors before this is honest. If the hand-labelling would push past 18:00 local, **abandon the stretch**. A superficial map is worse than none.

Outputs if attempted:
- `market_space/market_space.csv`
- `market_space/top_cells.md` — 3–5 top cells with allocation + risks
- `market_space/methodology.md` — precision/recall confusion matrix on hand-labelled sample

Add a one-paragraph note to Page 1 §2.7 pointing at the map (does not add a page).

### D7.10 — Pre-submit audit (30 min)

Manual sweep:

- [ ] `README.md` at root has kill-switch section, architecture, setup. Mentions final submission date.
- [ ] `memo/memo.pdf` exists, exactly 2 pages, lint passes.
- [ ] `memo/evidence_graph.json` resolves for every number in `memo.md`.
- [ ] `probes/probe_library.md` has ≥ 30 entries.
- [ ] `probes/failure_taxonomy.md` has pre- and post-mechanism trigger rates.
- [ ] `probes/target_failure_mode.md` present, ≤ 500 words.
- [ ] `method/method.md` + `ablation_results.json` + `held_out_traces.jsonl` + `stat_test_output.json` present.
- [ ] Delta A > 0, CI > 0, p < 0.05 — OR honest R4 fallback language in memo.
- [ ] Demo video URL loads from incognito browser.
- [ ] `scripts/lint_logs.py` green.
- [ ] No real Tenacious data anywhere in the repo (grep `@tenacious\.`, grep for founder names from the sales deck allowlist, grep for real pricing numbers).
- [ ] Kill-switch audit log last entry shows unset routing.
- [ ] All Tenacious-branded artifacts carry `draft` markers.
- [ ] `eval/score_log.json`, `eval/trace_log.jsonl`, `eval/baseline.md` still present.

### D7.11 — Submit (15 min)

- Tag `final-D7`. Push to `main`.
- Upload `memo/memo.pdf` to a public Google Drive link (no login required).
- Upload demo video link or confirm YouTube-unlisted URL is public.
- File the submission form with: repo URL, PDF link, video link.

### D7.12 — End-of-week purge (15 min)

```
scripts/end_of_week_purge.sh
```

- Deletes `seed/sales_deck.pdf`, `seed/case_studies/`, `seed/pricing.yaml`, and any other seed materials under limited license from personal infrastructure (laptops, cloud-drive sync folders).
- Writes `data/purge_audit.jsonl` with per-file deletion receipts.
- Does **not** delete code — everything under `agent/`, `eval/`, `probes/`, `method/`, `memo/`, `scripts/`, `tests/`, `__specs/`, `__plans/` stays in the program repo.

Revoke API keys per [__specs/18 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/18-configuration.md) — Resend, Africa's Talking, HubSpot private-app, Langfuse, OpenRouter, Anthropic, GitHub read-only.

### D7 exit gate

- [ ] Final submission filed (repo + PDF + video) before 21:00 local.
- [ ] `final-D7` tag pushed.
- [ ] Purge audit log written.
- [ ] API keys revoked.
- [ ] [00-decisions.md](00-decisions.md) O5 closed with chosen pilot segment + rationale.

---

## Anti-patterns to avoid on D7

1. **Writing prose before the evidence graph.** The linter will catch it; worse, it biases you toward numbers that fit the story rather than the other way round.
2. **Over-editing the demo video.** One take per scene is fine; heavy editing eats 2–3 h easily.
3. **Hidden YouTube video or Drive with access request.** Kills the reviewer's flow.
4. **Adding content to the memo's Page 2 past the section count.** Page 2 is 6 sections. Adding a 7th pushes Page 3 and fails the lint.
5. **Committing `memo/memo.pdf` with a last-minute non-final number.** Every `make memo` rebuild must pass the linter; treat a passing PDF as finished.
6. **Skipping the incognito smoke test on the video link.** A private-video submission is a waste of a grade-able artifact.
7. **Forgetting the end-of-week purge.** Rule 3 violation.

## Final-day budget

| Activity | Wall clock | Spend |
|----------|-----------|-------|
| Memo + evidence graph | 5 h | < $0.50 |
| Demo recording | 2.5 h | $0 |
| Stretch (if attempted) | 3 h | < $0.50 |
| Packaging + audit + submit | 1 h | $0 |
| **Total D7** | **≈ 9 h** | **< $1** |

Week total still ≤ $20.
