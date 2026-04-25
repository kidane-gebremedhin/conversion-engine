# 09 — Calendar Booking (Cal.com)

The calendar layer exists so the agent can end an engaged conversation with a booked discovery call and a context brief attached — the single biggest lever the agent has on discovery-to-proposal conversion.

## Setup

- **Provider**: **Cal.com self-hosted** via `docker compose up` from `infra/docker-compose.yml`.
- **Rationale**: no credit card, no admin-API gate, and a local Cal.com instance is indistinguishable from a managed one for the challenge-week scope.
- **Calendar fixtures**: program-provided mock calendars in `infra/cal_fixtures/` (downloaded after policy acknowledgement is signed). Booking against a real calendar during the challenge week is a policy violation.

## Kill-switch interaction

Booking is one of the four outbound channels gated by `TENACIOUS_OUTBOUND_ENABLED` (see [spec 16 Rule 5](16-data-handling-and-kill-switch.md)). The agent's `agent/calendar/client.py:create_booking()` consults `gate_booking()` before any write:

- **Flag unset** → the booking is forced to the local-file mock at `data/calcom_local/bookings.jsonl`. The real Cal.com API is **not** called, regardless of whether `CALCOM_API_KEY` is configured.
- **Flag set + recipient is a synthetic prospect or the staff sink** → the real API is called.
- **Flag set + recipient is anything else** → `PolicyViolation` is raised; the process halts.

In practice, the challenge runs in webhook-only mode (the prospect self-books through the public Cal link the agent emailed). Real bookings only exist when (a) a real human consciously books and (b) the email containing that link wasn't sink-routed — i.e., when the kill switch is intentionally enabled.

## Configuration (env)

| Env var | Purpose |
|---|---|
| `CALCOM_BASE_URL` | e.g., `http://localhost:3000` in dev |
| `CALCOM_API_KEY` | Admin API key for programmatic slot discovery |
| `CALCOM_USERNAME` | Default event-type owner |
| `CALCOM_EVENT_TYPE_DISCOVERY_15` | Slug for the 15-minute discovery-offer event |
| `CALCOM_EVENT_TYPE_DISCOVERY_30` | Slug for the 30-minute discovery-scoping event |
| `CALCOM_WEBHOOK_URL` | Booking-created webhook (agent endpoint) |
| `CALCOM_WEBHOOK_SECRET` | HMAC secret |
| `CALCOM_DEFAULT_DURATION_MINUTES` | Default when not specified |
| `CALCOM_DEFAULT_DELIVERY_LEAD` | e.g., `arun@<domain>` (mock email) |

## Event types

Two event types created on Day 0 via `agent/calendar/client.py`:

- **`discovery-15`** — 15 minutes, used in cold outreach when the ask is "15 minutes to walk through our model."
- **`discovery-30`** — 30 minutes, used in engaged-reply flows when the ask is "a proper scoping conversation."

The composer selects the duration based on `sequence_position`:

- `cold_1`, `cold_2`, `curious` → 15-minute link.
- `engaged`, `objection_handling_book` → 30-minute link.

## Booking flow

```
Agent proposes time  ──▶  Composer includes Cal link with prospect timezone
                                       │
                                       ▼
         Prospect clicks link, picks slot, submits name + email
                                       │
                                       ▼
          Cal.com webhook POST /webhook/cal with booking payload
                                       │
                                       ▼
         Agent.webhook_cal_booking() handles the event:
         1. Verify HMAC signature
         2. Look up HubSpot contact by email
         3. Create HubSpot MEETING engagement + Deal
         4. Render discovery_call_context_brief.md per schema
         5. Post context brief as NOTE on Deal
         6. Post context brief to the Cal.com event "additional notes" field
         7. Send post-book confirmation email to prospect (routed through kill-switch)
         8. Langfuse trace the booking event
```

## Discovery call context brief

Schema: [`schemas/discovery_call_context_brief.md`](../tenacious_sales_data/schemas/discovery_call_context_brief.md). The agent **must** fill every required section — the brief's grade is measured on completeness, not optionally filling sections.

The context-brief synthesizer (`agent/calendar/context_brief.py`) consumes:

- `hiring_signal_brief.json`
- `competitor_gap_brief.json`
- `bench_summary.json`
- Langfuse trace of the thread (for objections, commercial signals, urgency quotes)
- LLM call with `seed/style_guide.md` + `seed/discovery_transcripts/*.md` as context (for Section 8 "suggested call structure")

Output: a single markdown document attached to the Deal and the Cal event. **At most one scroll on a laptop screen** — longer briefs are skipped by humans; that defeats the purpose.

The brief's **Section 10 — Agent confidence and unknowns** is mandatory. An agent that claims "high confidence on everything" signals it is not self-aware; the probe library includes a calibration check.

## Time-zone handling

Every Cal link the composer emits includes `?timezone=<iana>` with the prospect's inferred timezone:

- Crunchbase HQ country → primary IANA lookup.
- Domain TLD → fallback (.co.uk → Europe/London, .de → Europe/Berlin, etc.).
- `config.yaml > timezone.default` → last resort.

Scheduling edge cases the Act III probe library tests:

- **DST boundaries** (North American DST starts second Sunday of March; EU DST last Sunday of March — they are misaligned by ~2 weeks).
- **Asymmetric business hours** — proposing 6am local to a prospect in London while operating from East Africa.
- **India +5:30** (not a target but appears in Crunchbase sector peers).
- **Fractional offsets on non-ICS calendars** — a historical Cal.com bug surface.

The agent's time-proposal logic:

1. Default slot suggestions fall in the prospect's 09:00–17:00 local window.
2. At least one slot must fall in the **overlap band** (03:00–05:00 UTC overlap with Tenacious East Africa, configurable).
3. Slot suggestions are emitted in the prospect's local time in the email body, with a UTC equivalent in parentheses.

## Post-book confirmation

The confirmation email (channel template: `post_book_confirmation.j2`) reaffirms:

- Prospect name, date/time in prospect's local timezone.
- Delivery lead who will be on the call.
- One-line mention of what is attached ("a short context brief on your firm's hiring signal") — **not** the full brief, which is internal.
- No marketing, no case-study name-drops.

## What the calendar integration must NOT do

- Book against a real human calendar during the challenge week (fixtures only).
- Embed the full context brief in the prospect-facing confirmation email. The context brief is an **internal** artifact for the delivery lead.
- Propose a slot that falls outside the agent's current `available_slots` response from Cal.com (stale slot proposals break trust on the first touch).
- Silently fall back to `config.yaml > timezone.default` without logging — the Langfuse trace must record which timezone-resolution path fired.

## Deliverables checkpoints

- **Day 0**: `docker compose up` succeeds; a test booking flows end-to-end (create event type → book slot → confirmation email received); smoke test passes.
- **Interim**: Cal.com booking screenshot shows one synthetic prospect's 15-minute discovery call booked end-to-end.
- **Final (demo video)**: live show of the booking flow with the context brief visible in the Cal event and in HubSpot.
