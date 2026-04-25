# 03 — Act II: Production Stack (Enrichment + Agent + Channels + HubSpot + Cal.com)

## Goal

Stand up the full production stack so that one synthetic prospect can be enriched, receive a signal-grounded cold email, reply, be qualified, receive scheduling SMS, book a discovery call, and appear correctly in HubSpot and Cal.com — all gated by the kill switch so outbound routes to the staff sink. Produce p50/p95 latency across ≥20 synthetic-prospect interactions.

## Spec references

- [`__specs/01-architecture.md`](../__specs/01-architecture.md)
- [`__specs/04-data-sources.md`](../__specs/04-data-sources.md)
- [`__specs/05-signal-enrichment-pipeline.md`](../__specs/05-signal-enrichment-pipeline.md)
- [`__specs/06-agent-design.md`](../__specs/06-agent-design.md)
- [`__specs/07-channels.md`](../__specs/07-channels.md)
- [`__specs/08-hubspot-integration.md`](../__specs/08-hubspot-integration.md)
- [`__specs/09-calendar-booking.md`](../__specs/09-calendar-booking.md)
- [`__specs/10-observability.md`](../__specs/10-observability.md)
- [`__specs/16-data-handling-and-kill-switch.md`](../__specs/16-data-handling-and-kill-switch.md)

## Dependencies

- [`01-preflight.md`](01-preflight.md) complete.
- [`02-act1-tau2-baseline.md`](02-act1-tau2-baseline.md) can run in parallel with this phase (independent code paths).

## Tasks

### 3.1 Configuration layer and kill-switch gate

1. Implement `agent/config.py` using `pydantic-settings`:
   - Loads `.env` into a `Settings` model.
   - Loads `config.yaml` into a `Config` model.
   - Resolves `${PLACEHOLDER}` entries in YAML from `seed/baseline_numbers.md` and `seed/bench_summary.json`.
   - Asserts every required field; masks secrets in debug output.
2. Implement `agent/kill_switch.py`:
   - `deliver(channel, to, payload) -> MessageId` for message-shaped outbound (email/SMS/voice).
   - `gate_booking(prospect_email) -> "live" | "sink"` for programmatic Cal.com booking-creation.
   - Both rewrite to the sink when `TENACIOUS_OUTBOUND_ENABLED` is unset; bookings are forced to the local-file mock at `data/calcom_local/bookings.jsonl`.
   - Asserts `X-Tenacious-Status: draft` header present on email payloads.
   - Asserts recipient is either staff sink or in `data/synthetic_prospects.json` (for both gates).
   - Emits a `deliver.*` Langfuse span and a local audit-log line for both gates.
3. Wire `agent/calendar/client.py:create_booking()` to consult `gate_booking()` before any real-API write.
4. Add a CI grep test: fail the build if any file outside `agent/kill_switch.py` or `agent/channels/*/send.py` imports the provider send methods. Same grep also fails the build if any file outside `agent/calendar/client.py` calls Cal.com's bookings endpoint.

### 3.2 Synthetic prospects fixture

1. Write `data/synthetic_prospects.json` — at least 25 prospects derived from public **Crunchbase, LinkedIn job-post, and layoffs.fyi** data, combined with fictitious contact details (program-operated names; email addresses of the form `<role>+trp1-sink@example.com` — `example.com` is RFC 2606 §3 IANA-reserved so it cannot resolve to a real inbox, the `+trp1-sink` subaddress signals the program-week sink, and HubSpot's email validator accepts the format as-is; phone numbers in the `+1-555-01xx` reserved fictitious-number range). The `company_domain` field stays on the `*.example` reserved TLD (it is a lookup key, never an outbound recipient). The enrichment pipeline only **reads** from the three public sources; it never writes back, posts, or contacts any party associated with them. Include variety:
   - 5 in each of Segments 1, 2, 3, 4.
   - 5 edge cases (layoff+funding, interim CTO, AI-maturity 0 vs 3, bench-gap, multi-thread).
2. Include `prospect_email`, `prospect_name`, `prospect_company`, `prospect_title`, `company_domain` (matches a Crunchbase ODM entry), `expected_segment`, `expected_ai_maturity_score`, `notes`.

### 3.3 Data-source adapters

Implement each enrichment module with the contracts from [spec 05](../__specs/05-signal-enrichment-pipeline.md):

1. `agent/enrichment/crunchbase.py` — load `data/crunchbase_odm_sample.json`; `lookup_by_domain()`.
2. `agent/enrichment/layoffs.py` — load `data/layoffs_fyi_2026_q1.csv`; `within_window()`.
3. `agent/enrichment/jobposts.py` — Playwright scraper with the policy rate-limiter and user agent; reads the April-2026 snapshot primary and live-crawls ≤200 companies; writes to `data/crawl_counter.json`.
4. `agent/enrichment/leadership.py` — parses Crunchbase People + press; detects interim/acting via a regex list.
5. `agent/enrichment/ai_maturity.py` — implements the 6-signal weighted scoring; each justification carries `signal`, `status`, `weight`, `confidence`, `source_url`.
6. `agent/enrichment/tech_stack.py` — BuiltWith/Wappalyzer adapter.
7. `agent/enrichment/competitor_gap.py` — peer selection, peer scoring, top-quartile computation, gap findings with ≥2 peer_evidence entries each.

Each adapter:
- Returns a typed Pydantic result.
- Appends to `data_sources_checked[]` with `{source, status, error_message?, fetched_at}`.
- Respects the policy rate limit (2s per domain, 3 concurrent tabs max).

### 3.4 Pydantic brief models

1. `agent/enrichment/briefs.py` — Pydantic classes `HiringSignalBrief` and `CompetitorGapBrief` matching the JSON schemas.
2. `tests/test_schema_conformance.py` — validates each Pydantic `model_dump()` against the JSON schema in `tenacious_sales_data/schemas/*.schema.json`. Runs in CI.

### 3.5 Enrichment pipeline orchestrator

1. `agent/enrichment/pipeline.py` implements the DAG from [spec 05](../__specs/05-signal-enrichment-pipeline.md#pipeline-dag).
2. `make enrich DOMAIN=<domain>` runs the pipeline and writes briefs to `eval/briefs/<domain>/`.
3. Sets honesty flags per the table in [spec 05](../__specs/05-signal-enrichment-pipeline.md#honesty-flags-set-at-pipeline-end).
4. Classifies via `agent/classifier.py` (rule-based, abstention threshold 0.6).

### 3.6 Prompts and templates

1. Write the 11 prompts in `agent/prompts/` referenced in [spec 18](../__specs/18-configuration.md#8-prompt-ids-and-template-paths-yaml). Each prompt:
   - Quotes the five tone markers verbatim from `seed/style_guide.md`.
   - Lists disallowed phrases.
   - Embeds the before-send self-test.
   - Includes one or two few-shot exemplars drawn from `seed/email_sequences/*.md`.
2. Write the 8 email templates in `agent/channels/email/templates/`. Keep them Jinja2 thin; the LLM generates the body, the template wraps signature, headers, and the Cal link.

### 3.7 Composer and tone check

1. `agent/composer.py`:
   - Input: `(segment, hiring_signal_brief, competitor_gap_brief, prospect, sequence_position)`.
   - Calls the LLM with the correct prompt.
   - Parses output to `{subject, body, html}`.
   - Runs deterministic post-checks: word count, subject length, disallowed phrases, bench-gate.
   - Returns `briefs_referenced: [str]` — the list of brief field-paths used.
2. `agent/tone_check.py`:
   - Second LLM call scores the draft 1–5 on each of five markers.
   - Any marker <4 → regenerate once; second failure → flag for human.
   - Attaches scores to the Langfuse span.

### 3.8 Reply classifier and handlers

1. `agent/reply_handler.py`:
   - Classifier LLM call → `{engaged, curious, hard_no, soft_defer, objection, ambiguous}` with confidence.
   - `ambiguous` (confidence < 0.7) → route to human, no reply.
   - Class-specific response path via `composer.compose(sequence_position=warm_<class>)`.
   - `hard_no` path: no reply, HubSpot `outreach_status=opted_out`, suppression list update.
2. `agent/handoff.py`:
   - The five handoff conditions from [spec 06](../__specs/06-agent-design.md#capability-4--handoff-gate).
   - Creates HubSpot task with the rendered discovery-call context brief.
   - Sends one acknowledgement message to the prospect.

### 3.9 Channel adapters

1. `agent/channels/email/send.py` — Resend or MailerSend adapter; `send(to, payload) -> message_id`; called only from `deliver()`.
2. `agent/channels/email/webhook.py` — FastAPI endpoint; signature verify; parse; route to reply handler.
3. `agent/channels/sms/send.py` — Africa's Talking adapter; enforces <160 chars, no emoji, no marketing.
4. `agent/channels/sms/webhook.py` — FastAPI endpoint; three-intent classifier (confirm, reschedule, escalate).
5. `agent/channels/voice/*` — stub for bonus tier; no-op if `VOICE_RIG_BASE_URL` unset.

### 3.10 HubSpot integration

1. `agent/hubspot/schema.py` — creates the custom properties on Day-0 startup (idempotent).
2. `agent/hubspot/client.py` — thin wrapper over HubSpot MCP; token-bucket rate limiter (100 calls / 10 s); retry-with-backoff on 429.
3. `agent/hubspot/events.py` — implements the event-writer contracts from [spec 08](../__specs/08-hubspot-integration.md#conversation-event-contracts).
4. Runtime assertion on boot: `HUBSPOT_PORTAL_ID` does not match a production-portal pattern.

### 3.11 Cal.com integration

1. `agent/calendar/client.py` — event-type setup, slot discovery, booking lookup.
2. `agent/calendar/webhook.py` — handles `booking.created`; signature verify; invoke context-brief synthesizer.
3. `agent/calendar/context_brief.py` — renders the 10-section discovery-call context brief template from [`schemas/discovery_call_context_brief.md`](../tenacious_sales_data/schemas/discovery_call_context_brief.md); attaches to the Cal event and HubSpot Deal as a NOTE.

### 3.12 FastAPI server

1. `agent/server.py` — exposes `/webhook/email`, `/webhook/sms`, `/webhook/voice`, `/webhook/cal`, `/health`.
2. Each webhook: signature verify → normalize → agent call → kill-switch-gated response.

### 3.13 Observability wiring

1. `agent/observability/langfuse.py` — span helpers, trace-level attribute builders, evidence-graph export.
2. `agent/observability/cost.py` — per-span cost from rate card; rolling trace cost.
3. Add the dashboard boards listed in [spec 10](../__specs/10-observability.md#dashboards-helpful-not-required) — not required but they pay for themselves during debugging.

### 3.14 End-to-end synthetic-prospect run

1. `make compose-and-send DOMAIN=<domain>` runs the full pipeline on one prospect:
   - Enrich → classify → compose → tone-check → deliver (to sink).
   - HubSpot writes.
   - Langfuse trace.
2. Manually reply to the sink inbox with an engaged-class message; watch the agent classify, respond, and book.
3. Repeat across the 25+ synthetic prospects in `data/synthetic_prospects.json` until ≥20 real email+SMS interaction traces exist in Langfuse.

### 3.15 20-interaction latency harvest

1. Run `make compose-and-send` across enough prospects to produce ≥20 real interactions covering:
   - Cold email sends (Segments 1–4 and abstain).
   - Engaged replies and grounded responses.
   - Curious replies and targeted replies.
   - Objection replies (price, incumbent vendor, small POC).
   - Hard-no opt-outs.
   - SMS scheduling coordination.
   - Cal.com bookings.
2. Export the p50/p95 latency numbers from Langfuse into `eval/runs/interim/latency_report.json`.

## Acceptance criteria

- [ ] `make smoke` passes.
- [ ] `make enrich DOMAIN=<any>` produces schema-valid `hiring_signal_brief.json` and `competitor_gap_brief.json`.
- [ ] `make compose-and-send DOMAIN=<any>` produces a draft email with `X-Tenacious-Status: draft`, routes to sink, creates a HubSpot engagement, emits a Langfuse trace.
- [ ] At least one end-to-end thread: cold → engaged reply → warm response with Cal link → booking → context brief attached to the Deal.
- [ ] The email-to-SMS handoff works for at least one warm-lead scheduling interaction.
- [ ] ≥20 real interaction traces in Langfuse, with p50/p95 numbers exported.
- [ ] Tone-check regenerate rate <20% across the 20+ runs.
- [ ] Zero kill-switch bypass events across the run.
- [ ] `scripts/audit_week.py` reports zero policy violations.

## Submission gate

**Interim**: the production-stack status, enrichment-pipeline status, competitor-gap-brief status, p50/p95 latency, and one complete synthetic-prospect thread are required for the Wednesday PDF report. See [`04-interim-submission.md`](04-interim-submission.md).

## Exit risks

- **Enrichment slow on live job-post scrape**: the 2-second-per-domain rate limit plus Playwright startup cost can push per-prospect enrichment above 60s. Mitigation: prefer the frozen April-2026 snapshot; live-crawl only for prospects where the snapshot lacks coverage.
- **Webhook URL instability**: ngrok/Cloudflare Tunnel URLs rotate, provider webhooks go stale. Mitigation: persistent subdomain; re-register webhook when the URL changes; document the rotation in `README.md`.
- **HubSpot MCP install friction**: the MCP install is still young and occasionally fails. Mitigation: `agent/hubspot/client.py` abstracts over MCP vs direct REST; flip via `HUBSPOT_USE_MCP=true|false`.
- **Tone-check regenerate loops**: if the tone-check model is too strict, drafts loop. Mitigation: max 1 retry, then flag for human; log flagged drafts to `eval/runs/tone_flagged.jsonl` for prompt-tuning later.
- **Cross-thread leakage during multi-prospect tests**: running 25 prospects concurrently against one HubSpot sandbox can cause race conditions. Mitigation: sequential execution for the first pass; add proper async isolation later if needed.
- **Scraping cap breach**: 200 distinct domains across a week is tight if each prospect needs fresh velocity. Mitigation: live-crawl only when snapshot delta warrants; log the counter in every run.
