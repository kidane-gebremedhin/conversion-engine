# Conversion Engine — Tenacious Consulting outbound agent

Automated lead-generation + conversion agent for Tenacious Consulting and Outsourcing. Finds companies matching one of four ICP segments, grounds outreach in a verifiable hiring-signal + competitor-gap brief, qualifies over email, and books discovery calls via Cal.com.

**Interim submission scope only** (Acts I + II — see [`__specs/17-deliverables-checklist.md`](__specs/17-deliverables-checklist.md) §A).

## Architecture

```
seed/ + data/          ─►  enrichment pipeline
  (fixtures)                 │
                             ▼
                     hiring_signal_brief.json
                     ai_maturity_score.json
                     competitor_gap_brief.json
                             │
                             ▼
                     ICP classifier (abstention)
                             │
                             ▼
     ┌── policies ─►  orchestrator (state machine)  ◄── webhooks ──┐
     │ tone, bench,        │                                        │
     │ confidence,         ▼                                        │
     │ handoff      channels ─► killswitch (default: sink) ─►  sink / provider
     └───────────────────► integrations                            │
                          (HubSpot, Cal.com)                       │
                             │                                      │
                             ▼                                      │
                       trace_log.jsonl  + score_log.json             │
                       (eval/ + Langfuse)                            │
```

Full component diagram: [`__specs/01-architecture.md`](__specs/01-architecture.md).

State machine: `COLD → NURTURE_{1,2,3} → QUALIFIED → SCHEDULING → BOOKED → HANDED_OFF`, with `STOP` and `HUMAN_HANDOFF` cross-cuts.

## Setup

```
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                          # core deps; add '[live]' for Playwright + Resend SDK + Langfuse
cp .env.example .env                      # fill in keys or leave blank for mock mode
cp config.example.yaml config.yaml        # (already copied on first clone)
make bootstrap                            # seed synthetic prospects + fixture state
make health                               # sanity check
```

Offline/mock mode is the default. The mock LLM client is deterministic (seeded) and drives all prompts without API keys. Set `CONVERGINE_LLM_MODE=live` + `OPENROUTER_API_KEY=...` to switch to real calls.

## Day-0 Pre-flight (external services)

Each step below closes one row of [`__plans/01-d0-to-d3-interim-path.md`](__plans/01-d0-to-d3-interim-path.md) §D0.1. Most are free-tier sandboxes.

### 1. Email — Resend

Decision locked on Resend (O1 in [`__plans/00-decisions.md`](__plans/00-decisions.md)).

1. Sign up at [resend.com](https://resend.com) (free tier: 3 000 emails/month, no credit card).
2. Verify a sandbox domain (or use the onboarding `onresend.dev` sender for smoke tests).
3. Copy the API key into `.env`:
   ```
   RESEND_API_KEY=re_xxx…
   RESEND_FROM_DOMAIN=convergine-sandbox.example.com
   RESEND_FROM_ADDRESS=outbound@convergine-sandbox.example.com
   RESEND_WEBHOOK_SECRET=whsec_xxx…
   ```
4. Register an **inbound-reply webhook** in the Resend dashboard pointing to:
   ```
   {PUBLIC_BASE_URL}/webhooks/email/reply
   ```
   Handler: [`agent/server.py:31`](agent/server.py#L31) → [`agent/channels/email/webhook.py`](agent/channels/email/webhook.py). For local dev, tunnel with `ngrok http 8000` or equivalent, and use the ngrok URL as `PUBLIC_BASE_URL`.
5. Verify: send a test email to yourself and confirm the webhook POSTs with a valid signature.

### 2. CRM — HubSpot Developer Sandbox (via in-repo MCP server)

Decision locked on an in-repo MCP server that wraps Private-App REST (O8). The agent spawns [`agent/integrations/hubspot_mcp_server.py`](agent/integrations/hubspot_mcp_server.py) as a subprocess and speaks stdio MCP to it.

1. Create a HubSpot developer account at [developers.hubspot.com](https://developers.hubspot.com).
2. Inside the developer dashboard, create a **Developer Test Account** (the sandbox).
3. In that sandbox: Settings → Integrations → Private Apps → **Create private app**. Grant scopes:
   - `crm.objects.companies.read` / `.write`
   - `crm.objects.contacts.read` / `.write`
   - `crm.objects.deals.read` / `.write`
   - `crm.schemas.companies.read` / `.write`, same for `contacts` and `deals`
   - `crm.schemas.custom.read` / `.write` + `crm.objects.custom.read` / `.write` (Conversation Event object)
4. Copy the access token into `.env`:
   ```
   HUBSPOT_PRIVATE_APP_TOKEN=pat-na1-xxx…
   # Optional overrides; auto-detect is fine:
   # HUBSPOT_CLIENT_MODE=mcp            # mcp | rest | local
   # HUBSPOT_MCP_URL=http://localhost:4000
   # HUBSPOT_CONVERSATION_EVENT_OBJECT_TYPE=convergine_conversation_event
   ```
5. Provision the sandbox schema (custom properties + custom object; idempotent):
   ```
   python -m scripts.hubspot_bootstrap
   ```
6. Run the D0 smoke test — spawns the MCP server and round-trips a test contact:
   ```
   python -m scripts.hubspot_smoke
   ```
   Success prints `ok — contact_id=<id>`. The smoke test asserts `mode=mcp`.

**Run the MCP server standalone (optional):**
```
python -m agent.integrations.hubspot_mcp_server            # stdio
python -m agent.integrations.hubspot_mcp_server --http     # Streamable HTTP on :4000
```

### 3. SMS — Africa's Talking sandbox

1. Sign up at [africastalking.com](https://africastalking.com), use the **sandbox** app (free).
2. Claim a virtual shortcode + keyword prefix in the sandbox simulator.
3. Set:
   ```
   AFRICASTALKING_USERNAME=sandbox
   AFRICASTALKING_API_KEY=atsk_xxx…
   AFRICASTALKING_SHORTCODE=22222
   AFRICASTALKING_WEBHOOK_SECRET=…
   ```
4. Register the inbound webhook → `{PUBLIC_BASE_URL}/webhooks/sms/inbound` ([`agent/server.py:38`](agent/server.py#L38)).
5. Verify: send a test SMS from the sandbox simulator and watch the webhook hit.

### 4. Calendar — Cal.com (self-hosted)

1. Start Docker (if not already): `sudo systemctl start docker`.
2. Bring up Cal.com + its Postgres:
   ```
   docker compose up -d
   docker compose logs -f calcom      # first boot runs Prisma migrations (~30–90 s)
   ```
3. Verify:
   ```
   curl -s http://localhost:3000 | head -c 200
   ```
4. Complete the web-UI onboarding at <http://localhost:3000> (admin user, 3 event types: `discovery-30`, `demo-45`, `followup-15`).
5. Generate an API key from Cal.com settings, then set:
   ```
   CALCOM_BASE_URL=http://localhost:3000
   CALCOM_API_KEY=cal_live_xxx…
   CALCOM_WEBHOOK_SECRET=…
   ```
6. Register the webhook → `{PUBLIC_BASE_URL}/webhooks/calcom` ([`agent/server.py:44`](agent/server.py#L44)).

### 5. Signal pipeline — Playwright

1. Install live-extras + the chromium browser binary:
   ```
   pip install -e '.[live]'
   playwright install chromium
   ```
2. Fetch one public job listing to prove the stack ([`scripts/fetch_job_sample.py`](scripts/fetch_job_sample.py)):
   ```
   python -m scripts.fetch_job_sample                         # defaults: Stripe's Greenhouse board
   python -m scripts.fetch_job_sample --company vercel        # any public Greenhouse slug
   python -m scripts.fetch_job_sample --url https://…         # arbitrary URL
   ```
   Output: `data/jobposts_samples/<slug>_<timestamp>.json` matching the `JobPost` schema in [`agent/enrichment/jobposts.py:26`](agent/enrichment/jobposts.py#L26).

### 6. Observability — Langfuse

1. Create a cloud project at [cloud.langfuse.com](https://cloud.langfuse.com) (free tier).
2. Generate public + secret keys; set:
   ```
   LANGFUSE_HOST=https://cloud.langfuse.com
   LANGFUSE_PUBLIC_KEY=pk-lf-xxx…
   LANGFUSE_SECRET_KEY=sk-lf-xxx…
   LANGFUSE_PROJECT=convergine-local
   ```
3. Verify one test trace appears in the Langfuse UI after `make health`.

### 7. LLM — OpenRouter

1. Sign up at [openrouter.ai](https://openrouter.ai), generate an API key.
2. Set:
   ```
   OPENROUTER_API_KEY=sk-or-v1-xxx…
   CONVERGINE_LLM_MODE=live
   ```
3. Smoke: `python -m agent.main --healthcheck` — cost captured on Langfuse span.

### 8. Data sources — seed datasets

1. Crunchbase ODM sample — drop the 1 001-record JSON under `data/crunchbase_odm/companies.json`. Source: `luminati-io/Crunchbase-dataset-samples`.
2. Layoffs snapshot — `data/layoffs_fyi/layoffs.csv`.
3. Job-posts snapshot — `data/jobposts_snapshot/<domain>/now.json` + `prior.json` for the early-April 2026 window.
4. τ²-Bench — `git clone sierra-research/tau2-bench` and pin the tag that matches `config.yaml:tau2.version`.

## Interim reproduction

```
make baseline          # τ²-Bench-style dev-slice baseline → eval/score_log.json + trace_log.jsonl
make run-batch N=20    # 20 synthetic prospects → enrichment + outreach traces
make latency           # eval/latency_report.json (p50/p95 over ≥ 20 interactions)
make run PROSPECT=fixture-seg1-strong-signals   # full COLD → BOOKED e2e
```

See [`reports/interim.md`](reports/interim.md) for the written status report.

## Kill-switch

**The kill-switch default is UNSET. All outbound is routed to a local staff sink.** This is required by [`__specs/16-data-handling-and-kill-switch.md`](__specs/16-data-handling-and-kill-switch.md).

### Where it lives

| Surface | Location |
|---------|----------|
| Config flag | `config.yaml` → `killswitch.enabled` (default: `false`) |
| Env var (belt + braces) | `CONVERGINE_ENABLE_REAL_OUTBOUND` (default: `0`) |
| Router implementation | [`agent/integrations/killswitch.py`](agent/integrations/killswitch.py) |
| Audit log | `data/killswitch_audit.jsonl` (append-only, SHA-256 chain) |
| Local sink | `data/sink/email.jsonl`, `data/sink/sms.jsonl` (one record per routed send) |

### Default behaviour (UNSET)

Every `send_email` / `send_sms` call passes through `KillSwitch.route_*`. When `enabled == false`, the recipient is rewritten to `config.killswitch.sink_email` (default `sink+convergine@staff-sandbox.tenacious.invalid`) and the send is persisted to `data/sink/` instead of reaching a real provider. The audit log records both the *intended* and the *routed* recipient, with a running SHA-256 hash for tamper evidence.

### How to enable real outbound

Two conditions must both be true:

1. `config.yaml:killswitch.enabled: true`
2. Environment variable `CONVERGINE_ENABLE_REAL_OUTBOUND=1`

Plus: a signed program-staff acknowledgement, an entry at the bottom of this README naming the flipper, date, scope, and expected volume. Flipping with only one of {flag, env var} aborts boot — see [`agent/config.py:validate`](agent/config.py).

### If a real prospect address ends up in the queue while unset

It is rewritten to the sink and audit-logged. No leak path. The sink JSONL is append-only; a `lint_logs.py` scan runs in CI to catch secret/real-address regressions.

### Flip history

_(empty — no real outbound authorised for this repo.)_

## Repo layout

See [`__specs/02-repo-structure.md`](__specs/02-repo-structure.md). Interim deliverables live under `agent/`, `eval/`, `data/`, `scripts/`, and `reports/`. Acts III–V (`probes/`, `method/`, `memo/`) arrive post-interim.

## Tests / healthcheck

```
python -m agent.main --healthcheck        # config loads, fixtures present, killswitch unset
python -m eval.run_baseline --trials 5    # baseline reproduction
python -m scripts.latency_report          # p50/p95 over trace_log.jsonl
```

## License & data handling

All Tenacious-branded output is marked `draft` in metadata. No real Tenacious customer data in this repo. Synthetic-prospect markers carried on every Contact (`convergine_synthetic = true`). See [`__specs/16-data-handling-and-kill-switch.md`](__specs/16-data-handling-and-kill-switch.md) for the full policy.
