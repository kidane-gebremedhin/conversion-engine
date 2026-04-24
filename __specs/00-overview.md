# 00 — Overview

## The client

**Tenacious Consulting and Outsourcing** is a real B2B firm providing talent outsourcing and project-based consulting to technology-driven companies in North America and Europe. Engagement sizes range 3–12 engineers over 6–24 months for outsourcing, and 4 weeks to 4 months for project consulting. The delivery bench operates out of Addis Ababa with a guaranteed 3–5 hour daily time-zone overlap.

## The problem

The Tenacious CEO and CFO describe three linked pains:

1. **Outbound prospecting is manual.** A partner or senior engineer identifies candidate companies through personal network and LinkedIn browsing, with no systematic coverage of the market.
2. **Qualification is inconsistent.** Two prospects with identical firmographics receive very different first messages because outreach applies intuition rather than a repeatable playbook.
3. **Follow-up is slow.** Once a prospect replies, the person who initiated handles the thread personally — queued behind delivery work and losing momentum.

The revenue consequence is a long tail of conversations that stall not because the prospect said no but because Tenacious did not keep up. The Tenacious CFO estimates **30–40% of qualified conversations stall in the first two weeks** (per `seed/baseline_numbers.md`).

## The system

An agent that does five things, in order:

1. **Finds** prospective companies from public data (Crunchbase ODM, layoffs.fyi, public job posts).
2. **Qualifies** them against a real intent signal (the hiring signal brief + AI-maturity score + bench-to-brief match).
3. **Grounds** the conversation in a research finding, not a vendor pitch (the competitor gap brief).
4. **Runs a nurture sequence** via email (primary), SMS (warm scheduling), and voice (bonus).
5. **Books a discovery call** with a Tenacious delivery lead, handing off a context brief.

The character of the challenge: the system is **not only a qualifier, it is a researcher**. The most successful output reads as a grounded view of a prospect's AI maturity, a comparison against the top quartile of their sector, and a specific gap worth a thirty-minute conversation. Qualification is the filter; research is the value proposition.

## Scope boundaries

**In scope for the challenge week:**

- Synthetic prospects derived from public Crunchbase / LinkedIn / layoffs.fyi data with fictitious contact details.
- Outbound email and SMS routed through the program-operated sink.
- τ²-Bench retail baseline reproduction on a pinned dev-tier model.
- Adversarial probing, a mechanism over the target failure mode, and a two-page memo.

**Out of scope:**

- Real Tenacious customer data (no CRM exports, real threads, or live deal names).
- Real outbound contact (the kill switch routes every message to the staff sink; flipping it requires program-staff approval).
- Named client references in cold outreach (these require a discovery call and explicit consent).
- Fabricated case studies, pricing bands, or bench counts beyond what the seed files specify.

## The five-act loop

The engineering work decomposes into five acts, with an optional distinguished-tier stretch:

| Act | Goal | Primary deliverable |
|---|---|---|
| **I — Baseline and Ground Truth** | Reproduce τ²-Bench retail baseline on the dev slice with a pinned dev-tier model. | `score_log.json`, `trace_log.jsonl`, `baseline.md` (≤400 words) |
| **II — Production Stack Assembly** | Stand up email + SMS + CRM + calendar + signal-enrichment end-to-end. | One complete synthetic-prospect thread, HubSpot screenshot, Cal.com booking, p50/p95 latency across ≥20 interactions |
| **III — Adversarial Probing** | 30+ Tenacious-specific probes classified by business cost. Identify the highest-ROI failure. | `probe_library.md`, `failure_taxonomy.md`, `target_failure_mode.md` |
| **IV — Mechanism Design** | Original mechanism addressing the target failure mode. Beat Day-1 baseline on sealed held-out with 95% CI separation; honest report vs. GEPA/AutoAgent. | `method.md`, `ablation_results.json`, `held_out_traces.jsonl`, Delta A positive with p<0.05 |
| **V — The Memo** | Two-page decision memo to the Tenacious CEO and CFO. Every number traces to source. | `memo.pdf` (exactly 2 pages), `evidence_graph.json`, `README.md` for the inheriting engineer |
| **Distinguished-tier stretch** | Population-level market-space map applying AI-maturity scoring to the full Crunchbase ODM sample. | `market_space.csv`, `top_cells.md`, `methodology.md` |

## Submission shape

Two submissions:

1. **Interim submission** covers Acts I and II (`README.md`, `agent/`, `eval/`, `baseline.md`, plus a PDF report on architecture, stack status, enrichment status, competitor-gap-brief status, τ²-Bench baseline, p50/p95 latency, working/not-working notes).
2. **Final submission** adds Acts III–V (`probes/`, `method.md`, `ablation_results.json`, `held_out_traces.jsonl`, `evidence_graph.json`, `memo.pdf`) plus a demo video (≤8 min) showing the end-to-end email thread, HubSpot populating in real time, SMS channel handoff, abstention on weak signal, τ²-Bench harness, and the probe-library walkthrough.

The real prize is not the grade. The best submission becomes the starting point for a Tenacious pilot against real prospects, under program-staff oversight, with real commercial consequence. The specs are written for that destination.

## Guiding slogan

> Find the lead. Ground the conversation. Respect the brand. Ship it.
