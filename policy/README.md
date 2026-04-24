# Policy artifacts

Per-run policy evidence. Not for re-stating the policy itself (that lives in
[`tenacious_sales_data/policy/`](../tenacious_sales_data/policy/) and in
[`__specs/16-data-handling-and-kill-switch.md`](../__specs/16-data-handling-and-kill-switch.md)).

## Contents

- `acknowledgement_signed.txt` — UTC timestamp of the trainee's signed acknowledgement.
  Written by `make ack`. Required for the smoke test to pass.
- `audit_reports/` — weekly output of `scripts/audit_week.py`. Committed.

## Handling a policy violation

If `scripts/audit_week.py` finds a violation or a `PolicyViolation` is raised
at runtime, the incident-reporting flow in
[`__specs/16-data-handling-and-kill-switch.md`](../__specs/16-data-handling-and-kill-switch.md#rule-9--incident-reporting)
applies. Do not silently catch and retry.
