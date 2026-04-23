# Conversion Engine — Implementation Plan Index

Calendar- and file-level execution plan for building the system defined under [`__specs/`](../__specs/). Days are labeled **D0 → D7** relative to the engineer's start; the challenge's interim submission lands at end of **D3** and the final at end of **D7**.

> Plan author's reference point: this plan was drafted on 2026-04-22 (the challenge document's literal interim date). The schedule itself is **relative** — the engineer chooses their D0.

## How to use this directory

1. Read [00-decisions.md](00-decisions.md) first — it is the single source of truth for all locked and open choices. Every other file cites it.
2. Skim [05-work-breakdown.md](05-work-breakdown.md) to see every file that must exist in the finished repo, keyed to a day + effort estimate.
3. Work daily from [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md) → [02-d4-act3-probes.md](02-d4-act3-probes.md) → [03-d5-d6-act4-mechanism.md](03-d5-d6-act4-mechanism.md) → [04-d7-act5-memo-demo.md](04-d7-act5-memo-demo.md).
4. When a risk trigger fires, consult [06-risks.md](06-risks.md) and invoke the mitigation named in the owning file.

## Files

| # | File | Purpose |
|---|------|---------|
| — | [README.md](README.md) | This index + status board |
| 00 | [00-decisions.md](00-decisions.md) | Locked + open decisions; single source of truth |
| 01 | [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md) | Pre-flight (D0) → Act I (D1) → Act II (D2–D3) → **Interim submit** |
| 02 | [02-d4-act3-probes.md](02-d4-act3-probes.md) | Act III: ≥ 30 probes + failure taxonomy + target failure mode |
| 03 | [03-d5-d6-act4-mechanism.md](03-d5-d6-act4-mechanism.md) | Act IV: mechanism + ablations + held-out eval + stat test (Delta A p < 0.05) |
| 04 | [04-d7-act5-memo-demo.md](04-d7-act5-memo-demo.md) | Act V: memo + evidence graph + demo video + **Final submit** |
| 05 | [05-work-breakdown.md](05-work-breakdown.md) | File-level WBS: every file → day → effort → acceptance test |
| 06 | [06-risks.md](06-risks.md) | Risk register with trigger metrics, thresholds, owners |

## Interim submission status board (mirror of [__specs/17 §A](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md))

> Tick as you go. Owner: [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md).

- [ ] `README.md` at root with architecture + setup + **kill-switch section**
- [ ] `.env` configured from `__specs/.env.example`
- [ ] `config.yaml` configured from `__specs/config.example.yaml`
- [ ] `agent/` — email, SMS, HubSpot MCP, Cal.com, enrichment pipeline
- [ ] `agent/requirements.txt` (or `pyproject.toml`)
- [ ] `eval/` — τ²-Bench harness + `score_log.json` + `trace_log.jsonl`
- [ ] `eval/baseline.md` ≤ 400 words
- [ ] Resend verified running (email)
- [ ] Africa's Talking sandbox verified running (SMS warm-lead)
- [ ] HubSpot Developer Sandbox verified running
- [ ] Cal.com verified running (`docker compose`)
- [ ] Langfuse verified running
- [ ] Enrichment: Crunchbase ODM + job-post velocity + layoffs.fyi + leadership + AI maturity (0–3) all producing output
- [ ] `competitor_gap_brief.json` generated for ≥ 1 test prospect
- [ ] τ²-Bench baseline with 95 % CI reported
- [ ] p50/p95 latency from **≥ 20** real email/SMS interactions
- [ ] One synthetic prospect: COLD → BOOKED (HubSpot populated, Cal.com booked)
- [ ] Kill-switch default unset; audit log present
- [ ] All Tenacious-branded outputs carry `draft` marker
- [ ] No real Tenacious data in any committed file
- [ ] Interim PDF report published to public Google Drive link
- [ ] Repo tagged `interim-D3`

## Final submission status board (mirror of [__specs/17 §B](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md))

> Tick as you go. Owners: [02](02-d4-act3-probes.md), [03](03-d5-d6-act4-mechanism.md), [04](04-d7-act5-memo-demo.md).

### Probes
- [ ] `probes/probe_library.md` with ≥ 30 structured probes across 10 categories
- [ ] `probes/failure_taxonomy.md` with pre- and post-mechanism trigger rates
- [ ] `probes/target_failure_mode.md` — Tenacious-specific cost derivation

### Method
- [ ] `method/method.md` — mechanism + rationale + hyperparameters + 3 ablations
- [ ] `method/ablation_results.json` — pass@1 + 95 % CI + cost/task + p95 latency for 3 conditions
- [ ] `method/held_out_traces.jsonl` — raw traces from the 3 conditions
- [ ] `method/stat_test_output.json` — **Delta A > 0, CI > 0, p < 0.05**
- [ ] `memo/evidence_graph.json` — every numeric memo claim mapped to source

### Memo (`memo/memo.pdf` — exactly 2 pages)

**Page 1:**
- [ ] Executive summary (3 sentences)
- [ ] τ²-Bench pass@1 table (published / Day-1 / our method, each with 95 % CI)
- [ ] Cost per qualified lead (target < $5, penalty > $8)
- [ ] Speed-to-lead delta (Tenacious manual 30–40 % vs. measured)
- [ ] Competitive-gap outbound: signal-grounded vs. exploratory reply-rate delta
- [ ] Annualised dollar impact at 3 adoption scenarios
- [ ] Pilot scope: 1 segment, 1 volume, 1 budget, 1 success criterion

**Page 2:**
- [ ] 4 failure modes τ²-Bench doesn't capture (Tenacious-specific)
- [ ] Public-signal lossiness (quiet-sophisticated / loud-shallow)
- [ ] Gap-analysis risks (with example)
- [ ] Brand-reputation unit economics (1 000 emails × 5 % wrong)
- [ ] One honest unresolved failure from probes
- [ ] Kill-switch trigger metric + threshold

### Demo video (≤ 8 min, public, no login)
- [ ] Live email e2e: signal-grounded → reply → qualify → Cal.com book
- [ ] Hiring signal brief + competitor gap brief (confidence scores visible)
- [ ] HubSpot contact populating live
- [ ] Email → SMS handoff for warm lead
- [ ] Grounded-honesty refusal (weak signal → no "aggressive hiring")
- [ ] Segment-classification trap handled correctly
- [ ] τ²-Bench run with trace visible
- [ ] Probe → concrete fix walkthrough
- [ ] Voice rig (bonus, optional)

### Stretch (optional)
- [ ] Market-space map per [__specs/15](/home/kg/Projects/10Academy/conversion-engine/__specs/15-market-space-map.md)

### Final packaging
- [ ] Incognito smoke-test of video link
- [ ] `scripts/lint_memo.py` green
- [ ] `scripts/lint_logs.py` green
- [ ] Pre-submit audit sweep per [04 §D7.10](04-d7-act5-memo-demo.md)
- [ ] Repo tagged `final-D7`
- [ ] PDF on public Drive
- [ ] Submission form filed
- [ ] End-of-week purge executed; audit log written
- [ ] API keys revoked

## Budget tracker

Update after each day. Target envelope: **< $20 per trainee for the week**.

| Day | Activity | Target spend | Actual | Cumulative |
|-----|----------|--------------|--------|-----------|
| D0 | Provisioning + smoke tests | < $0.50 | | |
| D1 | τ²-Bench baseline | < $1.00 | | |
| D2 | Stack + enrichment | < $2.00 | | |
| D3 | Interim polish + e2e + latency batch | < $0.50 | | |
| D4 | Probe runs (dev-tier) | < $0.30 | | |
| D5 | Mechanism dev + dry run | < $1.00 | | |
| D6 | Held-out eval (eval-tier, 3 conditions × 5 trials × 20) | < $12.00 | | |
| D7 | Memo + demo | < $1.00 | | |
| | **Week total** | **< $20.00** | | |

Cost-per-qualified-lead (memo headline): **target < $5.00, penalty > $8.00** ([__specs/10 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/10-observability.md)).

## Escalation protocol

| Situation | Action |
|-----------|--------|
| Risk trigger in [06](06-risks.md) fires | Invoke the named mitigation in the owning file immediately — no deliberation |
| Kill-switch flag flipped unintentionally | Revert in `config.yaml`; purge audit log scanned for any routed-to-real events |
| Real Tenacious prospect data found in repo | Stop all outbound; `git rm` and force-push-with-care; notify program staff within 2 h |
| Delta A trending toward p ≥ 0.05 during D6 | Execute R4 ladder; never fabricate |
| Eval-tier spend projected > $12 | R3 mitigation: 5 → 3 trials, then model swap, then stop |

## Cross-references

| You need… | Go to |
|-----------|-------|
| What to do right now | the latest incomplete `D#` section in [01](01-d0-to-d3-interim-path.md) → [04](04-d7-act5-memo-demo.md) |
| Which file to create next | [05-work-breakdown.md](05-work-breakdown.md) filtered by current day |
| Which choice is still open | [00-decisions.md §2](00-decisions.md) |
| What can be cut if behind | per-day cut-list section in [01](01-d0-to-d3-interim-path.md), [02](02-d4-act3-probes.md), [03](03-d5-d6-act4-mechanism.md) |
| How to route outbound to the sink | [__specs/16 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md) |
| What the memo must contain | [__specs/14](/home/kg/Projects/10Academy/conversion-engine/__specs/14-memo-specification.md) + [04 §D7.4](04-d7-act5-memo-demo.md) |
| What goes in the demo video | [04 §D7.6](04-d7-act5-memo-demo.md) + [__specs/17 §B.3](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md) |

## Principles (distilled)

1. **Grounded honesty over fluency.** Every outbound claim traces to a signal in the brief. Silence beats over-claiming.
2. **Bench is a hard gate.** Never commit to capacity `bench_summary.yaml` does not show.
3. **Evidence-graph-first on the memo.** Write the graph, then render prose. Fabrication is disqualifying.
4. **Kill-switch default unset.** All outbound routes to the sink unless the flag is explicitly enabled.
5. **Stub-first on D0.** Every target file exists as a skeleton before any logic, so D2 lanes can work in parallel.
6. **Cost < $5 per qualified lead.** Measured in the memo, sourced from `invoice_summary.json`.
7. **Find the lead. Ground the conversation. Respect the brand. Ship it.**
