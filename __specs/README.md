# Conversion Engine — Specifications Index

This directory is the engineering specification for the **Conversion Engine** — an automated lead-generation and conversion system for Tenacious Consulting and Outsourcing, built for TRP1 Week 10.

The system finds new prospective clients from public data, qualifies them against a real intent signal, runs a nurture sequence, and books discovery calls with a Tenacious delivery lead. Qualification is the filter; **research is the value proposition**.

## Source of truth

Every specification in this directory derives from, and must remain consistent with, these canonical sources:

1. The TRP1 Week 10 Challenge Brief — *Conversion Engine for Sales Automation*.
2. The *Draft Tenacious Sales Materials Template* — templates for the four internal artifacts the agent produces (delivery bench summary, hiring signal brief, competitor gap brief, discovery call context brief) and the pricing / style / ICP formalizations.
3. The seed materials in `tenacious_sales_data/` (ICP, style guide, baseline numbers, bench summary, case studies, email sequences, discovery transcripts, pricing sheet, sales deck).
4. The policy files in `tenacious_sales_data/policy/` (data handling, acknowledgement) and `LICENSE.md`.
5. The JSON Schemas in `tenacious_sales_data/schemas/`.

If a spec conflicts with a source above, the source wins and the spec must be corrected.

## Reading order

| # | Spec | What it covers |
|---|---|---|
| [00](00-overview.md) | Overview | Problem, goals, five-act loop, scope boundaries |
| [01](01-architecture.md) | Architecture | Components, request/reply flow, deployment |
| [02](02-repo-structure.md) | Repo structure | Directory layout and ownership |
| [03](03-icp-and-segments.md) | ICP and segments | Four fixed segments, classification, abstention |
| [04](04-data-sources.md) | Data sources | Crunchbase ODM, layoffs.fyi, job posts, τ²-Bench |
| [05](05-signal-enrichment-pipeline.md) | Enrichment pipeline | Firmographics → briefs, AI-maturity scoring |
| [06](06-agent-design.md) | Agent design | Composer, reply classifier, honesty constraints, handoff |
| [07](07-channels.md) | Channels | Email (primary), SMS (warm-scheduling), Voice (bonus) |
| [08](08-hubspot-integration.md) | HubSpot | MCP server, schema, every-event writes |
| [09](09-calendar-booking.md) | Cal.com | Self-hosted booking, fixtures, time-zone handling |
| [10](10-observability.md) | Observability | Langfuse traces, per-trace cost, latency |
| [11](11-tau2-bench-harness.md) | τ²-Bench harness | Retail baseline, dev slice, held-out |
| [12](12-probe-library.md) | Probe library | 30+ adversarial probes, categories, target failure |
| [13](13-mechanism-design.md) | Mechanism design | Act IV mechanism, deltas A/B/C |
| [14](14-memo-specification.md) | Memo | Two-page decision memo, evidence graph |
| [15](15-market-space-map.md) | Market-space map | Distinguished-tier stretch deliverable |
| [16](16-data-handling-and-kill-switch.md) | Policy enforcement | Kill-switch, scraping rules, draft marking |
| [17](17-deliverables-checklist.md) | Deliverables | Interim (Acts I–II) and Final (Acts III–V) |
| [18](18-configuration.md) | Configuration | Env vars, YAML config, secrets handling |

Two example artifacts accompany the specs:

- [`.env.example`](.env.example) — every environment variable the system reads, with safe defaults and placeholders.
- [`config.example.yaml`](config.example.yaml) — every operational knob (thresholds, prices, windows, model IDs, base URLs).

## Non-negotiables

These are enforced by spec and by code; violating any is grounds for disqualification from the challenge:

- **Kill switch defaults to unset.** Every outbound routes to the staff sink until `TENACIOUS_OUTBOUND_ENABLED=1` is set deliberately.
- **No real customer contact.** Every prospect the system addresses during the challenge week is synthetic.
- **Grounded or silent.** The agent never asserts a signal it cannot cite; low confidence forces softer language, abstention, or handoff.
- **No bench over-commitment.** The agent never commits capacity that `bench_summary.json` does not show.
- **No fabricated Tenacious numbers.** Every numeric claim in the memo traces to `baseline_numbers.md`, `bench_summary.json`, a trace file, or a cited public source.
- **No hard-coded secrets, base URLs, model IDs, or prices.** Every such value is pulled from environment or YAML config, as defined in [spec 18](18-configuration.md).
- **Draft marking on every Tenacious-branded output.** Emails carry `X-Tenacious-Status: draft`; HubSpot records carry `tenacious_status=draft`.
