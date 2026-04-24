# 10 — Observability

Langfuse is the trace-and-cost record. Every LLM call, tool call, enrichment step, reply classification, and send event emits a span attached to a conversation-level trace. **No claim in the memo survives without a trace ID.**

## Setup

- **Provider**: **Langfuse cloud free tier** (no credit card).
- **Rationale**: per-trace cost attribution, tool-span support, UI for review, and an OTel-compatible export for the evidence graph.

## Configuration (env)

| Env var | Purpose |
|---|---|
| `LANGFUSE_HOST` | e.g., `https://cloud.langfuse.com` |
| `LANGFUSE_PUBLIC_KEY` | Project public key |
| `LANGFUSE_SECRET_KEY` | Project secret key |
| `LANGFUSE_PROJECT_ID` | Project identifier |
| `LANGFUSE_TRACE_PREFIX` | Namespace prefix, e.g., `trp1_week10_conversion_engine_<trainee_id>` |

## Trace model

One **trace** per prospect conversation (keyed on `thread_id = hash(prospect_email)`). All outbound, inbound, enrichment, classification, and handoff events on that conversation attach as child spans.

```
trace: thread_<thread_id>
├── span: enrichment.pipeline
│   ├── span: crunchbase.lookup
│   ├── span: layoffs.check
│   ├── span: jobposts.fetch
│   ├── span: leadership.detect
│   ├── span: ai_maturity.score
│   ├── span: tech_stack.infer
│   ├── span: bench_match
│   ├── span: competitor_gap.peers
│   └── span: classifier.icp
├── span: composer.cold_1
│   ├── span: llm.compose (model=<tier>, prompt_tokens=, completion_tokens=, usd_cost=)
│   └── span: tone_check (scores_per_marker)
├── span: deliver.email
│   ├── attribute: kill_switch_state = "sink" | "live"
│   └── attribute: provider_message_id
├── span: hubspot.record_outbound
├── span: webhook.email.inbound
├── span: reply.classify
├── span: composer.reply_engaged
├── span: deliver.email
├── span: calendar.booking_created
├── span: context_brief.synthesize
└── span: hubspot.record_booking
```

## Span attributes (required)

Every span sets at minimum:

- `span.name` — canonical, dot-delimited.
- `prospect.domain` — for filtering.
- `prospect.segment` — current segment (may change across enrichment passes).
- `prospect.ai_maturity_score` — snapshot at span start.
- `brief.hiring_signal_generated_at` — for staleness checks.
- `cost.usd` — dollar cost of this span (LLM spans; zero elsewhere).
- `trace.total_cost_usd` — rolling trace-level sum.
- `tier` — `dev` or `eval`, critical for cost budget accounting.
- `kill_switch.state` on any `deliver.*` span.

Optional but encouraged:

- `tone_check.scores` — per-marker score object.
- `honesty_flags` — flags active at the time of send.

## Cost attribution

`agent/observability/cost.py` computes per-span cost from the model's published rate card, stored in `config.yaml > llm.rate_cards`. Rates are in USD per 1M tokens, separated into input and output. The function:

```python
cost = (prompt_tokens / 1_000_000) * rate_card[model].input
     + (completion_tokens / 1_000_000) * rate_card[model].output
```

**Never hard-coded.** Updating a model's rate card is a config change.

## Latency metrics

From trace spans, compute:

- `p50_latency_compose_ms`, `p95_latency_compose_ms` — wall-time of the composer span (cold and warm separately).
- `p50_latency_enrichment_ms`, `p95_latency_enrichment_ms` — full pipeline wall-time.
- `p50_latency_reply_classify_ms` — reply classification.
- `p50_latency_end_to_end_ms` — inbound-webhook-in to outbound-sent across a reply.

The **interim submission requires p50/p95 latency across ≥20 real email+SMS interactions**. Computed from `eval/runs/interim/` trace exports.

## Conversation-level metrics

Computed periodically (daily during the challenge week) and emitted as Langfuse "metrics" events:

| Metric | Definition |
|---|---|
| **cold_send_count** | Outbound cold emails dispatched |
| **reply_rate_cold** | Replies / cold sends over last 72h |
| **reply_rate_signal_grounded** | Replies when `signal_grounded=True` (segment match + briefs complete) |
| **reply_rate_exploratory** | Replies on `abstain` path (generic exploratory email) |
| **stalled_thread_rate** | `(engaged|curious replies that did NOT book within 14d) / (engaged|curious replies)` — the memo KPI |
| **abstention_rate** | `abstain / total classifications` |
| **bench_gap_detected_rate** | Prospects with `bench_available=false` |
| **tone_check_regenerate_rate** | Fraction of drafts regenerated once, twice, or flagged |
| **handoff_rate_per_reason** | Breakdown by the five handoff conditions |
| **cost_per_qualified_lead** | Rolling `total_trace_cost / count(qualified_leads)` |

## Evidence-graph export

`evidence_graph.json` (final submission) maps each numeric claim in `memo.pdf` to:

- A Langfuse trace ID, OR
- A row in `seed/baseline_numbers.md`, OR
- A row in `seed/bench_summary.json`, OR
- A public-source URL.

`agent/observability/langfuse.py` exposes `export_evidence_graph(run_id) -> EvidenceGraph` that walks all traces for a run and emits the JSON.

## Data minimization in traces

Langfuse spans must **not** log:

- Full PII beyond first name + email.
- Payment or banking data.
- HIPAA / GDPR-health categories.

When a composer prompt includes the full `hiring_signal_brief.json`, the span records the **brief URL** as an attribute, not the full brief body. Brief files live in the repo and are referenced, not duplicated.

## τ²-Bench integration

Every τ²-Bench trial emits a dedicated trace prefixed `tau2_<domain>_<task_id>` with:

- `tier` attribute for dev/eval selection.
- `tau2.task_id`, `tau2.partition` (`dev_30` or `sealed_20`).
- Full turn-by-turn spans for retrospection.

`score_log.json` and `trace_log.jsonl` (Act I deliverables) are derived from these traces. See [spec 11](11-tau2-bench-harness.md).

## Dashboards (helpful, not required)

Langfuse UI boards for the challenge week:

- **Conversation funnel** — cold → reply → book, by segment.
- **Cost per trace distribution** — histogram, p50/p95 markers, cost-per-lead overlay.
- **Tone-check regeneration rate** — alert when >10% (signals composer prompt drift).
- **Abstention-rate trend** — alert when >30% (signals classifier or data-source regression).

## What the observability layer must NOT do

- Silently drop spans on network error. Spans are buffered and retried; if the buffer overflows, the process logs a prominent warning.
- Log prompts containing real customer PII (there is none, but the assertion must exist in code).
- Attribute cost to the wrong tier. Every `llm.*` span sets `tier` explicitly; attribution by model-ID heuristic is prohibited because eval-tier and dev-tier models may share APIs.
- Export more detail to Langfuse than the policy allows. The export list is in `config.yaml > observability.allowed_attributes`.
