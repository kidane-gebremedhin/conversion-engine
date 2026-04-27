# Runbook

All commands run from the repo root.

| Terminal | Process | Command | Lifetime |
|---|---|---|---|
| A | Cal.com + Postgres | `docker compose -f infra/docker-compose.yml up -d` | long-lived |
| B | Webhook tunnel | `ngrok http 8000` | long-lived |
| C | FastAPI server | `make server` | long-lived |
| D | Ad-hoc runs | `make enrich …`, `make compose-and-send …`, etc. | short-lived |

> HubSpot MCP is **not** a separate daemon — the Python agent spawns it over stdio per-process.

---

## 1. One-Time Setup

```bash
make setup                               # venv, deps, scaffold .env + config.yaml
vi .env                                  # fill in credentials
make ack                                 # policy acknowledgement (smoke-test gate)
npm install -g @hubspot/mcp-server       # global, once per machine
```

Prereqs: `node --version` ≥ v18, `docker --version` available.

---

## 2. Cal.com (Terminal A)

First boot only:
```bash
cp infra/.env.calcom.example infra/.env.calcom
# fill in NEXTAUTH_SECRET, CALENDSO_ENCRYPTION_KEY, CRON_API_KEY
docker compose -f infra/docker-compose.yml up -d
```

Open <http://localhost:3000>, create admin account, then create event types `discovery-15` and `discovery-30`. Copy the API key from Settings → Developer into `.env`:

```
CALCOM_API_KEY=cal_live_...
CALCOM_USERNAME=<your-username>
```

Verify: `make day0-calcom` → `✓ booked: id=bk-...`.

---

## 3. Webhook Tunnel (Terminal B)

```bash
ngrok http 8000 --domain=<your-subdomain>.ngrok.app
# or: cloudflared tunnel --url http://localhost:8000
```

Update `.env` with the public URL and register webhooks at each provider:

| Provider | Path | Secret env var |
|---|---|---|
| Resend | `/webhook/email` (`email.bounced`, `email.replied`) | `RESEND_WEBHOOK_SECRET` |
| Africa's Talking | `/webhook/sms` (delivery + incoming) | — |
| Cal.com | `/webhook/cal` (`BOOKING_CREATED`) | `CALCOM_WEBHOOK_SECRET` |

---

## 4. FastAPI (Terminal C)

```bash
make server                              # uvicorn on :8000
curl -s localhost:8000/health | jq
```

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Kill-switch state + timestamp |
| POST | `/webhook/email` | Resend reply inbound |
| POST | `/webhook/sms` | Africa's Talking inbound |
| POST | `/webhook/voice` | Voice stub |
| POST | `/webhook/cal` | Cal.com `booking.created` |

---

## 5. Langfuse

Cloud, no daemon. Set in `.env`:
```
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PROJECT_ID=<uuid>
```
Without keys, traces fall back to `data/local_traces.jsonl`.

---

## 6. Verify

```bash
make smoke
# ✓ policy ack, kill-switch unset, sinks routing, HubSpot/Cal.com/Langfuse reachable
```

---

## 7. Day-to-Day

### Enrich + send

```bash
make enrich DOMAIN=culcha.com            # → eval/briefs/<domain>/
make compose-and-send DOMAIN=culcha.com  # → enrich → compose → tone-check → sink → HubSpot
```

Domain must match a `company_domain` in [`data/synthetic_prospects.json`](data/synthetic_prospects.json).

### τ²-Bench harness — produce a score

The harness ([`eval/harness.py`](eval/harness.py)) drives the vendored τ²-Bench at [`eval/tau2/`](eval/tau2/) via `tau2.runner.batch.run_tasks`. Every score in [`eval/score_log.json`](eval/score_log.json) reflects a real multi-turn retail conversation; there is no mock fallback.

Each run emits one Langfuse trace with a `tau2.trial` generation per (task, seed) carrying the turn-by-turn trajectory, model, tokens, and `cost.usd`. The parent trace gets `tau2.cost_per_task_usd`, `tau2.cost_total_usd`, `tau2.pass_at_1_mean`, and a `pass_at_1` Langfuse score.

**Dev-slice baseline (Act I):**
```bash
make tau2-baseline                                                # 30 tasks × 5 trials
make tau2-baseline TAU2_TRIALS=1                                  # quick smoke (1 trial)
make tau2-baseline TAU2_ARGS="--model qwen/qwen3-next-80b-a3b"    # different agent model
```

**Sealed eval (Act IV scoring):** requires `TAU2_SEALED_ACCESS=1` + `EVAL_TIER_ENABLED=1` in `.env`.
```bash
make tau2-eval                                                    # 20 tasks × 5 trials, eval tier
make tau2-eval TAU2_TRIALS=1                                      # one-trial smoke
```

**Direct invocation** for finer control:
```bash
PYTHONPATH=. .venv/bin/python -m eval.harness \
    --partition retail_dev_30 --trials 5 --tier dev \
    --model qwen/qwen3-next-80b-a3b --seed 42 --max-concurrency 4
```

Outputs:

| File | Contents |
|---|---|
| [`eval/score_log.json`](eval/score_log.json) | `pass_at_1_mean`, `ci_95`, `cost_per_task_usd`, `p50/p95_latency_ms`, `langfuse_trace_url`, repro-delta vs published reference |
| [`eval/trace_log.jsonl`](eval/trace_log.jsonl) | One row per simulation: `task_id`, `seed`, `pass`, full messages, tokens, cost, wall time |
| stderr summary | One line: pass@1 + 95% CI + cost/task + Langfuse trace URL |

**Pinning:** `tau2.pinned_sha` in [config.yaml](config.yaml) is recorded as `git_sha_tau2` on every score-log entry; drift from the working tree at `eval/tau2/` fails reproducibility checks.

**Cost attribution:** prefers LiteLLM's own `completion_cost`; if LiteLLM has no rate card for the served slug (common for OpenRouter date-versioned models like `deepseek-v3.2-20251201`), falls back to [`config.yaml > llm.rate_cards`](config.yaml).

### Act IV mechanism — `make tau2-ablation`

Runs three conditions on the same partition. Mechanism is `dual_control_agent` ([agent/tau2_mechanism/dual_control_agent.py](agent/tau2_mechanism/dual_control_agent.py)) — a system-prompt augmentation hardening tau2 retail's existing dual-control rules into model-readable instructions. See [`method/method.md`](method/method.md) for design rationale.

| Condition | Agent | Purpose |
|---|---|---|
| **A_baseline** | `llm_agent` | Day-1 control |
| **B_mechanism** | `dual_control_agent` | Full mechanism (R1–R5) |
| **C_ablation** | `dual_control_agent_lite` | R1+R2 only — isolates R3+R4+R5 contribution |

```bash
make tau2-ablation                                                                        # dev partition, 5 trials × 3 conditions
make tau2-ablation TAU2_ABLATION_TRIALS=1                                                 # one-trial smoke
```

Direct invocation:
```bash
PYTHONPATH=. .venv/bin/python -m method.run_ablations \
    --partition retail_sealed_20 --tier eval --baseline-tier dev \
    --trials 5 --bootstrap-resamples 5000
```

Outputs (under `method/`):

| File | Contents |
|---|---|
| `ablation_results.json` | pass@1 + 95% CI + cost-per-task + p95 latency for all three conditions; Delta A (paired-task percentile bootstrap) with 95% CI and two-sided p-value; Delta-A gate verdict; GEPA placeholder for Delta B |
| `held_out_traces.jsonl` | Every simulation from every condition, tagged with `condition` |
| `stat_test.md` | Bootstrap math + verdict (PASSES if Δ A > 0 ∧ p < 0.05, else DOES NOT PASS) |

### Other commands

```bash
make probes                              # run probe library
make probes P=P-0001                     # single probe
make memo                                # render 2-page memo.pdf
make test                                # pytest
make lint                                # ruff
make audit                               # weekly policy audit
make final-check                         # pre-submission gauntlet
```

---

## 8. Deploying to Render

1. Dashboard → **New** → **Web Service** → connect repo.
2. **Build:** `pip install --upgrade pip && pip install -r agent/requirements.txt`
3. **Start:** `uvicorn agent.server:app --host 0.0.0.0 --port $PORT`
4. **Health Check:** `/health`
5. **Instance:** Starter ($7/mo) — free tier sleeps and drops webhooks.

Env extras:
- `HUBSPOT_USE_MCP=false` — Render's Python image has no `npx`; use REST on Render, MCP locally.
- `TENACIOUS_OUTBOUND_ENABLED` — **leave unset** unless staff-approved.

Replace ngrok URLs with `https://<service>.onrender.com/webhook/{email,sms,cal}` at each provider.

---

## 9. Shutdown

```bash
# Terminal C: Ctrl-C FastAPI
# Terminal B: Ctrl-C tunnel
docker compose -f infra/docker-compose.yml down
# HubSpot MCP dies with its Python parent — nothing to stop.
```

---

## Troubleshooting

**Cal.com "table public.App does not exist"**
```bash
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d
# If still failing:
docker compose -f infra/docker-compose.yml run --rm --entrypoint "" \
    calcom sh -c "cd /calcom && yarn workspace @calcom/prisma db-deploy"
```

**`make compose-and-send` fails with "not in synthetic_prospects.json"** — `DOMAIN=` must match a `company_domain` in [`data/synthetic_prospects.json`](data/synthetic_prospects.json).

**HubSpot MCP fails to start** — check `node --version` (≥ v18). See [`infra/hubspot_mcp.md`](infra/hubspot_mcp.md). Don't set `HUBSPOT_USE_MCP=false` locally — that demotes to REST and fails `make final-check`.

**τ²-Bench LiteLLM `model isn't mapped yet`** — silenced by [`eval/harness.py`](eval/harness.py)'s startup hook; cost falls back to [`config.yaml > llm.rate_cards`](config.yaml). Add a rate-card entry there if a new model shows `cost_total_usd: 0.0` in the score log.

**τ²-Bench task fails with `Expecting value: line 1 column 1 (char 0)`** — dev-tier model returned non-JSON for a tool call or NL-assertion judge. Harness's tolerant-JSON shim handles empty / markdown-fenced / prose-wrapped cases at both call sites; if you still see this on a new tau2 module, extend `_tolerate_empty_tool_call_args` in [`eval/harness.py`](eval/harness.py).
