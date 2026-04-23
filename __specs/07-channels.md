# 07 — Channels (Email / SMS / Voice)

**Source:** Challenge document — "The Production Stack", "Why email is primary for Tenacious", "Note on channel priority".

## 1. Channel hierarchy

**Email is primary.** Tenacious prospects are founders, CTOs, and VPs Engineering who live in email. Cold SMS is unusual for this audience and frequently perceived as intrusive.

**SMS is secondary** — reserved for warm leads who have already replied by email and prefer fast coordination for scheduling.

**Voice is the final channel** — a discovery call, booked by the agent, **delivered by a human** Tenacious delivery lead. The agent never cold-calls.

> Penalty note from the document: "A trainee who rebuilds the compliance version's voice-heavy architecture here will find their prospects do not respond to voice cold outreach."

## 2. Email — primary

### Provider
**Resend** (free tier, 3 000 emails/month, no credit card required).

### Outbound path
```
agent.draft_outreach()
 → policies.tone_check()
 → policies.bench_check()
 → policies.confidence.enforce()
 → integrations.killswitch.route()      # default sink unless flag set
 → channels.email.send.resend_client.send()
 → langfuse.trace_span("email.send")
 → crm.log_event("email_sent")
```

### Resend integration
- Domain: `convergine-sandbox.<your-verified-domain>` (verified at week start).
- From address: `outbound@convergine-sandbox.<domain>` — sandbox pattern makes the synthetic nature explicit.
- Subject-line template: `{{ segment_opening }}: {{ short_finding }}` (e.g., "Your Series B → hiring velocity: a quick observation").
- Headers:
  - `X-Convergine-Trace-Id: <trace_uuid>` — idempotency.
  - `X-Convergine-Draft: true` — while kill-switch unset or `draft_approved == false`.
  - `X-Convergine-Variant: signal_grounded | exploratory`.
  - `X-Convergine-Segment: 1 | 2 | 3 | 4 | abstain`.
  - `List-Unsubscribe: <mailto:unsubscribe+<trace_uuid>@<domain>>, <https://.../unsub/<trace_uuid>>` — RFC 8058 compliant.

### Inbound webhook
- Endpoint: `POST /webhooks/email/reply` in `agent/channels/email/webhook.py` (FastAPI).
- Payload: Resend inbound/reply webhook JSON schema → normalised to `EmailReply`.
- Handling:
  1. Look up trace by `In-Reply-To` header or `References` chain → `thread_id`.
  2. If `thread_id` unknown, treat as cold reply to a sink address → drop + alert.
  3. If recognised, enqueue `classify_reply` prompt, produce `EmailReplyIntent`, transition state.
- Dedup: same `Message-Id` processed once per 24 h.

### Templates
Located at `agent/channels/email/templates/`. Jinja2. Allowlist of variables: brief, maturity, gap, icp, prospect, tenacious.

Required templates:
- `cold_signal_grounded.j2` — signal-grounded variant.
- `cold_exploratory.j2` — abstention / low-confidence variant.
- `nurture_1.j2`, `nurture_2.j2`, `nurture_3.j2` — follow-ups preserving style-guide tone markers.
- `scheduling_offer.j2` — attaches Cal.com link + two suggested slots in prospect's timezone.
- `post_book_confirmation.j2` — confirms booked slot, attaches one-line context for the Tenacious lead.
- `handoff_human.j2` — plain-text to on-call lead with thread summary.

## 3. SMS — secondary (warm-lead scheduling)

### Provider
**Africa's Talking sandbox** — free, two-way SMS, virtual short codes. Registered webhook + keyword prefix per trainee.

### When to use
SMS is only sent after:
1. The prospect has replied at least once by email; AND
2. Either the prospect explicitly asked for SMS (reply intent `preferred_channel == "sms"`) OR the thread has been idle ≥ 96 h and the prospect opted in to SMS in a prior reply.

### Outbound format
- 160-char hard cap (plain ASCII; no emoji). Long messages split at sentence boundary with `(1/2)` / `(2/2)` markers.
- Signature: `— Tenacious (reply STOP to unsubscribe)`.
- Content scope: scheduling only. Never quotes pricing. Never cites bench specifics. No competitor-gap claims in SMS.

### Inbound webhook
- Endpoint: `POST /webhooks/sms/inbound`.
- Africa's Talking webhook schema → `SmsReply`.
- Handled the same way as email replies but constrained to scheduling intents (other intents escalate to email or human handoff).
- Kill-switch: all SMS routes to the staff sink until flag set.

### Short-code keyword prefix
- Every trainee's outbound SMS carries an agreed prefix (e.g., `[CV-NN]`) so the shared rig can route inbound back to the correct handler.
- Prefix + full short-code config in `config.yaml` under `sms.africastalking.*`.

## 4. Voice — bonus

### Provider
**Tenacious Shared Voice Rig** — program-operated. The agent does **not** dial prospects. The agent only arranges for the prospect to receive a call from a human delivery lead via Cal.com.

### Bonus demo (if time)
A single scripted voice call through the Shared Voice Rig, showing:
- Agent dispatches a voice-call request after BOOKED.
- Rig dials the staff sink (not a real prospect).
- Human lead picks up; conversation proceeds.

Registration: webhook + trainee keyword prefix per rig docs. See [18-configuration.md](18-configuration.md) for the env vars.

## 5. Channel-handoff policy matrix

| Current | Trigger | Next |
|---------|---------|------|
| Email | Prospect reply `preferred_channel=sms` + thread state `QUALIFIED` | SMS (warm) |
| Email | Prospect reply `intent=bench_question` outside bench | Human handoff |
| Email | Prospect reply `intent=pricing_question` beyond public tier | Human handoff |
| SMS | Complex objection or intent not `scheduling_question` | Back to email; notify human lead |
| BOOKED (any) | Confirmed Cal.com slot | Human delivery lead owns from here |

## 6. Rate-limit choreography

- Resend: 3 000/month free; a 500-msec jittered delay between sends avoids burst bans.
- Africa's Talking sandbox: generous in sandbox; still gate at 1 SMS / 3 seconds per short-code.
- Webhook handler is idempotent on provider message IDs — replays are harmless.

## 7. Compliance and privacy

- `List-Unsubscribe` header on every email; one-click unsubscribe URL is served by a tiny static handler.
- SMS `STOP` keyword is recognised and recorded in CRM; no further SMS to that number.
- No real Tenacious prospect contact is processed; all addresses are synthetic (`<slug>@sink.convergine.local`) until kill-switch is flipped.
- See [16-data-handling-and-kill-switch.md](16-data-handling-and-kill-switch.md) for the router that enforces this.

## 8. Acceptance tests

- `send_email` called with kill-switch unset routes to `config.killswitch.sink_email`, not to the stated `to`.
- A 180-char SMS body raises `SmsBodyTooLong` in `send_sms`.
- An email with a missing `X-Convergine-Trace-Id` header is rejected by the webhook handler as un-attributable.
- A prospect who replies with `"please text me at +44 7... to schedule"` results in state `SCHEDULING` over SMS only **after** `preferred_channel == "sms"` is detected, and only if the prospect has an on-file short-code consent captured earlier in the thread.
- Voice tool calls issued cold (without BOOKED state) raise `VoiceRequiresBookedState`.
