# 14 — Memo Specification (Act V, `memo.pdf`)

**Source:** Challenge document — "Act V — The Memo" (Page 1 / Page 2), "Deliverables → Final Submission → PDF Report", "Evidence-Graph Grading".

## 1. Constraints

- **Exactly 2 pages, no more no less.** Grading enforces.
- Addressed to the **Tenacious CEO and CFO**.
- **Every numeric claim** must map to `evidence_graph.json` with a source trace_id, an `invoice_summary.json` line, a `method/ablation_results.json` selector, or a published public source.
- **Fabricated Tenacious numbers are a disqualifying violation**, separate from the standard penalty.
- Page size: US Letter or A4; 11–12 pt serif body; 1 inch / 2.54 cm margins. No cover page.

## 2. Page 1 — The Decision

Mandatory sections in order:

### 2.1 Executive summary (3 sentences)
- Sentence 1: What was built (one line).
- Sentence 2: Headline number (pass@1 delta, or cost-per-qualified-lead, or stalled-thread delta).
- Sentence 3: Recommendation (pilot scope).

### 2.2 τ²-Bench pass@1 results
Three rows, each with 95 % CI:
- Published τ²-Bench retail reference (~42 % ceiling).
- Our Day-1 baseline (from `eval/score_log.json`).
- Our method (from `method/ablation_results.json`).

Source: `method/held_out_traces.jsonl`.

### 2.3 Cost per qualified lead
One number, derived as in [10 §4](10-observability.md). Source: `memo/invoice_summary.json` + `eval/trace_log.jsonl`. Target < $5; penalty if > $8 without justification.

### 2.4 Speed-to-lead delta (stalled-thread rate)
- Tenacious current manual process: 30–40 % stalled in first two weeks (source: Tenacious executive interview).
- Our system measured from traces: `<N>%` (source: `eval/trace_log.jsonl`, filter `stage_final != BOOKED && nurture_last_at > 14d`).

If our number is lower, **show the math** (traces counted, window, methodology).

### 2.5 Competitive-gap outbound performance
- Fraction of outbound tagged `outbound_variant=signal_grounded` vs. `=exploratory`.
- Reply-rate delta between the two, 95 % CI.
- Source: traces filtered by the variant tag.

### 2.6 Annualized dollar impact — three adoption scenarios

| Scenario | Segments | Lead volume / mo | Discovery-call conv | Proposal conv | Close conv | ACV midpoint | Annualised impact |
|----------|----------|------------------|---------------------|---------------|------------|--------------|-------------------|
| Minimal | 1 segment only | X | 35–50 % | 25–40 % | — | $240–720 K (talent) / $80–300 K (consulting) | $A |
| Moderate | 2 segments | Y | ... | ... | ... | ... | $B |
| Full | All 4 segments | Z | ... | ... | ... | ... | $C |

Every cell sources from `eval/trace_log.jsonl` (volume), published Tenacious conversion rates (35–50 %, 25–40 %), and the public pricing sheet. **No fabricated Tenacious numbers.**

### 2.7 Pilot scope recommendation (one paragraph)
Exactly:
- **One segment** (pick one, justify in one line).
- **One lead volume** per week.
- **One weekly budget** (USD).
- **One measurable success criterion** Tenacious can track after 30 days.

## 3. Page 2 — The Skeptic's Appendix

Mandatory sections in order:

### 3.1 Four failure modes τ²-Bench does not capture

Each failure must be **Tenacious-specific** (offshore-perception objection, bench-mismatch risk, brand-reputation from wrong hiring signal, etc.). Each entry:
- What the failure is.
- Why τ²-Bench misses it.
- What would need to be added to catch it.
- What that addition would cost (rough engineering estimate).

Vague entries ("agent might offend someone") are penalised; specific entries ("agent uses offshore language that triggers in-house hiring managers") earn credit.

### 3.2 Public-signal lossiness

Name the known false-positive and false-negative modes of AI-maturity scoring:

- **Quietly sophisticated but publicly silent**: what the agent does wrong, business impact.
- **Loud but shallow**: what the agent does wrong, business impact.

Cite at least one fixture case from the probe library for each.

### 3.3 Gap-analysis risks

One paragraph per real risk, with a concrete example from our data:
- When a top-quartile practice is a **deliberate non-choice** by the prospect.
- When a top-quartile practice is **irrelevant to the sub-niche**.

### 3.4 Brand-reputation comparison (unit economics)

Concrete statement: "If our agent sends 1 000 signal-grounded emails with 5 % factually-wrong-signal rate, is the brand damage worth the 7–12 % reply rate?"

Include explicit unit-economics table:
- Expected replies: `0.10 × 1 000 = 100`.
- Expected brand-damaging incidents: `0.05 × 1 000 = 50`.
- Assumed cost per brand-damaging incident (stated assumption, e.g., $2 000 — document how this is derived).
- Break-even reply value: `(50 × $2 000) / 100 = $1 000 per reply to break even`.
- Compare to expected deal value per reply given the conversion chain and ACV midpoint.

### 3.5 One honest unresolved failure

Name one probe from `probes/probe_library.md` that **we did not resolve**. State:
- Why it resists resolution.
- What the business impact would be if deployed anyway.
- What it would cost to fix.

### 3.6 Kill-switch clause

One sentence of the measurable trigger metric + threshold under which the Tenacious CEO should pause the system. Example shape:

> If the weekly `cost_per_qualified_lead` exceeds $10 OR the signal-grounded reply rate drops below 4 % for two consecutive weeks OR the false-positive rate on hand-labelled audit exceeds 8 %, pause outbound and revert to manual qualification.

## 4. `evidence_graph.json` contract

Shape:
```json
{
  "version": "1.0",
  "generated_at": "2026-04-25T20:45:00Z",
  "claims": [
    {
      "claim_id": "memo.page1.executive_summary.headline",
      "page": 1,
      "statement_hash": "sha256:...",
      "statement_preview": "our method beats Day-1 baseline by +7.3 pts pass@1...",
      "sources": [
        {"type": "ablation_results", "path": "method/ablation_results.json", "selector": "$.held_out.method.pass_at_1"},
        {"type": "ablation_results", "path": "method/ablation_results.json", "selector": "$.held_out.day1_baseline.pass_at_1"},
        {"type": "stat_test", "path": "method/stat_test_output.json"}
      ]
    },
    {
      "claim_id": "memo.page1.stalled_thread_delta",
      "sources": [
        {"type": "published", "citation": "Tenacious executive interview (seed materials)"},
        {"type": "trace_count", "path": "eval/trace_log.jsonl", "filter": "stage_final != BOOKED && days_since_first_touch > 14"}
      ]
    }
  ]
}
```

Every numeric string in `memo.md` is grep-able to an `evidence_graph.json` entry. A `make memo` step runs a linter (`scripts/lint_memo.py`) that fails the build if any number in `memo.md` lacks a graph entry.

## 5. Recommended tooling

- `memo/memo.md` → Pandoc → `memo/memo.pdf`.
- Template: `memo/template.tex` with strict 2-page constraint (`\usepackage[a4paper, margin=2.54cm]{geometry}`).
- `scripts/lint_memo.py`:
  - Extracts numbers (regex `\b\d+(?:[.,]\d+)?\s*%?\b`) from memo.md.
  - For each, checks that an `evidence_graph.json` claim statement contains it.
  - Exits non-zero if unreferenced numbers exist.
  - Exits non-zero if PDF page count ≠ 2.

## 6. Acceptance tests

- `memo/memo.pdf` is exactly 2 pages (`pdfinfo memo/memo.pdf | grep Pages` → `2`).
- `scripts/lint_memo.py memo/memo.md memo/evidence_graph.json` exits 0.
- Every `evidence_graph.json` claim's `source.path` exists and the `selector` (if JSON-path) resolves.
- Kill-switch clause is present and contains at least one numeric threshold.
- All four Tenacious-specific failure modes are present and distinct from each other.
