# 01 — Interim Critical Path (D0 → D3)

**Purpose:** Execute Acts I + II and land the **interim submission** at the end of D3.

**Locked inputs:** [00-decisions.md](00-decisions.md), [05-work-breakdown.md](05-work-breakdown.md).

**Acceptance target:** every box in [__specs/17 §A](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md) ticked before D3 21:00 local. Required PDF published to a public Google Drive link; repo tagged `interim-D3`.

---

## D0 — Pre-flight (≈ 4 h)

Runs through the Day-0 table in [__specs/10 §0 equivalent / __specs/17 §A.7 sanity](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md). Completes before any coding begins. Parallelisable across a pair.

### D0.1 — External-service provisioning

| Task | Done when |
|------|-----------|
| Provision Resend free tier + verify sandbox domain + register reply webhook | One test email to your own address lands; webhook POSTs to `http://localhost:8000/webhooks/email/reply` with a valid signature |
| Provision Africa's Talking sandbox + virtual shortcode + keyword prefix | One test SMS routed to webhook handler |
| Provision HubSpot Developer Sandbox + Private App token + run `scripts/hubspot_bootstrap.py` + start in-repo MCP server + create test contact | `scripts/hubspot_smoke.py` (spawns MCP server, calls `upsert_contact`) returns a contact id |
| `docker compose up -d calcom postgres` + seed 3 event types | `POST /bookings` on the `discovery-30` slug succeeds |
| Create Langfuse cloud project + generate keys | One test trace visible in UI |
| OpenRouter API key + first smoke call | Smoke call returns; cost captured on Langfuse span |
| Clone `sierra-research/tau2-bench` + pin tag in `config.yaml` | `git describe --tags` matches pin; retail domain importable |
| Download Crunchbase ODM sample (`luminati-io/Crunchbase-dataset-samples`) | 1 001-record JSON under `data/crunchbase_odm/companies.json` |
| Snapshot `layoffs.fyi` CSV | File under `data/layoffs_fyi/layoffs.csv`; parses |
| Unpack jobposts early-April 2026 snapshot | Under `data/jobposts_snapshot/`; ≥ N companies loaded |
| Read seed materials (style guide, bench summary, pricing, email sequences) | Notes extracted into `agent/llm/prompts/system.md` drafts |
| Sign data-handling policy acknowledgement | Filed with program staff |

**Close open decisions as you go:** O1 (email provider), O2 (dev-tier model), O7 (concurrency), O8 (HubSpot mode). Update [00-decisions.md](00-decisions.md) when each closes.

### D0.2 — Repo scaffolding + stub-first

All files in [05-work-breakdown.md](05-work-breakdown.md) marked **D0 stub** exist as Python files or YAML with:

- Module docstring describing purpose + pointer into `__specs/`.
- `raise NotImplementedError("see __plans/05-work-breakdown.md row <N>")` for methods.
- Dataclass / pydantic models filled in where the schema is decided (they are the seams other lanes depend on).

Commit these in one PR titled `D0: scaffolding`. Tag `d0-complete`.

### D0.3 — Safety rails

- `integrations/killswitch.py` body implemented + wired. Default unset. Audit log appending with hash chain.
- `scripts/route_sink.py` running locally to receive sink emails/SMS.
- `scripts/lint_logs.py` in CI.
- Pre-commit hook: `grep -n 'draft_approved.*True' agent/` returns zero hits (nothing hard-codes approval).
- README drafted — architecture, setup, kill-switch section ([__specs/16 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md)).

### D0 exit gate

Do not start D1 until:

- [ ] `python -m agent.main --healthcheck` returns 0 (config loads, all stub imports resolve).
- [ ] `curl localhost:8000/healthz` returns `{status: "ok"}`.
- [ ] `docker compose ps` shows Cal.com + Postgres healthy.
- [ ] Langfuse UI shows one test trace.
- [ ] HubSpot sandbox has the `convergine_*` custom properties created on Company and Contact.
- [ ] Kill-switch audit log has its first entry (from a smoke test).
- [ ] [00-decisions.md](00-decisions.md) has O1, O7, O8 closed; O2 can remain open until D1.

---

## D1 — Act I: τ²-Bench baseline (≈ 6 h)

Reference: [__specs/11 §5](/home/kg/Projects/10Academy/conversion-engine/__specs/11-tau2-bench-harness.md).

### D1.1 — Wire the harness

- Implement `eval/harness.py` — `Tau2BenchHarness` with `run_slice`, `score`.
- Implement `eval/run_baseline.py` — CLI entry for `make baseline`.
- Instrument every task run with a Langfuse root span; tag `slice, task_id, method_name=day1_baseline, trial`.

### D1.2 — Close O2 (dev-tier model)

Run one dry task against Qwen3-Next-80B-A3B. If it produces a coherent trajectory with correct tool-call formatting at seed 42, lock O2 to Qwen. Otherwise swap to DeepSeek V3.2. Update [00-decisions.md](00-decisions.md).

### D1.3 — Run the baseline

```
make baseline
```

- 30 dev tasks × 5 trials = 150 trajectories.
- Bootstrap 95 % CI over per-task pass@1 (1 000 resamples).
- Emit `eval/score_log.json` with two rows: `day1_baseline` and `reproduction_check` (rerun at same seed; CI width should shrink slightly as the variance gets the same source).
- Emit `eval/trace_log.jsonl` with full trajectories.
- Record cost per run, p50/p95 latency per task.

### D1.4 — Author `baseline.md`

Max 400 words covering:

1. What was reproduced (retail domain + pinned tag + dev-tier model).
2. Confidence interval (point ± 95 %).
3. Cost per run and total D1 spend.
4. Unexpected behaviour (any task that consistently failed, any tool-call formatting issues).

### D1 exit gate

- [ ] `score_log.json` has both rows, each with non-null CI.
- [ ] `trace_log.jsonl` has ≥ 150 lines.
- [ ] `baseline.md` ≤ 400 words.
- [ ] D1 LLM spend ≤ $1 (well under $4 Days 1–4 envelope).
- [ ] Published τ²-Bench retail reference (~42 % ceiling) noted in `baseline.md`.

---

## D2 — Act II: production stack + enrichment (≈ 10 h solo; ≈ 5 h paired)

Reference: [__specs/01](/home/kg/Projects/10Academy/conversion-engine/__specs/01-architecture.md), [__specs/05](/home/kg/Projects/10Academy/conversion-engine/__specs/05-signal-enrichment-pipeline.md), [__specs/06–09](/home/kg/Projects/10Academy/conversion-engine/__specs/06-agent-design.md).

### D2 Lane A — Enrichment pipeline

Implementation order:

1. `enrichment/crunchbase.py` (load ODM, firmographics, funding events).
2. `enrichment/layoffs.py` (CSV parser + alias table).
3. `enrichment/jobposts.py` (snapshot reader + velocity; Playwright for ≤ 200 live companies).
4. `enrichment/leadership.py` (press + Crunchbase key-people diff).
5. `enrichment/techstack.py` (BuiltWith optional).
6. `enrichment/ai_maturity.py` (0–3 scorer + justification; one dev-tier LLM call).
7. `enrichment/competitor_gap.py` (peer selection + gap practices).
8. `enrichment/pipeline.py` (orchestrator emitting the three JSON artifacts).

Milestone: `python -m agent.main --enrich <uuid>` produces `hiring_signal_brief.json`, `ai_maturity_score.json`, `competitor_gap_brief.json` under `data/briefs_cache/<uuid>/`.

### D2 Lane B — Channels

1. `channels/email/send.py` + killswitch wiring (must pass acceptance test: unset → sink).
2. `channels/email/templates/` (cold signal-grounded, cold exploratory, nurture 1/2/3, scheduling offer, post-book confirmation, handoff).
3. `channels/email/webhook.py` (reply classification hook).
4. `channels/sms/send.py` (160-char cap, sentence-boundary split).
5. `channels/sms/webhook.py` (AT sandbox schema).

Milestone: fixture email flows out → sink → webhook replay → thread transitions.

### D2 Lane C — Integrations + policies

1. `integrations/hubspot_mcp.py` (upserts + `log_event`; backoff).
2. `integrations/calcom.py` (availability + book + context brief attach).
3. `policies/tone.py`, `bench.py`, `confidence.py`, `channel_handoff.py`.

Milestone: a fixture draft is tone-checked + bench-checked + confidence-aware-phrased before send.

### D2 Lane D — Orchestrator + prompts

1. Populate `agent/llm/prompts/*.md` (system, classify_icp, draft_outreach, draft_followup, classify_reply, tone_check, bench_check).
2. `agent/llm/tools.py` tool schemas.
3. `agent/orchestrator.py` state machine.
4. `agent/server.py` FastAPI webhooks.
5. `agent/icp/classifier.py` rules-based classifier with abstention.

Milestone: `python -m agent.main --prospect <uuid>` walks COLD → NURTURE_1 on fixture data.

### D2 exit gate

- [ ] Lanes A–D all pass their milestone.
- [ ] One synthetic prospect has a complete enrichment bundle.
- [ ] HubSpot sandbox shows a Company + Contact from a fixture run.
- [ ] Cal.com shows a test booking with the context brief attached.
- [ ] D2 LLM spend ≤ $2 cumulative.

### D2 16:00 — PDF report scaffold

By 16:00 local on D2, author `reports/interim.md` with all section headings and placeholder tables, before the numbers are final. Placeholders are `<filled at D3>`. This prevents D3 from being consumed by prose work.

---

## D3 — Interim submission (≈ 8 h including polish)

Reference: [__specs/17 §A](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md).

### D3.1 — End-to-end synthetic prospect (morning)

Run the full flow:

```
make run PROSPECT=fixture-seg1-strong-signals
```

The prospect flows COLD → NURTURE (maybe) → QUALIFIED → SCHEDULING → BOOKED. Verify:

- HubSpot Company populated with all `convergine_*` custom properties non-null.
- HubSpot Contact linked; Conversation Events list shows all stages.
- Deal opened at `BOOKED`; `convergine_segment` and `convergine_thread_id` set.
- Cal.com booking created with the context brief attached (150–250 words).
- Kill-switch audit log shows the outbound routed to sink.
- Draft markers present in email headers, SMS body, HubSpot event payloads, Cal.com metadata.

### D3.2 — Volume + latency run

Run 20+ synthetic prospects (from `scripts/seed_synthetic_prospects.py`) through at least the enrichment + cold-email + reply paths.

```
make run-batch N=20
scripts/latency_report.py > eval/latency_report.json
```

Verify `eval/latency_report.json` has p50/p95 for `email.send`, `sms.send`, `agent.prompt.draft_outreach`, `enrich.full` over ≥ 20 distinct trace ids.

### D3.3 — Report polish (early afternoon)

Fill the placeholders in `reports/interim.pdf`:

- Architecture overview ([__specs/01](/home/kg/Projects/10Academy/conversion-engine/__specs/01-architecture.md)).
- Production stack status (all services verified running, with screenshots).
- Enrichment pipeline status (all 7 signals producing output, with a sample `hiring_signal_brief.json`).
- Competitor gap brief status (≥ 1 test prospect).
- τ²-Bench baseline score + methodology (copy from `baseline.md`).
- p50/p95 latency table from `latency_report.json`.
- What is working / what is not / plan for D4–D7.

### D3.4 — Gate checks (T-4h, T-2h, T-1h before 21:00 local)

| Gate | Check | Action if fail |
|------|-------|----------------|
| T-4h | Is e2e prospect green? | Apply cut-list item 1 (drop SMS inbound) |
| T-2h | Does `evidence_graph.json` have enough for the memo scaffold? | Apply cut-list item 2 (stub competitor gap) |
| T-1h | Is PDF ≤ 2 pages for interim report? (Interim is flexible length; main memo is strict 2 pages) | Apply cut-list item 6: drop MCP → REST if HubSpot is the blocker |
| T-30m | Manual audit: grep for real prospect addresses / unmarked drafts / secrets in logs | **Block submission**, fix, re-audit |

### D3.5 — Submit

- Tag repo `interim-D3`. Push to `main`.
- Upload `reports/interim.pdf` to a public Google Drive link (no login required).
- Confirm submission form entry references both the repo URL and the Drive link.

### D3 exit gate (final checks before submit)

- [ ] `README.md` at root with architecture + setup + kill-switch section.
- [ ] `agent/`, `eval/`, `baseline.md` all present per [__specs/17 §A.2–A.4](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md).
- [ ] `score_log.json` + `trace_log.jsonl` ≥ 150 trajectories.
- [ ] Interim PDF covers every A.5 bullet with real numbers.
- [ ] ≥ 20 real email/SMS interactions in trace log with p50/p95 reported.
- [ ] One synthetic prospect end-to-end verified on screen + in screenshots.
- [ ] Kill-switch default unset; audit log present; no real data committed.
- [ ] Repo public; tag `interim-D3` pushed; Drive link accessible without login.

---

## Cut-list (apply in this sequence if running late)

1. **Drop SMS inbound webhook** — keep outbound only; note in report. Preserves A.6 requirement because A.5 only says Africa's Talking verified running.
2. **Stub `competitor_gap_brief.json`** — ship `hiring_signal_brief.json` alone; mark the gap brief as "landing D4". A.5 "≥ 1 test prospect" still met minimally if we keep the stub structure.
3. **Drop `reproduction_check` row** — one `day1_baseline` row with CI suffices for a literal reading of A.3.
4. **Voice rig** — already out of scope per [00-decisions.md](00-decisions.md) §3.
5. **Drop Langfuse on production stack** — keep Langfuse on τ²-Bench only; derive production p50/p95 from FastAPI middleware logs.
6. **Drop HubSpot MCP** — use REST directly on the same interface. [__specs/08](/home/kg/Projects/10Academy/conversion-engine/__specs/08-hubspot-integration.md) is interface-level; either transport satisfies it.

**Never cut:**
- Kill-switch default unset.
- Draft markers on every outbound.
- τ²-Bench baseline with 95 % CI.
- One full end-to-end synthetic prospect.
- Trace log that the memo's evidence graph will cite.

---

## Time budgets

| Phase | Wall clock | LLM spend |
|-------|-----------|-----------|
| D0 | 4 h | < $0.50 |
| D1 | 6 h | < $1.00 |
| D2 | 10 h solo / 5 h paired | < $2.00 |
| D3 | 8 h | < $0.50 |
| **Through interim** | **≈ 28 h solo** | **≤ $4 (fits dev-tier D1–D4 envelope)** |

Solo engineers behind on D2 should paired-swarm lanes A + D on D3 morning; lanes B + C can complete post-interim and land in the final submission.
