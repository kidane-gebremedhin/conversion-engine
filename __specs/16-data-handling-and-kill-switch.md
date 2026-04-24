# 16 — Data Handling and Kill Switch

The policy rules in [`tenacious_sales_data/policy/data_handling_policy.md`](../tenacious_sales_data/policy/data_handling_policy.md) and the limited license in [`tenacious_sales_data/LICENSE.md`](../tenacious_sales_data/LICENSE.md) are **binding**. This spec defines how the implementation enforces each clause in code — not merely in documentation.

**Violations are grounds for removal from the program.** The rules do not depend on intent; they depend on the code pattern.

## Rule 1 — No real Tenacious customer data leaves Tenacious

The implementation receives no CRM exports, no real threads, and no real deal names. If the repo ever contains such data (through program error), it is reported to tutors immediately and deleted.

Enforcement: a CI check scans committed files for patterns that could plausibly be real customer data (email domains not in `tenacious_sales_data/`, phone numbers, names absent from the synthetic-prospects fixture). The check runs on every `git push`.

## Rule 2 — Every prospect the system contacts during the challenge week is synthetic

Every prospect in `data/synthetic_prospects.json` is a **synthetic profile** derived from public Crunchbase firmographics combined with **fictitious contact details**. Program-operated email and phone addresses replace real ones. The program's SMS rig routes all outbound to a staff-controlled sink.

**You may not use real company contact addresses.** Not even ones found on a public website. A `contact@examplecompany.com` in the queue **resolves to the sink**, not to the real company.

Enforcement:

- `data/synthetic_prospects.json` is the **only** allowed source of prospect contact records. A runtime check in `agent/kill_switch.py` asserts the recipient is drawn from this file **or** matches the staff sink pattern.
- Any other recipient raises `PolicyViolation` and halts the process.

## Rule 3 — Seed materials are licensed for the challenge week only

Per `LICENSE.md`:

- **May**: read, reference, and adapt seed materials inside the repo during the week.
- **May**: quote ICP, pricing bands, and sample email sequences in agent prompts.
- **May**: retain the repo after the challenge with these redactions:
  - All Tenacious-branded email copy marked `draft` in metadata.
  - Bench-summary references replaced with placeholder counts.
- **May not**: redistribute seed materials outside the repo, publish publicly, or quote client / case-study names beyond the anonymized materials.

Enforcement:

- The repo `.gitignore` explicitly excludes `data/real_*`, `eval/runs/leakable_*`, and any non-tenacious_sales_data path that could contain customer data.
- A redaction script `scripts/redact_for_portfolio.sh` exists to apply the post-week redactions in one pass.

## Rule 4 — Public-source scraping rules

Per the data-handling policy:

- **Public pages only.** No login. No stored cookies or session tokens for gated content.
- **No captcha bypass.** A captcha triggers `status: rate_limited` in `data_sources_checked` and stops that scrape.
- **Robots.txt is respected.** Checked on first contact per domain, cached 24h.
- **Rate limit**: at least 2 seconds between requests to the same domain; at most 3 concurrent tabs per domain.
- **User agent**: `TRP1-Week10-Research (trainee@trp1.example)` — never impersonates a browser or a named crawler.
- **Live-crawl cap**: no more than 200 distinct companies during the challenge week.

Enforcement (`agent/enrichment/jobposts.py`, `agent/enrichment/leadership.py`):

- A global in-memory `DomainRateLimiter` tracks per-domain request timestamps; requests under 2s fail fast.
- `data/crawl_counter.json` is updated atomically; a 201st unique domain lookup raises `PolicyViolation`.
- A `robots.txt` cache is checked before any GET; disallowed paths raise `PolicyViolation`.
- Playwright is configured with the policy user agent; a startup assertion verifies the UA is not the default browser UA.

## Rule 5 — The kill switch is not optional

### Contract

The kill switch is a single function, `deliver(channel, to, payload) -> message_id`, in `agent/kill_switch.py`. **No other code path from agent to external sender exists.** This is the load-bearing policy boundary.

```python
def deliver(channel: Channel, to: str, payload: Payload) -> MessageId:
    if not settings.TENACIOUS_OUTBOUND_ENABLED:
        to = settings.sink_for(channel)     # email / sms / voice sink
        payload = _mark_sink_metadata(payload)
    _assert_draft_header_present(payload)
    _assert_recipient_synthetic_or_sink(to, channel)
    _log_langfuse_deliver_span(channel, to, payload)
    return _channel_adapter(channel).send(to, payload)
```

### Configuration

- `TENACIOUS_OUTBOUND_ENABLED` — **defaults to unset**. `.env.example` ships with the line commented out.
- `EMAIL_SINK_ADDRESS`, `SMS_SINK_NUMBER`, `VOICE_SINK_NUMBER` — staff-controlled destinations, provided by program staff.
- Flipping `TENACIOUS_OUTBOUND_ENABLED=1` requires program-staff approval (the approval is logged and required as part of the pilot-selection process).

### Enforcement at three levels

1. **In code**: the kill switch is the only sender path. A CI grep fails the build if any file outside `agent/kill_switch.py` imports a provider SDK (`resend`, `mailersend`, `africastalking`, voice rig) and calls its send method directly.
2. **At runtime**: `deliver()` asserts the recipient is either a synthetic-prospect address (from `data/synthetic_prospects.json`) or the staff sink. Any other recipient raises `PolicyViolation`.
3. **At boot**: `infra/smoke_test.sh` confirms the kill-switch gate is wired before the agent starts processing outbound. A failure is a Day-1 readiness blocker.

### The contract documented in README

The repository `README.md` documents the kill switch explicitly — what it is, how it is configured, how the smoke test verifies it, and what the approval process is for flipping it. This is a **required** README section (see [spec 17](17-deliverables-checklist.md)).

## Rule 6 — Tenacious-branded output is marked draft

Any output of the system that contains Tenacious-branded content (emails, call scripts, proposal snippets, pricing) is marked `draft` in metadata. The Tenacious executive team reserves the right to redact any such content from the memo.

Enforcement:

- **Emails**: every outbound payload carries `X-Tenacious-Status: draft` header. `_assert_draft_header_present(payload)` fires inside `deliver()`. Missing header raises `PolicyViolation`.
- **HubSpot records**: every contact, deal, and engagement carries `tenacious_status=draft` by default. See [spec 08](08-hubspot-integration.md).
- **Memo**: every Tenacious-branded claim in `evidence_graph.json` carries `draft_status: draft`. See [spec 14](14-memo-specification.md).

## Rule 7 — Data minimization in traces

Langfuse and HubSpot traces log only what is necessary for:

- Evaluating agent performance.
- Producing the evidence graph for the memo.
- Debugging failures.

**Do not log**:

- Full PII beyond first name + email (no home address, no personal phone unless the prospect explicitly shared it for scheduling).
- Payment / banking info.
- HIPAA / GDPR-health-category content.

Enforcement:

- `config.yaml > observability.allowed_attributes` defines the closed set of attribute keys Langfuse spans may carry. `agent/observability/langfuse.py` strips any non-allowed attributes before export.
- HubSpot custom properties are restricted to the `tenacious_*` prefix (see [spec 08](08-hubspot-integration.md)).

## Rule 8 — Non-disclosure of Tenacious internal data

No Tenacious internal data enters a public repository or platform. The repo may be kept private during the challenge; before any public release, the redaction script is applied.

## Rule 9 — Incident reporting

If the system has:

- Sent outbound to a real (non-sink) recipient,
- Logged real customer PII,
- Scraped in a way that may violate a source's terms,
- Or done anything else that may violate the policy,

**stop the agent immediately** and post in Slack with a description and timestamp. Program staff help assess and remediate. **Honest accidental reporting is treated much more favorably than concealment.**

Enforcement in code:

- `agent/kill_switch.py` raises `PolicyViolation` on any sink-bypass attempt. The exception is uncatchable at the channel layer (it propagates to the process boundary).
- A post-hoc audit script `scripts/audit_week.py` walks Langfuse traces for any `deliver.*` span whose recipient is not the sink or a synthetic address; the report is reviewed on Day 7 and attached to the final submission.

## Rule 10 — Questions

When in doubt, ask. The policy is deliberately conservative; edge cases are resolved in `#trp1-week10-conversion-engine` Slack, not by the implementation making a judgment call.

## Acknowledgement artifact

Per `policy/acknowledgement.md`:

- Acknowledgement is signed before Act I starts.
- `infra/acknowledgement_signed.txt` contains the UTC timestamp of confirmation; `infra/smoke_test.sh` verifies this file exists.
- The repo includes both `infra/acknowledgement_signed.txt` and `policy/acknowledgement_signed.txt` (one location or the other, per the smoke test's expectation).

## Summary: what the implementation must NOT do

- Import a provider SDK outside `agent/kill_switch.py` or its channel adapters.
- Send outbound to an address that is not the staff sink or a synthetic-prospect address.
- Ship outbound without the `X-Tenacious-Status: draft` header.
- Scrape more than 200 distinct domains during the challenge week.
- Log PII beyond first name and email.
- Commit an `.env` file, HubSpot token, Resend key, or Africa's Talking secret.
- Default `TENACIOUS_OUTBOUND_ENABLED` to anything but unset.
- Hide or silently remediate a policy violation.
