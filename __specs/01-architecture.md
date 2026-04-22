# 01 — Architecture

**Source:** Challenge document — "The Production Stack", "Act II — Production Stack Assembly", "Signal enrichment pipeline".

## 1. Component topology

```
                         ┌──────────────────────────────────────────┐
                         │             Seed Repo (Day 0)            │
                         │  ICP.md  deck.pdf  style_guide.md        │
                         │  pricing.yaml  bench_summary.yaml        │
                         │  email_sequences/  case_studies/         │
                         └────────────────────┬─────────────────────┘
                                              │ (static, read-only)
                                              ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │                      Enrichment Pipeline (batch)                    │
   │                                                                     │
   │  Crunchbase ODM ── funding events ─┐                                │
   │  Playwright  ───── job posts ──────┤                                │
   │  layoffs.fyi CSV ── layoff event ──┼─► signal_enrichment.py         │
   │  press / Crunchbase ── leadership ─┤       │                        │
   │  BuiltWith/Wappalyzer ── stack ────┘       ▼                        │
   │                                     hiring_signal_brief.json        │
   │                                     ai_maturity_score.json          │
   │                                     competitor_gap_brief.json       │
   └─────────────────────────────────────────────┬───────────────────────┘
                                                 │
                                                 ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │                       Agent Orchestrator                            │
   │                                                                     │
   │   State machine: COLD → NURTURE → QUALIFIED → SCHEDULING → BOOKED   │
   │   Tools: draft_email, send_email, send_sms, book_call, log_crm,     │
   │          handoff_human, tone_check, bench_check                     │
   │   LLM: Qwen3-Next-80B-A3B / DeepSeek V3.2 (dev)                     │
   │        Claude Sonnet 4.6 / GPT-5 class (eval only)                  │
   └──────┬──────────────┬────────────────┬──────────────┬────────────┬──┘
          │              │                │              │            │
          ▼              ▼                ▼              ▼            ▼
      Resend       Africa's Talking   HubSpot MCP    Cal.com      Voice Rig
     (email out   (SMS warm-lead)    (contact +     (booking +   (bonus, keyword
      + webhook)                      deal + log)    invite)      prefix)
          │              │                │              │            │
          └──────────────┴──────┬─────────┴──────────────┴────────────┘
                                │
                                ▼
                           Langfuse cloud
                    (trace_log.jsonl + cost attribution)
                                │
                                ▼
                       τ²-Bench Harness
                (dev slice 30, sealed held-out 20)
```

## 2. Runtime layers

| Layer | Primary choice | Fallback | Budget |
|-------|----------------|----------|--------|
| Email (primary) | Resend free 3 000/mo | MailerSend free | $0 |
| SMS (secondary) | Africa's Talking sandbox | — | $0 |
| Voice (bonus) | Tenacious Shared Voice Rig | — | program-hosted |
| CRM | HubSpot Developer Sandbox (MCP, 100 req/10 s) | — | $0 |
| Calendar | Cal.com self-hosted (docker compose) | — | $0 |
| Dev LLM | OpenRouter → Qwen3-Next-80B-A3B **or** DeepSeek V3.2 | — | < $4 (Days 1–4) |
| Eval LLM | Claude Sonnet 4.6 **or** GPT-5 class | — | < $12 (Days 5–7) |
| Enrichment | Playwright + FastAPI wrapper | — | $0 |
| Observability | Langfuse cloud free tier | — | $0 |
| Eval harness | τ²-Bench (retail + telecom) | — | $0 |

Total per-trainee envelope: **< $20 for the week**.

## 3. Key sequence — first outreach to booked call

```
┌─ agent ─┐     ┌ enrich ┐    ┌ resend ┐   ┌ hubspot ┐   ┌ cal.com ┐   ┌ langfuse ┐
   │            │              │            │              │             │
   │ 1. pick    │              │            │              │             │
   │    company │              │            │              │             │
   │───────────►│              │            │              │             │
   │ 2. brief   │              │            │              │             │
   │◄───────────│              │            │              │             │
   │ 3. classify ICP + confidence (+abstain if < threshold)              │
   │ 4. draft email (signal-grounded variant OR generic-explore variant) │
   │ 5. tone_check → regenerate if style-guide drift                     │
   │ 6. bench_check → strip any capacity claims not in bench_summary     │
   │ 7. send_email ──────────────►│            │              │           │
   │                              │ 8. open/click/reply webhook          │
   │◄─────────────────────────────│            │              │           │
   │ 9. log_crm ─────────────────────────────►│              │           │
   │10. classify reply intent (interested / objection / off-topic / stop)│
   │11. if "schedule": compose Cal.com link OR offer SMS handoff        │
   │12. book_call ──────────────────────────────────────────►│           │
   │13. attach context brief (hiring_signal + competitor_gap) to invite │
   │14. emit trace ────────────────────────────────────────────────────►│
   │15. COMPLETE — human delivery lead owns the discovery call.          │
```

## 4. State machine

```
                    (reply: interested + wants call)
     COLD ──┬──► NURTURE_1 ──► NURTURE_2 ──► NURTURE_3 ──► STALE
            │        │              │              │
            │        ▼              ▼              ▼
            │    QUALIFIED ◄────────┴──────────────┘
            │        │
            │        ▼
            │    SCHEDULING ──► BOOKED ──► HANDED_OFF
            │        │
            │        └── (prefers SMS) ──► SMS_SCHEDULING ──► BOOKED
            │
            └──► STOP (unsubscribe / objection) ─► CLOSED_LOST
```

`NURTURE_N` uses the anonymised Tenacious sequences in the seed repo, rewritten by the agent but preserving `style_guide.md` tone markers.

## 5. Durable state

| Store | Contents | Retention |
|-------|----------|-----------|
| HubSpot | `Contact`, `Company`, `Deal`, `Conversation Event` | permanent (sandbox) |
| Postgres (local) | `prospect`, `brief_cache`, `thread_state`, `probe_run`, `trace_ref` | challenge week |
| Langfuse | trace_log.jsonl, token counts, model cost | retained per free-tier TTL |
| Filesystem | `hiring_signal_brief.json`, `competitor_gap_brief.json`, per-prospect | per-run artifact |

## 6. Rate-limit budgets

| Service | Limit | Our usage |
|---------|-------|-----------|
| HubSpot MCP | 100 req / 10 s | < 5 req / prospect ≈ safe at any realistic volume |
| Resend free | 3 000 emails / month | ≤ 60 outbound × 7 days = 420, safe |
| Africa's Talking | sandbox, no hard cap | warm-lead only |
| OpenRouter dev | pay-per-token | rate-cap at 2 concurrent calls |

## 7. Failure-tolerance choices

- **Idempotent outbound**: every email carries an `X-Convergine-Trace-Id`; Resend webhook dedupes replay.
- **Brief cache**: enrichment for a company is cached 24 h; re-run explicit via CLI.
- **Bench check is hard-gated** — if the draft references capacity that `bench_summary.yaml` does not carry, the send is blocked, not rewritten silently.
- **Kill-switch middleware** sits between `send_email` and Resend; default routes to staff sink.

## 8. Cross-references

- Data schemas: [05-signal-enrichment-pipeline.md](05-signal-enrichment-pipeline.md)
- Tools + prompts: [06-agent-design.md](06-agent-design.md)
- Channel implementations: [07-channels.md](07-channels.md)
- Repository layout matching this topology: [02-repo-structure.md](02-repo-structure.md)
