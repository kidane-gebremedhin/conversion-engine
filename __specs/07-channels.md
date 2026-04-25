# 07 — Channels

Three channels with strict hierarchy. **Email is primary. SMS is secondary, only for warm-lead scheduling. Voice is the final channel — a discovery call booked by the agent and delivered by a human.**

Matching channel to segment is a deliberate scope choice. Tenacious's prospects are founders, CTOs, and VPs of Engineering. They live in email (and LinkedIn DMs and occasional Slack). Cold SMS to this segment is perceived as intrusive; cold voice is worse. A trainee who rebuilds a voice-heavy architecture here will find prospects do not respond.

## Channel matrix

| Channel | Cold | Warm (post-reply) | Purpose |
|---|---|---|---|
| **Email** | ✓ primary | ✓ substantive replies | Research-grounded outreach, qualification, discovery offer |
| **SMS** | ✗ banned | ✓ scheduling coordination only | Confirming a slot, moving a time, sending a Cal link |
| **Voice** | ✗ banned | ✓ booked discovery call (human) | 15–30 minute scoping conversation |

All three message channels above, **plus programmatic Cal.com booking-creation**, share a single kill-switch flag (`TENACIOUS_OUTBOUND_ENABLED`). When the flag is unset, all four route to a staff-controlled sink — email, SMS, and voice via `deliver()`, bookings via `gate_booking()` + the local-file mock at `data/calcom_local/`. See [spec 16 Rule 5](16-data-handling-and-kill-switch.md) for the contract.

## Email channel

### Provider

- Primary: **Resend** free tier (3,000 emails/month, no credit card, webhook-capable).
- Fallback: **MailerSend** free tier.
- Provider is selected via `EMAIL_PROVIDER` env var (`resend` | `mailersend`). Switching providers requires only the adapter swap in `agent/channels/email/send.py`.

### Configuration (no hard-coded values)

| Env var | Purpose |
|---|---|
| `EMAIL_PROVIDER` | `resend` or `mailersend` |
| `RESEND_API_KEY` / `MAILERSEND_API_KEY` | Provider auth |
| `RESEND_FROM_ADDRESS` | e.g., `research@<configured-domain>` (program-provisioned domain) |
| `RESEND_WEBHOOK_URL` | Inbound reply webhook (ngrok / Cloudflare Tunnel for dev) |
| `RESEND_WEBHOOK_SECRET` | HMAC secret for signature verification |
| `EMAIL_SINK_ADDRESS` | Staff sink when kill switch unset |
| `EMAIL_DEFAULT_REPLY_TO` | Fallback reply-to |

### Outbound flow

1. Composer produces `{ subject, body, html }`.
2. `deliver("email", to, payload)` is called.
3. Kill-switch gate rewrites `to = EMAIL_SINK_ADDRESS` unless `TENACIOUS_OUTBOUND_ENABLED=1`.
4. Adapter sets canonical headers:
   - `X-Tenacious-Status: draft` (Rule 6 in [spec 16](16-data-handling-and-kill-switch.md))
   - `X-Tenacious-Brief-Id: <hiring_signal_brief.id>`
   - `X-Tenacious-Segment: segment_<n>` or `abstain`
   - `X-Tenacious-Trace-Id: <langfuse_trace_id>`
5. Adapter calls provider API; captures `message_id`.
6. HubSpot engagement created; Langfuse span closed.

### Inbound webhook

Endpoint: `POST /webhook/email`.

1. Verify provider HMAC signature using `RESEND_WEBHOOK_SECRET`. Fail → 401.
2. Extract `{ thread_id, from, subject, body_text, received_at }`.
3. Look up thread by `in_reply_to` / `references` headers; fall back to `message_id` correlation.
4. Invoke reply classifier (see [spec 06](06-agent-design.md)).
5. Route per class; respond via the same kill-switch gate.

### Cold sequence — three emails

Per [`seed/email_sequences/cold.md`](../tenacious_sales_data/seed/email_sequences/cold.md):

| # | Timing | Max words | Purpose |
|---|---|---|---|
| 1 | Day 0 | 120 | Signal-grounded opener |
| 2 | Day 5 (no reply) | 100 | Research-finding follow-up (competitor gap brief content) |
| 3 | Day 12 (no reply) | 70 | Gracious close — no guilt, no fourth touch |

**Three emails is the maximum. A fourth cold touch within 30 days is a policy violation.**

Subject-line first-word must be one of: `Context`, `Note`, `Request`, `Congrats`, `Question`, `Follow-up`. Forbidden first-words: `Quick`, `Just`, `Hey`, `Checking`.

### Warm / reply sequence

Per [`seed/email_sequences/warm.md`](../tenacious_sales_data/seed/email_sequences/warm.md). The composer uses the reply-class-specific prompt. All replies preserve the five tone markers and include a Cal link only when the class is `engaged` or `curious`.

### Re-engagement sequence — stalled threads

Per [`seed/email_sequences/reengagement.md`](../tenacious_sales_data/seed/email_sequences/reengagement.md). Fires only when:

- Last reply was `engaged` or `curious`.
- No booking on Cal.com within 7 days of the last agent message.
- No opt-out, hard-no, or soft-defer in the thread.
- Prospect has not been re-engaged in the last 45 days.

Three touches, then parked for 180 days. Re-engagement carries **new information** (new hiring signal, new competitor move, new industry data) — never a "just checking in."

### Termination rules (hard)

The outbound sequence stops immediately on any of:

1. The prospect replies (thread moves to reply-handling).
2. The prospect opts out.
3. The address bounces or is invalid.
4. A later enrichment pass disqualifies the prospect (e.g., layoff between Email 1 and Email 2). Thread closed, reason logged.

## SMS channel

### Provider

**Africa's Talking sandbox**. Free, two-way SMS, virtual short codes, routed to staff sink during the challenge week.

### Configuration

| Env var | Purpose |
|---|---|
| `AT_API_KEY`, `AT_USERNAME` | Africa's Talking auth |
| `AT_SHORT_CODE` | Virtual short code |
| `AT_WEBHOOK_URL` | Inbound SMS webhook |
| `AT_WEBHOOK_SECRET` | Signature secret |
| `SMS_SINK_NUMBER` | Staff sink number when kill switch unset |

### When the agent uses SMS

**Only** when:

1. The prospect has replied by email at least once (warm lead, not cold).
2. The prospect has explicitly shared a phone number in-thread, OR Tenacious has a verified direct number from a public profile.
3. The purpose is **scheduling coordination only** — confirming a time, moving a slot, sending a Cal link.

### What SMS must NOT contain

- Substantive content (competitor-gap insights, pricing discussion, capability framing). These are email-only.
- Marketing language, emojis, or URL shorteners that aren't Cal.com.
- Any content on a cold thread. SMS is strictly post-reply.

### SMS template (under 160 characters, single message)

```
Hi [Name] — [Agent first name] at Tenacious. Per our email: [specific action, e.g., Tue 10am PT]? Cal confirms at: [short link]. Reply N if the slot no longer works.
```

The message is assembled inline by the composer; there are no Jinja2 templates for SMS.

### Inbound SMS webhook

Endpoint: `POST /webhook/sms`. Three intents recognized:

| Content | Intent | Action |
|---|---|---|
| `N` / `no` / `reschedule` | decline-slot | Agent proposes two new slots via email (SMS → email handoff). |
| `Y` / `yes` / `confirm` | confirm | Agent confirms Cal booking, no further SMS. |
| Anything else | escalate | Route to human; no SMS reply. |

## Voice channel (bonus)

### Provider

Program-operated **Shared Voice Rig**. Registered webhook + keyword prefix per trainee.

### Configuration

| Env var | Purpose |
|---|---|
| `VOICE_RIG_BASE_URL` | Rig base URL |
| `VOICE_RIG_WEBHOOK_URL` | Inbound callback |
| `VOICE_RIG_KEYWORD_PREFIX` | Per-trainee prefix |
| `VOICE_RIG_WEBHOOK_SECRET` | Signature secret |

### What the agent uses voice for

- Booking a discovery call (the *end* of the agent's responsibility; the call itself is delivered by a human Tenacious delivery lead).
- In the bonus-demo path: one real voice call end-to-end through the Shared Voice Rig — exercising the τ²-Bench conversational capabilities.

Voice is not used for cold outreach. Ever.

## Channel handoff policy

A thread moves between channels per these transitions:

```
   Email cold (up to 3 touches) ── prospect replies ──▶ Email warm
                                   │
                                   ├── prospect shares phone ──▶ SMS (scheduling only)
                                   │
                                   └── discovery call booked ──▶ Voice (human-delivered)
```

The demo video (final submission) must show an **email-to-SMS handoff** for a warm lead who replied by email and prefers fast SMS scheduling.

## Time-zone handling

Prospects span EU, US, and East Africa. The composer includes the prospect's timezone (from Crunchbase HQ country, or the domain TLD, or a default per `config.yaml > timezone.default`) when proposing slots. Cal.com booking URLs include `?timezone=<iana>`.

**Scheduling edge-case probes** (see [spec 12](12-probe-library.md)) specifically target:

- DST transitions (US begins DST in March, EU in late March).
- Fractional timezones (India +5:30, which is not a Tenacious target but appears in Crunchbase).
- East Africa (+3:00) — Tenacious's own time zone.

## Channel priority in deliverables

The demo video must show channel hierarchy clearly:

1. Cold email with signal-grounded content.
2. Engaged email reply, handled substantively.
3. SMS handoff for warm-lead scheduling coordination.
4. Discovery call booked on Cal.com.
5. (Bonus) Live voice call through the Shared Voice Rig.

Rebuilding a voice-cold-outreach architecture inverts the intended design and scores low on Probe Originality. Do not do it.
