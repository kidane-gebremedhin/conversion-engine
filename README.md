# Conversion Engine

An automated lead-generation and conversion system for **Tenacious Consulting and Outsourcing**. Finds prospective clients from public data, qualifies them against a real intent signal, runs a grounded nurture sequence, and books discovery calls with a Tenacious delivery lead.

> **Find the lead. Ground the conversation. Respect the brand. Ship it.**

This repository is the TRP1 Week 10 Conversion Engine challenge implementation. The engineering specification lives under [`__specs/`](__specs/); execution plans under [`__plans/`](__plans/).

---

## Kill switch — read this first

Every outbound message (email, SMS, voice) passes through **exactly one function**, `deliver()` in [`agent/kill_switch.py`](agent/kill_switch.py). That function consults the environment variable `TENACIOUS_OUTBOUND_ENABLED`:

- **Unset (default)** → outbound routes to the program-operated **staff sink**. Real prospects never receive messages.
- **Set to `1`** → outbound routes to the actual recipient. **This requires explicit program-staff approval.**

Additional runtime guards:

- The recipient must be the sink **or** a synthetic prospect in [`data/synthetic_prospects.json`](data/synthetic_prospects.json). Any other recipient raises `PolicyViolation`.
- Every email outbound must carry `X-Tenacious-Status: draft`. Missing header → `PolicyViolation`.
- No code path outside [`agent/kill_switch.py`](agent/kill_switch.py) (and its thin channel adapters) may import a provider SDK's send method. Enforced by CI grep.

The smoke test [`infra/smoke_test.sh`](infra/smoke_test.sh) verifies the gate is wired before the agent starts processing outbound. Flipping the kill switch without staff approval is a policy violation even if no message actually reaches a real prospect — the policy is about the code pattern, not the outcome.

See [`__specs/16-data-handling-and-kill-switch.md`](__specs/16-data-handling-and-kill-switch.md) for the full policy-enforcement contract.

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
          Email (primary)   SMS (warm-scheduling)   Voice (bonus)
          Resend/MailerSend Africa's Talking        Shared Voice Rig
              │                 │                    │
              ▼                 ▼                    ▼
                    Inbound Reply Handler (FastAPI)
              │                 │                    │
              ▼                 ▼                    ▼
        HubSpot MCP      Cal.com (self-host)      Langfuse (traces + cost)
```

See [`__specs/01-architecture.md`](__specs/01-architecture.md) for the full architecture spec.

---

## Setup

### Prerequisites

- Python 3.11+
- Docker (for self-hosted Cal.com)
- A tunneling tool (ngrok or Cloudflare Tunnel) for webhook delivery in dev

### One-command setup

```bash
make setup
```

This will:

1. Create a `.venv/`, install `agent/requirements.txt`.
2. Copy `.env.example` → `.env` (edit to fill in secrets).
3. Copy `config.example.yaml` → `config.yaml` (operational knobs).
4. Install Playwright's Chromium binary for job-post scraping.

### Required accounts (free tier, no credit card)

See [`__plans/01-preflight.md`](__plans/01-preflight.md) for the full pre-flight. The credentials below go in `.env`:

| Service | Purpose | Env vars |
|---|---|---|
| [Resend](https://resend.com) or [MailerSend](https://mailersend.com) | Email (primary) | `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`, `RESEND_FROM_ADDRESS` |
| [Africa's Talking sandbox](https://africastalking.com/) | SMS (warm scheduling) | `AT_API_KEY`, `AT_USERNAME`, `AT_SHORT_CODE` |
| [HubSpot Developer Sandbox](https://developers.hubspot.com/) | CRM | `HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_APP_ID`, `HUBSPOT_PORTAL_ID` |
| [Langfuse cloud free tier](https://cloud.langfuse.com) | Observability | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| [OpenRouter](https://openrouter.ai) | Dev-tier LLM (Qwen / DeepSeek) | `OPENROUTER_API_KEY` |
| Anthropic or OpenAI | Eval-tier LLM (sealed held-out only) | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |

### Local infra

```bash
# Cal.com self-hosted
docker compose -f infra/docker-compose.yml up -d

# τ²-Bench clone (pin SHA in config.yaml)
git clone https://github.com/sierra-research/tau2-bench.git eval/tau2
```

### Policy acknowledgement

Before Act I starts, read [`tenacious_sales_data/policy/data_handling_policy.md`](tenacious_sales_data/policy/data_handling_policy.md), file the acknowledgement per staff instructions, then:

```bash
make ack
```

This drops a UTC-timestamped `acknowledgement_signed.txt` in both `infra/` and `policy/`. The smoke test requires this file to exist.

---

## Running

**Looking for the full step-by-step start-up guide?** See [`RUNBOOK.md`](RUNBOOK.md) —
covers HubSpot MCP, Cal.com docker-compose, webhook tunnel, FastAPI server,
Langfuse, and τ²-Bench, with the per-terminal process table.


```bash
# Readiness check (5 green checks: email sink, SMS sink, HubSpot, Cal.com, Langfuse)
make smoke

# Enrich one prospect (produces hiring_signal_brief.json + competitor_gap_brief.json)
make enrich DOMAIN=orrin-labs.example

# End-to-end one synthetic prospect
make compose-and-send DOMAIN=orrin-labs.example

# Reproduce the τ²-Bench retail dev-slice baseline
make tau2-baseline

# Execute the probe library
make probes

# Sealed held-out eval (guarded)
TAU2_SEALED_ACCESS=1 EVAL_TIER_ENABLED=1 make tau2-eval

# Render the two-page memo
make memo

# Start the inbound FastAPI server
make server
```

**Deploying to Render (staging/prod):** see [`RUNBOOK.md` §8b](RUNBOOK.md#8b-deploy-to-render-production-fastapi-host)
— build/start commands, required env vars, webhook wiring, and the
`HUBSPOT_USE_MCP=false` caveat for the Render Python image.

---

## Repository layout

```
agent/                 # Agent, enrichment, channels, HubSpot, Cal.com, observability, LLM
eval/                  # τ²-Bench harness, score_log, trace_log, baseline.md
probes/                # Act III probe library, taxonomy, target failure
method/                # Act IV mechanism, ablations, held-out traces
memo/                  # Act V two-page memo, evidence graph, inheritor README
data/                  # Frozen public snapshots and synthetic-prospect fixtures
infra/                 # Docker compose, smoke test, kill-switch docs
market_space/          # Distinguished-tier stretch (opt-in)
tenacious_sales_data/  # Read-only seed: ICP, style guide, baseline numbers, bench, etc.
scripts/               # CLI entry points for enrich, compose-and-send, audit, final-check
tests/                 # Pytest suite (schema conformance, kill-switch, classifier rules)
__specs/               # Engineering specification (19 files)
__plans/               # Execution plans (11 files)
```

See [`__specs/02-repo-structure.md`](__specs/02-repo-structure.md) for the full layout contract.

---

## Deliverables

- **Interim**: Acts I–II (`README.md`, `agent/`, `eval/`, `baseline.md`, PDF report). Checklist: [`__specs/17-deliverables-checklist.md`](__specs/17-deliverables-checklist.md#interim-submission).
- **Final**: adds Acts III–V (`probes/`, `method/`, `memo.pdf`, demo video ≤8 min). Checklist: [`__specs/17-deliverables-checklist.md`](__specs/17-deliverables-checklist.md#final-submission).

---

## Non-negotiables

- Kill switch defaults unset.
- No real customer contact during the challenge week.
- Every Tenacious-branded outbound carries `X-Tenacious-Status: draft`.
- No hard-coded secrets, base URLs, model IDs, or prices — everything via `.env` or `config.yaml`.
- No fabricated Tenacious numbers. Every memo claim resolves to a trace ID, a seed row, or a public source.

---

## License and attribution

Seed materials in `tenacious_sales_data/` are licensed to this repo for the challenge week per [`tenacious_sales_data/LICENSE.md`](tenacious_sales_data/LICENSE.md). Do not redistribute.
