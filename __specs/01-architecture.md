# 01 — Architecture

## High-level diagram

```
                        ┌───────────────────────────┐
                        │   Crunchbase ODM (frozen) │
                        │   layoffs.fyi (CSV)       │
                        │   Public job posts        │
                        │   (Playwright, ≤200/wk)   │
                        └───────────┬───────────────┘
                                    │
                                    ▼
             ┌──────────────────────────────────────────────┐
             │       Signal-Enrichment Pipeline             │
             │  firmographics → hiring velocity → layoffs   │
             │  → leadership → AI-maturity → tech stack     │
             │  → bench-to-brief match                      │
             └───────────────┬──────────────────────────────┘
                             │ hiring_signal_brief.json
                             │ competitor_gap_brief.json
                             ▼
                   ┌────────────────────┐
                   │   The Agent        │
                   │                    │
                   │  • ICP classifier  │
                   │    (abstains)      │
                   │  • Tone-aware      │
                   │    composer        │
                   │  • Reply handler   │
                   │  • Handoff gate    │
                   └────────┬───────────┘
                            │ every draft
                            ▼
           ┌───────────────────────────────────────┐
           │  Kill-Switch Gate (policy/16)         │
           │  TENACIOUS_OUTBOUND_ENABLED?          │
           │  unset → staff sink                   │
           │  set   → real sender                  │
           └──┬─────────────────┬────────────────┬─┘
              ▼                 ▼                ▼
        ┌──────────┐     ┌─────────────┐    ┌──────────────┐
        │  Email   │     │    SMS      │    │    Voice     │
        │ Resend / │     │  Africa's   │    │  Shared      │
        │MailerSend│     │  Talking    │    │  Voice Rig   │
        └────┬─────┘     └─────┬───────┘    └──────┬───────┘
             │webhook           │webhook           │webhook
             ▼                  ▼                  ▼
        ┌──────────────────────────────────────────────────┐
        │         Inbound Reply Handler (FastAPI)          │
        │  classify → route → HubSpot write → Langfuse     │
        └───────────────────────┬──────────────────────────┘
                                │
                                ▼
                     ┌────────────────────┐       ┌────────────────┐
                     │  HubSpot MCP       │◄──────│   Cal.com      │
                     │  (every event)     │       │   (self-host)  │
                     └────────────────────┘       └────────────────┘

                     ┌──────────────────────────┐
                     │  Langfuse (cloud)        │◄─── every LLM call,
                     │  traces, costs, latency  │     tool call, decision
                     └──────────────────────────┘

                     ┌──────────────────────────┐
                     │  τ²-Bench Harness (eval) │──── pinned dev-tier
                     │  retail domain baseline  │     & eval-tier models
                     └──────────────────────────┘
```

## Components

### 1. Signal-enrichment pipeline

A synchronous DAG that, given a Crunchbase domain, produces two briefs and writes them to disk (`eval/briefs/<domain>/`) and to the HubSpot contact record. Runs **before** the first outreach. See [spec 05](05-signal-enrichment-pipeline.md).

### 2. The agent

A single LangGraph / PydanticAI / custom-loop agent (choice is implementation-level; the spec is model- and framework-agnostic) with four capabilities:

- **ICP classifier** — assigns a segment in {1, 2, 3, 4, `abstain`} with a confidence score.
- **Composer** — drafts subject + body per segment and per signal brief, in the five tone markers, within the 120-word cold-email cap.
- **Reply classifier and responder** — classifies inbound reply in {engaged, curious, hard_no, soft_defer, objection} and composes the response.
- **Handoff gate** — routes to human (delivery lead) on any of five conditions (pricing outside band, staffing specificity, named reference request, regulatory language, C-level at 2000+ headcount).

### 3. Kill-switch gate

A single function `deliver(channel, to, payload)` sits between every composer and every real sender. It consults `TENACIOUS_OUTBOUND_ENABLED`; when unset (the default), it rewrites `to` to the program-operated sink. There is **no other code path** from agent to sender. See [spec 16](16-data-handling-and-kill-switch.md).

### 4. Channel senders

- **Email** via Resend or MailerSend free tier (free, no credit card). Primary channel. See [spec 07](07-channels.md).
- **SMS** via Africa's Talking sandbox. Used only for warm-lead scheduling coordination.
- **Voice** (bonus) via the program-operated Shared Voice Rig.

Each sender is isolated behind a narrow interface; the rest of the system does not know which provider is in use.

### 5. Inbound reply handler

A FastAPI service exposing three webhook endpoints (`/webhook/email`, `/webhook/sms`, `/webhook/voice`). Each:

1. Verifies the webhook signature against the provider secret.
2. Normalizes the payload to a canonical `InboundMessage` record.
3. Calls the agent's reply classifier.
4. Writes a conversation event to HubSpot via MCP.
5. Emits a Langfuse trace with cost and latency attribution.
6. If the agent decides to reply, enqueues the outbound via the kill-switch gate.

### 6. HubSpot integration

HubSpot Developer Sandbox with the MCP server installed. The agent (or its tools) writes on every conversation event: contact create/update, note with the briefs attached, task for human handoff, deal object on booking. See [spec 08](08-hubspot-integration.md).

### 7. Cal.com booking

Self-hosted via `docker compose up` from `infra/docker-compose.yml`. Calendar fixtures are program-provided. Cal.com webhooks notify the agent on booking; the agent posts a discovery-call context brief to the calendar event. See [spec 09](09-calendar-booking.md).

### 8. Observability

Langfuse cloud free tier. Every LLM call, tool call, and routing decision emits a span; costs are attributed per-trace; p50/p95 latency is computed from trace timestamps. See [spec 10](10-observability.md).

### 9. τ²-Bench harness

A clone of `github.com/sierra-research/tau2-bench` run against the retail domain with the pinned dev-tier model for Acts I and II, and the eval-tier model for Act IV's sealed held-out partition only. See [spec 11](11-tau2-bench-harness.md).

## Request flow — outbound cold email

```
1. Enrichment pipeline materializes hiring_signal_brief.json + competitor_gap_brief.json
   for prospect.
2. Agent.classify(brief) → segment + confidence.
   - if confidence < threshold → abstain → generic exploratory email path.
3. Agent.compose(segment, briefs) → draft {subject, body, html}.
4. Agent.tone_check(draft) → score per marker.
   - if score < threshold on any marker → regenerate once; if still low → flag for human.
5. deliver("email", prospect.email, draft) → kill-switch gate.
   - TENACIOUS_OUTBOUND_ENABLED unset → to = staff sink.
   - enabled → to = prospect.email.
6. Provider API call → message_id.
7. HubSpot MCP: upsert contact, create engagement (EMAIL), attach briefs.
8. Langfuse: emit trace with cost attribution.
```

## Request flow — inbound reply

```
1. Provider webhook → /webhook/email.
2. Signature verify. If fails → 401, log.
3. Parse → InboundMessage { thread_id, from, subject, body, received_at }.
4. Agent.classify_reply(body) → {engaged|curious|hard_no|soft_defer|objection|ambiguous}.
5. If ambiguous → route to human (no agent reply).
6. If hard_no → HubSpot set outreach_status=opted_out, add to suppression list, no reply.
7. Otherwise → Agent.respond() → draft → tone_check → deliver() (kill-switch gate).
8. If draft contains Cal link → HubSpot create task, attach discovery-call context brief.
9. HubSpot upsert engagement.
10. Langfuse trace.
```

## Deployment

- **Language**: Python 3.11+.
- **Process topology (local dev)**: Cal.com (docker-compose), FastAPI inbound handler (uvicorn), single-process agent loop. No Redis, no Postgres, no orchestrator — complexity only on genuine need.
- **Process topology (if extended)**: FastAPI can be fronted by `ngrok` or Cloudflare Tunnel to expose local webhooks during development.
- **Secrets**: `.env` (never committed). See [spec 18](18-configuration.md) and `.env.example`.
- **Packaging**: `agent/requirements.txt` pins every dep.

## Non-architectural decisions deferred to implementation

These are not spec-level choices; the implementing engineer picks:

- LangGraph vs. PydanticAI vs. a hand-rolled state machine.
- Thread ID key — synthetic UUID vs. prospect_email as composite key. (Whatever is chosen must survive multi-thread leakage probing — see [spec 12](12-probe-library.md).)
- FastAPI middleware stack, logging format.
- `.env` loader (`python-dotenv`, `pydantic-settings`, etc.).
