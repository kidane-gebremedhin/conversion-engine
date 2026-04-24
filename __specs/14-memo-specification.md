# 14 — Memo Specification (Act V)

A two-page decision memo addressed to the Tenacious CEO and CFO. **Every number traces to a trace file or a published source.** The memo is the deliverable that determines whether this system is ever run against real Tenacious prospects.

## Format constraints

- **Exactly 2 pages.** Not more, not less.
- **PDF**, rendered from `memo/memo.md` via `memo/render.py` (weasyprint, md-to-pdf, or equivalent).
- **Footer every page**: page number, trace-report UTC timestamp, `evidence_graph.json` hash.
- **Font and margins** are configurable in `config.yaml > memo.typography` — not hard-coded.

## Page 1 — The decision

1. **Three-sentence executive summary.**
   - Sentence 1: what was built.
   - Sentence 2: the headline number (with 95% CI and cost).
   - Sentence 3: the recommendation (pilot scope, budget, success criterion).

2. **τ²-Bench pass@1 results**, all with 95% CIs, sourced from `held_out_traces.jsonl`:
   - Published reference (≈42% retail Feb 2026).
   - Day-1 baseline (your reproduction).
   - Your mechanism.
   - GEPA / automated-optimization baseline on the same compute budget.

3. **Cost per qualified lead**, derived from:
   - Rig + LLM spend (`invoice_summary.json` + `trace_log.jsonl`).
   - Lead count (`qualified` = classifier confidence ≥ threshold AND engaged/curious reply).
   - Target: **under $5**. Penalty threshold: **$8** (see [Evidence-Graph Grading](#evidence-graph-grading) below).

4. **Speed-to-lead delta**:
   - Current Tenacious manual process stalled-thread rate: **30–40%** (`seed/baseline_numbers.md`).
   - Your system's measured stalled-thread rate from traces.
   - Show the math. Under-claiming with a note on sample size is acceptable; over-claiming without traces is disqualifying.

5. **Competitive-gap outbound performance**:
   - Fraction of outbound that led with a research finding (AI-maturity score + top-quartile competitor gap) vs. a generic Tenacious pitch.
   - Reply-rate delta between the two variants.
   - Source: traces tagged by outbound variant.

6. **Annualized dollar impact at three adoption scenarios**:
   - One segment only.
   - Two segments.
   - All four segments.
   - Each scenario includes expected deal volume, conversion rates (`seed/baseline_numbers.md`), and ACV (revised ranges, not aspirational).
   - Each scenario is reproducible from trace files and published conversion rates.

7. **Pilot-scope recommendation**:
   - One segment name.
   - A specific lead volume per month.
   - A specific weekly budget.
   - One measurable success criterion Tenacious can track after 30 days.

## Page 2 — The Skeptic's Appendix

1. **Four failure modes τ²-Bench does not capture** — but would show up in a real Tenacious deployment. Each entry states what it is, why the benchmark misses it, what would need to be added to catch it, and the business impact. Tenacious-specific (not generic B2B):
   - e.g., offshore-perception objection, bench mismatch, brand-reputation risk from wrong hiring signals.
   - Vague examples ("the agent will say something offensive") are penalized; specific examples ("the agent uses offshore language that triggers in-house hiring managers") are rewarded.

2. **Public-signal lossiness**:
   - Known false-positive and false-negative modes of AI-maturity scoring.
   - What does a quietly-sophisticated-but-silent company look like in your system? What does a loud-but-shallow one look like?
   - For each, what does the agent do wrong, and what is the business impact?

3. **Gap-analysis risks**:
   - When is a top-quartile practice a **bad** benchmark? (Deliberate strategic choice by the prospect; capability genuinely irrelevant in their sub-niche.)
   - One paragraph per real risk, with an example from your data.

4. **Brand-reputation comparison**:
   - If the agent sends 1,000 signal-grounded emails and 5% contain factually wrong signal data, is the brand damage worth the 7–12% reply rate?
   - Unit economics with an explicit assumption about the reputation cost of a wrong-signal email.

5. **One honest failure** — a probe from `probe_library.md` that was not resolved by the mechanism, and the impact if deployed anyway.

6. **Kill-switch clause**:
   - Specific trigger metric (e.g., "wrong-signal-email rate above 2% on a 50-message rolling window").
   - Threshold.
   - Rollback condition — what the Tenacious CEO does if the trigger fires.

## Evidence graph

`memo/evidence_graph.json` — **every numeric claim in the memo maps to one of**:

- A Langfuse trace ID (`trace_<id>`), OR
- A row in `seed/baseline_numbers.md` (cited as "Tenacious internal, `seed/baseline_numbers.md`"), OR
- A row in `seed/bench_summary.json` (cited as "Tenacious internal, `seed/bench_summary.json`, as of 2026-04-21"), OR
- A trace file in `eval/runs/` (cited as "measured from trace ID `xxx`"), OR
- A published public source (with URL).

Fabricated Tenacious numbers are a **disqualifying violation**, separate from the standard evidence-graph penalty.

Structure:

```json
{
  "memo_sha256": "<hash-of-memo.pdf>",
  "generated_at": "2026-04-25T20:00:00Z",
  "claims": [
    {
      "claim_id": "C-001",
      "claim_text": "τ²-Bench retail pass@1 with our mechanism: 55% (95% CI 48–62%).",
      "page": 1,
      "section": "pass_at_1_results",
      "source_type": "trace_file",
      "source_ref": "method/held_out_traces.jsonl",
      "trace_id_range": ["tau2_heldout_0001", "tau2_heldout_0020"]
    },
    {
      "claim_id": "C-002",
      "claim_text": "Baseline stalled-thread rate: 30–40%.",
      "page": 1,
      "section": "speed_to_lead",
      "source_type": "seed_baseline_numbers",
      "source_ref": "tenacious_sales_data/seed/baseline_numbers.md#operational-baselines"
    },
    {
      "claim_id": "C-003",
      "claim_text": "Industry cold-email reply rate baseline: 1–3%.",
      "page": 1,
      "section": "competitive_gap_outbound",
      "source_type": "public_source",
      "source_ref": "https://leadiq.com/benchmarks/2026"
    }
  ]
}
```

## Tenacious-branded content — draft marking

Any memo content that reproduces Tenacious-branded language is flagged in the evidence graph:

```json
{
  "claim_id": "C-017",
  "claim_text": "\"Scale your AI team faster than in-house hiring can support\" (Segment 1 high-readiness pitch)",
  "tenacious_branded": true,
  "draft_status": "draft",
  "source_ref": "tenacious_sales_data/seed/icp_definition.md#segment-1-pitch-language"
}
```

The Tenacious executive team reserves the right to redact any draft-status claim from the memo.

## README for the engineer who inherits this

`memo/README_for_inheritor.md` — written for the engineer who would inherit this work after the challenge. Covers:

- How to run enrichment for one prospect from cold.
- How to run the τ²-Bench harness against the held-out slice.
- Where every secret is stored (`.env`, `config.yaml`, HubSpot Developer Sandbox credentials — never committed).
- Where the kill switch lives and how to flip it responsibly (program-staff approval required).
- Known failure modes and the probe-library entries that trigger them.
- Next steps if selected for the Tenacious pilot.

## Evidence-Graph Grading (from the challenge brief)

| Observable | Note |
|---|---|
| Reproduction fidelity | Against pinned τ²-Bench retail. |
| Probe originality | Tenacious-specific probes earn higher credit. |
| Mechanism attribution | Automated statistical check on Delta A. |
| Cost-quality Pareto | Per qualified lead, not per message. Penalty if `>$8` without justification. Target: `<$5`. |
| Evidence-graph integrity | Every claim in memo.pdf maps to a trace, seed number, or public source. Fabricated Tenacious numbers = disqualifying. |
| Skeptic's Appendix quality | Must address Tenacious-specific risks (brand reputation, bench mismatch, offshore-perception objections). Generic risks are penalized. |

## What the memo must NOT do

- Exceed two pages.
- Claim a Tenacious number not in `seed/baseline_numbers.md`, not in `seed/bench_summary.json`, not in a trace file, and not publicly citable.
- Use aspirational ACV ranges. The revised Feb-2026 ranges in `baseline_numbers.md` are the only ones permitted.
- Cite a named client or case study beyond what is anonymized in `seed/case_studies.md`.
- Omit the kill-switch clause.
- Present deltas without 95% CIs.
