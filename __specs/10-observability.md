# 10 — Observability (Langfuse + Cost Attribution)

**Source:** Challenge document — "The Production Stack" (Observability row), "Evidence-graph integrity" (grading).

## 1. Provider

**Langfuse cloud free tier.** One project per trainee. All agent + enrichment LLM calls instrumented.

## 2. What we trace

| Span | Attributes |
|------|------------|
| `enrich.<source>` (crunchbase / jobposts / layoffs / leadership / stack / ai_maturity / gap) | `crunchbase_uuid`, elapsed, cost, records_fetched |
| `agent.prompt.<name>` | `stage`, `variant`, `segment`, `model`, token_in, token_out, cost |
| `tool.<name>` | `stage`, `input_hash`, elapsed |
| `email.send` / `sms.send` | `trace_id`, `to` (sink), `draft`, `variant` |
| `hubspot.<op>` | `rate_limit_remaining`, elapsed |
| `calcom.<op>` | `booking_id`, elapsed |
| `probe.<id>` | pass/fail, cost, elapsed |
| `tau2_bench.task.<id>` | trial, pass@1, cost |

Every root span carries:
- `thread_id` (uuid)
- `crunchbase_uuid`
- `killswitch_enabled` (bool)
- `method_name` (Day-1 baseline / auto-optim / our-method)
- `git_sha`

## 3. Cost attribution

### Per-call cost

Derived at the LLM-client level from OpenRouter's response metadata:
```python
cost_usd = (tokens_in * cost_per_1k_in + tokens_out * cost_per_1k_out) / 1000
```

Store `cost_usd` on every LLM span. Provider prices pulled from `config.yaml` → `llm.providers.<model>.prices`.

### Rig usage

Resend + Africa's Talking + HubSpot + Cal.com are free in their used tiers. We still log a `$0.00` entry per call for completeness — keeps the invoice totals honest.

### invoice_summary.json

Built at the end of the week from Langfuse exports + the `cost_usd` column. Shape:

```json
{
  "period": {"from": "2026-04-19T00:00:00Z", "to": "2026-04-25T21:00:00Z"},
  "totals": {
    "usd": 14.82,
    "calls": 1871,
    "prospects_touched": 47
  },
  "by_model": {
    "qwen3-next-80b-a3b": {"calls": 1612, "usd": 3.21},
    "deepseek-v3.2": {"calls": 52, "usd": 0.18},
    "claude-sonnet-4-6": {"calls": 207, "usd": 11.43}
  },
  "by_stage": {
    "enrich": {"calls": 412, "usd": 0.89},
    "draft_outreach": {"calls": 147, "usd": 2.31},
    "tone_check": {"calls": 294, "usd": 1.42},
    "classify_reply": {"calls": 123, "usd": 0.61},
    "tau2_bench": {"calls": 825, "usd": 8.51},
    "probes": {"calls": 70, "usd": 1.08}
  },
  "by_day": [
    {"date": "2026-04-19", "usd": 0.42},
    {"date": "2026-04-20", "usd": 1.08},
    ...
  ]
}
```

Path: `memo/invoice_summary.json`. Referenced by `evidence_graph.json` for every cost claim in the memo.

## 4. Cost-per-qualified-lead

**Definition** (used in memo, Page 1):

```
cost_per_qualified_lead_usd =
    (total_llm_usd + amortised_rig_usd) 
  / (count(threads with state >= QUALIFIED) during period)
```

- `amortised_rig_usd` = $0 during the challenge week (all sandbox/free tiers). We still note the formula because the memo must show how the metric scales with paid tiers.
- **Target: < $5 per qualified lead.** Penalty if > $8 without explicit justification.

## 5. trace_log.jsonl

Format: one JSON object per **completed trace** (a root span plus its subtree). Schema:

```json
{
  "trace_id": "...",
  "thread_id": "...",
  "crunchbase_uuid": "...",
  "start_ts": "2026-04-22T09:15:00Z",
  "end_ts": "2026-04-22T09:15:04Z",
  "root_span": "agent.full_flow",
  "spans": [
    {"name": "enrich.crunchbase", "elapsed_ms": 123, "cost_usd": 0.0},
    {"name": "agent.prompt.draft_outreach", "elapsed_ms": 812, "cost_usd": 0.0018, "tokens_in": 2812, "tokens_out": 314}
  ],
  "outcome": {"stage_final": "QUALIFIED", "segment": 2, "variant": "signal_grounded"},
  "tags": {"killswitch_enabled": false, "method_name": "signal_confidence_aware"}
}
```

Collected by a Langfuse export script (`scripts/export_traces.py`) into `eval/trace_log.jsonl` and `method/held_out_traces.jsonl`.

## 6. p50 / p95 latency — interim deliverable requirement

The interim PDF report requires **p50/p95 latency numbers from at least 20 real email and SMS interactions pulled from trace log**.

Implementation:

```python
# scripts/latency_report.py
import json, numpy as np
lines = [json.loads(l) for l in open("eval/trace_log.jsonl")]
for stage in ("email.send", "sms.send", "agent.prompt.draft_outreach", "enrich.full"):
    ms = [s["elapsed_ms"] for t in lines for s in t["spans"] if s["name"] == stage]
    print(stage, "n=", len(ms), "p50=", np.percentile(ms, 50), "p95=", np.percentile(ms, 95))
```

Persist output to `eval/latency_report.json` (interim-report-ready). Must cover ≥ 20 synthetic prospect interactions.

## 7. Alerting

- Per-prospect cost > $0.20 → emit Langfuse event `cost.pathology`, pause orchestrator.
- HubSpot 429 repeated 3× in 30 s → back-off + pause.
- Any `tone_check.pass == false` after 3 retries → `handoff_human`.
- Langfuse ingestion failure → local fall-back JSONL append; never block the main flow.

## 8. Acceptance tests

- Every LLM call present in `trace_log.jsonl` has non-null `cost_usd`, `tokens_in`, `tokens_out`.
- The sum over all `cost_usd` in `trace_log.jsonl` equals (± $0.05) `invoice_summary.json.totals.usd`.
- `latency_report.json` contains p50/p95 over ≥ 20 distinct `trace_id`s for `email.send`.
- Every memo claim citing a number has a matching `evidence_graph.json` entry whose `source.trace_id` or `source.invoice_line` exists in the artifacts.
