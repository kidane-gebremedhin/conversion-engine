# 08 — HubSpot Integration

Every conversation event the agent emits writes to HubSpot through the Model Context Protocol (MCP) server. HubSpot is the operational system of record for the conversation; Langfuse is the trace-and-cost record. Both must be consistent.

## Setup

- **Provider**: HubSpot Developer Sandbox app (free, no credit card). App is created on Day 0; app ID + private app token recorded in `.env`.
- **MCP server**: HubSpot's official MCP server (installed per [HubSpot MCP docs](https://developers.hubspot.com/)). 100 API calls per 10 seconds.
- **Authentication**: private-app token (`HUBSPOT_PRIVATE_APP_TOKEN`), never committed. OAuth is not used.

## Configuration (env)

| Env var | Purpose |
|---|---|
| `HUBSPOT_BASE_URL` | e.g., `https://api.hubapi.com` (configurable for mock vs. live) |
| `HUBSPOT_PRIVATE_APP_TOKEN` | Auth token |
| `HUBSPOT_APP_ID` | App identifier |
| `HUBSPOT_MCP_SERVER_URL` | MCP server endpoint |
| `HUBSPOT_PORTAL_ID` | Developer sandbox portal |
| `HUBSPOT_OWNER_ID_DEFAULT` | Default owner for created contacts |
| `HUBSPOT_DEAL_PIPELINE_ID` | Pipeline for discovery-booked deals |

## Custom properties

Created once on Day 0 via `agent/hubspot/schema.py`. All custom properties are prefixed `tenacious_` so they are visible and removable in one filter.

### Contact object

| Property | Type | Purpose |
|---|---|---|
| `tenacious_status` | enum(`draft`, `final`, `opted_out`) | Required on every record; defaults to `draft` |
| `tenacious_segment` | enum(`segment_1_series_a_b`, `segment_2_mid_market_restructure`, `segment_3_leadership_transition`, `segment_4_specialized_capability`, `abstain`) | ICP classification |
| `tenacious_segment_confidence` | number (0–1) | From the hiring signal brief |
| `tenacious_ai_maturity_score` | enum(`0`, `1`, `2`, `3`) | From AI-maturity scoring |
| `tenacious_ai_maturity_confidence` | enum(`high`, `medium`, `low`) | Confidence in the score |
| `tenacious_outreach_status` | enum(`never_contacted`, `cold_1_sent`, `cold_2_sent`, `cold_3_sent`, `warm_active`, `booked`, `opted_out`, `parked`) | Thread state |
| `tenacious_last_brief_generated_at` | datetime | Freshness check |
| `tenacious_hiring_signal_brief_url` | string | Link to brief file in repo / storage |
| `tenacious_competitor_gap_brief_url` | string | Link to brief file in repo / storage |
| `tenacious_enrichment_sources_checked` | string (JSON) | Serialized `data_sources_checked` array |
| `tenacious_honesty_flags` | multi-enum | All fired honesty flags |
| `tenacious_bench_gap_detected` | bool | Mirror of `hiring_signal_brief.bench_to_brief_match.bench_available == false` |
| `tenacious_kill_switch_state` | enum(`sink`, `live`) | The kill-switch state at time of last send |
| `tenacious_trace_id_latest` | string | Latest Langfuse trace ID |

### Deal object

Created on discovery-call booking.

| Property | Type | Purpose |
|---|---|---|
| `tenacious_discovery_call_scheduled_at` | datetime | Cal.com booking time (UTC) |
| `tenacious_discovery_call_timezone_prospect` | string | IANA timezone |
| `tenacious_delivery_lead_email` | string | Assigned human |
| `tenacious_context_brief_url` | string | The markdown context brief attached |
| `tenacious_segment_at_booking` | enum | Snapshot of segment at booking time |
| `tenacious_evidence_graph_id` | string | Cross-ref for memo |

### Engagement types

Every conversation event is written as a HubSpot **engagement** with these canonical types:

| Engagement type | When created | Associations |
|---|---|---|
| `EMAIL` | Every outbound email draft sent; every inbound reply received | Contact |
| `NOTE` | Brief attachments, tone-check scores, policy flags | Contact |
| `TASK` | Human-handoff triggered | Contact + Deal |
| `MEETING` | Cal.com booking confirmed | Contact + Deal |
| `CALL` | Voice-rig interaction (bonus) | Contact + Deal |

## Conversation event contracts

`agent/hubspot/events.py` exposes one function per event:

- `upsert_contact(prospect) -> contact_id`
- `attach_brief(contact_id, brief_type, brief_json, brief_url)` — one NOTE per brief, with a structured JSON body.
- `record_outbound(contact_id, draft, provider_message_id, trace_id)` — creates an EMAIL engagement with the subject/body, tone-check scores, and draft flag.
- `record_inbound(contact_id, reply, classification, trace_id)` — creates an EMAIL engagement with the classification result.
- `create_handoff_task(contact_id, reason, delivery_lead_email, context_brief_md)` — TASK engagement.
- `record_booking(contact_id, cal_booking)` — creates the MEETING engagement and the Deal.
- `mark_opted_out(contact_id, reason)` — sets `tenacious_outreach_status=opted_out` and `tenacious_status=opted_out`.

Every function:

1. Rate-limits at 100 calls per 10s (token bucket in-memory).
2. Retries on 429 with exponential backoff (max 3 retries, then dead-letter to `eval/hubspot_dead_letter.jsonl`).
3. Emits a Langfuse tool-span for the call.

## Every conversation event → HubSpot

**Invariant** (enforced by code review, probe-tested in Act III): for every message the agent sends or receives, there is exactly one HubSpot engagement with a matching `trace_id`. The probe library includes a consistency check that replays traces against HubSpot queries to detect drift.

## Data minimization in HubSpot

Per Rule 7 in `data_handling_policy.md`:

- **Log**: first name, email, company, public LinkedIn URL, segment, confidence scores, brief URLs, trace IDs, message contents (the thread).
- **Do not log**: full PII beyond first name + email (no home address, no personal phone unless the prospect shared it explicitly for scheduling), payment info, HIPAA-sensitive or GDPR-health data.

When uncertain, default to not logging.

## Draft marking

Every contact and deal record created during the challenge week carries `tenacious_status = "draft"`. The Tenacious executive team reserves the right to redact any such record from the memo. Draft marking is **not** removed on booking; the `MEETING` engagement is also draft until program-staff review.

## Interim-submission requirement

The interim PDF (Wednesday) must include a HubSpot screenshot showing one synthetic prospect's contact record with all custom properties populated, enrichment timestamps present, and the `tenacious_status=draft` flag visible.

## Final-submission demo requirements

The demo video must show, in real time:

- Contact record populating as the enrichment pipeline completes.
- Engagements appearing as the agent sends cold email 1, receives a reply, and responds.
- A MEETING engagement and Deal created at Cal.com booking time.
- The context brief visible as a NOTE attached to the Deal.

## What the integration must NOT do

- Modify or delete contacts created outside this repo's prefix. The custom-property prefix `tenacious_` is the safety boundary.
- Remove `tenacious_status=draft` programmatically. Only a human clears draft status.
- Log real customer PII under any circumstance (there is none in the sandbox, but the code path must not exist either).
- Post to the production HubSpot portal. `HUBSPOT_PORTAL_ID` must point to the Developer Sandbox; a runtime assertion fails the process if the portal ID matches a known production pattern.
