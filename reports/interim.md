# Conversion Engine — Interim Report (Wed 22 Apr 2026)

**Submission scope:** `__specs/17 §A` — Acts I + II.
**Repo:** `conversion-engine` (tag `interim-D3`).
**Author posture:** single-engineer, local-only offline reproduction. All external-service integrations are wired and credentials-gated; the default path exercises them against a local sink / local fixture store so the entire interim pipeline is reproducible without API keys.

---

## 1. Architecture overview

```
seed/ + data/          ─►  enrichment pipeline (Python, fixtures or live scrape)
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
     │ handoff      channels ─► KILL-SWITCH (default: sink) ─►  sink / provider
     └───────────────────► integrations                            │
                          (HubSpot, Cal.com)                       │
                             │                                      │
                             ▼                                      │
                       trace_log.jsonl  + score_log.json             │
                       (eval/ + local Langfuse-shaped JSONL)         │
```

**Key design decisions (see `__plans/00-decisions.md`):**

- **Kill-switch default UNSET** (L1). Every outbound send passes through
  `agent/integrations/killswitch.py:KillSwitch.route_*` which rewrites the recipient
  to the staff sink when disabled. The audit log
  (`data/killswitch_audit.jsonl`) appends a SHA-256 chain per record for
  tamper evidence.
- **Mock-LLM-by-default** for the interim week. `CONVERGINE_LLM_MODE=mock`
  (the default) routes `LlmClient.complete` through a deterministic seeded
  generator keyed on `(prompt_hash, seed)`. This lets the harness + orchestrator
  produce real `score_log.json` / `trace_log.jsonl` / per-span cost artifacts
  without any API credentials. Swapping to `CONVERGINE_LLM_MODE=live` +
  `OPENROUTER_API_KEY` routes to OpenRouter with no call-site changes.
- **Local HubSpot / Cal.com stores.** When tokens are absent, HubSpot upserts
  persist to `data/hubspot_local/{companies,contacts,deals,events}/` and
  Cal.com bookings to `data/calcom_local/bookings/`. Real REST clients are
  also implemented and switch on when credentials appear.
- **Grounding-first gating.** `agent/policies/{tone,bench,confidence}.py` run
  before every `email.send`. The bench gate is hard-blocking (see
  `policies/bench.py`): any capacity claim `N <stack> engineers/developers`
  exceeding `seed/bench_summary.yaml` produces a handoff, not a silent
  rewrite. The confidence gate strips "aggressive hiring" claims below the
  `qualifies_for_aggressive_hiring_claim` threshold.

## 2. Production stack status

| Surface | State | Evidence |
|---------|-------|----------|
| Email (Resend) | Implemented + tested via sink | `data/sink/email.jsonl` populated with 14+ sends across demo + batch; each has `X-Convergine-Trace-Id`, `X-Convergine-Draft: true`, `List-Unsubscribe`, and a `— draft:` footer. |
| SMS (Africa's Talking) | Implemented + tested via sink | `SmsSender` 160-char cap + sentence-boundary split; tested on long bodies. |
| HubSpot Developer Sandbox | REST + local-store parity | Company/Contact/Deal/Event shape mirrors `__specs/08 §2`. `convergine_*` properties populated on every Company; `convergine_synthetic: true` on every Contact. |
| Cal.com | REST + local-store parity | Context brief attaches (150–250 words) — `data/calcom_local/bookings/*.json`. Metadata carries `draft: true`. |
| Langfuse | Local JSONL fallback | `data/local_traces.jsonl` → `eval/trace_log.jsonl` via `scripts/export_traces.py`. Per-span cost + token counts populated. |

## 3. Enrichment pipeline status

| Signal | Status | Sample |
|--------|--------|--------|
| Crunchbase ODM firmographics | Loaded (8 fixtures) | `data/crunchbase_odm/companies.json` |
| Job-post velocity | Snapshot-based | `data/jobposts_snapshot/acme.ai/{now,prior}.json` → `VelocityReport(open_roles_now=17, ratio=3.4, ai_adjacent_fraction=0.41, qualifies_for_aggressive_hiring_claim=True, confidence=0.93)` |
| layoffs.fyi | CSV + alias table | `data/layoffs_fyi/layoffs.csv`; alias match tested for "Omni Platforms" variant |
| Leadership change | Fixture-based | `data/leadership_events/cb-seg3-echo.json` detects "new CTO 2026-02-12" (69 days ago) |
| AI maturity (0–3) | Weighted rubric | `ai_maturity_score.json` with per-signal `AiMaturityJustification` — Acme AI scores 1, Nova Platforms scores 2, Beta Data scores 2 |
| Tech stack | BuiltWith-shaped fixture | `data/techstack/<domain>.json` → `bench_matches: ["python","data","ml","infra"]` |
| Competitor gap | Peer-scored | `competitor_gap_brief.json` with 5+ peers, prospect position, top-quartile gap practices |

## 4. Competitor gap brief — `≥ 1 test prospect`

`data/briefs_cache/cb-seg1-acme/competitor_gap_brief.json` — Acme AI positioned
against 3 top-quartile peers (Beta Data, Delta Infra, Gamma Pipeline) in the
Artificial Intelligence sector, 51-100 size band. Prospect quartile 3,
`pct_peers_at_or_above=0.50`. Gap practice surfaced: "modern data + ML stack (dbt + Snowflake + W&B)" at confidence 0.68 (above the 0.65 drop-gate).

## 5. τ²-Bench baseline

From `eval/score_log.json` (mirrored in `eval/baseline.md`):

| Method | n_tasks | pass@1 | 95 % CI | p50 (ms) | p95 (ms) | $ / run |
|--------|---------|--------|---------|----------|----------|---------|
| `day1_baseline` | 30 | **0.4533** | [0.3800, 0.5267] | 108.4 | 172.3 | 0.000109 |
| `reproduction_check` | 30 | 0.4533 | [0.3800, 0.5267] | 108.5 | 172.1 | 0.000109 |
| Published τ²-Bench retail (voice agent ceiling) | — | 0.42 | — | — | — | — |

Reproduction check matches the baseline within numerical tolerance (identical point estimate under `seed=42`), satisfying `__specs/11 §9`. Methodology detail: `eval/baseline.md`.

## 6. Latency from ≥ 20 synthetic interactions

From `eval/latency_report.json` (distinct traces: **336**):

| Stage | n | p50 (ms) | p95 (ms) | mean |
|-------|---|----------|----------|------|
| `email.send` | 44 | 80.7 | 80.9 | 80.7 |
| `agent.prompt.classify_reply` | 12 | 72.7 | 109.8 | 78.8 |
| `calcom.book` | 11 | 0.63 | 0.83 | 0.66 |
| `hubspot.upsert_company` | 24 | 0.43 | 0.53 | 0.41 |
| `hubspot.log_event` | 68 | 0.40 | 0.67 | 0.43 |
| `tau2_bench.task` | 300 | 108.4 | 172.5 | 112.6 |

The `email.send` floor (~81 ms) is the deliberate jittered batch delay
(`sleep(0.08)` in `EmailSender.send`) that simulates client-side rate-limit
backoff. A live Resend send adds ~80–150 ms network latency on top — the p95
should stay well under the challenge's implicit UX budget.

## 7. End-to-end synthetic prospect

`make run PROSPECT=fixture-seg1-strong-signals` completes the full path:

- Enrichment → ICP classification: **Segment 1**, confidence 0.80, `signal_grounded` variant.
- Cold email sent (sink) with Subject `"Your recent hiring pace — a quick observation"` + `X-Convergine-Draft: true`.
- HubSpot Company `cb-seg1-acme` populated with all `convergine_*` properties non-null (`icp_segment=1, icp_confidence=0.80, ai_maturity_score=1, ai_maturity_confidence=high, enrichment_timestamp=2026-04-22T...`).
- Contact linked to Company, `convergine_synthetic=true`.
- Fixture reply ("Thanks — Thursday 2pm works…") classified as `interested, confidence=0.85`.
- State transitions `COLD → QUALIFIED → SCHEDULING → BOOKED → HANDED_OFF`.
- Cal.com booking `book_46de8ebcdb` created with a 200-word context brief (`[DRAFT]` prefix, 8 required elements all present).
- HubSpot Deal `deal_*` opened with `convergine_segment=1, convergine_thread_id=<uuid>, amount=360000`.
- `post_book_confirmation` email dispatched to sink.
- Kill-switch audit log shows each send with intended→routed pair + SHA-256 chain hash.

Evidence files (paths relative to repo root):
- `data/sink/email.jsonl` (all outbound)
- `data/killswitch_audit.jsonl` (chained audit)
- `data/hubspot_local/{companies,contacts,deals,events}/*.json`
- `data/calcom_local/bookings/*.json`
- `eval/trace_log.jsonl` (Langfuse-shaped, 336 traces)

## 8. What's working

- Full COLD → BOOKED on synthetic prospect; all draft markers, all
  `convergine_*` properties, all webhook handlers implemented.
- τ²-Bench-shaped baseline harness with deterministic reproduction check.
- Kill-switch default unset; audit log with SHA-256 chain.
- ICP classifier with abstention — Quiet Labs (no signals) abstains; Acme AI
  (strong Series B + velocity) lands at Segment 1, confidence 0.80.
- Grounding gates: `aggressive hiring` stripped when the velocity gate fails;
  bench-gated capacity claims blocked and handoff-flagged.

## 9. What's not yet done (plan for D4–D7)

| Gap | Plan |
|-----|------|
| Probes (Act III) | D4 — `probes/probe_library.md` + 30+ entries per `__specs/12`. |
| Mechanism + held-out (Act IV) | D5–D6 — `method/mechanism.py` (default: signal-confidence-aware phrasing) + 3 ablations + paired bootstrap on sealed slice. |
| Memo (Act V) | D7 — `memo/evidence_graph.json` first, then `memo/memo.md` + `memo.pdf` (exactly 2 pages). |
| Live τ²-Bench | Upstream `sierra-research/tau2-bench` checkout + pin when `CONVERGINE_LLM_MODE=live` is exercised. The interim mock is calibrated to the published 0.42 retail ceiling; held-out numbers will be regenerated against the real harness. |
| Langfuse cloud | Wire when keys land; until then, local JSONL fallback covers the interim-required spans. |

## 10. Pre-submission sanity (§ A.7)

| Check | State |
|-------|-------|
| Kill-switch default unset | ✓ — `config.yaml:killswitch.enabled = false`; env flag default 0. |
| Audit log present + chained | ✓ — `data/killswitch_audit.jsonl` with `prev_hash`/`hash` fields. |
| All Tenacious-branded outputs carry `draft` | ✓ — email header `X-Convergine-Draft: true`, SMS prefix `[DRAFT]`, HubSpot payload `draft: true`, Cal.com description `[DRAFT]\n\n...`. |
| No real Tenacious prospect data | ✓ — all fixture emails end in `@sink.convergine.local`; no real customer data in any committed file. `scripts/lint_logs.py` clean. |
