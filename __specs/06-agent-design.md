# 06 — Agent Design

The agent has four capabilities: **classify**, **compose**, **reply**, **handoff**. Each capability is a narrow function with a typed contract; the agent has no "general reasoning" path that bypasses these.

## Design principles

1. **Grounded or silent.** Every claim in every message resolves to a field in the hiring signal brief or competitor gap brief. If the brief does not ground a claim, the agent does not make it.
2. **Confidence-aware phrasing.** Low confidence turns assertions into questions. `ask` rather than `assert` is the default.
3. **Bench-gated.** The agent never commits capacity `bench_summary.json` does not show.
4. **Single ask per message.** Cold emails have one call-to-action. Stacking asks is a tone violation.
5. **Abstention is a valid output.** If segment confidence is below threshold or signals conflict, the agent sends a generic exploratory email, not a confident wrong pitch.
6. **Handoff is not failure.** Five conditions route to a human with a context brief. Trying to close a conversation outside the agent's authority is a policy violation.

## Capability 1 — ICP classifier

**Input**: `hiring_signal_brief.json`.
**Output**: `{ segment: Segment1|Segment2|Segment3|Segment4|Abstain, confidence: float, rationale: string }`.

**Implementation**: rule-based (not LLM-call) per the ordered rules in [spec 03](03-icp-and-segments.md). LLM is used only for interpreting free-text signals (founder anti-offshore stance, interim/acting phrasing). The primary classifier is deterministic; this keeps cost low and behavior auditable.

**Abstain condition**: `segment_confidence < icp.abstain_threshold` (default 0.6). Abstention routes to the `composer_abstain.txt` prompt.

## Capability 2 — Composer

**Input**: `(segment, hiring_signal_brief, competitor_gap_brief, prospect_profile, sequence_position)`.

`sequence_position ∈ { cold_1, cold_2, cold_3, warm_engaged, warm_curious, warm_objection_*, warm_soft_defer, reeng_1, reeng_2, reeng_3 }`.

**Output**: `{ subject: str, body: str, html: str, cal_link: str | None, segment_used: str, briefs_referenced: [str] }`.

**Sub-steps**:

1. **Prompt selection** — `agent/prompts/composer_segment_<n>.txt` (or `composer_abstain.txt`). Prompts include the five tone markers, the segment-specific pitch language pair (high / low AI-readiness), the style-guide dos/don'ts, and a few-shot exemplar drawn from the corresponding seed file (`cold.md`, `warm.md`, `reengagement.md`).
2. **Brief binding** — the composer receives both briefs as structured JSON in the prompt. It emits a `briefs_referenced` list of field-paths it used (e.g., `buying_window_signals.funding_event`, `competitor_gap_brief.gap_findings[0]`). This list is the evidence-graph input for this message.
3. **Bench check** — if the draft mentions a specific stack, the composer asserts `bench_summary[stack].available_engineers > 0`. If not, the draft is regenerated with staffing specificity removed, or the agent escalates to handoff.
4. **Length and format constraints** — cold emails ≤120 words; subject ≤60 chars; one call-to-action; no emojis in cold; no marketing taglines in signature. Enforced by a deterministic post-check, not by LLM trust.
5. **Tone preservation check** — second LLM call scores the draft against the five markers (Direct / Grounded / Honest / Professional / Non-condescending), each on a 1–5 scale. Any marker scoring <4 triggers ONE regeneration; a second failure flags the draft for human review and suppresses auto-send.

### Prompt engineering rules (non-negotiable)

Every composer prompt includes these literal system-prompt fragments (configurable in `agent/prompts/` but not bypassable):

- The five tone markers verbatim from [`seed/style_guide.md`](../tenacious_sales_data/seed/style_guide.md).
- The disallowed phrases list: `just following up`, `circling back`, `hope this finds you well`, `wanted to touch base`, `top talent`, `world-class`, `A-players`, `rockstar`, `ninja`, `quick question`, `Hey there`.
- The "before-send" self-test: *"Would this email read well if it were quoted in a screenshot on LinkedIn with the prospect's annotation?"*
- The signature template, verbatim.

## Capability 3 — Reply classifier and responder

**Input**: an inbound `{ thread_id, body, subject, sender_email, received_at }`.

**Classifier output**: `class ∈ { engaged, curious, hard_no, soft_defer, objection, ambiguous }`.

**Ambiguous is mandatory, not optional**: if the classifier's confidence is below `reply.ambiguous_threshold` (default 0.7), the output is `ambiguous` and the reply routes to a human. **Confident-wrong classification is a worse failure than `ambiguous`.**

**Responder routing**:

| Class | Response path |
|---|---|
| `engaged` | `agent/prompts/reply_engaged.txt` — grounded answer + book (≤150 words) |
| `curious` | `agent/prompts/reply_curious.txt` — targeted context + book (≤90 words) |
| `hard_no` | **No reply.** HubSpot `outreach_status=opted_out`, suppression list update, Langfuse log. |
| `soft_defer` | `agent/prompts/reply_soft_defer.txt` — gracious close with specific re-engagement date (≤60 words) |
| `objection` | `agent/prompts/reply_objection.txt` — scripted objection handling, **never invent a discount**; route to human if price/scope outside bands |
| `ambiguous` | Route to human via handoff; no agent reply. |

### Hard-no handling — explicit rules

- **No apology.** "Sorry to have bothered you" is a tone violation.
- **No closing thank-you.** The prospect asked to be left alone; respect that directly.
- **Suppression list** is domain-scoped. A hard no from a single inbox suppresses **that inbox**; suppressing the whole company is a judgment call logged for human review.
- **Regulatory correction exception**: if the reply contains "wrong contact, our CTO is X", the agent forwards the corrected contact to the enrichment pipeline, closes the original thread silently, and does NOT auto-send to the new contact without re-running enrichment.

## Capability 4 — Handoff gate

The agent hands off to a human delivery lead in exactly five cases:

1. **Pricing outside quotable bands** (e.g., "what would it cost for 20 engineers for 18 months?").
2. **Specific staffing beyond bench confirmation** (e.g., "do you have a Databricks specialist with healthcare experience starting in July?").
3. **Named public client reference** requested in a specific sector.
4. **Regulatory / contracting / legal language** (MSA, DPA, BAA, specific clauses).
5. **C-level executive at 2,000+ headcount** — regardless of reply content.

Handoff action:

1. Agent sends one message: *"Our delivery lead will follow up within 24 hours with a specific answer."* (configurable wording).
2. Agent creates a HubSpot task assigned to the designated delivery lead (from `config.yaml > handoff.default_lead_email`).
3. Agent renders the **discovery call context brief** per [`schemas/discovery_call_context_brief.md`](../tenacious_sales_data/schemas/discovery_call_context_brief.md) and attaches it as a HubSpot note.
4. Agent does **not** send further outbound on this thread until the human delivery lead clears it.

## Abstention path — exploratory email

When the classifier abstains, the composer uses `composer_abstain.txt`. The exploratory email is:

- ≤ 100 words.
- Opens with a non-segment-specific observation about the prospect's public signal (e.g., "We've been looking at companies in the [sector] space at the [HC band] stage").
- Makes **no specific pitch**. No pricing, no capability claim, no case-study reference.
- Asks one low-commitment question (e.g., "How are you thinking about offshore-delivery mix these days?").
- Has a Cal link but does NOT push it as the primary ask.

The exploratory email is a deliberately softer touch. Its reply rate target in the memo is the baseline 1–3% (not the signal-grounded 7–12%).

## Multi-thread safeguard

The agent may be talking to two prospects at the same company (co-founder + VP Eng). **Threads are isolated by `(prospect_email, thread_id)`, never by company domain.** The composer receives only the current thread's history; it has no access to the other thread's content. Cross-thread leakage is a Probe Category 3 target (see [spec 12](12-probe-library.md)).

Implementation: the agent's context-builder loads history from HubSpot filtered by `contact_email`; a lint-check in CI greps `agent/` for any file that loads by `company_domain` for conversation context.

## Cost and latency constraints

- **Dev-tier model** (Qwen3-Next-80B-A3B or DeepSeek V3.2 via OpenRouter) for Days 1–4 development, adversarial probing, and mechanism prototyping. Per-run budget in `config.yaml > budgets.dev_llm_max_usd`.
- **Eval-tier model** (Claude Sonnet 4.6 or GPT-5 class) for **sealed held-out scoring only**. Guarded by env var `EVAL_TIER_ENABLED=1` to prevent accidental burn.
- **Target cost per qualified lead**: under `budgets.target_cost_per_qualified_lead_usd` (see [spec 14](14-memo-specification.md) for the penalty threshold).
- **Latency budget**: the composer should complete in p95 ≤ 20s for cold, p95 ≤ 15s for warm replies (so the thread feels responsive to a human prospect — measured from Langfuse).

## What the agent must NOT do

- Send a message that fails the tone-preservation check.
- Send a message whose `briefs_referenced` list is empty (no signal grounding).
- Commit capacity, pricing, or phase specifics beyond the quotable bands.
- Reply to a `hard_no`.
- Re-engage a thread already flagged `outreach_status=opted_out`.
- Compose more than three cold emails per prospect (cold sequence is strictly 3 touches).
- Use eval-tier model without the `EVAL_TIER_ENABLED=1` guard set.
