# 17 — Deliverables Checklist

Two submissions, both public (no login required). The interim covers Acts I–II; the final adds Acts III–V plus a demo video.

## Interim submission

**Submit**: GitHub repo + PDF report (via public Google Drive link).
**Scope**: the τ²-Bench baseline (Act I) and the full production stack running end-to-end (Act II).

### GitHub repo requirements

- [ ] **`README.md`** at root, containing:
  - Architecture diagram (copy from [spec 01](01-architecture.md)).
  - Setup instructions (`make setup`, `.env` variables, Day 0 checklist checklist reference).
  - **Kill-switch documentation** — what it is, how it is configured, why `TENACIOUS_OUTBOUND_ENABLED` defaults to unset, what flipping it requires, and that `infra/smoke_test.sh` verifies the gate before boot.
  - Requirements list.
- [ ] **`agent/`** containing:
  - All agent source files.
  - Email handler (Resend or MailerSend).
  - SMS handler (Africa's Talking for warm-lead scheduling).
  - HubSpot MCP integration.
  - Cal.com booking flow.
  - Enrichment pipeline.
  - `requirements.txt`.
- [ ] **`eval/`** containing:
  - τ²-Bench harness source (vendored or submoduled at pinned SHA).
  - `score_log.json` with at least the Act-I dev-tier baseline and reproduction check, both with 95% CIs.
  - `trace_log.jsonl` with full τ²-Bench trajectories across all dev trials.
- [ ] **`baseline.md`** (≤400 words) covering:
  - What reproduced.
  - Confidence interval.
  - Cost per run.
  - Any unexpected behavior.
- [ ] Policy files visible (`tenacious_sales_data/policy/*`, `LICENSE.md`).
- [ ] `.env.example` and `config.example.yaml` present; no real `.env` committed.

### PDF report requirements

- [ ] Architecture overview and key design decisions.
- [ ] **Production stack status**: each of Resend/MailerSend (email), Africa's Talking (SMS), HubSpot Developer Sandbox, Cal.com, Langfuse — verified running. Screenshots from each dashboard.
- [ ] **Enrichment pipeline status**: Crunchbase ODM firmographics, job-post velocity scraping, layoffs.fyi integration, leadership-change detection, AI-maturity scoring — all producing output on at least one synthetic prospect.
- [ ] **Competitor-gap-brief status**: top-quartile comparison pipeline generates `competitor_gap_brief.json` for at least one test prospect.
- [ ] **τ²-Bench baseline score** and methodology.
- [ ] **p50 / p95 latency** numbers from at least 20 real email and SMS interactions, pulled from Langfuse trace log.
- [ ] What is working, what is not, and what the plan is for remaining days.

## Final submission

**Submit**: GitHub repo + PDF report + Demo video (all public, no login required).

### GitHub repo (adds to interim)

#### `probes/` directory

- [ ] **`probes/probe_library.md`** — 30+ structured probe entries covering:
  - ICP misclassification
  - Hiring-signal over-claiming
  - Bench over-commitment
  - Tone drift from Tenacious style guide
  - Multi-thread leakage
  - Cost pathology
  - Dual-control coordination
  - Scheduling edge cases (EU / US / East Africa time zones)
  - Signal reliability with false-positive rates
  - Gap over-claiming from the competitor brief
  - Kill-switch bypass (hard zero trigger rate)
- [ ] **`probes/failure_taxonomy.md`** grouping probes by category with observed trigger rates.
- [ ] **`probes/target_failure_mode.md`** naming the single highest-ROI failure mode with explicit business-cost derivation in Tenacious terms (referencing ACV, stalled-thread rates, brand-reputation impact).

#### Method and evaluation files

- [ ] **`method/method.md`** — documents the mechanism, design rationale, hyperparameters, three ablation variants tested, plus a statistical test confirming Delta A is positive with **p < 0.05**.
- [ ] **`method/ablation_results.json`** — pass@1, 95% CI, cost-per-task, and p95 latency for:
  - Your method
  - Your Day-1 baseline
  - Automated-optimization baseline (GEPA or AutoAgent)
  - All on the sealed held-out slice.
- [ ] **`method/held_out_traces.jsonl`** — raw traces from each of the three conditions.
- [ ] **`memo/evidence_graph.json`** — every numeric claim in the memo → source (trace ID or invoice line item).

### PDF report — `memo.pdf`, exactly 2 pages

See [spec 14](14-memo-specification.md) for the full specification.

**Page 1: The Decision**

- [ ] Executive summary in three sentences: what was built, headline number, recommendation.
- [ ] τ²-Bench pass@1 results: published reference, Day-1 baseline, your method — all with 95% CIs, sourced from `held_out_traces.jsonl`.
- [ ] Cost per qualified lead derived from rig usage, LLM spend, and trace count, sourced from `invoice_summary.json` and `trace_log.jsonl`.
- [ ] Speed-to-lead delta: current Tenacious manual process (stalled-thread rate 30–40%) vs. your system's measured stalled-thread rate from traces.
- [ ] Competitive-gap outbound performance: fraction of outbound that led with a research finding vs. generic pitch, and the reply-rate delta.
- [ ] Annualized dollar impact at three adoption scenarios (one segment / two segments / all four), reproducible from traces and published conversion rates + ACV ranges.
- [ ] Pilot-scope recommendation: one segment, one lead volume, one dollar budget, one measurable success criterion Tenacious can track after 30 days.

**Page 2: The Skeptic's Appendix**

- [ ] Four failure modes τ²-Bench does not capture but would appear in a real Tenacious deployment, each with: what it is, why the benchmark misses it, what would need to catch it, what that would cost. Tenacious-specific (not generic).
- [ ] Public-signal lossiness: false-positive and false-negative modes of AI-maturity scoring with business impact.
- [ ] Gap-analysis risks: when a top-quartile practice is a bad benchmark, with an example from your data.
- [ ] Brand-reputation comparison: unit economics of wrong-signal emails at 5% error rate vs. 7–12% reply rate gain.
- [ ] One honest unresolved failure from the probe library with business-impact assessment.
- [ ] Kill-switch clause: specific trigger metric, threshold, and rollback condition.

### Demo video (max 8 minutes, no login required)

- [ ] Live email conversation end-to-end showing a synthetic prospect receiving a signal-grounded outreach email, replying, getting qualified through the hiring signal brief (Crunchbase funding, job-post velocity, layoffs.fyi, leadership changes, AI-maturity score), and having a discovery call booked via Cal.com.
- [ ] Show the hiring signal brief and competitor gap brief being generated for the prospect, with **per-signal confidence scores visible**.
- [ ] Show HubSpot contact record populating in real time with all fields non-null and enrichment timestamp current.
- [ ] Show an SMS scheduling interaction for a warm lead who has already replied by email (**demonstrating email-to-SMS channel handoff**).
- [ ] Show the agent correctly **refusing to over-claim** when a hiring signal is weak (e.g., not asserting "aggressive hiring" when fewer than five open roles exist).
- [ ] Show the agent correctly handling a prospect whose signals place them in a **different ICP segment than naive classification would suggest** (e.g., a post-layoff company that also recently raised funding → Segment 2, not Segment 1).
- [ ] Show τ²-Bench harness producing a score with query trace visible.
- [ ] Brief walkthrough of probe library and how at least one probe led to a **concrete fix** in the mechanism.
- [ ] **Bonus**: one real voice call end-to-end through the Shared Voice Rig, if completed.

### Evidence graph integrity

- [ ] **Every numeric claim in `memo.pdf` maps to**:
  - A trace file, OR
  - A Tenacious-provided number (`seed/bench_summary.json`, historical conversion rates in `seed/baseline_numbers.md`), OR
  - A public source URL.
- [ ] No fabricated Tenacious numbers anywhere.

## Grading observables

| Observable | Check |
|---|---|
| **Reproduction fidelity** | Pinned τ²-Bench retail reproduction within 95% CI |
| **Probe originality** | Tenacious-specific probes dominate the library |
| **Mechanism attribution** | Delta A positive with p < 0.05 |
| **Cost-quality Pareto** | Cost per qualified lead (not per message) under $5 target; penalty above $8 |
| **Evidence-graph integrity** | Every claim maps to source; no fabricated Tenacious numbers |
| **Skeptic's-appendix quality** | Tenacious-specific risks (brand, bench, offshore-perception), not generic |

## Final readiness check (24h before submission)

Run `make final_check`:

- [ ] `infra/smoke_test.sh` all green.
- [ ] `eval/score_log.json` contains the final method + baselines with 95% CIs.
- [ ] `method/ablation_results.json` present with all three variants and GEPA comparison.
- [ ] `memo/memo.pdf` is exactly 2 pages (page-count check).
- [ ] `memo/evidence_graph.json` has no `source_type: null` entries.
- [ ] No `.env` or secret file in the committed tree.
- [ ] No `X-Tenacious-Status: draft` header missing in the last 50 outbound drafts.
- [ ] Demo video uploaded and link confirmed public.
