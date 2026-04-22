# 08 — HubSpot Integration

**Source:** Challenge document — "The Production Stack" (CRM row), "Act II — Required integrations".

## 1. Provider

**HubSpot Developer Sandbox** — free. Accessed over the HubSpot MCP server. Rate limit 100 API calls per 10 s.

## 2. Object model

We use three standard object types plus one custom association record.

### Company
Mapped 1-to-1 from Crunchbase ODM.

| Field | Source | Custom property name |
|-------|--------|----------------------|
| `name` | `CrunchbaseRecord.name` | standard |
| `domain` | `CrunchbaseRecord.domain` | standard |
| `industry` | `CrunchbaseRecord.industries[0]` | standard |
| `numberofemployees` | `CrunchbaseRecord.employee_count_range` | standard |
| `country` | `CrunchbaseRecord.country` | standard |
| `crunchbase_uuid` | `CrunchbaseRecord.uuid` | `convergine_crunchbase_uuid` (custom, required) |
| `icp_segment` | `icp_classification.segment` (int or null) | `convergine_icp_segment` |
| `icp_mode` | `confident` \| `abstain` | `convergine_icp_mode` |
| `icp_confidence` | float | `convergine_icp_confidence` |
| `ai_maturity_score` | 0–3 | `convergine_ai_maturity_score` |
| `ai_maturity_confidence` | float | `convergine_ai_maturity_confidence` |
| `enrichment_timestamp` | ISO8601 | `convergine_enrichment_timestamp` |
| `hiring_signal_brief_url` | link to cached JSON artifact | `convergine_brief_url` |
| `competitor_gap_brief_url` | link to cached JSON artifact | `convergine_gap_brief_url` |

### Contact
A synthetic persona per prospect during the challenge week.

| Field | Source | Custom property name |
|-------|--------|----------------------|
| `email` | `<slug>@sink.convergine.local` | standard |
| `firstname` / `lastname` | synthetic | standard |
| `jobtitle` | inferred role (CTO / VP Eng / Founder) | standard |
| `associatedcompanyid` | HubSpot company id | association |
| `preferred_channel` | `email` \| `sms` | `convergine_preferred_channel` |
| `synthetic` | always `true` during the week | `convergine_synthetic` |

### Deal
Opened when a discovery call is booked.

| Field | Source |
|-------|--------|
| `dealname` | `Convergine discovery – {{ company.name }}` |
| `pipeline` | `default` |
| `dealstage` | `appointmentscheduled` |
| `amount` | expected ACV midpoint for the assigned segment |
| `closedate` | +90 days from booking |
| `convergine_segment` | segment id |
| `convergine_thread_id` | thread uuid |

### Conversation Event (custom)
Append-only log. One row per `agent.integrations.hubspot_mcp.log_event` call.

| Field | Type |
|-------|------|
| `event_id` | UUID |
| `contact_id` | HubSpot ref |
| `company_id` | HubSpot ref |
| `event_type` | see [06 §3 LogCrmInput](06-agent-design.md) |
| `channel` | `email` \| `sms` \| `voice` \| `system` |
| `trace_id` | Langfuse trace reference |
| `payload_json` | full event payload |
| `draft` | boolean, mirrors `X-Convergine-Draft` header |
| `created_at` | ISO8601 |

## 3. MCP client

```python
# agent/integrations/hubspot_mcp.py

class HubSpotClient:
    def __init__(self, mcp_url: str, token: str): ...

    # companies
    def upsert_company(self, c: CompanyUpsert) -> str: ...         # returns company_id
    def find_company_by_crunchbase_uuid(self, uuid: str) -> str | None: ...

    # contacts
    def upsert_contact(self, contact: ContactUpsert) -> str: ...

    # deals
    def create_deal(self, deal: DealCreate) -> str: ...
    def advance_deal_stage(self, deal_id: str, stage: str) -> None: ...

    # events
    def log_event(self, ev: ConversationEvent) -> None: ...         # idempotent on event_id
```

Wrap every call in:
- Exponential back-off (max 3 retries) for 429s.
- Langfuse span `hubspot.<op>` with `rate_limit_remaining` tag.
- Circuit-breaker: if 3 consecutive 5xx within 30 s, pause outbound pipeline and alert.

## 4. Idempotency

- `event_id` is a UUID generated once per state transition. MCP `log_event` deduplicates on `event_id`.
- `upsert_company`, `upsert_contact` use their natural keys (`crunchbase_uuid`, `email`) to avoid duplicates.

## 5. Rate-limit budget

100 calls per 10 s. A full COLD → BOOKED flow emits approximately:

| Step | Calls |
|------|-------|
| `upsert_company` | 1 |
| `upsert_contact` | 1 |
| `log_event` × conversation turns | 4–8 |
| `create_deal` + `advance_deal_stage` × 2 | 3 |
| **Total per prospect** | **9–13** |

Headroom: > 7× at saturation. Not a bottleneck.

## 6. Draft marking

Every `log_event` with `draft == true` is distinguishable in the HubSpot UI by a filtered view (`convergine_draft = true`). The memo + Skeptic's Appendix references this filter as the quarantine for any pre-approval outbound.

## 7. Demo-video expectations (interim + final)

- Screenshot of a populated **Company** record showing all `convergine_*` custom properties non-null.
- Screenshot of a **Contact** record with `associatedcompanyid` linking correctly.
- Screenshot of a **Conversation Event** list showing all stages for one prospect.
- `enrichment_timestamp` must be within 24 h of the demo recording.

## 8. Acceptance tests

- Inserting a Company without `crunchbase_uuid` raises `MissingCrunchbaseUuid`.
- A second `upsert_company` with the same `crunchbase_uuid` returns the existing company_id (no duplicate).
- `log_event` is idempotent: calling it twice with the same `event_id` results in one row in HubSpot.
- `create_deal` requires a linked company and contact; raises `UnlinkedDeal` otherwise.
- Rate-limit exhaustion produces a 429 → back-off path exercised under test.
