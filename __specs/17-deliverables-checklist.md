# 17 — Deliverables Checklist

**Source:** Challenge document — "Deliverables" (Interim + Final), "Evidence-Graph Grading".

---

## Section A — Interim Submission

> **Deadline: Wednesday 22 April 2026, 21:00 UTC.**
> **TODAY. All items below must land before 21:00 UTC.**

**Submission format:** GitHub repo (public link) **+** PDF report (public Google Drive link).

### A.1 Repo — required at root

- [ ] `README.md` — architecture diagram + setup + requirements + **kill-switch documentation** ([16 §4](16-data-handling-and-kill-switch.md))
- [ ] `.env.example` — all env vars listed ([.env.example](.env.example))
- [ ] `config.example.yaml` — application tunables ([config.example.yaml](config.example.yaml))

### A.2 `agent/` directory

- [ ] All agent source files
- [ ] Email handler (Resend **or** MailerSend integration) — [07 §2](07-channels.md)
- [ ] SMS handler (Africa's Talking for warm-lead scheduling) — [07 §3](07-channels.md)
- [ ] HubSpot MCP integration — [08](08-hubspot-integration.md)
- [ ] Cal.com booking flow — [09](09-calendar-booking.md)
- [ ] Enrichment pipeline — [05](05-signal-enrichment-pipeline.md)
- [ ] `requirements.txt` (or `pyproject.toml`)

### A.3 `eval/` directory

- [ ] τ²-Bench harness source — [11](11-tau2-bench-harness.md)
- [ ] `score_log.json` with at least:
  - Act I dev-tier baseline with 95 % CI
  - A reproduction check with 95 % CI
- [ ] `trace_log.jsonl` with full τ²-Bench trajectories across all dev trials

### A.4 `baseline.md`

- [ ] ≤ 400 words
- [ ] Covers: what was reproduced, confidence interval, cost per run, unexpected behaviour

### A.5 PDF report (interim)

Public Google Drive link. Required content:

- [ ] Architecture overview and key design decisions (see [01](01-architecture.md))
- [ ] Production stack status — all verified running:
  - Resend **or** MailerSend (email, primary channel)
  - Africa's Talking (SMS, secondary for warm-lead scheduling)
  - HubSpot Developer Sandbox
  - Cal.com
  - Langfuse
- [ ] Enrichment pipeline status — all producing output:
  - Crunchbase ODM firmographics
  - Job-post velocity scraping
  - layoffs.fyi integration
  - Leadership-change detection
  - AI maturity scoring (0–3)
- [ ] Competitor gap brief status: top-quartile comparison pipeline generating `competitor_gap_brief.json` for **≥ 1** test prospect
- [ ] τ²-Bench baseline score and methodology
- [ ] p50/p95 latency from **≥ 20** real email + SMS interactions pulled from trace log ([10 §6](10-observability.md))
- [ ] What is working, what is not, and the plan for the remaining days

### A.6 Minimum end-to-end demonstration

At least one synthetic prospect has flowed COLD → BOOKED:

- [ ] Received an email
- [ ] Replied
- [ ] Got qualified
- [ ] Booked a discovery call
- [ ] Appears in HubSpot with all `convergine_*` properties populated
- [ ] Appears in Cal.com with context brief attached

### A.7 Pre-submission sanity

- [ ] Kill-switch default unset; audit log present
- [ ] All Tenacious-branded outputs carry `draft` marker
- [ ] No real Tenacious prospect data in any file

---

## Section B — Final Submission

> **Deadline: Saturday 25 April 2026, 21:00 UTC.**
> **T+3 days from interim.**

**Submission format:** GitHub repo (public) **+** PDF report (public) **+** Demo video (public, no login).

### B.1 Repo — adds to Wednesday's

#### `probes/` directory

- [ ] `probe_library.md` with **≥ 30** structured probe entries covering all 10 categories — [12 §2](12-probe-library.md)
- [ ] `failure_taxonomy.md` — probes grouped by category with **observed trigger rates**
- [ ] `target_failure_mode.md` — single highest-ROI failure mode, with explicit business-cost derivation in Tenacious terms (referencing ACV, stalled-thread rates, brand-reputation impact)

#### `method/` + `eval/` additions

- [ ] `method/method.md` — mechanism, design rationale, hyperparameters, **3 ablation variants**, statistical test showing Delta A positive at **p < 0.05**
- [ ] `method/ablation_results.json` — pass@1, 95 % CI, cost-per-task, p95 latency for your method + Day-1 baseline + automated-optimization baseline, **all on sealed held-out slice**
- [ ] `method/held_out_traces.jsonl` — raw traces from each of the 3 conditions
- [ ] `memo/evidence_graph.json` — every numeric claim in the memo mapped to source trace id or invoice line item

### B.2 PDF report — `memo/memo.pdf`, **exactly 2 pages, no more no less**

#### Page 1 — The Decision (see [14 §2](14-memo-specification.md))

- [ ] Executive summary in **3 sentences**: what was built, headline number, recommendation
- [ ] τ²-Bench pass@1 results: published reference, Day-1 baseline, your method — all with 95 % CIs, sourced from `held_out_traces.jsonl`
- [ ] Cost per qualified lead derived from rig usage + LLM spend + trace count, sourced from `invoice_summary.json` and `trace_log.jsonl`
- [ ] Speed-to-lead delta: Tenacious manual process (30–40 % stalled) vs. your measured stalled-thread rate
- [ ] Competitive-gap outbound performance: signal-grounded vs. exploratory reply-rate delta, sourced from variant-tagged traces
- [ ] Annualized dollar impact at **3 adoption scenarios** (1 segment, 2 segments, all 4)
- [ ] Pilot scope: one segment, one lead volume, one dollar budget, one measurable success criterion

#### Page 2 — The Skeptic's Appendix (see [14 §3](14-memo-specification.md))

- [ ] **4 failure modes** τ²-Bench does not capture but would appear in a real Tenacious deployment (each with what, why benchmark misses it, what to add, what that costs) — must be Tenacious-specific
- [ ] Public-signal lossiness: false-positive + false-negative modes of AI-maturity scoring (quietly-sophisticated-but-silent vs. loud-but-shallow), agent behaviour, business impact
- [ ] Gap-analysis risks: when top-quartile practice is a bad benchmark (one paragraph per real risk, with an example from your data)
- [ ] Brand-reputation comparison: unit economics of 1 000 emails at 5 % factually-wrong rate
- [ ] **One honest unresolved failure** from Day-4 probe library with business-impact assessment
- [ ] Kill-switch clause: trigger metric + threshold + rollback condition

### B.3 Demo video — **≤ 8 minutes, no login required**

- [ ] Live email conversation end-to-end: signal-grounded outreach → reply → qualification through hiring-signal brief → discovery call booked via Cal.com
- [ ] Hiring signal brief + competitor gap brief generated, **per-signal confidence scores visible**
- [ ] HubSpot contact record populating in real time, all fields non-null, enrichment timestamp current
- [ ] SMS scheduling interaction for a warm lead who has replied by email (email → SMS handoff)
- [ ] Agent **refuses to over-claim** when a hiring signal is weak (e.g., not asserting "aggressive hiring" when fewer than 5 open roles exist)
- [ ] Agent **correctly handles** a prospect whose signals place them in a different ICP segment than a naive classification would suggest (e.g., post-layoff company that also recently raised)
- [ ] τ²-Bench harness producing a score with query trace visible
- [ ] Walkthrough of probe library + how **at least one probe led to a concrete fix**
- [ ] **Bonus:** one real voice call end-to-end through the Shared Voice Rig if completed

---

## Section C — Cross-references to grading observables

| Observable | Primary spec(s) | Required artifacts |
|------------|-----------------|---------------------|
| Reproduction fidelity | [11](11-tau2-bench-harness.md) | `score_log.json`, `trace_log.jsonl`, `baseline.md` |
| Probe originality | [12](12-probe-library.md) | `probe_library.md` with ≥ 30 entries, Tenacious-specific |
| Mechanism attribution | [13](13-mechanism-design.md) | `method.md`, `ablation_results.json`, `held_out_traces.jsonl`, `stat_test.py` output |
| Cost-quality Pareto | [10](10-observability.md), [14](14-memo-specification.md) | `invoice_summary.json`, cost-per-qualified-lead in memo — **target < $5, penalty > $8** |
| Evidence-graph integrity | [14](14-memo-specification.md), [16 §9](16-data-handling-and-kill-switch.md) | `evidence_graph.json`, `scripts/lint_memo.py` passes |
| Skeptic's appendix quality | [14 §3](14-memo-specification.md) | Page 2 of `memo.pdf` — Tenacious-specific risks only |

---

## Section D — Beyond grading

> "The best submission from this week becomes the starting point for a Tenacious pilot. That is the real grade — whether your work is trustworthy enough that the Tenacious CEO is willing to point it at live revenue."

Design choices that favour this outcome:

- Kill-switch default unset and clearly documented.
- Every number in the memo is traceable.
- Bench-gated commitment is non-negotiable.
- Brand-reputation unit economics are explicit and honest.
- Pilot recommendation names **one** segment at a cautious volume with a **30-day** review criterion.

> Find the lead. Ground the conversation. Respect the brand. Ship it.
