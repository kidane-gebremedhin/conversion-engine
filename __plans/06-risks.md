# 06 — Risk Register

**Purpose:** Name the top risks that can kill either deadline or the evidence-graph integrity of the memo. Each risk has: a trigger metric, an explicit threshold, the mitigation, and the owning `__plans/` file that carries the mitigation's execution detail.

**Operating rule:** When a trigger metric crosses its threshold, the owning file's cut-list or fallback is invoked **without further deliberation**. Risks are priced in up front so that mid-execution panic doesn't cost time.

---

## R1 — Interim slip past D3 submission

**What:** The interim deadline passes with either `agent/` or `eval/` incomplete, or the PDF report missing required bullets from [__specs/17 §A.5](/home/kg/Projects/10Academy/conversion-engine/__specs/17-deliverables-checklist.md).

**Trigger metric:** Count of unchecked boxes in the interim gate checklist at T-4h / T-2h / T-1h relative to D3 21:00 local.

**Thresholds:**
- T-4h: > 6 unchecked → invoke cut-list item 1 (drop SMS inbound).
- T-2h: > 3 unchecked → invoke cut-list items 2–3 (stub competitor gap; drop reproduction-check).
- T-1h: > 1 unchecked (non-A.7) → invoke cut-list items 5–6 (drop Langfuse on prod stack; drop HubSpot MCP → REST).

**Mitigation owner:** [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md) §D3.4.

**Residual risk:** Even with all cuts, if end-to-end prospect is not green by T-1h, submit with best-effort documentation in the PDF report and a clear "what is not yet working" section. Partial credit is recoverable; dishonest claims are not.

---

## R2 — Sealed held-out slice leaks into tuning

**What:** Act IV mechanism is inadvertently tuned on the 20-task sealed slice, invalidating Delta A.

**Trigger metric:** Any git-tracked file under `agent/`, `method/`, or `probes/` references `eval/held_out_slice.json` or imports from it outside of `eval/harness.py` or `method/stat_test.py`.

**Threshold:** Any hit.

**Mitigation owner:** [03-d5-d6-act4-mechanism.md](03-d5-d6-act4-mechanism.md) + [05-work-breakdown.md](05-work-breakdown.md) row `scripts/audit_seal.sh`.

**Controls:**
1. `scripts/audit_seal.sh` runs in CI on every commit touching `agent/` or `method/`. Fails build on hit.
2. Human sign-off required before first `make held-out` invocation on D5. Sign-off is a commit-message convention: `held-out-run: approved-by=<name>`.
3. Held-out slice file is chmod 444 on disk; accidental edits bounce.

**Residual risk:** Consciously chosen hyperparameters that *generalise from dev slice* may still overfit the family. Honest memo language if Delta A is borderline — never fabricate.

---

## R3 — Eval-tier budget blown on D5–D6

**What:** Held-out run at 3 conditions × 5 trials × 20 tasks = 300 task-runs at eval-tier pricing overshoots the $12 envelope.

**Trigger metric:** Projected cost to complete held-out (linear extrapolation from first 20 runs × remaining runs) visible in the Langfuse cost dashboard.

**Thresholds:**
- Projected > $10 with 100 runs remaining: drop trials per condition from 5 → 3, re-project.
- Projected > $12 with 60 runs remaining: abort, switch eval-tier model to the other option (Claude Sonnet 4.6 ↔ GPT-5 per O3), re-run with 3 trials.
- Projected > $15: stop, document in `method.md`, report Delta A with whatever trials completed.

**Mitigation owner:** [03-d5-d6-act4-mechanism.md](03-d5-d6-act4-mechanism.md) §D5.3.

**Controls:**
- Langfuse cost dashboard checked every 30 min during held-out run.
- `eval.tau2_bench.budget_eval_usd: 12.00` hard-coded in `config.yaml`; harness aborts if exceeded.

---

## R4 — Delta A fails p ≥ 0.05

**What:** The statistical test does not show a significant improvement of our method over the Day-1 baseline on the sealed held-out slice.

**Trigger metric:** `method/stat_test_output.json` → `p_value`.

**Threshold:** `p_value ≥ 0.05` or `ci.lower ≤ 0`.

**Mitigation owner:** [03-d5-d6-act4-mechanism.md](03-d5-d6-act4-mechanism.md) §D6 fallback + [04-d7-act5-memo-demo.md](04-d7-act5-memo-demo.md).

**Fallback ladder (in order):**
1. Inspect per-task deltas. If a subset of tasks shows a large deficit that is out-of-scope for our mechanism (e.g., dual-control-heavy tasks that our signal-confidence mechanism does not touch), report task-weighted Delta A restricted to the scope the mechanism targets. Document the restriction in `method.md`.
2. Try ablation 3c (eval-tier validator) as the primary method. It is a more expensive but stronger variant; if it clears p < 0.05 within budget, swap and redo stat test.
3. If still failing, **write the memo honestly.** Page 1 reports the non-significant delta with the CI, and one sentence of interpretation (e.g., "our mechanism reduces variance on brand-reputation-sensitive traces but does not lift overall pass@1"). Page 2's "one honest unresolved failure" slot is this. **Never fabricate.** The evidence-graph linter will catch it; the grade will suffer, but disqualification is avoided.

**Residual risk:** Grading penalty for failing Delta A. The fabrication alternative is **disqualifying**, so honesty is strictly better.

---

## R5 — Empty repo → scaffolding churn on D2

**What:** Without stub-first discipline, D2 swim lanes block each other on missing imports and circular dependencies. Engineers waste 2–4 h of coding time on import plumbing instead of logic.

**Trigger metric:** Any `ImportError` or `ModuleNotFoundError` from `pytest` or `python -m agent.main` after D0 exit gate.

**Threshold:** Any occurrence after D0.

**Mitigation owner:** [05-work-breakdown.md](05-work-breakdown.md) §13 (reusables) + D0 stub-first rule.

**Controls:**
1. Every file in the WBS marked **D0 stub** exists before D1 begins. CI checks: `python -c "import agent, agent.orchestrator, agent.enrichment.pipeline, ..."` succeeds.
2. Public interfaces (dataclasses, protocol classes, tool schemas) are filled in D0. Only method bodies raise `NotImplementedError`.
3. A pair-programming audit of the stub tree at D0 exit catches missed seams.

---

## R6 — Disqualifying brand/data error

**What:** Any of: real Tenacious customer data in a committed file, kill-switch default set to `true`, an unmarked Tenacious-branded output in an artifact, a fabricated Tenacious number in the memo.

**Trigger metric:** Any of the following:
- `grep -r '@tenacious.com\|@tenacious.co' agent/ data/ memo/` returns a hit.
- `config.yaml:killswitch.enabled` != `false` in the committed file.
- Any email/SMS/HubSpot/Cal.com artifact in `data/` or `memo/figures/` missing the `draft` marker.
- `scripts/lint_memo.py` fails on an unresolved number in `memo.md`.

**Threshold:** Any hit is **disqualifying**.

**Mitigation owner:** [00-decisions.md](00-decisions.md) §1 (L1–L3, L8, L13) + [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md) §D3.4 T-30m manual audit + [04-d7-act5-memo-demo.md](04-d7-act5-memo-demo.md) §D7 pre-submit audit.

**Controls:**
1. Pre-commit hook runs the four greps above; commit fails if any matches.
2. `scripts/lint_logs.py` runs in CI on every PR; fails if secret-regexes hit JSONL files.
3. `scripts/lint_memo.py` runs on every memo build; fails on unresolved numbers and on PDFs ≠ 2 pages.
4. T-30m manual sweep before interim submit; T-60m manual sweep before final submit.

**Residual risk:** A human mistake in the manual-audit step. Mitigated by the automated layers above; if they all pass, the remaining surface is small.

---

## R7 — PDF report blocks on pending metrics

**What:** The interim PDF or the memo draft cannot be assembled because required numbers (τ²-Bench baseline, p50/p95, cost per lead, reply-rate delta) have not yet been computed, and prose cannot precede them.

**Trigger metric:** Time-to-deadline × % of `<filled at D3>` placeholders still unfilled in the PDF draft.

**Threshold:**
- Interim: > 30 % of placeholders unfilled at T-2h.
- Final: > 30 % of memo numbers unresolved at D7 17:00 local.

**Mitigation owner:** [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md) §D2 16:00 scaffold rule + [04-d7-act5-memo-demo.md](04-d7-act5-memo-demo.md) §D7 evidence-graph-first discipline.

**Controls:**
1. PDF scaffold (all headings + placeholder tables) is authored at **D2 16:00** local, before numbers are final.
2. Memo: `evidence_graph.json` is authored **before** the prose. The prose is a render of the graph. This inverts the usual write-then-cite pattern.
3. Numbers that won't land in time are replaced with a "pending — will be published as addendum" stub and the stub is documented in "what is not working" in the interim PDF, or as an unresolved failure on Page 2 of the memo.

---

## R8 — External-service fragility on D0

**What:** One of Resend / Africa's Talking / HubSpot MCP / Cal.com / Langfuse provisioning stalls, eating D0 time. Cascades into compressed D1–D3.

**Trigger metric:** Cumulative D0 wall-clock hours when one service is still unprovisioned.

**Thresholds:**
- > 5 h total on D0: invoke fallback per-service (REST for HubSpot, local Langfuse via `langfuse/langfuse-docker`, ignore Africa's Talking and mark SMS as stretch).
- > 6 h: defer Langfuse cloud; use local JSONL fallback (`data/local_traces.jsonl`) for the week; pay the integration cost on D7 if time.

**Mitigation owner:** [01-d0-to-d3-interim-path.md](01-d0-to-d3-interim-path.md) §D0.1 + [00-decisions.md](00-decisions.md) §2 (O1, O8).

**Controls:**
1. Provisioning tasks are parallel, not serial.
2. Every service has a named fallback in `config.yaml`.
3. One teammate owns "unblock" rather than coding during D0.

---

## R9 — Prompt-cache / LLM provider outage during D5 held-out

**What:** OpenRouter or the chosen eval-tier provider goes down mid-held-out-run. Partial traces, inconsistent temperatures, Delta A invalidated.

**Trigger metric:** Any non-2xx response rate > 5 % over a 5-minute window during held-out.

**Threshold:** 5 %.

**Mitigation owner:** [03-d5-d6-act4-mechanism.md](03-d5-d6-act4-mechanism.md) §D5.4 retry policy.

**Controls:**
1. Each task-run is resumable: the harness checkpoints per-task and skips already-completed tasks on rerun.
2. Both OpenRouter Qwen and a direct Anthropic key are warm and tested by D5.
3. Eval model can be swapped mid-run only at a **condition boundary** (never mid-trial-set); switch is logged in `method.md`.

**Residual risk:** If outage spans > 2 h and we are already at 5→3 trial fallback, document as an honest unresolved constraint on memo Page 2.

---

## R10 — Seed-material redaction on D7

**What:** At week end, personal infrastructure still holds copies of `seed/sales_deck.pdf`, `seed/case_studies/`, `seed/pricing.yaml`. This violates Challenge Rule 3.

**Trigger metric:** Output of `scripts/end_of_week_purge.sh --dry-run` lists files remaining.

**Threshold:** Any file remaining after purge confirmation.

**Mitigation owner:** [04-d7-act5-memo-demo.md](04-d7-act5-memo-demo.md) §D7 final packaging + [__specs/16 §7](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md).

**Controls:**
1. `scripts/end_of_week_purge.sh` runs D7 evening after submission; writes to `data/purge_audit.jsonl`.
2. Purge includes laptop cloud-drive sync dirs (Dropbox / iCloud / Drive File Stream) explicitly configured in the script.
3. Code stays in the program repo; `seed/` is removed from personal infra.

---

## Risk summary table

| ID | Risk | Owner file | Pre-mitigation likelihood | Post-mitigation residual |
|----|------|-----------|---------------------------|--------------------------|
| R1 | Interim slip | 01 | High | Medium — cut-list reduces blast radius |
| R2 | Sealed-slice leak | 03 + 05 | Low | Very low — CI check |
| R3 | Eval-tier budget blown | 03 | Medium | Low — dashboard + trial fallback |
| R4 | Delta A fails p ≥ 0.05 | 03 + 04 | Medium | Medium — honest memo, not disqualifying |
| R5 | Scaffolding churn | 05 | Medium | Low — stub-first |
| R6 | Brand/data error | 00, 01, 04 | Low | Very low — automation + manual audit |
| R7 | PDF blocks on metrics | 01, 04 | Medium | Low — scaffold-first + evidence-graph-first |
| R8 | External-service fragility | 01, 00 | Medium | Medium — named fallbacks |
| R9 | LLM provider outage | 03 | Low | Low — resumable harness |
| R10 | Seed-material redaction miss | 04 | Low | Very low — automated purge |
