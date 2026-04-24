# 00 — Decisions Log

This is the append-only record of architectural and strategic decisions made while building the Conversion Engine. Every decision names its context, the options considered, the chosen option, and the reason. A decision is never silently reversed — a later entry supersedes an earlier one and explains why.

Format: ADR-style. Each decision is dated in UTC and numbered.

---

## D-001 · Channel hierarchy: email primary, SMS warm, voice bonus

**Context**: Tenacious sells to founders, CTOs, and VPs of Engineering — a cohort that lives in email and LinkedIn, not SMS or voice. Cold SMS to this segment reads as intrusive; cold voice is worse.

**Options**:
- (a) Voice-heavy, following the compliance-software version of this challenge.
- (b) Email-primary, with SMS reserved for warm scheduling and voice as a bonus tier for booked discovery calls.

**Decision**: **(b)**. Matches the challenge brief's explicit scope choice and the Tenacious ICP. Rebuilding a voice-heavy architecture inverts the intended design.

**Consequence**: the demo video must show an email-to-SMS handoff and books the discovery call via Cal.com; a cold voice call is explicitly out of scope.

**Spec anchor**: [`__specs/07-channels.md`](../__specs/07-channels.md)

---

## D-002 · Dev-tier vs eval-tier model split

**Context**: Limited LLM budget (target dev <$4, eval <$12 per trainee for the week). Burning eval-tier credit on dev-slice runs is a common Day-0 mistake.

**Options**:
- (a) One model tier for everything.
- (b) Cheap dev-tier for Acts I–III and mechanism prototyping, expensive eval-tier only for the sealed held-out partition.

**Decision**: **(b)**. Dev-tier: Qwen3-Next-80B-A3B or DeepSeek V3.2 via OpenRouter. Eval-tier: Claude Sonnet 4.6 or GPT-5 class. Eval-tier access is guarded at runtime by `EVAL_TIER_ENABLED=1`.

**Consequence**: every LLM call carries a `tier` attribute; cost attribution distinguishes dev vs eval; budget monitoring is per-tier.

**Spec anchor**: [`__specs/11-tau2-bench-harness.md`](../__specs/11-tau2-bench-harness.md), [`__specs/18-configuration.md`](../__specs/18-configuration.md)

---

## D-003 · Kill switch is a single function

**Context**: The policy requires every outbound to pass through a kill-switch gate. The gate must be auditable and tamper-evident.

**Options**:
- (a) A decorator applied to each channel-send function.
- (b) A per-channel middleware.
- (c) **One function `deliver(channel, to, payload)` in `agent/kill_switch.py`** as the **only** path from agent to provider SDKs.

**Decision**: **(c)**. A CI grep fails the build if any file outside `agent/kill_switch.py` directly imports a provider SDK's send method.

**Consequence**: the provider-adapter layer exposes `send(to, payload)` functions but they are only callable from `deliver()`. Code review enforces.

**Spec anchor**: [`__specs/16-data-handling-and-kill-switch.md`](../__specs/16-data-handling-and-kill-switch.md)

---

## D-004 · Briefs as Pydantic models mirroring JSON Schemas

**Context**: The agent must emit `hiring_signal_brief.json` and `competitor_gap_brief.json` matching the provided JSON Schemas. Drift between schemas and code is a common failure.

**Options**:
- (a) Hand-write Pydantic models, re-validate against schema in tests.
- (b) Generate Pydantic models from JSON Schema (`datamodel-code-generator`).
- (c) Validate JSON at write time only, no Pydantic types.

**Decision**: **(a)** with a CI test that validates each generated brief against the schema. Generator tooling adds friction; validation in test catches drift.

**Consequence**: `agent/enrichment/briefs.py` contains Pydantic classes; `tests/test_schema_conformance.py` validates fixtures against `tenacious_sales_data/schemas/*.schema.json`.

**Spec anchor**: [`__specs/05-signal-enrichment-pipeline.md`](../__specs/05-signal-enrichment-pipeline.md)

---

## D-005 · Thread isolation keyed by prospect email

**Context**: Multi-thread leakage (co-founder + VP Eng at same company) is a probe category and a real-world failure mode.

**Options**:
- (a) Key conversation state by company domain.
- (b) Key by `(prospect_email, thread_id)`.

**Decision**: **(b)**. The agent's context builder loads history by `contact_email` only; a CI lint grep flags any file that loads by `company_domain` for conversation context.

**Consequence**: HubSpot queries use contact_email as the join key. The probe library includes a multi-thread leakage test at zero-tolerance trigger rate.

**Spec anchor**: [`__specs/06-agent-design.md`](../__specs/06-agent-design.md), [`__specs/12-probe-library.md`](../__specs/12-probe-library.md)

---

## D-006 · ICP classifier is rule-based, LLM only for free-text sub-signals

**Context**: The ICP classification rules are ordered and deterministic. An LLM-based classifier would be harder to audit and more expensive.

**Options**:
- (a) LLM-based classifier with the rules in the prompt.
- (b) **Rule-based classifier; LLM only for sub-signals** (founder anti-offshore stance, interim/acting detection, AI-adjacent role titles).

**Decision**: **(b)**. The primary classifier is deterministic Python code. LLM sub-calls are isolated to the specific free-text interpretation problems they solve.

**Consequence**: classifier behavior is auditable. Sub-signal LLM calls are traced and budgeted independently.

**Spec anchor**: [`__specs/06-agent-design.md`](../__specs/06-agent-design.md)

---

## D-007 · Abstention is a first-class outcome

**Context**: Probe category 1 (ICP misclassification) tests that the agent abstains when signal is weak. Abstention must not be a failure path.

**Options**:
- (a) Abstention falls back to a default (Segment 1).
- (b) **Abstention triggers the exploratory email prompt** (`composer_abstain.txt`), which makes no specific pitch.

**Decision**: **(b)**. Below `icp.abstain_threshold` (default 0.6), the composer uses the exploratory prompt. `tenacious_segment = abstain` in HubSpot.

**Consequence**: the memo cites abstention-rate as a quality metric alongside reply rate.

**Spec anchor**: [`__specs/03-icp-and-segments.md`](../__specs/03-icp-and-segments.md), [`__specs/06-agent-design.md`](../__specs/06-agent-design.md)

---

## D-008 · Tone-preservation check is a second LLM call

**Context**: The style guide specifies five tone markers. Composer drift is a probe category.

**Options**:
- (a) Embed tone rules in the composer prompt only.
- (b) **Second LLM call that scores the draft against the five markers**, with regeneration below threshold.

**Decision**: **(b)**. Adds one LLM call per message; traceable cost in `tone_check.*` span. Threshold: `4/5` on every marker; one retry then flag for human.

**Consequence**: this is a candidate mechanism for Act IV. Its cost is tracked separately for the memo's unit-economics analysis.

**Spec anchor**: [`__specs/06-agent-design.md`](../__specs/06-agent-design.md), [`__specs/13-mechanism-design.md`](../__specs/13-mechanism-design.md)

---

## D-009 · Seed files are authoritative; YAML mirrors with placeholder resolution at boot

**Context**: Tenacious prices, ACVs, and bench counts are in `seed/baseline_numbers.md` and `seed/bench_summary.json`. Duplicating them in `config.yaml` risks drift.

**Options**:
- (a) Hard-code numbers in YAML.
- (b) **Mirror with `${PLACEHOLDER}` syntax; resolve at boot from seed files.**

**Decision**: **(b)**. `agent/config.py` parses seed files on startup and substitutes placeholders in the YAML. Fails boot if a placeholder cannot be resolved.

**Consequence**: updating a seed number propagates automatically to the running config. No numeric literal for price or ACV appears in Python code.

**Spec anchor**: [`__specs/18-configuration.md`](../__specs/18-configuration.md)

---

## D-010 · Defer implementation-framework choice (LangGraph / PydanticAI / hand-rolled)

**Context**: Several frameworks work. Lock-in is premature before we know which capabilities (human-in-loop handoff, multi-thread isolation, tool routing) dominate.

**Options**:
- (a) Commit to LangGraph.
- (b) Commit to PydanticAI.
- (c) **Hand-rolled state machine with narrow interfaces, revisit after Act II.**

**Decision**: **(c)** for the interim; revisit if Act IV mechanism work exposes a clear framework fit. The spec is framework-agnostic.

**Consequence**: if migration happens, it is scoped to the `agent/classifier.py`, `agent/composer.py`, `agent/reply_handler.py` modules only.

**Spec anchor**: [`__specs/01-architecture.md`](../__specs/01-architecture.md)

---

## D-011 · HubSpot custom-property prefix = `tenacious_`

**Context**: HubSpot Developer Sandbox is multi-tenant in principle; other tests or future tenants could share the sandbox.

**Options**:
- (a) Unprefixed custom properties.
- (b) **Prefix every custom property with `tenacious_`.**

**Decision**: **(b)**. One-filter removability. Safer interop with other sandbox consumers.

**Consequence**: every HubSpot property in the schema carries `tenacious_`; `HUBSPOT_PORTAL_ID` asserts non-production portal at runtime.

**Spec anchor**: [`__specs/08-hubspot-integration.md`](../__specs/08-hubspot-integration.md)

---

## D-012 · Cold sequence is strictly 3 touches

**Context**: The email sequences seed file caps cold at three emails. A fourth touch within 30 days is a policy violation per the seed.

**Options**:
- (a) Cap at 3 and close, as specified.
- (b) Extend with a fourth "signal update" touch.

**Decision**: **(a)**. Non-negotiable.

**Consequence**: re-engagement (stalled thread) is a separate sequence that fires only after an engaged/curious reply.

**Spec anchor**: [`__specs/07-channels.md`](../__specs/07-channels.md)

---

## D-013 · Market-space map is explicitly opt-in

**Context**: The distinguished-tier stretch requires hand-labeling a validation sample. Superficial attempts misdirect strategy.

**Options**:
- (a) Default-on stretch.
- (b) **`market_space.enabled: false` in `config.yaml`; trainee opts in deliberately with a Day-6-specific budget.**

**Decision**: **(b)**. The stretch must not displace Act V effort.

**Consequence**: if Act V slips, the stretch is cut first. This is written into [`09-work-breakdown.md`](09-work-breakdown.md).

**Spec anchor**: [`__specs/15-market-space-map.md`](../__specs/15-market-space-map.md)

---

## Decision change template

To supersede a decision, add a new entry referencing the old:

```
## D-N · <new decision>
Supersedes: D-M
Reason: <what changed>
...
```
