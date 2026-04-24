# Conversion Engine — Implementation Plans

This directory is the engineering **execution plan** for the Conversion Engine. The specs in [`__specs/`](../__specs/) define **what** the system is; the plans here define **how we build it**. Each plan names a phase of work, lists concrete engineering tasks, and specifies the acceptance criteria that close the phase.

## Plan shape

Each plan file follows the same structure:

| Section | Purpose |
|---|---|
| **Goal** | One-paragraph summary of what this phase produces. |
| **Spec references** | The `__specs/` docs that constrain this work. |
| **Dependencies** | Plans, fixtures, or credentials required before this phase starts. |
| **Tasks** | Numbered, small, tractable engineering tasks. |
| **Acceptance criteria** | Concrete checks that the phase is complete. |
| **Submission gate** | Whether this phase feeds the interim or final submission. |
| **Exit risks** | Failure modes that justify pausing and re-planning. |

## Plans index

| # | Plan | Feeds | Spec anchors |
|---|---|---|---|
| [00](00-decisions.md) | Decisions log | All | All |
| [01](01-preflight.md) | Pre-flight (accounts, policy ack, smoke test) | Interim | 16, 17, 18 |
| [02](02-act1-tau2-baseline.md) | Act I — τ²-Bench retail baseline | Interim | 11 |
| [03](03-act2-production-stack.md) | Act II — Production stack (enrichment + agent + channels + HubSpot + Cal.com) | Interim | 01, 04, 05, 06, 07, 08, 09, 10 |
| [04](04-interim-submission.md) | Interim submission (packaging + PDF + 20-interaction latency) | **Interim gate** | 17 |
| [05](05-act3-probes.md) | Act III — Probe library + target failure mode | Final | 12 |
| [06](06-act4-mechanism.md) | Act IV — Mechanism + sealed held-out evaluation | Final | 13 |
| [07](07-act5-memo-demo.md) | Act V — Two-page memo + evidence graph + demo video | **Final gate** | 14, 17 |
| [08](08-stretch-market-space.md) | Distinguished-tier stretch — market-space map | Optional | 15 |
| [09](09-work-breakdown.md) | Cross-phase work-breakdown structure | All | All |
| [10](10-risks.md) | Risk register | All | All |

## Execution order (no dates)

```
preflight ──▶ Act I ──┐
              ├──▶ interim ──▶ Act III ──▶ Act IV ──▶ Act V ──▶ (stretch)
Act II ───────┘
```

The interim submission gate closes Act I + Act II. Act III depends on Act II being live (probes execute against the agent). Act IV depends on Act III naming a target failure mode. Act V depends on Act IV's `ablation_results.json`. The stretch (market-space map) branches off Act II enrichment and must **not** displace Act V effort.

## Non-negotiables carried into every plan

These come from [`__specs/16-data-handling-and-kill-switch.md`](../__specs/16-data-handling-and-kill-switch.md) and apply to every task:

- **Kill switch defaults unset.** Every task that exercises outbound verifies `TENACIOUS_OUTBOUND_ENABLED` is unset until the smoke test passes.
- **No real customer contact.** Every prospect used in a task is drawn from `data/synthetic_prospects.json` or is the staff sink.
- **Draft marking.** Every Tenacious-branded artifact produced by a task carries `draft` metadata.
- **No hard-coded secrets, URLs, model IDs, prices.** Every task that reads such a value reads it from `.env` or `config.yaml`.
- **Incident reporting.** Any accidental policy deviation is reported to tutors before the task resumes.

## Definition of "done"

A plan is closed when **all** of the following hold:

1. Every task is checked off or explicitly deferred with a written reason.
2. Every acceptance-criteria bullet passes (automated check preferred; manual OK if documented).
3. The submission-gate artifacts for that phase are present in the repo.
4. `infra/smoke_test.sh` still passes.
5. No new policy violations appear in `scripts/audit_week.py` output.

## How to use these plans

- **Start of session**: open the current plan, read the Tasks and Acceptance sections.
- **End of session**: check off completed tasks; if a task spawned a new one, add it.
- **Before submission**: confirm the submission gate's artifacts against the checklist in [spec 17](../__specs/17-deliverables-checklist.md).
- **On policy alarm**: stop, read [`10-risks.md`](10-risks.md), report, resume only after the risk is classified.
