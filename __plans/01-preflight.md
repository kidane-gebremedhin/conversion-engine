# 01 — Pre-flight (Accounts, Policy, Smoke Test)

## Goal

Get every external account provisioned, the policy acknowledgement signed, the kill switch default-unset, and the five-green-check smoke test passing. This phase is gated before Act I starts; without it, later phases will fail in ways that are harder to debug.

## Spec references

- [`__specs/16-data-handling-and-kill-switch.md`](../__specs/16-data-handling-and-kill-switch.md) — every policy rule and how it's enforced.
- [`__specs/17-deliverables-checklist.md`](../__specs/17-deliverables-checklist.md) — the submission scaffolding this phase creates.
- [`__specs/18-configuration.md`](../__specs/18-configuration.md) — every `.env` and YAML value touched here.
- [`tenacious_sales_data/DAY0_CHECKLIST.md`](../tenacious_sales_data/DAY0_CHECKLIST.md) — source of truth for this phase.

## Dependencies

None. This is the first phase.

## Tasks

### 1.1 Repo scaffolding

1. Create the top-level directories per [`__specs/02-repo-structure.md`](../__specs/02-repo-structure.md): `agent/`, `eval/`, `probes/`, `method/`, `memo/`, `data/`, `infra/`, `policy/`.
2. Mirror the seed into the repo: copy (read-only) the contents of `tenacious_sales_data/` into the repo if not already present; verify the copy is byte-identical.
3. Write a minimal `README.md` at the repo root with a placeholder architecture diagram and a clear kill-switch section (copy from [spec 01](../__specs/01-architecture.md) and [spec 16](../__specs/16-data-handling-and-kill-switch.md)).
4. Create `.gitignore` that excludes `.env`, `*.key`, `eval/runs/`, `eval/briefs/`, `method/held_out_traces.jsonl` until Act IV, `memo/memo.pdf` until Act V, and `tau2_sealed_heldout/`.
5. Create `Makefile` with targets per [spec 02](../__specs/02-repo-structure.md#makefile-targets).

### 1.2 Policy acknowledgement

1. Read `tenacious_sales_data/policy/data_handling_policy.md` in full. Not skim.
2. Read `tenacious_sales_data/policy/acknowledgement.md` in full.
3. Fill in the acknowledgement form and submit per program-staff instructions.
4. After receiving confirmation, write `infra/acknowledgement_signed.txt` and `policy/acknowledgement_signed.txt` each containing the UTC timestamp of confirmation (e.g., `2026-04-22T14:30:00Z`).
5. Commit both files.

### 1.3 Accounts

Provision each account. For each, record the credential in `.env` (never committed) and record a screenshot of the "test event received" state in `memo/evidence_snapshots/day0/`:

1. **Resend** (preferred) or **MailerSend** free tier. Send a test email to your own address; register the reply webhook via ngrok or Cloudflare Tunnel. Record `RESEND_API_KEY`, `RESEND_WEBHOOK_URL`, `RESEND_WEBHOOK_SECRET`, `RESEND_FROM_ADDRESS`, `EMAIL_SINK_ADDRESS`.
2. **Africa's Talking sandbox**. Register a virtual short code; route one test SMS to your local webhook handler. Record `AT_API_KEY`, `AT_USERNAME`, `AT_SHORT_CODE`, `AT_WEBHOOK_URL`, `AT_WEBHOOK_SECRET`, `SMS_SINK_NUMBER`.
3. **HubSpot Developer Sandbox**. Create the app; install the HubSpot MCP server; create one test contact via API. Record `HUBSPOT_PRIVATE_APP_TOKEN`, `HUBSPOT_APP_ID`, `HUBSPOT_PORTAL_ID`, `HUBSPOT_MCP_SERVER_URL`. Assert the portal ID matches a Developer-Sandbox pattern, not a production-portal pattern.
4. **Langfuse cloud free tier**. Create the project; emit one test trace. Record `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PROJECT_ID`.
5. **OpenRouter** for dev-tier LLM. Top up to at least the `budgets.dev_llm_max_usd` target. Record `OPENROUTER_API_KEY`.
6. **Anthropic** or **OpenAI** for eval-tier LLM. Top up to at least `budgets.eval_llm_max_usd`. Record `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Leave `EVAL_TIER_ENABLED` UNSET.

### 1.4 Local infrastructure

1. **Cal.com** self-hosted: `docker compose up` from `infra/docker-compose.yml`. Create the `discovery-15` and `discovery-30` event types. Book one test slot end-to-end (create event type → book slot → confirmation email received). Record `CALCOM_BASE_URL`, `CALCOM_API_KEY`, `CALCOM_USERNAME`, `CALCOM_WEBHOOK_URL`, `CALCOM_WEBHOOK_SECRET`.
2. **Playwright**: `playwright install chromium`. Write the 10-line sample `agent/enrichment/jobposts_smoke.py` that fetches one public job listing and prints JSON; verify the user agent is the policy-mandated `TRP1-Week10-Research (trainee@trp1.example)`.
3. **Python environment**: Python 3.11+; `uv venv` or `python -m venv .venv`; `pip install -r agent/requirements.txt`.

### 1.5 Config files

1. Copy `__specs/.env.example` → `.env` at repo root. Fill in every required value.
2. Copy `__specs/config.example.yaml` → `config.yaml` at repo root. Leave placeholder resolution alone for now (implemented in Act II).
3. Verify `.env` is gitignored (`git status` shows nothing).
4. Verify `TENACIOUS_OUTBOUND_ENABLED` is **unset or commented out** in `.env`. Run `grep TENACIOUS_OUTBOUND_ENABLED .env` and confirm no non-commented line.

### 1.6 τ²-Bench clone

1. `git clone https://github.com/sierra-research/tau2-bench.git eval/tau2` (or use submodule).
2. Pin the SHA in `config.yaml > tau2.pinned_sha`.
3. Run the retail domain against the dev-tier model on three tasks to confirm the benchmark executes without crashing (this is the readiness check, not the Act I baseline).

### 1.7 Sealed held-out partition

1. Receive the 20-task sealed partition from program staff via encrypted channel.
2. Store **outside the repo tree** at `../tau2_sealed_heldout/` (path matches `TAU2_HELDOUT_PATH`).
3. Confirm the checksum provided by program staff.
4. Leave `TAU2_SEALED_ACCESS` UNSET.

### 1.8 Smoke test

Write `infra/smoke_test.sh` that asserts all of the following and exits non-zero on any failure:

1. `acknowledgement_signed.txt` exists (both `infra/` and `policy/` locations).
2. `grep TENACIOUS_OUTBOUND_ENABLED .env` returns either no output or a commented line.
3. A test email dispatched via `deliver()` lands in the `EMAIL_SINK_ADDRESS` (not the real inbox).
4. A test SMS via `deliver()` lands at `SMS_SINK_NUMBER`.
5. A HubSpot test contact is created and visible via API.
6. A Cal.com test booking completes end-to-end.
7. A Langfuse test trace is visible in the project.
8. The τ²-Bench retail domain runs three tasks without crashing.

Target runtime: under 3 minutes.

## Acceptance criteria

- [ ] Acknowledgement timestamps committed in both `infra/` and `policy/`.
- [ ] `.env` exists, is gitignored, and contains all required values.
- [ ] `config.yaml` exists with placeholder-resolution deferred.
- [ ] `infra/smoke_test.sh` exits 0 with five green checks.
- [ ] No secret is committed (verified via `git log -p` grep for common secret prefixes).
- [ ] `TENACIOUS_OUTBOUND_ENABLED` is unset in `.env`.
- [ ] `EVAL_TIER_ENABLED` and `TAU2_SEALED_ACCESS` are unset in `.env`.
- [ ] Day-0 evidence snapshots filed under `memo/evidence_snapshots/day0/`.

## Submission gate

None directly — this phase is pre-submission. But without it, the interim submission cannot be assembled.

## Exit risks

- **Ngrok or Cloudflare Tunnel unstable**: webhooks drop, looks like agent failure. Mitigation: use a persistent subdomain; keep the tunnel in a dedicated terminal.
- **HubSpot MCP server install fails**: the MCP server has occasional install friction. Mitigation: fall back to direct REST with the private-app token; the interface in `agent/hubspot/client.py` is thin enough that the swap is mechanical.
- **Policy acknowledgement delayed by program staff**: Act I is gated on this. Mitigation: file the acknowledgement first thing; while waiting, do tasks 1.1, 1.3, 1.4, 1.6 (anything not gated on the held-out partition).
- **Accidental secret commit**: a common Day-0 failure. Mitigation: `git-secrets` pre-commit hook with patterns for Resend, Anthropic, OpenAI, Africa's Talking key formats.
