# 02 — Repository Structure

**Source:** Challenge document — "GitHub Repo Requirements" (interim + final).

## 1. Top-level layout

```
conversion-engine/
├── README.md                      # architecture diagram, setup, requirements, kill-switch docs
├── pyproject.toml / requirements.txt
├── .env.example                   # all secrets (see __specs/.env.example)
├── config.example.yaml            # tunables (see __specs/config.example.yaml)
├── docker-compose.yml             # Cal.com + optional Langfuse self-host
├── Makefile                       # `make setup`, `make baseline`, `make run`, `make probe`, `make eval`
│
├── agent/                         # all agent source (interim deliverable)
│   ├── __init__.py
│   ├── main.py                    # CLI entry: `python -m agent.main --prospect <crunchbase_id>`
│   ├── orchestrator.py            # state machine COLD→NURTURE→QUALIFIED→BOOKED
│   ├── state.py                   # ThreadState, Prospect, Brief dataclasses
│   ├── config.py                  # pydantic-settings loader (reads .env + config.yaml)
│   │
│   ├── llm/
│   │   ├── client.py              # OpenRouter wrapper, retry, Langfuse instrumentation
│   │   ├── prompts/               # all system + user prompts (versioned)
│   │   │   ├── classify_icp.md
│   │   │   ├── draft_outreach.md
│   │   │   ├── draft_followup.md
│   │   │   ├── classify_reply.md
│   │   │   ├── tone_check.md
│   │   │   └── bench_check.md
│   │   └── tools.py               # tool-schema definitions
│   │
│   ├── enrichment/
│   │   ├── crunchbase.py          # ODM sample loader + funding events
│   │   ├── jobposts.py            # Playwright scraper (BuiltIn / Wellfound)
│   │   ├── layoffs.py             # layoffs.fyi CSV parser
│   │   ├── leadership.py          # press + Crunchbase leadership-change detector
│   │   ├── techstack.py           # BuiltWith / Wappalyzer wrapper
│   │   ├── ai_maturity.py         # 0–3 scorer with per-signal justification
│   │   ├── competitor_gap.py      # top-quartile peers + gap extraction
│   │   └── pipeline.py            # orchestrator emitting hiring_signal_brief.json + competitor_gap_brief.json
│   │
│   ├── icp/
│   │   ├── classifier.py          # segment classifier with abstention
│   │   └── segments.yaml          # 4 fixed segments + filters
│   │
│   ├── channels/
│   │   ├── email/
│   │   │   ├── send.py            # Resend client
│   │   │   ├── webhook.py         # FastAPI inbound reply handler
│   │   │   └── templates/         # jinja2 templates; draft-marked metadata
│   │   ├── sms/
│   │   │   ├── send.py            # Africa's Talking client
│   │   │   └── webhook.py         # FastAPI inbound SMS handler
│   │   └── voice/                 # optional bonus
│   │       └── rig.py             # Shared Voice Rig webhook + keyword prefix
│   │
│   ├── integrations/
│   │   ├── hubspot_mcp.py         # MCP client, event logger
│   │   ├── calcom.py              # booking + invite with attached brief
│   │   └── killswitch.py          # sink router — default unset
│   │
│   ├── policies/
│   │   ├── tone.py                # style_guide.md enforcement
│   │   ├── bench.py               # bench-gated commitment policy
│   │   ├── confidence.py          # signal-confidence-aware phrasing
│   │   └── channel_handoff.py     # email → SMS → voice handoff rules
│   │
│   └── server.py                  # FastAPI app exposing webhooks + healthz
│
├── eval/                          # τ²-Bench harness (interim deliverable)
│   ├── harness.py                 # wraps sierra-research/tau2-bench
│   ├── baseline.md                # Act I write-up (≤ 400 words)
│   ├── score_log.json             # pass@1 + 95 % CI per run
│   ├── trace_log.jsonl            # full trajectories
│   ├── dev_slice.json             # 30-task dev slice pointer
│   ├── held_out_slice.json        # 20-task sealed partition pointer (delivered by program)
│   └── run_baseline.py            # `python eval/run_baseline.py --trials 5`
│
├── probes/                        # Act III / final deliverable
│   ├── probe_library.md           # 30+ structured entries
│   ├── failure_taxonomy.md        # grouped by category with trigger rates
│   ├── target_failure_mode.md     # highest-ROI failure, Tenacious-cost derivation
│   ├── probes/                    # executable probe files, one per entry
│   │   ├── icp_misclass_*.yaml
│   │   ├── signal_overclaim_*.yaml
│   │   ├── bench_overcommit_*.yaml
│   │   ├── tone_drift_*.yaml
│   │   ├── multi_thread_leak_*.yaml
│   │   ├── cost_pathology_*.yaml
│   │   ├── dual_control_*.yaml
│   │   ├── scheduling_tz_*.yaml
│   │   ├── signal_reliability_*.yaml
│   │   └── gap_overclaim_*.yaml
│   └── run_probes.py              # emits failure_taxonomy.md + observed trigger rates
│
├── method/                        # Act IV final deliverable
│   ├── method.md                  # mechanism + rationale + hyperparameters + 3 ablations
│   ├── ablation_results.json      # pass@1, 95 % CI, cost-per-task, p95 latency
│   ├── held_out_traces.jsonl      # raw traces for each of 3 conditions
│   ├── mechanism.py               # implementation of the chosen mechanism
│   └── stat_test.py               # paired bootstrap / permutation test for Delta A
│
├── market_space/                  # optional distinguished-tier (Day 6)
│   ├── market_space.csv
│   ├── top_cells.md
│   └── methodology.md
│
├── memo/                          # Act V final deliverable
│   ├── memo.pdf                   # exactly 2 pages
│   ├── memo.md                    # source markdown
│   ├── evidence_graph.json        # every numeric claim → trace_id / invoice line
│   ├── invoice_summary.json       # LLM + rig spend
│   └── figures/
│
├── seed/                          # read-only inputs from the private seed repo (Day 0)
│   ├── ICP.md
│   ├── sales_deck.pdf             # anonymised
│   ├── case_studies/              # redacted, sector+size descriptors only
│   ├── email_sequences/
│   ├── pricing.yaml               # public-tier bands
│   ├── bench_summary.yaml         # updated weekly, authoritative for capacity
│   ├── sample_calls/              # synthetic transcripts
│   └── style_guide.md             # tone markers
│
├── data/
│   ├── crunchbase_odm/            # 1001-record sample
│   ├── layoffs_fyi/               # CC-BY CSV snapshot
│   ├── jobposts_snapshot/         # early-April 2026 frozen snapshot
│   └── briefs_cache/              # per-prospect enriched briefs
│
├── scripts/
│   ├── setup_calcom.sh
│   ├── setup_hubspot_sandbox.sh
│   ├── provision_resend.py
│   ├── route_sink.py              # default kill-switch sink
│   └── seed_synthetic_prospects.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── __specs/                       # these specification files
```

## 2. Interim-vs-final inventory

| Deliverable | Path | Due |
|-------------|------|-----|
| Repo root README with architecture + setup + kill-switch docs | [README.md](../README.md) | Wed |
| Agent source tree | `agent/` | Wed |
| τ²-Bench harness + baseline + traces | `eval/` | Wed |
| `baseline.md` (≤ 400 words) | `eval/baseline.md` | Wed |
| PDF report (interim) | `reports/interim.pdf` | Wed (public Drive link) |
| `probes/` directory with 30+ probes, taxonomy, target-failure-mode | `probes/` | Sat |
| `method.md` + `ablation_results.json` + `held_out_traces.jsonl` | `method/` | Sat |
| `evidence_graph.json` | `memo/` | Sat |
| `memo.pdf` (exactly 2 pages) | `memo/` | Sat |
| Demo video (≤ 8 min, public, no login) | `demo/` or external link | Sat |

## 3. Makefile targets (recommended)

```
make setup           # installs deps, launches Cal.com + Langfuse locally
make bootstrap       # creates HubSpot sandbox objects, Resend webhook, AT shortcode
make enrich PROSPECT=<crunchbase_id>
make run PROSPECT=<crunchbase_id>     # full COLD → BOOKED flow
make baseline        # τ²-Bench dev-slice pass@1 × 5 trials
make probe           # executes probes/, emits taxonomy + trigger rates
make held-out        # eval-tier run of method + day1 + auto-optim
make memo            # builds memo.pdf from memo.md + evidence_graph.json
make demo            # scripted e2e flow for the video
```

## 4. Branch / commit hygiene

- `main` is always green; tagged `interim-wed` at Wed 21:00 UTC.
- Each act lands as one PR: `act1-baseline`, `act2-stack`, `act3-probes`, `act4-mechanism`, `act5-memo`.
- No secrets committed — `.env` gitignored; `.env.example` tracked.
- Seed materials (`seed/`) are **not** redistributed — gitignored if the seed license forbids; otherwise private repo only.
