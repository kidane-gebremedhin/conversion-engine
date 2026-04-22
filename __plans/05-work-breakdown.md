# 05 — Work Breakdown Structure

**Purpose:** Map every file in the target repo ([__specs/02 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/02-repo-structure.md)) to a day, a predecessor, an effort estimate, and an acceptance test. The engineer follows this table top-to-bottom inside each day.

**Legend:** XS ≤ 30 min, S ≤ 1 h, M ≤ 2 h, L ≤ 4 h, XL > 4 h. Effort is for a single engineer familiar with the specs.

**Stub-first discipline:** On D0 every file listed for D1–D3 is created as a stub with a docstring and a `raise NotImplementedError`. This lets D2 swim lanes work in parallel without import errors.

---

## 1. Dependency graph (ASCII)

```
config + env  ──►  LLM client ─┐
                                │
seed/ loader (read-only) ──────┼──► enrichment pipeline ─┐
                                │                         │
Crunchbase ODM / layoffs /      │                         │
jobposts snapshot ─────────────┘                          │
                                                          ▼
killswitch  ──┐                                  agent/orchestrator
email client ─┤                                           │
sms client   ─┼──► integrations (hubspot,                 │
calcom client ┤     calcom) ─────────────────────────────►│
              │                                           │
policies (tone, bench, confidence, handoff) ─────────────►│
                                                          │
                                                          ▼
                                           FastAPI server
                                        (webhooks + healthz)
                                                          │
                                                          ▼
                                           τ²-Bench harness
                                           (dev slice D1 — CI control)
                                                          │
                            ┌─────────────────────────────┤
                            ▼                             ▼
                   probes/ (D4) ──► method/ (D5–D6) ──► memo/ (D7)
                                    + held-out eval
```

Key rule: nothing in `method/` or `probes/` may import from a module that has not yet stubbed its public interface. D0 stubbing prevents churn.

---

## 2. Top-level (repo root)

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `README.md` | D0 | — | S | Matches [__specs/02 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/02-repo-structure.md); kill-switch section present per [__specs/16 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md) |
| `.env` (from `.env.example`) | D0 | secrets provisioning | XS | `pydantic-settings` loads without error ([__specs/18 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/18-configuration.md)) |
| `config.yaml` (from `config.example.yaml`) | D0 | — | XS | `agent.config.load_config()` returns a valid model |
| `pyproject.toml` / `requirements.txt` | D0 | — | S | `pip install -e .` or `pip install -r requirements.txt` succeeds in clean venv |
| `docker-compose.yml` | D0 | — | S | `docker compose up -d calcom postgres` → Cal.com responds on :3000 |
| `Makefile` | D0 | — | S | `make setup`, `make baseline`, `make run`, `make probe`, `make memo` all documented and invoked without errors (bodies can shell out) |
| `.gitignore` | D0 | — | XS | `.env`, `data/briefs_cache/`, `seed/` (if license forbids), `__pycache__/`, `.venv/`, `*.pdf` (except memo) |

## 3. `agent/` — core package

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `agent/__init__.py` | D0 | — | XS | Package importable |
| `agent/config.py` | D0 | `.env`, `config.yaml` | S | Boot validation per [__specs/18 §5](/home/kg/Projects/10Academy/conversion-engine/__specs/18-configuration.md) |
| `agent/state.py` | D0 stub, D2 body | config | S | `ThreadState`, `Prospect`, `Brief` pydantic models round-trip |
| `agent/main.py` | D2 | orchestrator | S | `python -m agent.main --prospect <uuid>` runs the full loop on a fixture |
| `agent/orchestrator.py` | D2 | state, enrichment, policies, channels, integrations | L | State machine transitions verified against [__specs/06 §6](/home/kg/Projects/10Academy/conversion-engine/__specs/06-agent-design.md); fixture prospect flows COLD → BOOKED |
| `agent/server.py` | D2 | orchestrator, webhooks | M | FastAPI `/healthz`, `/webhooks/email/reply`, `/webhooks/sms/inbound`, `/webhooks/calcom` respond |
| `agent/llm/client.py` | D1 | config | M | OpenRouter call succeeds with prompt-cache headers; cost captured on span |
| `agent/llm/tools.py` | D1 stub, D2 body | state | S | Tool schemas validate inputs per [__specs/06 §3](/home/kg/Projects/10Academy/conversion-engine/__specs/06-agent-design.md) |
| `agent/llm/prompts/system.md` | D2 | style_guide, segments | S | Loads at boot; contains all constraint clauses |
| `agent/llm/prompts/classify_icp.md` | D2 | segments | XS | Output schema validates |
| `agent/llm/prompts/draft_outreach.md` | D2 | briefs | S | Produces subject + body + `signals_cited` JSON |
| `agent/llm/prompts/draft_followup.md` | D2 | draft_outreach | XS | Follow-up preserves tone markers |
| `agent/llm/prompts/classify_reply.md` | D2 | — | S | Returns `EmailReplyIntent` per [__specs/06 §5](/home/kg/Projects/10Academy/conversion-engine/__specs/06-agent-design.md) |
| `agent/llm/prompts/tone_check.md` | D2 | style_guide | XS | Returns `{pass, violations, suggestions}` |
| `agent/llm/prompts/bench_check.md` | D2 | bench_summary | XS | Extracts capacity claims with start/end offsets |

### `agent/enrichment/`

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `agent/enrichment/crunchbase.py` | D2 | data/crunchbase_odm | S | `by_domain("acme.ai")` returns a `CrunchbaseRecord` |
| `agent/enrichment/jobposts.py` | D2 | data/jobposts_snapshot | M | `velocity()` respects `qualifies_for_aggressive_hiring_claim` gate per [__specs/04 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/04-data-sources.md) |
| `agent/enrichment/layoffs.py` | D2 | data/layoffs_fyi | S | `find_by_company` returns expected match on fixture company |
| `agent/enrichment/leadership.py` | D2 | crunchbase | S | Detects a new-CTO signal on a fixture within 90-day window |
| `agent/enrichment/techstack.py` | D2 | BuiltWith/Wappalyzer | S | Degrades gracefully without API key |
| `agent/enrichment/ai_maturity.py` | D2 | jobposts, leadership, techstack | M | Produces 0–3 score + per-signal justification per [__specs/05 §5](/home/kg/Projects/10Academy/conversion-engine/__specs/05-signal-enrichment-pipeline.md) |
| `agent/enrichment/competitor_gap.py` | D2 | crunchbase, ai_maturity | M | Produces 5–10 peers + gap practices with confidence per [__specs/05 §6](/home/kg/Projects/10Academy/conversion-engine/__specs/05-signal-enrichment-pipeline.md) |
| `agent/enrichment/pipeline.py` | D2 | all above | M | Emits all three JSON artifacts under `data/briefs_cache/<uuid>/` in < 60 s p95 |

### `agent/icp/`

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `agent/icp/segments.yaml` | D0 | — | S | All 4 fixed segments present with qualifiers/disqualifiers per [__specs/03 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/03-icp-and-segments.md) |
| `agent/icp/classifier.py` | D2 | segments.yaml, brief | S | Abstention fires on fixture with ambiguous margins; segment-4 gate enforced |

### `agent/channels/`

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `agent/channels/email/send.py` | D2 | killswitch | S | `send_email` routes to sink when switch unset |
| `agent/channels/email/webhook.py` | D2 | orchestrator | M | Valid Resend reply payload transitions thread state |
| `agent/channels/email/templates/cold_signal_grounded.j2` | D2 | briefs | S | Renders with fixture brief; contains exactly one gap practice |
| `agent/channels/email/templates/cold_exploratory.j2` | D2 | — | XS | Renders without brief dependency |
| `agent/channels/email/templates/nurture_{1,2,3}.j2` | D2 | style_guide | S each | Preserves tone markers |
| `agent/channels/email/templates/scheduling_offer.j2` | D2 | calcom | XS | Contains Cal.com link + TZ annotation |
| `agent/channels/email/templates/post_book_confirmation.j2` | D2 | calcom booking | XS | Renders on fixture booking event |
| `agent/channels/email/templates/handoff_human.j2` | D2 | — | XS | Plain-text body with thread summary |
| `agent/channels/sms/send.py` | D2 | killswitch | S | 160-char cap enforced; splits at sentence boundary |
| `agent/channels/sms/webhook.py` | D2 | orchestrator | S | AT webhook schema → `SmsReply` |
| `agent/channels/voice/rig.py` | D7 bonus only | — | M | Skip unless stretch |

### `agent/integrations/`

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `agent/integrations/hubspot_mcp.py` | D2 | config | M | Idempotent upserts on `crunchbase_uuid` / `email`; rate-limit back-off wired |
| `agent/integrations/calcom.py` | D2 | config | M | `book()` attaches 150–250-word context brief per [__specs/09 §5](/home/kg/Projects/10Academy/conversion-engine/__specs/09-calendar-booking.md) |
| `agent/integrations/killswitch.py` | D0 | config | S | Every send goes through; audit log appended per [__specs/16 §8](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md) |

### `agent/policies/`

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `agent/policies/tone.py` | D2 | style_guide | S | Returns `pass=false` on style-guide violation fixture |
| `agent/policies/bench.py` | D2 | bench_summary | S | Blocks send when draft overclaims capacity (fixture: 8 Python engineers when bench shows 4) |
| `agent/policies/confidence.py` | D2 | briefs | S | Rejects "aggressive hiring" when `qualifies_for_aggressive_hiring_claim=false` |
| `agent/policies/channel_handoff.py` | D2 | — | S | Email→SMS rule only fires after explicit consent + `QUALIFIED` state |

## 4. `eval/` — τ²-Bench

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `eval/harness.py` | D1 | llm/client | M | `run_slice("dev", trials=5, method="day1_baseline")` returns `SliceResult` with 95 % CI |
| `eval/run_baseline.py` | D1 | harness | XS | `make baseline` invokes; writes `score_log.json` + `trace_log.jsonl` |
| `eval/baseline.md` | D3 | score_log.json | S | ≤ 400 words, covers reproduction + CI + cost + surprises |
| `eval/score_log.json` | D1 | harness | — | Contains `day1_baseline` + `reproduction_check` rows |
| `eval/trace_log.jsonl` | D1 + D5 | harness | — | ≥ 150 trajectories from dev slice by D3; + held-out traces by D6 |
| `eval/dev_slice.json` | D0 | τ²-Bench clone | XS | Points to 30 tasks |
| `eval/held_out_slice.json` | D0 | program delivery | XS | Points to 20 tasks; untouched until D5 |

## 5. `probes/` — Act III (D4)

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `probes/probe_library.md` | D4 | all probe yaml | L | ≥ 30 entries covering all 10 categories per [__specs/12 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/12-probe-library.md) |
| `probes/failure_taxonomy.md` | D4 | run_probes | M | Per-category trigger rates (pre-mechanism) |
| `probes/target_failure_mode.md` | D4 | taxonomy | S | Names one probe, derives business cost |
| `probes/probes/*.yaml` | D4 | fixtures | M × 10 categories | Each loads, fixture resolves, runs under `run_probes.py` |
| `probes/run_probes.py` | D4 | orchestrator, fixtures | M | Emits `failure_taxonomy.md`; CI-reproducible |

## 6. `method/` — Act IV (D5–D6)

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `method/mechanism.py` | D5 | chosen candidate policy | M | Implements `Mechanism` protocol per [__specs/06 §7](/home/kg/Projects/10Academy/conversion-engine/__specs/06-agent-design.md) |
| `method/method.md` | D6 | ablation_results | M | Covers rationale + hyperparameters + 3 ablations + Deltas A/B/C |
| `method/ablation_results.json` | D6 | harness, mechanism | S | pass@1 + CI + cost + p95 × 3 conditions × 3 ablations |
| `method/held_out_traces.jsonl` | D6 | harness on held-out | — | 3 conditions × ≥ 3 trials × 20 tasks |
| `method/stat_test.py` | D6 | held_out_traces | S | Outputs Delta A > 0, CI > 0, p < 0.05 |
| `method/stat_test_output.json` | D6 | stat_test | XS | Persisted for evidence_graph |

## 7. `memo/` — Act V (D7)

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `memo/evidence_graph.json` | D7 AM | all artifacts | M | Every numeric claim maps to a source per [__specs/14 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/14-memo-specification.md) |
| `memo/invoice_summary.json` | D7 AM | Langfuse export | S | Totals match trace sum ± $0.05 |
| `memo/template.tex` | D7 AM | — | S | Strict 2-page geometry |
| `memo/memo.md` | D7 PM | evidence_graph | L | Page 1 § and Page 2 § sections per [__specs/14 §2, §3](/home/kg/Projects/10Academy/conversion-engine/__specs/14-memo-specification.md) |
| `memo/memo.pdf` | D7 PM | memo.md | XS | `pdfinfo memo.pdf \| grep Pages` returns 2 |
| `memo/figures/*.{png,pdf}` | D7 PM | as needed | S | Embedded, attributed |

## 8. `market_space/` — optional stretch (D7 only if green)

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `market_space/market_space.csv` | D7 | enrichment over all ODM | M | One row per (sector, size, readiness) cell |
| `market_space/top_cells.md` | D7 | market_space.csv | S | 3–5 cells with allocation + risks |
| `market_space/methodology.md` | D7 | ≥ 30 hand-labels | M | Precision/recall confusion matrix |

## 9. `seed/` (read-only; provided D0)

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `seed/ICP.md`, `sales_deck.pdf`, `case_studies/`, `email_sequences/`, `pricing.yaml`, `bench_summary.yaml`, `sample_calls/`, `style_guide.md` | D0 | program delivery | — | All present per [__specs/02 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/02-repo-structure.md) |

## 10. `data/`

| Path | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `data/crunchbase_odm/companies.json` | D0 | `luminati-io/Crunchbase-dataset-samples` | XS | 1 001 records load |
| `data/layoffs_fyi/layoffs.csv` | D0 | layoffs.fyi download | XS | CSV parses; column schema matches [__specs/04 §3](/home/kg/Projects/10Academy/conversion-engine/__specs/04-data-sources.md) |
| `data/layoffs_fyi/aliases.yaml` | D2 | hand-curated | XS | ≥ 5 aliases for common fuzzy matches |
| `data/jobposts_snapshot/` | D0 | program delivery | XS | Early-April 2026 snapshot present |
| `data/briefs_cache/` | D2 auto | pipeline | — | 24 h TTL honoured |
| `data/killswitch_audit.jsonl` | D0 auto | killswitch | — | Append-only, line-hash chain |

## 11. `scripts/`

| File | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `scripts/setup_calcom.sh` | D0 | docker-compose | XS | `docker compose up -d calcom` + seeds event types |
| `scripts/setup_hubspot_sandbox.sh` | D0 | HubSpot account | XS | Creates custom properties from config list |
| `scripts/provision_resend.py` | D0 | Resend account | XS | Registers webhook, verifies sandbox domain |
| `scripts/route_sink.py` | D0 | killswitch | XS | Starts the staff-sink web receiver |
| `scripts/seed_synthetic_prospects.py` | D2 | Crunchbase ODM | S | Generates 8–10 synthetic prospects used by probes |
| `scripts/audit_seal.sh` | D0 stub, D5 body | eval/ | XS | Fails non-zero if any git-tracked tuning code references `held_out_slice.json` |
| `scripts/export_traces.py` | D3 | Langfuse | S | Pulls spans → `eval/trace_log.jsonl` |
| `scripts/latency_report.py` | D3 | trace_log | XS | Emits p50/p95 over ≥ 20 traces per [__specs/10 §6](/home/kg/Projects/10Academy/conversion-engine/__specs/10-observability.md) |
| `scripts/lint_memo.py` | D7 | evidence_graph | S | Exits non-zero if any number in memo.md unresolved or if PDF ≠ 2 pages |
| `scripts/lint_logs.py` | D0 | — | XS | Fails on secret-regex hits in jsonl files |
| `scripts/end_of_week_purge.sh` | D7 | — | XS | Deletes seed/ from personal infra, writes audit |

## 12. `tests/`

| Path | Day | Predecessor | Effort | Acceptance test |
|------|-----|-------------|--------|-----------------|
| `tests/unit/` | D2 | corresponding module | M across module | Each `agent/*` module has at least one unit test covering its acceptance criterion |
| `tests/integration/test_e2e_prospect.py` | D3 | full stack | S | Fixture prospect COLD → BOOKED with sink routing |
| `tests/fixtures/` | D0/D2 | — | S | Synthetic prospects + signal overrides + email payloads |

---

## 13. Reusable utilities to avoid duplicating

Nothing exists in the repo yet. All code is greenfield. For each **external** library, prefer the following:

| Need | Library | Notes |
|------|---------|-------|
| Config loading | `pydantic-settings` | `.env` + yaml overlay |
| LLM client | `openai`-compatible client against OpenRouter base URL | Prompt cache via headers |
| HTTP server | `fastapi` + `uvicorn` | Single app serves all webhooks |
| Playwright crawler | `playwright` (Chromium only) | `robots.txt` respected; `User-Agent` declared |
| CSV parsing (layoffs) | stdlib `csv` + pydantic record | Avoid pandas unless memo stats need it |
| Date handling | stdlib `datetime` + `zoneinfo` | Calendar TZ probe coverage |
| PDF render | `pandoc` CLI via subprocess + LaTeX template | Deterministic 2-page output |
| Stat test | stdlib `random` + numpy only for percentile | No heavy ML deps needed |
| Langfuse SDK | `langfuse` Python client | Fallback writes to `data/local_traces.jsonl` |
| HubSpot MCP | MCP client SDK (per [__specs/08 §3](/home/kg/Projects/10Academy/conversion-engine/__specs/08-hubspot-integration.md)) or REST fallback | See O8 in [00-decisions.md](00-decisions.md) |

---

## 14. Parallelization guidance

D2 is the biggest parallel day. Lanes that can proceed concurrently once D0 stubs exist:

- **Lane A:** `agent/enrichment/*` (1 engineer, M–L total).
- **Lane B:** `agent/channels/email/*` + `agent/channels/sms/*` (1 engineer, M total).
- **Lane C:** `agent/integrations/*` + `agent/policies/*` (1 engineer, M total).
- **Lane D:** `agent/orchestrator.py` + prompts (1 engineer after Lane A's brief schemas stabilise, M).

A solo engineer does them sequentially in the order A → C → B → D. Estimated solo wall-clock: 8–10 h on D2; budget D3 AM to catch up.
