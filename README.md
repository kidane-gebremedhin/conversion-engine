# Conversion Engine

An automated lead-generation and conversion system for **Tenacious Consulting and Outsourcing**. Finds prospective clients from public data, qualifies them against real intent signals, runs a grounded nurture sequence, and books discovery calls.

> **Find the lead. Ground the conversation. Respect the brand. Ship it.**

Specs: [`__specs/`](__specs/) · Plans: [`__plans/`](__plans/) · Step-by-step operations: [`RUNBOOK.md`](RUNBOOK.md)

---

## Kill Switch — Read This First

`TENACIOUS_OUTBOUND_ENABLED` gates **every outbound action** (email, SMS, voice, Cal.com bookings).

| State | Behavior |
|---|---|
| **Unset (default)** | All channels route to staff sinks — no real prospect gets contacted |
| **Set to `1`** | Routes to actual recipients — requires explicit staff approval |

Additional guards:
- Recipient must be the **sink** or an entry in [`data/synthetic_prospects.json`](data/synthetic_prospects.json). Anything else → `PolicyViolation`.
- Every email must carry `X-Tenacious-Status: draft`. Missing header → `PolicyViolation`.
- CI grep enforces that only [`agent/kill_switch.py`](agent/kill_switch.py) (and thin adapters) import provider send methods.

See [`__specs/16-data-handling-and-kill-switch.md`](__specs/16-data-handling-and-kill-switch.md) for the full contract.

---

## Architecture

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
                   │  • ICP classifier  │ (rule-based; abstains below 0.6)
                   │  • Tone-aware      │
                   │    composer        │ (5 tone markers; 120-word cap)
                   │  • Reply handler   │ (5 reply classes + ambiguous)
                   │  • Handoff gate    │ (5 conditions to human)
                   └────────┬───────────┘
                            │ every draft
                            ▼
           ┌───────────────────────────────────────┐
           │  Kill-Switch Gate                     │
           │  TENACIOUS_OUTBOUND_ENABLED?          │
           │  unset → staff sink                   │
           │  set   → real sender                  │
           └──┬─────────────────┬────────────────┬─┘
              ▼                 ▼                ▼
          Email (primary)   SMS (scheduling)   Voice (bonus)
              │                 │                │
              ▼                 ▼                ▼
        HubSpot MCP      Cal.com (self-host)   Langfuse (traces + cost)
```

---

## Quick Start

```bash
# 1. Setup
make setup                    # creates venv, installs deps, copies .env.example
vi .env                       # fill in credentials (see table below)
make ack                      # policy acknowledgement

# 2. Start services (see RUNBOOK.md for details)
docker compose -f infra/docker-compose.yml up -d   # Cal.com + Postgres
ngrok http 8000               # webhook tunnel (Terminal B)
make server                   # FastAPI on :8000 (Terminal C)

# 3. Verify
make smoke                    # 5+ green checks

# 4. Run
make enrich DOMAIN=delamode-group.com
make compose-and-send DOMAIN=delamode-group.com
```

### Required Accounts (free tier)

| Service | Purpose | Key `.env` vars |
|---|---|---|
| [Resend](https://resend.com) | Email | `RESEND_API_KEY`, `RESEND_FROM_ADDRESS` |
| [Africa's Talking](https://africastalking.com/) | SMS | `AT_API_KEY`, `AT_USERNAME` |
| [HubSpot Dev Sandbox](https://developers.hubspot.com/) | CRM | `HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_PORTAL_ID` |
| [Langfuse](https://cloud.langfuse.com) | Observability | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| [OpenRouter](https://openrouter.ai) | LLM | `OPENROUTER_API_KEY` |

---

## Key Commands

```bash
# Enrichment & outbound
make enrich DOMAIN=<domain>              # produce hiring + competitor briefs
make compose-and-send DOMAIN=<domain>    # full pipeline → kill-switch-gated send

# τ²-Bench
make tau2-baseline                       # dev-slice baseline
TAU2_SEALED_ACCESS=1 EVAL_TIER_ENABLED=1 make tau2-eval   # sealed held-out

# Probes & memo
make probes                              # run probe library
make probes P=P-0001                     # single probe
make memo                                # render 2-page memo.pdf

# Ops
make server                              # FastAPI on :8000
make test                                # pytest suite
make lint                                # ruff
make audit                               # weekly policy audit
make final-check                         # pre-submission gauntlet
```

**Available synthetic prospect domains** (use with `DOMAIN=`):

| Domain | Company | Segment |
|---|---|---|
| `delamode-group.com` | Delamode | seg4 — specialized capability |
| `conshohockenbrewing.com` | Conshohocken Brewing | seg4 |
| `whitehilltech.com` | Whitehill Technologies | seg4 |
| `connempathy.com` | Connempathy | seg4 |
| `consolidatedparts.com` | Consolidated Parts | abstain |
| `alliancehospice.com` | Alliance Hospice | abstain |
| `americraftmfg.com` | Americraft | abstain |
| `fivestarcarting.com` | Five Star Carting | abstain |
| `comax.coop` | La Coop Comax | abstain |
| `windowclassics.com` | Window Classics | abstain |

_(See `data/synthetic_prospects.json` for all 25 prospects.)_

---

## Repository Layout

```
agent/                 # Agent core: enrichment, channels, HubSpot, Cal.com, LLM
eval/                  # τ²-Bench harness, score_log, trace_log, baseline.md
probes/                # Act III probe library + failure taxonomy
method/                # Act IV mechanism, ablations, held-out traces
memo/                  # Act V two-page memo + evidence graph
data/                  # Frozen snapshots, synthetic prospects, layoffs CSV
infra/                 # Docker compose, smoke test, kill-switch docs
scripts/               # CLI: enrich, compose-and-send, audit, final-check
tests/                 # Pytest: schema, kill-switch, classifier
__specs/               # Engineering specification (19 files)
__plans/               # Execution plans (11 files)
tenacious_sales_data/  # Read-only seed data (ICP, style guide, bench)
```

---

## Demo Video — Step-by-Step Walkthrough

> The demo video (≤8 min) must show the system running end-to-end. Follow the steps below, in order, to reproduce every segment required by the spec.

### Prerequisites
All services running: Cal.com, webhook tunnel, FastAPI server, Langfuse keys configured. Run `make smoke` first — all checks green.

### Step 1 — Enrichment Live (1:00)
```bash
make enrich DOMAIN=delamode-group.com
```
Show: Langfuse spans appearing, `hiring_signal_brief.json` + `competitor_gap_brief.json` written to `eval/briefs/delamode-group.com/`, per-signal confidence scores visible in the output.

### Step 2 — Cold Email Live (1:00)
```bash
make compose-and-send DOMAIN=delamode-group.com
```
Show: Agent composes a segment-specific email, tone-check passes, kill-switch routes to sink, HubSpot contact record populates. Note the `sink: True` in output.

### Step 3 — Engaged Reply (1:00)
Reply from the sink inbox with an "interested" message. Show:
- Reply classifier tags it as `engaged`
- Warm response composed with Cal.com booking link
- HubSpot engagement updated

### Step 4 — SMS Handoff (0:45)
Prospect shares phone number or requests SMS scheduling. Show:
- Agent switches from email to SMS channel
- SMS confirmation routed via SMS sink
- Channel handoff visible in Langfuse trace

### Step 5 — Cal.com Booking (0:45)
Show: Slot picked, booking created (routes to `data/calcom_local/bookings.jsonl` when kill switch is off), context brief attached to HubSpot Deal as a NOTE.

### Step 6 — Abstention Path (0:30)
```bash
make compose-and-send DOMAIN=windowclassics.com
```
Show: Agent refuses to assert "aggressive hiring" when <5 open roles exist. Softer exploratory language appears instead.

### Step 7 — Classification Nuance (0:30)
Show a prospect with overlapping signals (e.g., post-layoff + funding) being classified as Segment 2, not Segment 1. Show the rule firing in Langfuse.

### Step 8 — τ²-Bench Score (0:30)
```bash
make tau2-baseline
```
Show: Harness produces a trace; pass@1 visible in output.

### Step 9 — Probe Walkthrough (0:45)
```bash
make probes P=P-0001
```
Show one probe that drove a mechanism fix — before/after trigger rate.

### Step 10 — Outro (0:20)
State the pilot recommendation and the kill-switch clause (trigger metric, threshold, rollback condition).

---

## Non-Negotiables

- Kill switch defaults unset.
- No real customer contact during the challenge week.
- Every outbound carries `X-Tenacious-Status: draft`.
- No hard-coded secrets — everything via `.env` or `config.yaml`.
- No fabricated Tenacious numbers — every claim resolves to a trace, seed row, or public source.

---

## License

Seed materials in `tenacious_sales_data/` are licensed for the challenge week per [`tenacious_sales_data/LICENSE.md`](tenacious_sales_data/LICENSE.md).
