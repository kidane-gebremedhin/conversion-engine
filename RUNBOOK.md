# Runbook — starting every service

Every command in this file runs from the repo root. Four terminals are
recommended: one for each long-running process (MCP, Cal.com, tunnel,
FastAPI). The Makefile wires the short commands; the long form is shown
so you can see what the Makefile does.

---

## 0. One-time setup (first clone)

```bash
# 0a. Python environment and base deps
make setup
# Creates .venv/, installs agent/requirements.txt, copies .env.example → .env,
# copies config.example.yaml → config.yaml, installs Playwright's Chromium.

# 0b. Edit .env — fill in every credential marked "required" in the file
${EDITOR:-vi} .env

# 0c. Policy acknowledgement (required by smoke test)
make ack
# Writes infra/acknowledgement_signed.txt and policy/acknowledgement_signed.txt.

# 0d. Global installs (host-level, one-time)
npm install -g @hubspot/mcp-server                # HubSpot MCP server
# Docker Desktop (or `docker` + `docker compose`) — install per your OS.
# Node 18+ and npm — required for both the MCP server and any Cal.com rebuilds.
```

Sanity check before going further:

```bash
node --version            # must print v18.x or later
docker --version
npx -y @hubspot/mcp-server --help >/dev/null && echo "hubspot mcp OK"
```

---

## 1. Start HubSpot MCP (no separate terminal needed)

The Python agent starts the MCP server itself — `HubSpotClient` spawns
`npx -y @hubspot/mcp-server` over stdio every time it's instantiated
(see [agent/hubspot/mcp_client.py](agent/hubspot/mcp_client.py)). You do
**not** run a long-lived MCP daemon.

Verify the one-shot Day-0 contact creation:

```bash
make day0-hubspot
# Expected:
#   → MCP server started via `npx -y @hubspot/mcp-server`
#   ✓ created test contact id='12345' email=daytest+<hex>@trp1-sink.example via mcp
```

Troubleshooting: if this fails, see [infra/hubspot_mcp.md](infra/hubspot_mcp.md).
Do NOT set `HUBSPOT_USE_MCP=false` to route around the failure — that
demotes the run to REST, which fails `make final-check`.

---

## 2. Start Cal.com (Terminal A)

```bash
# First-boot only: populate infra/.env.calcom with three real secrets.
cp infra/.env.calcom.example infra/.env.calcom
cat >> /tmp/calcom-secrets <<EOF
NEXTAUTH_SECRET=$(openssl rand -base64 32)
CALENDSO_ENCRYPTION_KEY=$(openssl rand -hex 16)
CRON_API_KEY=$(openssl rand -base64 32)
EOF
# paste those three lines over the placeholder lines in infra/.env.calcom.
# IMPORTANT: no `<...>` angle brackets around the values — Cal.com's
# config parser treats them as literal characters.

# Bring up Postgres, run migrations once, then start Cal.com.
docker compose -f infra/docker-compose.yml up -d

# Watch the migration step finish, then the web app come up.
docker compose -f infra/docker-compose.yml logs -f calcom-migrate
# Expect: "The following migration(s) have been applied:" followed by the
# full list, then the container exits with code 0.

docker compose -f infra/docker-compose.yml logs -f calcom
# Ready when you see: "ready - started server on 0.0.0.0:3000"

# One-time: open http://localhost:3000 in a browser, create the admin
# account, then create two event types (slug matters):
#   - discovery-15   (15 min)
#   - discovery-30   (30 min)
# Copy the user's API key from Settings → Developer and paste into .env:
#   CALCOM_API_KEY=...
#   CALCOM_USERNAME=<your-calcom-username>
```

Day-0 end-to-end booking proof:

```bash
make day0-calcom
# Expected:
#   → event type 'discovery-15' id=et-... (rest)
#   → first slot: 2026-04-...T09:00:00
#   ✓ booked: id=bk-...
#   ✓ confirmed readback: start_time_utc=2026-04-...T09:00:00
```

Shutdown: `docker compose -f infra/docker-compose.yml down`.

### Troubleshooting — "table public.App does not exist"

If you see a flood of `PrismaClientKnownRequestError: The table public.App
does not exist in the current database` messages from the `calcom` container,
the migration init never ran (or ran against the wrong database). Fix:

```bash
# 1. Make sure the migration container completed successfully.
docker compose -f infra/docker-compose.yml ps
# calcom-migrate should be in state "exited (0)". If not:

# 2. Force a fresh start — wipe the DB volume and retry.
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d

# 3. If calcom-migrate still exits non-zero, run migrations manually:
docker compose -f infra/docker-compose.yml run --rm --entrypoint "" \
  calcom sh -c "cd /calcom && yarn workspace @calcom/prisma db-deploy"
```

If the errors persist after step 3, the upstream `calcom/cal.com:latest`
image has shifted again — pin to a known-working tag by editing
`infra/docker-compose.yml` (`image: calcom/cal.com:v5.x.y`) and re-up.

---

## 3. Start the webhook tunnel (Terminal B)

Provider webhooks (Resend replies, Africa's Talking SMS, Cal.com
bookings) need a public URL that forwards to `http://localhost:8000`.
Pick **one** tunnel tool:

```bash
# Option 1: ngrok (persistent subdomain recommended)
ngrok http 8000 --domain=<your-reserved-subdomain>.ngrok.app

# Option 2: Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```

Note the public URL (e.g. `https://abcd.ngrok.app`) and paste into `.env`:

```
RESEND_WEBHOOK_URL=https://abcd.ngrok.app/webhook/email
AT_WEBHOOK_URL=https://abcd.ngrok.app/webhook/sms
CALCOM_WEBHOOK_URL=https://abcd.ngrok.app/webhook/cal
```

Then register each URL with its provider:

- **Resend** → project → Webhooks → add the URL with the `email.bounced`
  and `email.replied` events; copy the signing secret into
  `RESEND_WEBHOOK_SECRET`.
- **Africa's Talking** → SMS → Callback URLs → delivery + incoming
  callback to the URL above.
- **Cal.com** → Settings → Developer → Webhooks → `BOOKING_CREATED`
  (and `BOOKING_CANCELLED` if you want cancellation handling); secret
  → `CALCOM_WEBHOOK_SECRET`.

---

## 4. Start FastAPI (Terminal C)

```bash
make server
# uvicorn agent.server:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints exposed (see [agent/server.py](agent/server.py)):

| Method | Path              | Purpose                                  |
|--------|-------------------|------------------------------------------|
| GET    | /health           | kill-switch state + timestamp            |
| POST   | /webhook/email    | Resend / MailerSend reply                |
| POST   | /webhook/sms      | Africa's Talking inbound                 |
| POST   | /webhook/voice    | Shared Voice Rig (stub)                  |
| POST   | /webhook/cal      | Cal.com booking.created                  |

Verify:

```bash
curl -s localhost:8000/health | jq
# {
#   "ok": true,
#   "env": "dev",
#   "kill_switch": "sink",         # stays "sink" until TENACIOUS_OUTBOUND_ENABLED=1
#   "eval_tier_enabled": false,
#   ...
# }
```

---

## 5. Start Langfuse (optional; use the cloud free tier)

The Python SDK posts spans directly — no local daemon. Just paste keys
into `.env`:

```
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PROJECT_ID=<project uuid>
```

When keys are absent the agent appends to `data/local_traces.jsonl`
instead — handy for offline dev, insufficient for memo evidence claims.

---

## 6. τ²-Bench (not a daemon; one-shot runner)

```bash
# First-time clone. Path is eval/tau2 (inside the repo); .gitignore
# keeps the vendored source out of git. Activate the venv first —
# Ubuntu 24.04's system Python refuses `pip install` outside a venv
# (PEP 668 / externally-managed-environment).
source .venv/bin/activate         # run `make setup` first if .venv is missing
git clone https://github.com/sierra-research/tau2-bench.git eval/tau2
pip install -e eval/tau2

# Pin the SHA in config.yaml > tau2.pinned_sha:
(cd eval/tau2 && git rev-parse HEAD)

# Baseline (Terminal D, or any free shell)
make tau2-baseline
# Writes eval/score_log.json and eval/trace_log.jsonl; see eval/baseline.md.
```

Sealed held-out (dual-guarded):

```bash
TAU2_SEALED_ACCESS=1 EVAL_TIER_ENABLED=1 make tau2-eval
```

---

## 7. The five green checks

With MCP, Cal.com, tunnel, and FastAPI all up:

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

## 8. Day-to-day commands

```bash
# Enrich one prospect
make enrich DOMAIN=orrin-labs.example

# End-to-end one synthetic prospect (kill-switch gated)
make compose-and-send DOMAIN=orrin-labs.example

# Probe library (refreshes probes/failure_taxonomy.md)
make probes
make probes P=P-0001          # single probe

# Render the two-page memo
make memo

# Weekly policy audit (reads data/killswitch_audit.jsonl)
make audit

# Test suite + lint
make test
make lint

# Pre-submission gauntlet (fails hard on any policy/readiness miss)
make final-check
```

---

## 8b. Deploy to Render (production FastAPI host)

For staging/prod the FastAPI server in [agent/server.py](agent/server.py)
runs on [Render](https://dashboard.render.com) as a Web Service. Webhook
providers (Resend, Africa's Talking, Cal.com) need a stable public URL —
Render gives you one; ngrok is dev-only.

### 8b.1 Prerequisites

- Repo pushed to GitHub or GitLab — Render deploys from a git remote.
- All secrets from `.env` ready to paste into the Render dashboard (never
  commit them).
- Decide whether you need Playwright on the server. The scraper in
  [agent/enrichment/jobposts.py](agent/enrichment/jobposts.py) uses
  Chromium; if scraping runs out-of-band (cron/dev laptop), you can
  skip `playwright install` in the Render build and save ~400 MB +
  a minute of cold-start.

### 8b.2 Create the service (one-time)

1. Dashboard → **New** → **Web Service** → connect the repo → pick branch.
2. Settings:
   - **Environment:** `Python 3` (runtime `python-3.11.x`).
   - **Region:** closest to HubSpot/Cal.com webhook origins.
   - **Build Command:**
     ```
     pip install --upgrade pip && pip install -r agent/requirements.txt
     ```
     Add `&& playwright install --with-deps chromium` only if scraping
     runs on this dyno.
   - **Start Command:**
     ```
     uvicorn agent.server:app --host 0.0.0.0 --port $PORT
     ```
     Render injects `$PORT`; do NOT hardcode `8000`, and do NOT pass
     `--reload` in prod.
   - **Health Check Path:** `/health` (already returns 200 at
     [agent/server.py:33](agent/server.py#L33)).
   - **Instance Type:** Starter ($7/mo) minimum. The free tier sleeps
     after 15 min idle → webhooks will miss the cold start and the
     provider will retry-then-drop.
   - **Auto-Deploy:** on for staging, off for prod if you prefer
     tag-gated releases.

### 8b.3 Environment variables

Paste every required var from [.env.example](.env.example) into
Render's **Environment** tab. Minimum set for the server to boot and
smoke-check green:

| Var | Notes |
|---|---|
| `ENV` | `prod` or `staging` |
| `TENACIOUS_OUTBOUND_ENABLED` | **leave unset** unless staff-approved |
| `EVAL_TIER_ENABLED` | `false` unless running sealed eval |
| `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`, `RESEND_FROM_ADDRESS` | email channel |
| `AT_API_KEY`, `AT_USERNAME`, `AT_SHORT_CODE` | Africa's Talking SMS |
| `HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_APP_ID`, `HUBSPOT_PORTAL_ID` | CRM |
| `HUBSPOT_USE_MCP=false` | **required on Render** — the MCP path spawns `npx` which is not on the Python image. Use REST mode on Render and reserve MCP for local `make final-check`. |
| `CALCOM_API_KEY`, `CALCOM_USERNAME`, `CALCOM_WEBHOOK_SECRET` | booking |
| `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PROJECT_ID` | observability |
| `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM |

Mark API keys and webhook secrets as **Secret** in Render (they're
hidden from the dashboard after save).

### 8b.4 First deploy

1. Click **Create Web Service** — Render builds and deploys.
2. Watch the Logs tab for:
   - `pip install` finishing without error.
   - `Uvicorn running on http://0.0.0.0:<port>`.
   - First `GET /health` from Render's healthcheck probe returning 200.
3. Copy the public URL (`https://<service>.onrender.com`).

Verify:

```bash
curl -s https://<service>.onrender.com/health | jq
# Expect kill_switch: "sink" until TENACIOUS_OUTBOUND_ENABLED is set.
```

### 8b.5 Point webhooks at Render

Replace the ngrok URLs from §3 with the Render URL at each provider:

- **Resend** → Webhooks → URL `https://<service>.onrender.com/webhook/email`.
- **Africa's Talking** → SMS callbacks → same host, path `/webhook/sms`.
- **Cal.com** → Developer → Webhooks → `/webhook/cal`, event
  `BOOKING_CREATED` (+ `BOOKING_CANCELLED` if wired).

Each provider's signing secret must match the `*_WEBHOOK_SECRET` env var
on Render — signature verification is enforced in
[agent/channels/email/webhook.py](agent/channels/email/webhook.py),
[agent/channels/sms/webhook.py](agent/channels/sms/webhook.py), and
[agent/calendar/webhook.py](agent/calendar/webhook.py).

### 8b.6 Flipping the kill switch in prod

Setting `TENACIOUS_OUTBOUND_ENABLED=1` on Render routes real outbound.
Do this only with documented staff approval — see §*Kill switch* in
[README.md](README.md) and the policy contract at
[__specs/16-data-handling-and-kill-switch.md](__specs/16-data-handling-and-kill-switch.md).
Restart the service after toggling so the setting re-reads.

### 8b.7 Operational notes

- **Logs / traces:** Render tails stdout; structured traces go to
  Langfuse (§5). The `data/killswitch_audit.jsonl` file referenced by
  `make audit` is written to the dyno's ephemeral disk — attach a
  Render Persistent Disk at `/opt/render/project/src/data` if you need
  it to survive redeploys.
- **Cron jobs** (weekly audit, enrich refresh) belong in Render's
  **Cron Jobs** product, not the Web Service dyno. Point them at the
  same repo and use `python scripts/audit_week.py` / `scripts/enrich.py`
  as the command.
- **Do not** run `make tau2-eval` or `make tau2-baseline` on Render —
  that's a one-shot local/CI task and the vendored tau2 clone is
  `.gitignore`d.

---

## 9. Shutdown (end of session)

```bash
# Terminal C: Ctrl-C FastAPI
# Terminal B: Ctrl-C the tunnel
# Terminal A: Cal.com
docker compose -f infra/docker-compose.yml down

# (HubSpot MCP process dies with its Python parent — nothing to stop.)
```

---

## 10. Terminal-by-terminal summary

| Term | Process                        | Command                                              | Lifetime         |
|------|--------------------------------|------------------------------------------------------|------------------|
| A    | Cal.com + Postgres             | `docker compose -f infra/docker-compose.yml up -d`   | long-lived       |
| B    | ngrok / cloudflared            | `ngrok http 8000 --domain=<sub>.ngrok.app`           | long-lived       |
| C    | FastAPI (uvicorn)              | `make server`                                        | long-lived       |
| D    | ad-hoc runs (enrich, probes…)  | `make …`                                             | short-lived      |

The HubSpot MCP server is **not** in this table because the Python agent
starts it per-process via stdio; it never runs as a standalone service.
