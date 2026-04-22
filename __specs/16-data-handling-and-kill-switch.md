# 16 — Data Handling Policy and Kill-Switch

**Source:** Challenge document — "Data Handling Policy" (Rules 1–5), "Evidence-Graph Grading" (Evidence-graph integrity row).

## 1. Rules (disqualifying if violated)

1. **No real Tenacious customer data leaves Tenacious.** We never receive CRM exports, real email threads, real phone numbers, or real names of live deals.
2. **Every prospect the system interacts with during the challenge week is synthetic.** Synthetic = Crunchbase ODM firmographics + fictitious contact details. The program-operated SMS rig routes all outbound to a staff-controlled sink.
3. **Seed materials are limited-license** for the challenge week. No redistribution. All local copies deleted at end of week; code stays in the program repo.
4. **Kill-switch required.** If the code could plausibly run against real prospects, the README documents it and ships a config flag that, **when unset**, routes all outbound to the staff sink. **Default must be unset.**
5. **Tenacious-branded output marked `draft` in metadata.** Tenacious executive team reserves the right to redact any such content from the final memo.

Breaking any rule is **grounds for removal from the program**. Fabricated Tenacious numbers in the memo are a separate disqualifying violation per the Evidence-Graph Grading row.

## 2. Kill-switch architecture

```python
# agent/integrations/killswitch.py

class KillSwitch:
    def __init__(self, cfg: KillSwitchConfig):
        self.enabled = cfg.enabled                  # default False
        self.sink_email = cfg.sink_email
        self.sink_shortcode = cfg.sink_shortcode
        self.audit_log_path = cfg.audit_log_path

    def route_email(self, to: str, trace_id: str) -> str:
        if not self.enabled:
            self._audit("email", to, self.sink_email, trace_id)
            return self.sink_email
        self._audit("email", to, to, trace_id)
        return to

    def route_sms(self, to_number: str, trace_id: str) -> str:
        if not self.enabled:
            self._audit("sms", to_number, self.sink_shortcode, trace_id)
            return self.sink_shortcode
        self._audit("sms", to_number, to_number, trace_id)
        return to_number
```

Every `send_email` / `send_sms` tool call passes through the switch. There is **no code path** that bypasses it.

## 3. Configuration

```yaml
# config.yaml
killswitch:
  enabled: false                            # DEFAULT UNSET — routes to sink
  sink_email: "sink+convergine@staff-sandbox.tenacious.invalid"
  sink_shortcode: "22222"                   # program-provided short code
  audit_log_path: "data/killswitch_audit.jsonl"
```

Flipping to `true` requires:
1. Program staff confirmation in writing.
2. An entry in `README.md` stating the date, the flipper's identity, and the scope (domain, time window, expected volume).
3. A check on every boot that confirms `enabled == true` was set intentionally (env var `CONVERGINE_ENABLE_REAL_OUTBOUND=1` also required — belt + braces).

## 4. README-mandated documentation

The repo root `README.md` **must** contain a section titled "Kill-switch" covering:

- Where the switch lives (config path + env var).
- Default behaviour when unset.
- How to enable it (steps 1–3 above).
- Who audits flips (`data/killswitch_audit.jsonl`).
- What happens if a real prospect address ends up in the queue while the switch is unset (answer: routed to sink — no leak).

## 5. Synthetic-prospect marking

Every `Contact` in HubSpot carries `convergine_synthetic = true` while the switch is unset. A nightly job asserts:

```sql
-- conceptual: run against HubSpot via MCP queries
count(contact where convergine_synthetic = false) == 0
```

Any row failing this raises a P0 alert.

## 6. Draft marker propagation

| Surface | How `draft` is marked |
|---------|-----------------------|
| Email header | `X-Convergine-Draft: true` |
| Email body | A one-line footer `— draft: pending Tenacious delivery-lead approval` (removable only when `draft_approved == true`) |
| HubSpot event | `payload.draft = true` |
| Cal.com booking | `metadata.draft = true`; invite description prepends `[DRAFT]` |
| SMS | Prefix `[DRAFT]` in the sandbox body |

## 7. Data-deletion policy

At end of week:

- Seed materials (sales deck, case studies, pricing sheet) purged from all personal infrastructure: laptops, cloud drives, build servers.
- Code retained in program repo.
- Enriched briefs cached under `data/briefs_cache/` are retained only if they reference synthetic prospects; anything that accidentally references a real company is purged.
- `scripts/end_of_week_purge.sh` automates the deletion, writes an audit log to `data/purge_audit.jsonl`.

## 8. Audit trail

Every routing decision is appended to `data/killswitch_audit.jsonl`:

```json
{"ts": "2026-04-22T11:02:14Z", "channel": "email", "intended_to": "cto@acme.ai", "routed_to": "sink+convergine@staff-sandbox.tenacious.invalid", "trace_id": "...", "switch_enabled": false}
```

The audit log is **append-only** — `chmod 644`, no deletes, tamper check via a running SHA-256 hash appended to each line (Merkle-chain style).

## 9. Evidence-graph integrity (memo linkage)

Numbers in the memo must trace to:
- A Langfuse trace id, or
- An `invoice_summary.json` line item, or
- A Tenacious-provided number (bench summary, historical conversion rates in the seed), or
- A public source (τ²-Bench leaderboard, LeadIQ 2026, Apollo, Clay, Smartlead case studies).

Anything not in those four categories is a fabrication. `scripts/lint_memo.py` checks every number against `evidence_graph.json`; unresolved numbers fail the build.

## 10. Acceptance tests

- With `killswitch.enabled = false`, an email `send` call with `to="cto@acme.ai"` results in Resend seeing recipient `sink+convergine@staff-sandbox.tenacious.invalid`; the audit log records both the intended and routed addresses.
- Flipping `killswitch.enabled = true` without `CONVERGINE_ENABLE_REAL_OUTBOUND=1` refuses to boot.
- `scripts/end_of_week_purge.sh` deletes seed materials and leaves code intact; the audit log is produced.
- `scripts/lint_memo.py memo/memo.md memo/evidence_graph.json` catches a fabricated number inserted into a test fixture.
- Every outbound artifact (email, SMS, Cal.com invite) carries the draft marker when the switch is unset.
