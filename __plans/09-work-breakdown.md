# 09 — Cross-Phase Work Breakdown

## Purpose

A flat index of every tractable engineering task across the project, grouped by system area rather than phase. Use this view when allocating a half-day to a specific system area, when deciding what to parallelize, or when checking whether a cross-cutting concern (tracing, kill-switch, tone) has been handled everywhere it needs to be.

Each entry cites its owning plan and its spec anchor.

## A. Configuration, secrets, and kill switch

| # | Task | Plan | Spec |
|---|---|---|---|
| A1 | Author `.env.example` and `config.example.yaml` | — (already in specs) | [18](../__specs/18-configuration.md) |
| A2 | Implement `agent/config.py` with placeholder resolution from seed files | [03](03-act2-production-stack.md) | [18](../__specs/18-configuration.md) |
| A3 | Implement `agent/kill_switch.py` with `deliver()` as the only outbound path | [03](03-act2-production-stack.md) | [16](../__specs/16-data-handling-and-kill-switch.md) |
| A4 | CI grep check: provider SDK imports only in `kill_switch.py` and channel adapters | [03](03-act2-production-stack.md) | [16](../__specs/16-data-handling-and-kill-switch.md) |
| A5 | Runtime assertion: recipient is sink or synthetic | [03](03-act2-production-stack.md) | [16](../__specs/16-data-handling-and-kill-switch.md) |
| A6 | Runtime assertion: HubSpot portal ID is Developer Sandbox | [03](03-act2-production-stack.md) | [08](../__specs/08-hubspot-integration.md) |
| A7 | `infra/smoke_test.sh` with five green checks | [01](01-preflight.md) | [17](../__specs/17-deliverables-checklist.md) |
| A8 | `scripts/audit_week.py` — Langfuse-trace policy audit | [01](01-preflight.md), [04](04-interim-submission.md) | [16](../__specs/16-data-handling-and-kill-switch.md) |

## B. Data sources and enrichment

| # | Task | Plan | Spec |
|---|---|---|---|
| B1 | Download Crunchbase ODM sample to `data/` | [01](01-preflight.md) | [04](../__specs/04-data-sources.md) |
| B2 | Download layoffs.fyi CSV to `data/` | [01](01-preflight.md) | [04](../__specs/04-data-sources.md) |
| B3 | Obtain April-2026 job-post snapshot | [01](01-preflight.md) | [04](../__specs/04-data-sources.md) |
| B4 | `agent/enrichment/crunchbase.py` | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |
| B5 | `agent/enrichment/layoffs.py` | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |
| B6 | `agent/enrichment/jobposts.py` (Playwright + rate limiter + counter) | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md), [16](../__specs/16-data-handling-and-kill-switch.md) |
| B7 | `agent/enrichment/leadership.py` | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |
| B8 | `agent/enrichment/ai_maturity.py` | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |
| B9 | `agent/enrichment/tech_stack.py` | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |
| B10 | `agent/enrichment/competitor_gap.py` | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |
| B11 | `agent/enrichment/pipeline.py` orchestrator | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |
| B12 | Pydantic `HiringSignalBrief` and `CompetitorGapBrief` models + schema test | [03](03-act2-production-stack.md) | [05](../__specs/05-signal-enrichment-pipeline.md) |

## C. Agent core

| # | Task | Plan | Spec |
|---|---|---|---|
| C1 | `agent/classifier.py` rule-based with sub-signal LLM calls | [03](03-act2-production-stack.md) | [03](../__specs/03-icp-and-segments.md), [06](../__specs/06-agent-design.md) |
| C2 | Composer prompts (5 + abstain) | [03](03-act2-production-stack.md) | [06](../__specs/06-agent-design.md) |
| C3 | `agent/composer.py` with deterministic post-checks | [03](03-act2-production-stack.md) | [06](../__specs/06-agent-design.md) |
| C4 | `agent/tone_check.py` second-pass LLM scorer | [03](03-act2-production-stack.md) | [06](../__specs/06-agent-design.md) |
| C5 | Reply classifier and per-class responders | [03](03-act2-production-stack.md) | [06](../__specs/06-agent-design.md) |
| C6 | `agent/handoff.py` with the five conditions | [03](03-act2-production-stack.md) | [06](../__specs/06-agent-design.md) |
| C7 | Multi-thread isolation by prospect email | [03](03-act2-production-stack.md) | [06](../__specs/06-agent-design.md) |

## D. Channels

| # | Task | Plan | Spec |
|---|---|---|---|
| D1 | Email Jinja templates (8) | [03](03-act2-production-stack.md) | [07](../__specs/07-channels.md) |
| D2 | `agent/channels/email/send.py` (Resend + MailerSend) | [03](03-act2-production-stack.md) | [07](../__specs/07-channels.md) |
| D3 | `agent/channels/email/webhook.py` FastAPI endpoint | [03](03-act2-production-stack.md) | [07](../__specs/07-channels.md) |
| D4 | SMS `send.py` + `webhook.py` (Africa's Talking) | [03](03-act2-production-stack.md) | [07](../__specs/07-channels.md) |
| D5 | Voice `send.py` + `webhook.py` stubs (bonus) | [03](03-act2-production-stack.md) | [07](../__specs/07-channels.md) |
| D6 | Cold 3-email termination rules | [03](03-act2-production-stack.md) | [07](../__specs/07-channels.md) |
| D7 | Re-engagement state machine | [03](03-act2-production-stack.md) | [07](../__specs/07-channels.md) |

## E. HubSpot and Cal.com

| # | Task | Plan | Spec |
|---|---|---|---|
| E1 | `agent/hubspot/schema.py` creates `tenacious_*` properties | [03](03-act2-production-stack.md) | [08](../__specs/08-hubspot-integration.md) |
| E2 | `agent/hubspot/client.py` MCP wrapper + rate limiter | [03](03-act2-production-stack.md) | [08](../__specs/08-hubspot-integration.md) |
| E3 | `agent/hubspot/events.py` conversation-event writers | [03](03-act2-production-stack.md) | [08](../__specs/08-hubspot-integration.md) |
| E4 | Cal.com event types (`discovery-15`, `discovery-30`) | [01](01-preflight.md) | [09](../__specs/09-calendar-booking.md) |
| E5 | `agent/calendar/client.py` REST wrapper | [03](03-act2-production-stack.md) | [09](../__specs/09-calendar-booking.md) |
| E6 | `agent/calendar/webhook.py` booking handler | [03](03-act2-production-stack.md) | [09](../__specs/09-calendar-booking.md) |
| E7 | Discovery-call context-brief synthesizer | [03](03-act2-production-stack.md) | [09](../__specs/09-calendar-booking.md) |
| E8 | Time-zone resolver + DST-aware slot proposer | [03](03-act2-production-stack.md) | [09](../__specs/09-calendar-booking.md) |

## F. Observability

| # | Task | Plan | Spec |
|---|---|---|---|
| F1 | `agent/observability/langfuse.py` span helpers | [03](03-act2-production-stack.md) | [10](../__specs/10-observability.md) |
| F2 | `agent/observability/cost.py` per-span cost computation | [03](03-act2-production-stack.md) | [10](../__specs/10-observability.md) |
| F3 | Allowed-attribute filtering on export | [03](03-act2-production-stack.md) | [10](../__specs/10-observability.md) |
| F4 | Evidence-graph export from traces | [07](07-act5-memo-demo.md) | [10](../__specs/10-observability.md) |

## G. τ²-Bench harness

| # | Task | Plan | Spec |
|---|---|---|---|
| G1 | Clone tau2-bench at pinned SHA | [01](01-preflight.md) | [11](../__specs/11-tau2-bench-harness.md) |
| G2 | `eval/harness.py` with dual-guard sealed access | [02](02-act1-tau2-baseline.md) | [11](../__specs/11-tau2-bench-harness.md) |
| G3 | Act I baseline run (5 trials × 30 tasks) | [02](02-act1-tau2-baseline.md) | [11](../__specs/11-tau2-bench-harness.md) |
| G4 | `score_log.json`, `trace_log.jsonl`, `baseline.md` | [02](02-act1-tau2-baseline.md) | [11](../__specs/11-tau2-bench-harness.md) |
| G5 | Act IV sealed run (3 variants × 20 tasks × 5 trials) | [06](06-act4-mechanism.md) | [11](../__specs/11-tau2-bench-harness.md) |

## H. Probes (Act III)

| # | Task | Plan | Spec |
|---|---|---|---|
| H1 | Author 30+ probe YAML entries across 11 categories | [05](05-act3-probes.md) | [12](../__specs/12-probe-library.md) |
| H2 | `probes/run_probes.py` harness | [05](05-act3-probes.md) | [12](../__specs/12-probe-library.md) |
| H3 | `probes/failure_taxonomy.md` with trigger rates | [05](05-act3-probes.md) | [12](../__specs/12-probe-library.md) |
| H4 | `probes/target_failure_mode.md` with business-cost derivation | [05](05-act3-probes.md) | [12](../__specs/12-probe-library.md) |
| H5 | Kill-switch-bypass probe zero-trigger-rate verification | [05](05-act3-probes.md) | [12](../__specs/12-probe-library.md), [16](../__specs/16-data-handling-and-kill-switch.md) |

## I. Mechanism (Act IV)

| # | Task | Plan | Spec |
|---|---|---|---|
| I1 | Design mechanism (pick one direction) | [06](06-act4-mechanism.md) | [13](../__specs/13-mechanism-design.md) |
| I2 | Implement three ablation variants (A/B/C) | [06](06-act4-mechanism.md) | [13](../__specs/13-mechanism-design.md) |
| I3 | GEPA or AutoAgent automated-optimization baseline | [06](06-act4-mechanism.md) | [13](../__specs/13-mechanism-design.md) |
| I4 | `method/method.md` with rationale and ablations | [06](06-act4-mechanism.md) | [13](../__specs/13-mechanism-design.md) |
| I5 | `method/ablation_results.json` | [06](06-act4-mechanism.md) | [13](../__specs/13-mechanism-design.md) |
| I6 | `method/held_out_traces.jsonl` | [06](06-act4-mechanism.md) | [13](../__specs/13-mechanism-design.md) |
| I7 | Paired-bootstrap statistical test, p < 0.05 | [06](06-act4-mechanism.md) | [13](../__specs/13-mechanism-design.md) |

## J. Memo and demo (Act V)

| # | Task | Plan | Spec |
|---|---|---|---|
| J1 | `memo/invoice_summary.json` | [07](07-act5-memo-demo.md) | [14](../__specs/14-memo-specification.md) |
| J2 | `memo/memo.md` Page 1 — The Decision | [07](07-act5-memo-demo.md) | [14](../__specs/14-memo-specification.md) |
| J3 | `memo/memo.md` Page 2 — The Skeptic's Appendix | [07](07-act5-memo-demo.md) | [14](../__specs/14-memo-specification.md) |
| J4 | Render `memo.pdf` with strict 2-page check | [07](07-act5-memo-demo.md) | [14](../__specs/14-memo-specification.md) |
| J5 | `memo/evidence_graph.json` (no null source_type) | [07](07-act5-memo-demo.md) | [14](../__specs/14-memo-specification.md) |
| J6 | `memo/README_for_inheritor.md` | [07](07-act5-memo-demo.md) | [14](../__specs/14-memo-specification.md) |
| J7 | Demo video (≤8 minutes, all 11 storyboard segments) | [07](07-act5-memo-demo.md) | [17](../__specs/17-deliverables-checklist.md) |

## K. Submission packaging

| # | Task | Plan | Spec |
|---|---|---|---|
| K1 | Interim: PDF + screenshots + public repo | [04](04-interim-submission.md) | [17](../__specs/17-deliverables-checklist.md) |
| K2 | Interim: 20-interaction latency harvest | [03](03-act2-production-stack.md), [04](04-interim-submission.md) | [17](../__specs/17-deliverables-checklist.md) |
| K3 | Final: `probes/`, `method/`, `memo/`, demo video, final-submission tag | [07](07-act5-memo-demo.md) | [17](../__specs/17-deliverables-checklist.md) |

## L. Stretch (distinguished-tier)

| # | Task | Plan | Spec |
|---|---|---|---|
| L1 | `market_space/score_population.py` — score all 1001 companies | [08](08-stretch-market-space.md) | [15](../__specs/15-market-space-map.md) |
| L2 | Hand-labeled 30–50-row validation sample | [08](08-stretch-market-space.md) | [15](../__specs/15-market-space-map.md) |
| L3 | Precision/recall per readiness band | [08](08-stretch-market-space.md) | [15](../__specs/15-market-space-map.md) |
| L4 | Top-cells recommendations with bench-match gating | [08](08-stretch-market-space.md) | [15](../__specs/15-market-space-map.md) |

## Parallelization

Tasks that can run in parallel given adequate hands:

- A (config + kill switch) → unblocks B, C, D, E, F; the single highest-leverage opening item.
- B (enrichment) in parallel with D (channels) — both depend on A.
- G (τ²-Bench harness) in parallel with B, C, D — independent code paths.
- H (probes) must follow C, D, E running.
- I (mechanism) follows H; runs sequentially because it burns eval budget.
- J (memo) follows I.
- L (stretch) branches from B11/B12 output but must **not** displace J.

## What this WBS does NOT cover

- Decision-level trade-offs — those live in [`00-decisions.md`](00-decisions.md).
- Risk mitigations — those live in [`10-risks.md`](10-risks.md).
- Per-phase task detail — those live in plans `01`–`08`.
