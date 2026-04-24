# 04 — Interim Submission

## Goal

Package Acts I and II into a public GitHub repo + public PDF report that satisfies every line of the interim-submission checklist. The interim submission is a checkpoint, not a finish — but a failed interim blocks access to the sealed held-out partition that Act IV needs.

## Spec references

- [`__specs/17-deliverables-checklist.md`](../__specs/17-deliverables-checklist.md#interim-submission)

## Dependencies

- [`02-act1-tau2-baseline.md`](02-act1-tau2-baseline.md) closed (baseline, score_log, trace_log, baseline.md present).
- [`03-act2-production-stack.md`](03-act2-production-stack.md) closed (enrichment, agent, channels, HubSpot, Cal.com all live; ≥20 interaction traces).

## Tasks

### 4.1 Repo readiness pass

1. `README.md` at root contains:
   - Architecture diagram (from [spec 01](../__specs/01-architecture.md)).
   - Setup instructions: clone → `.env` → `make setup` → `make smoke`.
   - **Kill-switch section** (not optional): defaults unset, routes to sink, smoke test verifies, flipping requires program-staff approval.
   - Requirements list with Python version and system deps.
2. `agent/requirements.txt` pins every direct dep with `==` (not `>=`).
3. `.env.example` and `config.example.yaml` in `__specs/` are consistent with what's actually read.
4. `make smoke` green.
5. `make tau2-baseline` reproduces the Act I numbers.

### 4.2 Evidence artifacts

1. `eval/score_log.json` — includes `act1_baseline_<ts>` entry with mean, 95% CI, cost, latencies.
2. `eval/trace_log.jsonl` — 150 lines (5 trials × 30 tasks).
3. `eval/baseline.md` — ≤400 words, all four sections populated.
4. `eval/runs/interim/latency_report.json` — p50/p95 across ≥20 interactions.
5. `eval/briefs/<sample_domains>/` — at least 3 complete brief pairs (hiring signal + competitor gap) for distinct segments.

### 4.3 PDF report — structure

A single PDF published to public Google Drive. Max 10 pages including cover. Sections:

#### Cover page

- "Conversion Engine — Interim Report · TRP1 Week 10".
- Trainee name, cohort, submission UTC timestamp.
- One-sentence scope: "Acts I and II — τ²-Bench baseline and production stack."

#### Section 1 — Architecture overview (≤2 pages)

- Architecture diagram.
- Key design decisions with one-line rationale:
  - Kill switch as a single `deliver()` function.
  - Email primary, SMS warm-scheduling-only, voice bonus.
  - Rule-based ICP classifier; LLM only for free-text sub-signals.
  - Briefs as Pydantic with CI schema-conformance tests.
  - Dev-tier vs eval-tier LLM split.

#### Section 2 — Production stack status (≤1 page)

Each row includes a screenshot and the status of the first end-to-end test:

| Component | Provider | Status | Evidence |
|---|---|---|---|
| Email (primary) | Resend or MailerSend | ✓ | screenshot of sink inbox receiving a test outbound |
| SMS (secondary) | Africa's Talking | ✓ | screenshot of short code + test SMS delivery |
| CRM | HubSpot Developer Sandbox | ✓ | screenshot of one synthetic prospect's contact record with all `tenacious_*` properties populated and timestamps current |
| Calendar | Cal.com self-hosted | ✓ | screenshot of one booking end-to-end |
| Observability | Langfuse cloud | ✓ | screenshot of conversation trace view |

#### Section 3 — Enrichment pipeline status (≤1 page)

One paragraph per enrichment signal:

- Crunchbase ODM firmographics — one worked example showing firmographics resolved.
- Job-post velocity scraping — today vs 60-days-ago counts on one prospect.
- layoffs.fyi integration — matched layoff example.
- Leadership-change detection — one new-CTO example.
- AI-maturity scoring (0–3) — one example with the six-signal justification table visible.

Attach `hiring_signal_brief.json` and `competitor_gap_brief.json` for one test prospect as appendix assets.

#### Section 4 — Competitor gap brief status (≤1 page)

- Show one full `competitor_gap_brief.json` (redact long URLs).
- Highlight the `gap_findings` array: 2–3 practices with peer evidence and per-finding confidence scores.
- Explain how this brief is injected into the composer's prompt for Segment-4 outreach.

#### Section 5 — τ²-Bench baseline (≤1 page)

- Pass@1 mean, 95% CI, cost-per-run, p50/p95 latency — from `score_log.json`.
- Reproduction delta vs the Feb 2026 published reference.
- One-paragraph methodology (model, trials, seeds, pinned SHA).

#### Section 6 — p50 / p95 latency from real interactions (≤1 page)

- p50 and p95 across ≥20 synthetic-prospect interactions, split by:
  - Cold compose.
  - Reply classify.
  - Warm compose.
  - SMS scheduling.
  - End-to-end reply cycle.
- Bar chart with the breakdown.

#### Section 7 — What is working, what is not, plan for remaining days (≤1 page)

**Working**: bullet list of capabilities verified. **Not working or partial**: list with severity and planned remediation. **Plan for remaining days**: one-line-per-act breakdown for Acts III, IV, V (without specific dates — phase order only).

### 4.4 Final interim checks

1. Run `make final_check` (subset relevant to interim):
   - Smoke test green.
   - No `.env` in the committed tree.
   - No secret-looking strings (`grep -rE 'sk_|pk_|at_|hub_'`).
   - Every Tenacious-branded outbound in the last 50 runs carries `X-Tenacious-Status: draft`.
   - `scripts/audit_week.py` reports zero violations.
2. Push the repo to the public GitHub URL requested by program staff.
3. Upload the PDF to public Google Drive; set sharing to "anyone with link can view"; verify from an incognito window.
4. Submit both links via the program submission form.

## Acceptance criteria

- [ ] GitHub repo public, README renders, `make smoke` passes on a fresh clone.
- [ ] `eval/score_log.json`, `eval/trace_log.jsonl`, `eval/baseline.md` present.
- [ ] Interim PDF uploaded, all 7 sections populated, ≤10 pages.
- [ ] Screenshots from each stack component dated within the submission window.
- [ ] p50/p95 latency numbers sourced from Langfuse, not hand-computed.
- [ ] Submission form completed.

## Submission gate

**Interim gate** — this phase is the gate.

## Exit risks

- **Last-mile README bugs**: a fresh clone reveals a missing dep or a hard-coded path. Mitigation: test `make smoke` in a brand-new directory on a different machine or Docker image.
- **Screenshot leakage**: screenshots include real tokens or secret UI panels. Mitigation: review every screenshot in a preview tool before committing; redact tokens and URLs that could be misused.
- **Cost overrun right before submission**: re-running τ²-Bench to refresh traces can drain dev-tier budget. Mitigation: only re-run if `eval/score_log.json` is stale relative to a code change; otherwise reuse the existing traces.
- **Public drive access broken**: the Google Drive link silently requires login. Mitigation: open the URL in an incognito window at submission time and confirm it renders without a login prompt.
