# Conversion Engine — Spec Index

Production-grade specifications for the **Tenacious Consulting and Outsourcing Conversion Engine**: an automated lead-generation and conversion agent that finds prospects from public data, grounds the conversation in a hiring-signal + competitor-gap brief, runs a nurture sequence, and books discovery calls.

> **Interim submission: Wed 22 Apr 2026, 21:00 UTC — TODAY.**
> **Final submission: Sat 25 Apr 2026, 21:00 UTC.**
> See [17-deliverables-checklist.md](17-deliverables-checklist.md) for scope per deadline.

## Read order

| # | Spec | What it covers |
|---|------|----------------|
| 00 | [overview](00-overview.md) | Vision, scope, non-goals, success criteria |
| 01 | [architecture](01-architecture.md) | Component topology, sequence diagrams |
| 02 | [repo-structure](02-repo-structure.md) | Directory layout, module inventory |
| 03 | [icp-and-segments](03-icp-and-segments.md) | 4 ICP segments, classifier with abstention |
| 04 | [data-sources](04-data-sources.md) | Crunchbase ODM, layoffs.fyi, job posts, τ²-Bench |
| 05 | [signal-enrichment-pipeline](05-signal-enrichment-pipeline.md) | Hiring signal brief, AI maturity score, competitor gap brief |
| 06 | [agent-design](06-agent-design.md) | LLM agent, tools, prompts, state machine |
| 07 | [channels](07-channels.md) | Email (primary), SMS (secondary), voice (bonus) |
| 08 | [hubspot-integration](08-hubspot-integration.md) | CRM data model, MCP client, events |
| 09 | [calendar-booking](09-calendar-booking.md) | Cal.com self-hosted, discovery-call flow |
| 10 | [observability](10-observability.md) | Langfuse traces, cost attribution, invoice_summary |
| 11 | [tau2-bench-harness](11-tau2-bench-harness.md) | Baseline, dev slice, sealed held-out evaluation |
| 12 | [probe-library](12-probe-library.md) | 30+ adversarial probes by category |
| 13 | [mechanism-design](13-mechanism-design.md) | Act IV method + ablations + Delta A/B/C |
| 14 | [memo-specification](14-memo-specification.md) | Exactly-2-page decision memo layout |
| 15 | [market-space-map](15-market-space-map.md) | Distinguished-tier stretch deliverable |
| 16 | [data-handling-and-kill-switch](16-data-handling-and-kill-switch.md) | Policy, synthetic routing, kill-switch |
| 17 | [deliverables-checklist](17-deliverables-checklist.md) | Interim (Wed) + Final (Sat) acceptance criteria |
| 18 | [configuration](18-configuration.md) | Config loading, secret management |

## Configuration templates

- [.env.example](.env.example) — all secrets and external-service configuration
- [config.example.yaml](config.example.yaml) — application-level tunables (thresholds, model pins, rate limits)

## Guiding principles

1. **Find the lead. Ground the conversation. Respect the brand. Ship it.** (Document closing line.)
2. Qualification is the filter; **research is the value proposition**.
3. **Grounded honesty is a brand constraint** — over-claiming is worse than silence.
4. **Email is primary**, SMS is secondary for warm-lead scheduling, voice is a bonus tier.
5. **Every numeric claim in the memo must trace to a file or published source** — fabricated Tenacious numbers are a disqualifying violation.
6. **Default kill-switch = unset** — all outbound routes to the staff sink unless explicitly enabled.

## Traceability

Each spec header carries a **Source:** field pointing to the section of the challenge document it implements. The [17-deliverables-checklist.md](17-deliverables-checklist.md) cross-references every required artifact to the spec that defines it.
