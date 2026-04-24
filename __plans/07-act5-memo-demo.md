# 07 — Act V: The Memo, Evidence Graph, and Demo Video

## Goal

Produce `memo.pdf` (exactly two pages) addressed to the Tenacious CEO and CFO, an `evidence_graph.json` that maps every numeric claim to its source, a `README_for_inheritor.md` for the engineer who would inherit this work, and a ≤8-minute demo video that runs the system end-to-end on camera. This is the deliverable that determines whether the system is ever run against real Tenacious prospects.

## Spec references

- [`__specs/14-memo-specification.md`](../__specs/14-memo-specification.md)
- [`__specs/17-deliverables-checklist.md`](../__specs/17-deliverables-checklist.md#final-submission)

## Dependencies

- [`06-act4-mechanism.md`](06-act4-mechanism.md) closed; `method/ablation_results.json` and `method/held_out_traces.jsonl` present.
- Langfuse traces for ≥20 production-stack interactions with A/B tagging.
- `seed/baseline_numbers.md` and `seed/bench_summary.json` accessible.

## Tasks

### 7.1 Invoice summary

1. Write `memo/invoice_summary.json` with:

```json
{
  "llm_spend_usd": { "dev_tier": 3.20, "eval_tier": 9.40, "total": 12.60 },
  "rig_spend_usd": 0.00,
  "other_spend_usd": 0.00,
  "trace_count_total": 1830,
  "qualified_lead_count": 22,
  "cost_per_qualified_lead_usd": 0.57,
  "source_files": [
    "eval/score_log.json",
    "method/ablation_results.json",
    "eval/runs/interim/latency_report.json"
  ]
}
```

2. `qualified_lead` definition: classifier confidence ≥ `icp.abstain_threshold` **and** received an `engaged` or `curious` reply.
3. Compute `cost_per_qualified_lead_usd` = `llm_spend_total / qualified_lead_count`. Target under **$5**; penalty above **$8** per [spec 14](../__specs/14-memo-specification.md#evidence-graph-grading).

### 7.2 Page 1 — The Decision

Write `memo/memo.md`, Page 1:

1. **Three-sentence executive summary**: what was built, headline pass@1 with CI and cost, pilot recommendation.
2. **τ²-Bench pass@1 table**: published reference ≈ 42%, your Day-1 baseline, your mechanism, automated-optimization baseline — all with 95% CIs, from `held_out_traces.jsonl`.
3. **Cost per qualified lead**: the figure from `invoice_summary.json` with a one-line breakdown of how it was derived.
4. **Speed-to-lead delta**: manual Tenacious baseline 30–40% (cite `seed/baseline_numbers.md`) vs. your measured stalled-thread rate from traces. Show the math.
5. **Competitive-gap outbound performance**: fraction of outbound tagged `signal_grounded=True` vs. generic; reply-rate delta.
6. **Annualized dollar impact** at three adoption scenarios (one segment / two segments / all four), each with deal volume × conversion rate (from baseline_numbers) × ACV (revised Feb 2026 ranges).
7. **Pilot-scope recommendation**: one segment, one lead volume per month, one weekly budget, one 30-day success criterion.

### 7.3 Page 2 — The Skeptic's Appendix

Page 2 of `memo/memo.md`:

1. **Four failure modes τ²-Bench does not capture** but would appear in a real Tenacious deployment. Tenacious-specific, not generic.
2. **Public-signal lossiness**: AI-maturity false-positive and false-negative modes; "quietly sophisticated but publicly silent" and "loud but shallow"; business impact of each.
3. **Gap-analysis risks**: one paragraph per real risk with an example from your data.
4. **Brand-reputation comparison**: unit economics of 1,000 signal-grounded emails at 5% wrong-signal rate vs 7–12% reply rate. Explicit reputation-cost assumption.
5. **One honest unresolved failure** from `probe_library.md` with business-impact assessment.
6. **Kill-switch clause**: trigger metric (e.g., "wrong-signal-email rate above 2% on a 50-message rolling window"), threshold, rollback condition.

### 7.4 Render to PDF

1. `memo/render.py` uses weasyprint (or md-to-pdf) with the typography in `config.yaml > memo.typography`.
2. The renderer enforces `page_count_strict: 2` — fails if the output is not exactly 2 pages.
3. If the content overflows, revise; do not change the typography to cheat the constraint.

### 7.5 Evidence graph

1. Implement `memo/build_evidence_graph.py` that scans `memo.md` for every numeric claim and emits `memo/evidence_graph.json` per the schema in [spec 14](../__specs/14-memo-specification.md#evidence-graph).
2. Run the graph generator; walk each `claims[*]` entry and verify:
   - `source_type` is one of `trace_file | seed_baseline_numbers | seed_bench_summary | public_source`.
   - The referenced path or URL resolves.
   - `tenacious_branded: true` entries carry `draft_status: draft`.
3. Fail the build if any claim has `source_type: null` or an unresolvable reference.

### 7.6 README for inheritor

Write `memo/README_for_inheritor.md` — for the engineer who would inherit this work after the challenge. Cover:

1. How to run enrichment for one prospect from cold (one command).
2. How to run the τ²-Bench harness against the held-out slice (the dual-guard env vars).
3. Where every secret is stored (`.env`, `config.yaml`, HubSpot Dev Sandbox — all gitignored).
4. Where the kill switch lives; what flipping it requires; the program-staff approval path.
5. Known failure modes (pointers into `probe_library.md`) and which ones the current mechanism does and does not resolve.
6. Next steps if selected for the Tenacious pilot.

### 7.7 Demo video (≤8 minutes, no login required)

Storyboard:

| Segment | Duration | Shows |
|---|---|---|
| Intro | 0:20 | What's being demoed; architecture one-liner |
| Enrichment live | 1:00 | `make enrich DOMAIN=<synth>`; Langfuse spans appear; briefs materialize with per-signal confidence scores visible |
| Cold email live | 1:00 | Agent composes segment-specific email; tone-check pass; kill-switch routes to sink; HubSpot contact record fills |
| Engaged reply | 1:00 | Manually reply from sink inbox; classifier tags `engaged`; warm-reply composed with Cal link |
| SMS handoff | 0:45 | Prospect shares phone; agent switches to SMS for scheduling; confirmation routed via SMS sink |
| Cal.com booking | 0:45 | Slot picked; context brief attached to Deal; NOTE visible in HubSpot |
| Abstention path | 0:30 | Agent refuses to assert "aggressive hiring" on <5 open roles; softer exploratory language shown |
| Classification nuance | 0:30 | Post-layoff + funding company → Segment 2, not Segment 1 (show the rule firing in Langfuse) |
| τ²-Bench score | 0:30 | Harness produces a trace; pass@1 visible |
| Probe walkthrough | 0:45 | One probe that drove a mechanism fix; show before/after trigger rate |
| Bonus — voice | 0:30 | One real voice call through the Shared Voice Rig (optional) |
| Outro | 0:20 | Pilot recommendation + kill-switch clause |

Record with OBS or Loom at 1080p; annotate key points; no background music.

### 7.8 Final submission packaging

1. Merge the `memo/` and `method/` and `probes/` directories into the main branch.
2. Upload `memo.pdf`, the demo video, and the final PDF report (if separate from memo.pdf) to public Google Drive / YouTube (video); verify each link loads in an incognito window.
3. Push the repo; tag `final-submission`.
4. Submit via the program submission form.

## Acceptance criteria

- [ ] `memo/memo.pdf` exists and is **exactly 2 pages**.
- [ ] `memo/evidence_graph.json` has no `source_type: null` entries; every ref resolves.
- [ ] `memo/README_for_inheritor.md` is written and self-contained.
- [ ] `method/ablation_results.json` and `method/held_out_traces.jsonl` are committed.
- [ ] `probes/probe_library.md`, `probes/failure_taxonomy.md`, `probes/target_failure_mode.md` are committed.
- [ ] Demo video ≤ 8 minutes, public, no login required, covers the 11 storyboard segments.
- [ ] Kill-switch clause present in memo Page 2.
- [ ] Cost-per-qualified-lead < **$5** (or under $8 with a documented justification).
- [ ] No fabricated Tenacious numbers; CI evidence-graph check passes.

## Submission gate

**Final gate** — this phase is the gate.

## Exit risks

- **Memo page-count creep**: tight two-page constraint. Mitigation: cut ruthlessly; the Skeptic's Appendix can compress to dense paragraphs before it loses value.
- **Evidence-graph gaps**: a claim that sounds reasonable but has no source is disqualifying. Mitigation: the graph-generator enforces; fix at generation time.
- **Demo video over 8 minutes**: the storyboard above is ~8:15 if paced loosely. Mitigation: pre-record enrichment and τ²-Bench segments; run them in the background and talk over the output.
- **Draft marking drops in memo**: Tenacious-branded content not flagged `draft_status: draft`. Mitigation: CI grep on the evidence-graph JSON.
- **Fabricated numbers**: the single disqualifying violation class. Mitigation: every number in the memo is a macro that resolves from a source file; no numeric literals in the markdown.
- **Cost-per-lead penalty**: if above $8 without justification, the penalty applies. Mitigation: compute the number before rendering; if high, reduce the qualified-lead denominator honestly (did we really qualify them?), not the cost numerator.
