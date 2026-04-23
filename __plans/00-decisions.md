# 00 — Decisions Log

**Purpose:** Single source of truth for all architectural and scope decisions across the week. Every other `__plans/` file cites this document. No decision is re-opened by the engineer at the moment of implementation — if a choice is locked here, follow it; if it is open here, it names the phase where it closes and the fact that closes it.

**Calendar:** Days are labeled `D0 … D7` relative to the engineer's start. `D3` is the interim-submission day; `D7` is the final-submission day. Today's date at plan authoring is `2026-04-22` (noted for reference — the schedule is not bound to absolute dates).

---

## 1. Locked decisions

| # | Decision | Value | Rationale |
|---|----------|-------|-----------|
| L1 | Kill-switch default | **Unset** — routes all outbound to staff sink | Challenge rule 4 ([__specs/16 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md)) |
| L2 | Kill-switch env var name | `CONVERGINE_ENABLE_REAL_OUTBOUND` | Belt + braces with `config.yaml:killswitch.enabled` — both must be true to route to real recipients |
| L3 | Draft-marker surface | `X-Convergine-Draft: true` header, `[DRAFT]` prefix in SMS, `draft: true` in HubSpot payload + Cal.com metadata, one-line footer in email body | [__specs/16 §6](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md) |
| L4 | τ²-Bench seed | **42** | Published reproducibility convention; matches `config.example.yaml` |
| L5 | Sealed-slice audit protocol | `scripts/audit_seal.sh` runs in CI + human sign-off before any Day-5 held-out invocation | [__specs/11 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/11-tau2-bench-harness.md) |
| L6 | Grading-fixed segment names | Do not rename. Filters may be refined; taxonomy may not | [__specs/03 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/03-icp-and-segments.md) |
| L7 | HubSpot required property | Every `Company` carries `convergine_crunchbase_uuid` — evidence-graph root | [__specs/08 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/08-hubspot-integration.md) |
| L8 | Tenacious redaction rights | Tenacious executive team may redact any Tenacious-branded content from the memo | Challenge rule 5 |
| L9 | Channel hierarchy | Email primary → SMS secondary (warm-lead scheduling only) → Voice bonus (human-delivered) | [__specs/07 §1](/home/kg/Projects/10Academy/conversion-engine/__specs/07-channels.md) |
| L10 | Voice rig | **Out of scope** for the week. Attempt only as a stretch if D7 ≥ 14:00 is clear | [__specs/07 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/07-channels.md) |
| L11 | Aggressive-hiring gate | Hard-coded: ≥ 5 open roles AND ≥ 2.0× velocity ratio. Agent cannot assert "aggressive hiring" below the threshold regardless of prompt framing | [__specs/05 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/05-signal-enrichment-pipeline.md) |
| L12 | Segment-4 AI-maturity gate | Score ≥ 2 required. Below that, abstain | [__specs/03 §1, §2](/home/kg/Projects/10Academy/conversion-engine/__specs/03-icp-and-segments.md) |
| L13 | Evidence-graph-first discipline | `memo/evidence_graph.json` authored before memo prose. Linter fails if any number in `memo.md` is unresolved | [__specs/14 §4, §5](/home/kg/Projects/10Academy/conversion-engine/__specs/14-memo-specification.md) |
| L14 | Brief cache TTL | 24 h per `crunchbase_uuid`. Invalidate via `make enrich PROSPECT=<uuid> --force` | [__specs/04 §8](/home/kg/Projects/10Academy/conversion-engine/__specs/04-data-sources.md) |
| L15 | Live-crawl company cap | ≤ 200 companies in the challenge week. Prefer the frozen early-April 2026 snapshot | [__specs/04 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/04-data-sources.md) |
| L16 | Memo length | Exactly 2 pages. Linter verifies `pdfinfo memo.pdf \| grep Pages` returns `2` | [__specs/14 §1, §6](/home/kg/Projects/10Academy/conversion-engine/__specs/14-memo-specification.md) |
| L17 | Cost-per-qualified-lead target | < $5 target, > $8 penalised without justification | [__specs/10 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/10-observability.md) |

---

## 2. Open decisions (with named closing phase and closing fact)

Each open decision has:
- **Options** — candidates from the specs, no new candidates invented.
- **Closes at** — the day/phase the decision must be made.
- **Closing fact** — the observation or measurement that picks the winner.
- **Default fallback** — the choice if the closing fact is inconclusive at the deadline.

### O1 — Email provider

- **Choice:** Resend free tier (3 000/mo).
- **Closed at:** D0 pre-flight.
- **Rationale:** Generous free tier and well-documented webhook schema; provisioned cleanly in sandbox.
- **Impact of choice:** `agent/channels/email/send.py` uses the Resend client; `config.yaml:channels.email.provider` is pinned to `resend`.

### O2 — Dev-tier model (Days 1–4)

- **Options:** `qwen/qwen3-next-80b-a3b-instruct` via OpenRouter | `deepseek/deepseek-chat-v3.2` via OpenRouter.
- **Closes at:** **D1 start of Act I baseline**.
- **Closing fact:** First model to produce a stable τ²-Bench retail dev-slice run at pinned seed (no repeat/loop failures, coherent tool-call formatting). Use the other as `fallback`.
- **Default fallback:** Qwen3-Next-80B-A3B — cheaper per 1k tokens, strong instruction-following benchmark record.
- **Budget impact:** target < $4 over D1–D4.

### O3 — Eval-tier model (Days 5–7)

- **Options:** `claude-sonnet-4-6` | GPT-5 class.
- **Closes at:** **D5 start of held-out run**.
- **Closing fact:** Per-task cost at held-out scale (300 tasks = 3 conditions × 5 trials × 20). Winner is the one whose projected cost fits the $12 envelope with headroom for the ≥ 3-trial fallback.
- **Default fallback:** Claude Sonnet 4.6 — prompt-cache pricing advantage on our static system prompt is meaningful.
- **Budget impact:** target < $12 over D5–D7.

### O4 — Act IV mechanism candidate

- **Options:** (A) signal-confidence-aware phrasing | (B) bench-gated commitment policy | (C) ICP classifier with abstention | (D) tone-preservation check | (E) multi-channel handoff policy. Full descriptions: [__specs/13 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/13-mechanism-design.md).
- **Closes at:** **End of D4** after probe trigger-rate review.
- **Closing fact:** Candidate whose design directly addresses the probe category that maximises `business_cost_usd_per_incident × observed_trigger_rate_pre_mechanism` in `probes/failure_taxonomy.md`.
- **Default fallback:** (A) signal-confidence-aware phrasing — aligns with the highest-cost axis (brand reputation) and composes with the other defences.
- **Always kept as ablation variants regardless of winner:** (B) and (D). Cost is near zero and they earn safety credit.

### O5 — Pilot segment recommendation (for memo Page 1 §2.7)

- **Options:** Segment 1 (recently-funded A/B) | Segment 2 (mid-market restructuring) | Segment 3 (leadership transition) | Segment 4 (capability gap).
- **Closes at:** **D7 during memo composition**, after all metrics have landed.
- **Closing fact:** Segment with the largest measured signal-grounded-vs-exploratory reply-rate delta and cleanest bench match in our trace corpus.
- **Default fallback:** Segment 1 — cleanest public signal from Crunchbase + job posts; largest ACV spread ($240–720 K talent + $80–300 K consulting).

### O6 — Automated-optimization baseline (Delta B)

- **Options:** GEPA (Generative Evolutionary Prompt Automation) | AutoAgent.
- **Closes at:** **D5 start**.
- **Closing fact:** Which framework can be configured to match our method's compute budget (same dev-tier model, same trials, same slice) with less than 2 h of integration work.
- **Default fallback:** GEPA — simpler prompt-evolution loop; closer to our mechanism's surface; cheaper to run at our budget.

### O7 — Dev-tier concurrency

- **Options:** 1 concurrent LLM call | 2 concurrent.
- **Closes at:** **D0 pre-flight**.
- **Closing fact:** OpenRouter rate-limit behaviour observed on the first 10 calls. Two concurrent is faster but risks 429s on the free tier.
- **Default fallback:** 2 — declared in `config.example.yaml`. If we see any 429, drop to 1 and document.

### O8 — HubSpot integration mode

- **Choice:** MCP via in-repo server (`agent/integrations/hubspot_mcp_server.py`), spawned as a stdio subprocess by `HubSpotClient`. Tools: `upsert_company`, `find_company_by_crunchbase_uuid`, `upsert_contact`, `create_deal`, `advance_deal_stage`, `log_event`.
- **Closed at:** 2026-04-23, D0 pre-flight.
- **Rationale:** HubSpot's official remote MCP server (`https://mcp.hubspot.com`) is OAuth 2.1 + PKCE only — unsuitable for a non-interactive backend. Community servers (`peakmojo/mcp-hubspot`, `lkm1developer/hubspot-mcp-server`) omit deals and custom objects, which [__specs/08](/home/kg/Projects/10Academy/conversion-engine/__specs/08-hubspot-integration.md) requires. A thin Python MCP server wrapping REST with the Private App token matches the spec verbs exactly, keeps auth simple, and puts MCP in the critical path without an OAuth flow.
- **Fallbacks:** `HUBSPOT_CLIENT_MODE=rest` skips the MCP hop and calls REST directly on the same interface. `HUBSPOT_CLIENT_MODE=local` writes JSON fixtures for no-token dev. Auto-default is MCP when the token is set, local otherwise.

---

## 3. Explicitly out of scope for the week

These are **not** open decisions — they are pre-declared out of scope. Revisit only if all required deliverables are green:

- Voice rig (demo-only bonus, [__specs/07 §4](/home/kg/Projects/10Academy/conversion-engine/__specs/07-channels.md)).
- Market-space mapping stretch — only attempted at D7 14:00-local go/no-go ([__specs/15](/home/kg/Projects/10Academy/conversion-engine/__specs/15-market-space-map.md)).
- Learned ICP classifier with training labels — default is rules-based abstention ([__specs/03 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/03-icp-and-segments.md)).
- Live HubSpot production portal — sandbox only.
- Real Cal.com calendars — Tenacious team calendars are mocked by program-provided sample calendars.
- Live prospect crawls beyond the 200-company cap.

---

## 4. Change control

A decision in §1 (Locked) only re-opens if:

1. The engineer files an entry in [06-risks.md](06-risks.md) documenting why the lock is blocking.
2. The re-open is reflected in this file with a new row and a dated note.
3. The cascading impact on every downstream `__plans/` file is updated.

A decision in §2 (Open) that reaches its `Closes at` phase **must** close before the phase ends. The engineer records the chosen value, the observation that closed it, and any deviations from the default fallback here.

---

## 5. Quick-reference table for implementers

| Question | Answer / pointer |
|----------|------------------|
| Is the kill-switch flipped? | **No.** Unset by default (L1). |
| Which LLM do I call? | **Dev-tier** unless in a held-out eval run (O2, O3). |
| Do I need to route through killswitch? | **Yes**, every outbound — [__specs/16 §2](/home/kg/Projects/10Academy/conversion-engine/__specs/16-data-handling-and-kill-switch.md). |
| Can I assert "aggressive hiring"? | Only if L11 gate passes. |
| Can I pitch Segment 4? | Only if L12 gate passes. |
| What's the cost-per-lead target? | L17: < $5, > $8 penalised. |
| Where does a number in the memo come from? | An `evidence_graph.json` entry per L13. |
| Have I touched the sealed held-out slice? | Not before D5, and only after L5 audit passes. |
