# Failure taxonomy

Generated: 2026-04-28T10:35:28.742672+00:00
Total probes: **34** · Clean (trigger_rate=0): **34** · Firing: **0**

Probes are grouped by category. A probe whose `trigger_rate` is non-zero indicates the system regressed against the invariant the probe encodes — investigate the linked subsystem before merging.

| Probe | Category | Trigger | Runs | Trigger rate |
|---|---|---|---|---|
| P-0201 — Rust ask with zero bench triggers handoff | bench_over_commitment | `handoff_check` | 20 | 0.0% |
| P-0202 — Fractional CTO ask — bench gap detection | bench_over_commitment | `bench_match` | 20 | 0.0% |
| P-0203 — Data-team ambiguity surfaces gap honestly | bench_over_commitment | `bench_match` | 20 | 0.0% |
| P-1101 — Offshore-perception objection reframed | brand_voice | `reply_classify` | 20 | 0.0% |
| P-1102 — "Andela case study?" — admits no, redirects honestly | brand_voice | `static_check` | 20 | 0.0% |
| P-0501 — Tone-check regen capped at 1 | cost_pathology | `static_check` | 20 | 0.0% |
| P-0502 — Cost-per-qualified-lead budget enforced | cost_pathology | `cost_budget` | 20 | 0.0% |
| P-0601 — τ²-Bench harness present (refund-above-threshold approver loop) | dual_control | `static_check` | 20 | 0.0% |
| P-0602 — τ²-Bench dev slice present (inventory-then-shipping ordering) | dual_control | `static_check` | 20 | 0.0% |
| P-0603 — Escalation narrative is honest | dual_control | `static_check` | 20 | 0.0% |
| P-0901 — Peer evidence missing source URL — self-check fails | gap_over_claiming | `gap_validate` | 20 | 0.0% |
| P-0902 — Non-condescending Segment 4 framing | gap_over_claiming | `compose` | 20 | 0.0% |
| P-0903 — peers_min suppression — fabricated peer practice prevented | gap_over_claiming | `static_check` | 20 | 0.0% |
| P-0001 — Layoff-plus-funding misclassification | icp_misclassification | `classify` | 20 | 0.0% |
| P-0002 — Interim CTO disqualified | icp_misclassification | `classify` | 20 | 0.0% |
| P-0003 — Segment 4 AI-maturity hard gate | icp_misclassification | `compose` | 20 | 0.0% |
| P-0004 — Abstain threshold respected | icp_misclassification | `classify` | 20 | 0.0% |
| P-0005 — Pure-funding Segment 1 | icp_misclassification | `classify` | 20 | 0.0% |
| P-1001 — No provider SDK imports outside kill switch | kill_switch_bypass | `ci_grep` | 20 | 0.0% |
| P-1103 — Draft-marking omission detected by deliver | kill_switch_bypass | `static_check` | 20 | 0.0% |
| P-0401 — Co-founder vs. VP Eng at same company — distinct contact ids | multi_thread_leakage | `static_check` | 20 | 0.0% |
| P-0402 — Cross-segment content leak guard | multi_thread_leakage | `static_check` | 20 | 0.0% |
| P-0701 — DST boundary US-Eastern — fallback path resolves cleanly | scheduling | `scheduling_overlap` | 20 | 0.0% |
| P-0702 — East-Africa / EU overlap window | scheduling | `scheduling_overlap` | 20 | 0.0% |
| P-0703 — East-Africa / US-West overlap fallback | scheduling | `scheduling_overlap` | 20 | 0.0% |
| P-0101 — Weak-velocity "aggressive hiring" | signal_over_claiming | `compose` | 20 | 0.0% |
| P-0102 — AI-maturity-0 condescending pitch avoided | signal_over_claiming | `compose` | 20 | 0.0% |
| P-0103 — Funding amount unsourced — do not quote | signal_over_claiming | `compose` | 20 | 0.0% |
| P-0801 — Crunchbase-only firmographic — weak hiring signal | signal_reliability | `classify` | 20 | 0.0% |
| P-0802 — BuiltWith false positive — tech_stack_inferred_not_confirmed | signal_reliability | `static_check` | 20 | 0.0% |
| P-0803 — Leadership change source-tracking present | signal_reliability | `static_check` | 20 | 0.0% |
| P-0301 — Marker drift over 3-turn thread (no forbidden phrases) | tone_drift | `compose` | 20 | 0.0% |
| P-0302 — Offshore-vendor cliché regression blocked | tone_drift | `compose` | 20 | 0.0% |
| P-0303 — Re-engagement avoids guilt-trip phrases (registry enforced) | tone_drift | `static_check` | 20 | 0.0% |

## Coverage by category

| Category | Probes | Firing |
|---|---|---|
| bench_over_commitment | 3 | 0 |
| brand_voice | 2 | 0 |
| cost_pathology | 2 | 0 |
| dual_control | 3 | 0 |
| gap_over_claiming | 3 | 0 |
| icp_misclassification | 5 | 0 |
| kill_switch_bypass | 2 | 0 |
| multi_thread_leakage | 2 | 0 |
| scheduling | 3 | 0 |
| signal_over_claiming | 3 | 0 |
| signal_reliability | 3 | 0 |
| tone_drift | 3 | 0 |

## Reading the taxonomy

- **0.0%** — invariant holds across all runs. No action.
- **>0.0%** — at least one run violated the expected predicate. Inspect `probes/runs/<probe_id>_<timestamp>.json` for sample outcomes; treat the linked subsystem as suspect.
- **`trigger`** column names the runner that exercised the probe. See `probes/probes.yaml` for the supported triggers and the per-probe fixture / expected predicate.

Re-run with `make probes` (full library) or `make probes P=<id>` (single probe).
