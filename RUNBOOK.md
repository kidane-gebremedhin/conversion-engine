# Runbook — Start-to-Finish Operations Guide

All commands run from the repo root. Four terminals recommended.

| Terminal | Process | Command | Lifetime |
|---|---|---|---|
| A | Cal.com + Postgres | `docker compose -f infra/docker-compose.yml up -d` | long-lived |
| B | Webhook tunnel | `ngrok http 8000` | long-lived |
| C | FastAPI server | `make server` | long-lived |
| D | Ad-hoc runs | `make enrich …`, `make compose-and-send …`, etc. | short-lived |

> HubSpot MCP is **not** a separate daemon — the Python agent spawns it over stdio per-process.

---

## 0. One-Time Setup

```bash
# Install Python deps and scaffold config
make setup

# Fill in all required credentials
vi .env

# Policy acknowledgement (smoke test requires this)
make ack

# Global installs (host-level, once)
npm install -g @hubspot/mcp-server
```

Verify prerequisites:
```bash
node --version          # v18+
docker --version
```

---

## 1. Start Cal.com (Terminal A)

```bash
# First boot: create secrets file
cp infra/.env.calcom.example infra/.env.calcom
# Edit infra/.env.calcom — fill in:
#   NEXTAUTH_SECRET=$(openssl rand -base64 32)
#   CALENDSO_ENCRYPTION_KEY=$(openssl rand -hex 16)
#   CRON_API_KEY=$(openssl rand -base64 32)

# Start
docker compose -f infra/docker-compose.yml up -d

# Watch until ready
docker compose -f infra/docker-compose.yml logs -f calcom
# Ready when: "ready - started server on 0.0.0.0:3000"
```

**First boot only:** Open http://localhost:3000, create admin account, then create two event types:
- `discovery-15` (15 min)
- `discovery-30` (30 min)

Copy the API key from Settings → Developer into `.env`:
```
CALCOM_API_KEY=cal_live_...
CALCOM_USERNAME=<your-username>
```

Verify:
```bash
make day0-calcom
# ✓ booked: id=bk-...
```

---

## 2. Start Webhook Tunnel (Terminal B)

```bash
# Option 1: ngrok
ngrok http 8000 --domain=<your-subdomain>.ngrok.app

# Option 2: Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```

Copy the public URL and update `.env`:
```
RESEND_WEBHOOK_URL=https://<your-url>/webhook/email
AT_WEBHOOK_URL=https://<your-url>/webhook/sms
CALCOM_WEBHOOK_URL=https://<your-url>/webhook/cal
```

Register webhooks at each provider:
- **Resend** → Webhooks → `email.bounced`, `email.replied`; copy signing secret → `RESEND_WEBHOOK_SECRET`
- **Africa's Talking** → SMS → Callback URLs → delivery + incoming
- **Cal.com** → Settings → Developer → Webhooks → `BOOKING_CREATED`; secret → `CALCOM_WEBHOOK_SECRET`

---

## 3. Start FastAPI (Terminal C)

```bash
make server
# uvicorn on http://0.0.0.0:8000
```

Verify:
```bash
curl -s localhost:8000/health | jq
# { "ok": true, "kill_switch": "sink", ... }
```

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Kill-switch state + timestamp |
| POST | `/webhook/email` | Resend reply inbound |
| POST | `/webhook/sms` | Africa's Talking inbound |
| POST | `/webhook/voice` | Voice stub |
| POST | `/webhook/cal` | Cal.com `booking.created` |

---

## 4. Langfuse (Cloud — No Daemon)

Just set keys in `.env`:
```
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PROJECT_ID=<uuid>
```
When keys are absent, traces go to `data/local_traces.jsonl` (works for dev, not for memo evidence).

---

## 5. Verify Everything

```bash
make smoke
# ✓ Policy acknowledgement filed
# ✓ Kill switch TENACIOUS_OUTBOUND_ENABLED is unset
# ✓ Synthetic prospects fixture present (25 entries)
# ✓ Email deliver() routes to sink
# ✓ SMS deliver() routes to sink
# ✓ HubSpot client reachable (mode=mcp)
# ✓ Cal.com client reachable
# ✓ Langfuse reachable
```

---

## 6. Day-to-Day Operations

### Enrich a prospect
```bash
make enrich DOMAIN=delamode-group.com
# Writes briefs to eval/briefs/delamode-group.com/
```

### End-to-end email send (kill-switch gated)
```bash
make compose-and-send DOMAIN=delamode-group.com
# Enrich → compose → tone-check → deliver to sink → HubSpot write
```

### Available prospect domains

Use any of these with `DOMAIN=`:

```
delamode-group.com         conshohockenbrewing.com     whitehilltech.com
connempathy.com            consolidatedparts.com       alliancehospice.com
americraftmfg.com          fivestarcarting.com          comax.coop
windowclassics.com         wiringtech.com               ameriskengineering.com
hang.de                    cius.co.uk                   alphaballscrew.com
alpine-collision.com       connecttv.se                 tuffgirl.com
riverpointpgh.com          cavendishfoods.co.uk         syma-tech.de
sycamorehillcapital.com    conseil-telecom.net          c-i-ltd.co.uk
americanmetalroofs.com
```

_(Full list: `data/synthetic_prospects.json`)_

### Other commands
```bash
make tau2-baseline                        # τ²-Bench dev-slice baseline
make probes                               # run probe library
make probes P=P-0001                      # single probe
make memo                                 # render 2-page memo.pdf
make test                                 # pytest suite
make lint                                 # ruff
make audit                                # weekly policy audit
make final-check                          # pre-submission gauntlet
```

---

## 7. Demo Video — Step-by-Step Script

> Follow these steps in order to record the ≤8-minute demo video. All services must be running (§1–4 above). Run `make smoke` first.

### Intro (0:20)
State what's being demoed: "The Conversion Engine — an AI sales automation system that enriches prospects from public data, composes signal-grounded outreach, and books discovery calls." Show the architecture diagram briefly.

### Step 1 — Enrichment Live (1:00)
```bash
make enrich DOMAIN=delamode-group.com
```
**Show on camera:**
- Terminal output with per-signal confidence scores
- Langfuse trace appearing (open Langfuse dashboard)
- `eval/briefs/delamode-group.com/hiring_signal_brief.json` contents
- `eval/briefs/delamode-group.com/competitor_gap_brief.json` contents

### Step 2 — Cold Email Compose & Send (1:00)
```bash
make compose-and-send DOMAIN=delamode-group.com
```
**Show on camera:**
- Segment-specific email draft in output
- Tone-check pass (scores visible)
- `sink: True` confirming kill-switch routing
- HubSpot dashboard: contact record populating with enrichment fields

### Step 3 — Engaged Reply (1:00)
Manually send a reply from the sink inbox with an "interested" message. **Show on camera:**
- Webhook hits `/webhook/email` (FastAPI terminal logs)
- Reply classifier tags it `engaged`
- Warm response auto-composed with Cal.com booking link
- HubSpot engagement updated to show the reply thread

### Step 4 — SMS Scheduling Handoff (0:45)
Prospect shares phone number. **Show on camera:**
- Agent detects scheduling intent → switches to SMS channel
- SMS confirmation routed via SMS sink (kill-switch enforced)
- Langfuse trace shows cross-channel handoff

### Step 5 — Cal.com Booking (0:45)
**Show on camera:**
- Slot picked from Cal.com availability
- Booking created → `data/calcom_local/bookings.jsonl` (sink mode)
- Context brief attached to HubSpot Deal as a NOTE
- Open the HubSpot Deal to show the NOTE contents

### Step 6 — Abstention / Honesty Path (0:30)
```bash
make compose-and-send DOMAIN=windowclassics.com
```
**Show on camera:**
- Agent refuses to assert "aggressive hiring" when <5 open roles
- Softer exploratory language used instead
- Compare the language side-by-side with Step 2's output

### Step 7 — Classification Nuance (0:30)
**Show on camera:**
- A prospect with post-layoff + funding signals
- Classified as Segment 2 (mid-market restructure), not Segment 1
- Langfuse trace showing the rule that fired

### Step 8 — τ²-Bench Score (0:30)
```bash
make tau2-baseline
```
**Show on camera:** Harness produces a trace; pass@1 result visible.

### Step 9 — Probe Walkthrough (0:45)
```bash
make probes P=P-0001
```
**Show on camera:**
- The probe definition in `probes/probe_library.md`
- Before/after trigger rate showing a concrete mechanism fix

### Step 10 — Outro (0:20)
State: pilot recommendation, kill-switch clause (trigger metric, threshold, rollback condition).

---

## 8. Deploying to Render (Production)

### Create the service
1. Dashboard → **New** → **Web Service** → connect repo
2. Settings:
   - **Environment:** Python 3
   - **Build:** `pip install --upgrade pip && pip install -r agent/requirements.txt`
   - **Start:** `uvicorn agent.server:app --host 0.0.0.0 --port $PORT`
   - **Health Check:** `/health`
   - **Instance:** Starter ($7/mo) — free tier sleeps and drops webhooks

### Environment variables
Same as `.env`, plus:
- `HUBSPOT_USE_MCP=false` — Render's Python image has no `npx`; use REST mode on Render, MCP locally
- `TENACIOUS_OUTBOUND_ENABLED` — **leave unset** unless staff-approved

### Point webhooks at Render
Replace ngrok URLs with `https://<service>.onrender.com/webhook/{email,sms,cal}` at each provider.

---

## 9. Shutdown

```bash
# Terminal C: Ctrl-C FastAPI
# Terminal B: Ctrl-C tunnel
# Terminal A:
docker compose -f infra/docker-compose.yml down
# HubSpot MCP dies with its Python parent — nothing to stop.
```

---

## Troubleshooting

### Cal.com "table public.App does not exist"
```bash
# Force fresh start
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d
```
If that fails, run migrations manually:
```bash
docker compose -f infra/docker-compose.yml run --rm --entrypoint "" \
  calcom sh -c "cd /calcom && yarn workspace @calcom/prisma db-deploy"
```

### `make compose-and-send` fails with "not in synthetic_prospects.json"
The `DOMAIN=` value must match a `company_domain` in `data/synthetic_prospects.json`. See the domain list in §6 above.

### HubSpot MCP fails to start
Check `node --version` (needs v18+). See [`infra/hubspot_mcp.md`](infra/hubspot_mcp.md) for details. Do **not** set `HUBSPOT_USE_MCP=false` locally — that demotes to REST and fails `make final-check`.
