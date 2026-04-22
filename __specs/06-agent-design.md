# 06 — Agent Design

**Source:** Challenge document — "The Five-Act Loop" (Acts II + IV), "Sales Jargon for Talent Outsourcing", "Mechanism directions worth considering".

## 1. Design principles

1. **Grounded honesty over fluency.** Every claim in every outbound message must trace to a signal in `hiring_signal_brief.json` or the Tenacious sales deck.
2. **Qualify is a filter, research is the value.** Lead with a finding the prospect would read with interest.
3. **Bench is a hard constraint.** The agent never commits to capacity `bench_summary.yaml` does not show — even when asked directly.
4. **Channel hierarchy is fixed.** Email first; SMS only for warm-lead scheduling; voice handed off to a human.
5. **Respect the draft discipline.** Tenacious-branded output is marked `draft` in metadata until a human approves.

## 2. LLM backbone

| Use | Model | Where |
|-----|-------|-------|
| Dev-tier orchestration (Days 1–4) | Qwen3-Next-80B-A3B **or** DeepSeek V3.2 via OpenRouter | `agent/llm/client.py` |
| Eval-tier sealed held-out scoring (Days 5–7) | Claude Sonnet 4.6 **or** GPT-5 class | `eval/harness.py` |
| Enrichment synthesis (per-signal justification) | Dev-tier (cheap) | `agent/enrichment/ai_maturity.py` |

Model IDs, API keys, base URLs — see [.env.example](.env.example) + [config.example.yaml](config.example.yaml).

Caching: use OpenRouter's prompt-prefix caching for the Tenacious system prompt + sales-deck excerpt (≈ 3 000 tokens static). See [claude-api skill](../../.claude/) pattern.

## 3. Tool surface

Tools are the only way the agent acts on the world. Each tool has a schema, validated before execution, and emits a Langfuse span.

```python
# agent/llm/tools.py

class DraftEmailInput(BaseModel):
    prospect_uuid: str
    stage: Literal["cold", "nurture_1", "nurture_2", "nurture_3", "scheduling"]
    variant: Literal["signal_grounded", "exploratory"]

class SendEmailInput(BaseModel):
    to: EmailStr                    # routed through killswitch
    subject: str
    body_markdown: str
    trace_id: UUID                  # for idempotency
    draft_approved: bool = False    # must be True or kill-switch unset → sink

class SendSmsInput(BaseModel):
    to_shortcode: str
    body: str                        # 160 char hard cap
    trace_id: UUID

class LogCrmInput(BaseModel):
    prospect_uuid: str
    event_type: Literal["email_sent", "email_reply", "sms_sent", "sms_reply", "call_booked", "segment_assigned", "handoff_human"]
    payload: dict

class BookCallInput(BaseModel):
    prospect_uuid: str
    slot_iso: datetime
    tenacious_lead_email: EmailStr
    context_brief_md: str            # attached to invite

class ToneCheckInput(BaseModel):
    draft_markdown: str
    stage: str

class BenchCheckInput(BaseModel):
    draft_markdown: str              # rejects if it references capacity not in bench_summary.yaml

class HandoffHumanInput(BaseModel):
    reason: Literal["prospect_asked_for_specific_pricing", "prospect_asked_bench_beyond_capacity", "prospect_explicit_objection", "unknown_policy_boundary"]
    thread_summary_md: str
```

### Tool execution rules

- `send_email` **always** passes through `integrations.killswitch.route()` which rewrites recipient to `config.killswitch.sink_email` when `config.killswitch.enabled == false`.
- `send_email` is blocked unless `bench_check.pass == true` AND `tone_check.pass == true` **or** the call is part of the `exploratory` variant where bench/tone cleared on a prior step.
- `book_call` requires `state == SCHEDULING`; never called cold.
- `handoff_human` transitions thread to `HUMAN_HANDOFF` and emits a Slack/email to the on-call Tenacious lead. No further agent action until the human responds.

## 4. Policy modules (gate every generation)

### `policies/tone.py`
- Loads `seed/style_guide.md` tone markers.
- Runs a cheap second-model call: "Does this draft preserve these markers? return JSON `{pass: bool, violations: [...], suggestions: [...]}`."
- If `pass == false`, regenerate with the violations injected into the next draft prompt. Retry ≤ 2 times; then escalate to `handoff_human(reason="unknown_policy_boundary")`.

### `policies/bench.py`
- Parses `seed/bench_summary.yaml`: counts of available engineers per stack (Python, Go, data, ML, infra).
- Scans draft for phrases matching regex patterns like `\b(\d+)\s+(engineers|developers|data scientists|ml engineers)\b` and specific-stack claims.
- If the draft promises capacity not present in the summary, the send is **blocked** — not silently rewritten. The agent must regenerate with the bench constraint injected.

### `policies/confidence.py`
- Accepts `hiring_signal_brief.json` and the draft.
- Checks that every assertion in the draft is backed by a signal with the required confidence band (§4 of [05](05-signal-enrichment-pipeline.md)).
- Violations: "this draft asserts 'aggressive hiring' but `qualifies_for_aggressive_hiring_claim = false`" — regenerate.

### `policies/channel_handoff.py`
- Rules for switching channels:
  - Email → SMS: prospect replied by email AND explicitly asked for SMS scheduling OR thread age > 96 h with one reply.
  - SMS → Voice: only the human delivery lead does this (via Cal.com booking). Agent never composes voice.
  - Any channel → Human handoff: see `HandoffHumanInput.reason` enum.

## 5. Prompt architecture

Prompts are stored in `agent/llm/prompts/` as versioned Markdown files, loaded at boot, **never** concatenated by string interpolation that could inject instructions from prospect content.

### System prompt skeleton (`system.md`)
```
You are the Conversion Engine, the outbound agent for Tenacious Consulting and Outsourcing.
You write with the voice defined in {{ style_guide_excerpt }}.

You operate under three non-negotiable constraints:
1. GROUNDED HONESTY. You never assert a claim that is not backed by {{ hiring_signal_brief }}
   at the required confidence band. When a signal is weak, you ask rather than assert.
2. BENCH DISCIPLINE. You never commit to engineering capacity not listed in {{ bench_summary }}.
   If a prospect asks for specifics you cannot verify, you hand off to a human delivery lead.
3. DRAFT DISCIPLINE. All content you produce is a draft. It is marked as such in metadata.
   A human delivery lead owns the final send decision in production; for this challenge,
   the kill-switch default routes all outbound to a staff sink.

You have access to the following tools: {{ tool_manifest }}.
Your state machine is: {{ state_machine }}.
The four ICP segments, with fixed names, are: {{ segments_excerpt }}.
```

### Cold outreach prompt (`draft_outreach.md`)

Inputs:
- `hiring_signal_brief.json`, `ai_maturity_score.json`, `competitor_gap_brief.json`, `icp_classification.json`
- Variant: `signal_grounded` or `exploratory`

Output: JSON `{subject: str, body_markdown: str, signals_cited: [...], assertions_backed_by: [...]}`.

The prompt instructs:
- Open with the research finding (signal-grounded variant) or a one-sentence context reason (exploratory variant).
- At most one gap practice from `competitor_gap_brief.json` in the first message.
- No pricing numbers beyond the public-tier bands unless the prospect has asked.
- No founder names unless already present in the seed deck allowlist.
- Closing ask: a 30-minute discovery call, single concrete suggestion (e.g., "Thursday 2 pm UK" derived from prospect timezone).

### Reply classification prompt (`classify_reply.md`)
Output schema:
```json
{
  "intent": "interested | objection | off_topic | unsubscribe | scheduling_question | bench_question | pricing_question",
  "confidence": 0.84,
  "extracted": {
    "preferred_channel": "email | sms | null",
    "asked_time": "2026-04-24T14:00:00Z | null",
    "objection_class": "offshore_perception | cost | timing | capability | null"
  }
}
```

## 6. State machine

```
    COLD ──┬─► NURTURE_1 ─► NURTURE_2 ─► NURTURE_3 ─► STALE
           │       │             │             │
           │       ▼             ▼             ▼
           │   QUALIFIED ────────┴─────────────┘
           │       │
           │       ▼
           │   SCHEDULING ─► BOOKED ─► HANDED_OFF
           │       │
           │       └─(SMS preferred)─► SMS_SCHEDULING ─► BOOKED
           │
           └─► STOP (unsubscribe / objection) ─► CLOSED_LOST
```

Transitions:

| From → To | Trigger | Action |
|-----------|---------|--------|
| COLD → NURTURE_1 | No reply in 72 h | draft & send follow-up |
| NURTURE_1 → NURTURE_2 | No reply in 96 h | draft & send 2nd follow-up |
| NURTURE_2 → NURTURE_3 | No reply in 120 h | final, value-additive message |
| NURTURE_3 → STALE | No reply in 168 h | close thread silently |
| any → QUALIFIED | reply intent == interested && confidence ≥ 0.7 | log CRM, draft scheduling message |
| QUALIFIED → SCHEDULING | agent proposes slot(s) | attach Cal.com link |
| SCHEDULING → BOOKED | prospect confirms OR Cal.com webhook fires | attach context brief to invite |
| BOOKED → HANDED_OFF | call appears on Tenacious lead calendar | agent exits thread |
| any → STOP | intent == unsubscribe / explicit objection | log CRM, no further contact |
| any → HUMAN_HANDOFF | `handoff_human` tool called | notify on-call, freeze thread |

## 7. Mechanism integration hook (Act IV)

The agent orchestrator exposes a `Mechanism` interface that [13-mechanism-design.md](13-mechanism-design.md) plugs into:

```python
class Mechanism(Protocol):
    name: str
    def wrap_draft(self, brief, draft) -> str: ...
    def gate_send(self, draft) -> GateDecision: ...
    def post_reply(self, reply, thread) -> ReplyUpdate: ...
```

Baseline (Day 1) mechanism is a no-op. Act IV mechanism is one of:

- **Signal-confidence-aware phrasing** — rewrites phrasing based on `hiring_signal_brief.signals[*].confidence`.
- **Bench-gated commitment policy** — hard-blocks sends with capacity claims not backed by `bench_summary.yaml`.
- **ICP classifier with abstention** — routes low-confidence classifications to the `exploratory` variant.
- **Tone-preservation check** — adds a regeneration loop driven by `tone_check` scores.
- **Multi-channel handoff policy** — data-driven channel transitions against engagement outcomes.

Exactly one mechanism is selected as `method` for Act IV; the other directions are reported as failed or uncostly ablations in `method/ablation_results.json`.

## 8. Multi-thread isolation

When the agent talks to two contacts at the same company (co-founder and VP Eng), threads must **not** leak. Implementation:

- `ThreadState` is keyed by `(contact_email, crunchbase_uuid)`.
- The LLM context for any call includes only the current thread's history, the company-level brief, and the current draft state. It does **not** include other threads' histories.
- `multi_thread_leak_*` probes ([12](12-probe-library.md)) verify that an agent call for contact A never leaks content from contact B's thread into the draft for A.

## 9. Cost controls

- Token budget per prospect full-flow (COLD → BOOKED): **< 20 K input + < 3 K output tokens** at dev-tier.
- Hard cap per LLM call: 8 K output tokens (Qwen3-Next), rejects above.
- Langfuse cost attribution tag per call: `{stage, variant, tool, model}`.
- If per-prospect spend > $0.20, pipeline pauses and emits alert (see `cost_pathology_*` probe).

## 10. Acceptance tests

- A cold-email draft for a fixture prospect with strong signals mentions funding, velocity ratio, AI maturity band, and exactly one gap practice — no more.
- A cold-email draft for a fixture with `qualifies_for_aggressive_hiring_claim = false` never contains the phrase "aggressive hiring" (case-insensitive) nor synonyms.
- A reply that says "what's your pricing for a 10-person data team?" triggers `handoff_human(reason="prospect_asked_for_specific_pricing")` if the 10-person ask is outside the public-tier band.
- A reply from a prospect whose bench match is Python/data but who asks for "8 Go engineers" triggers `handoff_human(reason="prospect_asked_bench_beyond_capacity")`.
- Two threads at the same company produce drafts that do not share prose — diff is measurable.
