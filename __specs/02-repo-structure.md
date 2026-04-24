# 02 — Repository Structure

The repository layout matches the structure required by the challenge brief's interim and final submission deliverables, plus the specs and policies the implementation enforces.

```
conversion-engine/
├── README.md                          # Architecture diagram, setup, kill-switch docs
├── .env.example                       # Template; real .env never committed
├── .gitignore                         # Excludes .env, eval/runs/, briefs/, sealed/
├── Makefile                           # Common dev commands (see below)
│
├── __specs/                           # This directory — the engineering spec
│   ├── README.md
│   ├── 00-overview.md ... 18-configuration.md
│   ├── .env.example
│   └── config.example.yaml
│
├── __plans/                           # Day-by-day work breakdown (out of spec scope;
│   └── ...                            #   the planning docs live here)
│
├── agent/                             # The agent and all integrations
│   ├── __init__.py
│   ├── requirements.txt
│   ├── config.py                      # Pydantic settings; loads .env + YAML
│   ├── kill_switch.py                 # The single deliver() gate
│   ├── prompts/                       # System prompts, few-shot exemplars
│   │   ├── classifier.txt
│   │   ├── composer_segment_1.txt
│   │   ├── composer_segment_2.txt
│   │   ├── composer_segment_3.txt
│   │   ├── composer_segment_4.txt
│   │   ├── composer_abstain.txt
│   │   ├── reply_classifier.txt
│   │   ├── reply_engaged.txt
│   │   ├── reply_curious.txt
│   │   ├── reply_objection.txt
│   │   ├── reply_soft_defer.txt
│   │   ├── tone_preservation.txt
│   │   └── context_brief_synthesizer.txt
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── pipeline.py                # Orchestrates the DAG
│   │   ├── crunchbase.py              # ODM sample lookup
│   │   ├── layoffs.py                 # layoffs.fyi CSV parsing
│   │   ├── jobposts.py                # Playwright scraper (rate-limited)
│   │   ├── leadership.py              # CTO/VP-Eng change detection
│   │   ├── ai_maturity.py             # 0–3 scoring with justifications
│   │   ├── competitor_gap.py          # Top-quartile peer analysis
│   │   ├── tech_stack.py              # BuiltWith/Wappalyzer
│   │   └── briefs.py                  # Pydantic models matching schemas/
│   ├── classifier.py                  # ICP segment + confidence
│   ├── composer.py                    # Email/SMS draft generation
│   ├── tone_check.py                  # Five-marker scoring
│   ├── reply_handler.py               # Inbound classification and response
│   ├── handoff.py                     # The five handoff conditions
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── email/
│   │   │   ├── __init__.py
│   │   │   ├── send.py                # Resend / MailerSend adapter
│   │   │   ├── webhook.py             # FastAPI inbound endpoint
│   │   │   ├── render.py              # Jinja2 template binding
│   │   │   └── templates/
│   │   │       ├── cold_signal_grounded.j2
│   │   │       ├── cold_exploratory.j2     # Abstention path
│   │   │       ├── nurture_1.j2            # Day 5
│   │   │       ├── nurture_2.j2            # Day 12 close
│   │   │       ├── nurture_3.j2            # 6-month parking
│   │   │       ├── scheduling_offer.j2
│   │   │       ├── post_book_confirmation.j2
│   │   │       └── handoff_human.j2
│   │   ├── sms/
│   │   │   ├── __init__.py
│   │   │   ├── send.py                # Africa's Talking adapter
│   │   │   └── webhook.py
│   │   └── voice/
│   │       ├── __init__.py
│   │       ├── send.py                # Shared Voice Rig adapter (bonus)
│   │       └── webhook.py
│   ├── hubspot/
│   │   ├── __init__.py
│   │   ├── client.py                  # MCP client wrapper
│   │   ├── schema.py                  # Custom properties (tenacious_status, etc.)
│   │   └── events.py                  # Conversation-event writers
│   ├── calendar/
│   │   ├── __init__.py
│   │   ├── client.py                  # Cal.com REST client
│   │   ├── webhook.py                 # Booking-created handler
│   │   └── context_brief.py           # Renders schemas/discovery_call_context_brief.md
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── langfuse.py                # Trace span helpers
│   │   └── cost.py                    # Per-trace cost computation
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                  # OpenRouter / Anthropic adapter
│   │   └── tiers.py                   # dev-tier vs eval-tier selection
│   └── server.py                      # FastAPI app entrypoint
│
├── eval/                              # τ²-Bench harness + run artifacts
│   ├── tau2/                          # Cloned upstream submodule
│   ├── harness.py                     # Wraps tau2 with Langfuse + cost logging
│   ├── score_log.json                 # Day-1 baseline + reproduction check
│   ├── trace_log.jsonl                # Full τ²-Bench trajectories
│   ├── baseline.md                    # ≤400 words: what reproduced, CI, cost
│   └── runs/                          # Per-run trace files cited by evidence_graph
│
├── probes/                            # Act III artifacts
│   ├── probe_library.md               # 30+ structured probe entries
│   ├── failure_taxonomy.md            # Probes grouped by category, with trigger rates
│   ├── target_failure_mode.md         # Highest-ROI failure with business-cost derivation
│   └── runs/                          # Per-probe execution traces
│
├── method/                            # Act IV artifacts
│   ├── method.md                      # Mechanism, hyperparameters, three ablations
│   ├── ablation_results.json          # pass@1, 95% CI, cost-per-task, p95 latency
│   ├── held_out_traces.jsonl          # Sealed-slice traces (your_method, day1, gepa)
│   └── stat_test.md                   # Delta A positive with p<0.05
│
├── memo/                              # Act V artifacts
│   ├── memo.pdf                       # Exactly 2 pages
│   ├── memo.md                        # Source markdown for the PDF
│   ├── evidence_graph.json            # Every numeric claim → trace ID or source
│   ├── invoice_summary.json           # Rig + LLM spend totals for cost-per-lead
│   └── README_for_inheritor.md        # Written for the engineer inheriting this work
│
├── market_space/                      # Distinguished-tier stretch (optional)
│   ├── market_space.csv
│   ├── top_cells.md
│   ├── methodology.md
│   └── validation_sample.csv          # Hand-labeled 30–50 row precision/recall set
│
├── tenacious_sales_data/              # The seed materials (read-only mirror)
│   ├── DAY0_CHECKLIST.md
│   ├── LICENSE.md
│   ├── policy/
│   │   ├── data_handling_policy.md
│   │   └── acknowledgement.md
│   ├── schemas/
│   │   ├── hiring_signal_brief.schema.json
│   │   ├── competitor_gap_brief.schema.json
│   │   ├── discovery_call_context_brief.md
│   │   ├── sample_hiring_signal_brief.json
│   │   └── sample_competitor_gap_brief.json
│   └── seed/
│       ├── icp_definition.md
│       ├── style_guide.md
│       ├── baseline_numbers.md
│       ├── bench_summary.json
│       ├── pricing_sheet.md
│       ├── case_studies.md
│       ├── sales_deck.pptx
│       ├── sales_deck_notes.md
│       ├── email_sequences/
│       │   ├── cold.md
│       │   ├── warm.md
│       │   └── reengagement.md
│       └── discovery_transcripts/
│           ├── transcript_01_series_b_startup.md
│           ├── transcript_02_mid_market_restructure.md
│           ├── transcript_03_new_cto_transition.md
│           ├── transcript_04_specialized_capability.md
│           └── transcript_05_objection_heavy.md
│
├── data/                              # Frozen public snapshots for reproducibility
│   ├── crunchbase_odm_sample.json     # Apache-2.0 luminati-io mirror
│   ├── layoffs_fyi_2026_q1.csv
│   ├── job_posts_snapshot_2026-04-01.json
│   └── synthetic_prospects.json       # The 20+ test prospects + sink contacts
│
├── infra/
│   ├── docker-compose.yml             # Cal.com self-hosted
│   ├── cal_fixtures/                  # Program-provided mock calendars
│   ├── killswitch.md                  # The kill-switch contract
│   ├── smoke_test.sh                  # Five green checks
│   └── acknowledgement_signed.txt     # Created after policy acknowledgement
│
└── policy/                            # Mirror at repo root for smoke-test compatibility
    └── acknowledgement_signed.txt     # (same as infra/) — see DAY0_CHECKLIST.md
```

## Ownership and conventions

- **Per-spec ownership**: Each directory above maps to one or more specs in `__specs/`. The spec is the contract; the code is the implementation.
- **No business logic in `channels/`**: The channel modules are thin adapters. Composition, classification, and tone-checking happen in the agent core.
- **Briefs are Pydantic models**: `agent/enrichment/briefs.py` mirrors `tenacious_sales_data/schemas/*.schema.json`. A schema test in CI confirms drift is caught.
- **One kill switch**: There is exactly one place in the repo where `to` is decided for outbound — `agent/kill_switch.py`. Code-review enforces.
- **Templates live with their channel**: `agent/channels/email/templates/*.j2`. SMS does not have templates (one-line scheduling messages assembled inline).

## Makefile targets

The Makefile centralizes common dev commands so the inheriting engineer does not need to memorize incantations:

```
make setup            # Install deps, copy .env.example → .env, init Cal.com
make smoke            # Run infra/smoke_test.sh
make enrich DOMAIN=acme.com
                      # Run the enrichment pipeline for one prospect
make compose-and-send DOMAIN=acme.com
                      # End-to-end one synthetic prospect (kill-switch enforced)
make tau2-baseline    # Reproduce the τ²-Bench retail baseline on dev slice
make tau2-eval        # Run sealed held-out (eval-tier) — guarded by env var
make probes           # Execute the probe library against a synthetic prospect
make memo             # Render memo.md → memo.pdf
make ack              # Drop infra/acknowledgement_signed.txt with a UTC timestamp
```

## Files the implementation must NOT add

- A second outbound code path that bypasses the kill switch.
- Any committed `.env`, `secrets.yaml`, or HubSpot/Resend tokens.
- Real Tenacious customer data anywhere in the tree.
- A `bench_summary_v2.json` or any "updated" version of a seed file (these are read-only).
- Tenacious-branded outreach copy that lacks the `X-Tenacious-Status: draft` header in tests.
