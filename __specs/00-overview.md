# 00 — System Overview

**Source:** Challenge document — "Summary", "The Client", "Sales Jargon for Talent Outsourcing", "Beyond grading — the real prize".

## 1. What we are building

An automated lead-generation and conversion agent for **Tenacious Consulting and Outsourcing** (B2B talent outsourcing + project consulting, ~3–12 engineers per engagement, 6–24 month duration, clients in NA + EU). The agent:

1. **Finds** net-new companies from public data that match one of four ICP segments.
2. **Grounds** the first outreach in a verifiable *hiring signal brief* + *competitor gap brief*.
3. **Qualifies** the prospect through email conversation, honouring Tenacious's tone and bench constraints.
4. **Nurtures** with follow-ups and hands off to SMS for warm-lead scheduling when the prospect prefers it.
5. **Books** a discovery call via Cal.com with a human Tenacious delivery lead, attaching a context brief to the calendar invite.

## 2. Why it exists (business problem)

Current Tenacious pain from CEO/CFO interviews:

- **Outbound is manual** — partner/senior-engineer ad-hoc LinkedIn browsing, no systematic coverage.
- **Qualification is inconsistent** — identical firmographics get different first messages.
- **Follow-up is slow** — 30–40 % of qualified conversations stall in the first two weeks.

A reply-rate lift from the 1–3 % baseline to the 7–12 % signal-grounded top-quartile on ~60 thoughtful touches per week per person, multiplied by $240–720 K talent-ACV and $80–300 K consulting-ACV, is the value capture the system targets.

## 3. ICP segments (grading-fixed)

| # | Segment | Primary signal | Pitch register |
|---|---------|----------------|----------------|
| 1 | Recently-funded Series A/B startups | $5–30 M round in last 180 days | "scale faster than in-house hiring supports" / "stand up first AI function" |
| 2 | Mid-market platforms restructuring cost | Layoff in last 120 days, 200–2000 people | "replace higher-cost roles; operational discipline" |
| 3 | Engineering-leadership transitions | New CTO/VP Eng in last 90 days | Narrow vendor-reassessment window |
| 4 | Specialized capability gaps | ML platform / agentic / data-contract build + AI-maturity ≥ 2 | Project-based, higher margin |

Segment names are **fixed** for grading — do not rename. Filter adaptation is allowed; taxonomy is not.

## 4. In scope

- `τ²-Bench` retail reproduction, 30-task dev slice + 20-task sealed held-out.
- Email-primary conversational agent with HubSpot + Cal.com integration.
- Hiring signal brief (funding, job-post velocity, layoffs, leadership change, tech stack, AI maturity 0–3).
- Competitor gap brief (5–10 top-quartile sector peers, AI-maturity distribution, 2–3 specific practice gaps).
- 30+ probe library tailored to Tenacious failure modes.
- One original mechanism (Act IV) with Delta A positive at p < 0.05.
- Evidence-graph-backed 2-page memo addressed to the Tenacious CEO + CFO.

## 5. Non-goals

- Real customer contact data, real CRM exports, live prospect names (explicitly forbidden).
- Voice-heavy architecture ported from the compliance-software challenge — prospects are founders/CTOs/VPs Eng who live in email.
- Fabricated case studies or client logos beyond what the anonymised sales deck contains.
- Quoting pricing beyond the public-tier bands; deeper pricing routes to a human.
- Live crawls beyond 200 companies in the challenge week; use the frozen April 2026 snapshot by default.

## 6. Success definitions

### Interim (Wed 22 Apr 21:00 UTC)
Acts I + II complete: τ²-Bench baseline with 95 % CI on dev slice, full production stack end-to-end on one synthetic prospect (email → reply → qualify → book → HubSpot + Cal.com), enrichment pipeline producing `hiring_signal_brief.json` and `competitor_gap_brief.json` for ≥ 1 test prospect, p50/p95 latency over ≥ 20 synthetic interactions. See [17-deliverables-checklist.md](17-deliverables-checklist.md) §1.

### Final (Sat 25 Apr 21:00 UTC)
All five acts + optional market-space stretch. Delta A positive p < 0.05 on sealed held-out slice, 30+ Tenacious-specific probes, 2-page memo with evidence graph, ≤ 8 min demo video. See [17-deliverables-checklist.md](17-deliverables-checklist.md) §2.

### Beyond grading
Best submission runs a four-week pilot against **real** Tenacious prospects with program-staff oversight. That is the real grade — trustworthy enough that the CEO points it at live revenue.

## 7. Budget envelope

- **Under $20 per trainee for the week**, split roughly: dev-tier LLM < $4 Days 1–4, eval-tier LLM < $12 Days 5–7, rigs free.
- **Cost-per-qualified-lead target < $5**; penalty triggers above $8 without justification.

## 8. Hard guardrails (disqualifying if violated)

- No real Tenacious customer data leaves Tenacious.
- Every interacted-with prospect during the week is synthetic; outbound routes to the staff-controlled sink by default.
- Kill-switch default = **unset** (routes to sink). README documents the flag explicitly.
- All Tenacious-branded output marked `draft` in metadata.
- **Fabricated Tenacious numbers in the memo are disqualifying**, separate from the standard penalty.
