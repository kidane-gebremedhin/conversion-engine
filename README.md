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
pip install -e .
cp .env.example .env                      # fill in keys or leave blank for mock mode
cp config.example.yaml config.yaml        # (already copied on first clone)
make bootstrap                            # seed synthetic prospects + fixture state
make health                               # sanity check
```

Offline/mock mode is the default. The mock LLM client is deterministic (seeded) and drives all prompts without API keys. Set `CONVERGINE_LLM_MODE=live` + `OPENROUTER_API_KEY=...` to switch to real calls.

### Interim reproduction

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
