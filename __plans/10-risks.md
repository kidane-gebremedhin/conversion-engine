# 10 — Risk Register

A ranked list of what can go wrong during implementation, how it would manifest, and what the mitigation plan is. Risks are labeled by **severity** (impact × likelihood) and **phase** (when the risk is most acute).

Severity scale:

- **🔴 Critical** — disqualification or unrecoverable loss of progress.
- **🟠 High** — multi-day rework or gate-slip.
- **🟡 Medium** — recoverable but consumes budget or attention.
- **🟢 Low** — documented but unlikely to derail.

---

## R-001 · Kill-switch bypass 🔴

**Phase**: Acts II–V (every outbound touch).

**Manifestation**: Code path sends to a non-sink recipient. Detected by runtime assertion, probe category 11, or post-hoc audit.

**Why it matters**: Disqualifying per the policy. Even a single bypass test in code (without a real send) is a violation because the policy is about code pattern, not outcome.

**Mitigations**:

- One `deliver()` function as the only outbound path; CI grep enforces.
- Runtime assertion: recipient is sink or `data/synthetic_prospects.json` entry.
- Probe category 11 runs on every full `make probes`; zero-trigger-rate required to close Act III.
- `scripts/audit_week.py` re-verifies via Langfuse traces.

**Trigger → action**: stop, report to tutors per Rule 9, do not resume until remediated.

---

## R-002 · Fabricated Tenacious numbers 🔴

**Phase**: Act V memo drafting.

**Manifestation**: A number in `memo.pdf` (ACV, conversion rate, bench count) has no source in `seed/baseline_numbers.md`, `seed/bench_summary.json`, a trace file, or a public URL.

**Why it matters**: Disqualifying, separate from the standard evidence-graph penalty.

**Mitigations**:

- Every numeric claim in `memo.md` is a macro that resolves from a source.
- `build_evidence_graph.py` fails on `source_type: null`.
- No numeric literals for price, ACV, or bench count anywhere in `agent/` or `eval/` (enforced by D-009).

**Trigger → action**: strip the unsourced claim from the memo immediately; re-render; re-validate the evidence graph.

---

## R-003 · Eval-tier budget overrun 🔴

**Phase**: Act IV sealed run.

**Manifestation**: The three-variant sealed-partition run costs more than `budgets.eval_llm_max_usd` ($12 target). Truncated runs invalidate statistical tests.

**Why it matters**: No budget left for re-runs if a mechanism result is borderline.

**Mitigations**:

- Before enabling `EVAL_TIER_ENABLED=1`, compute the expected cost from the Act I dev-tier trace and the price ratio.
- If the projection exceeds budget, reduce trial count to 3 (documented in `method.md`) or drop variant C.
- Harness tracks rolling cost in-run and aborts the run cleanly if budget exhausted.

**Trigger → action**: pause the run; decide to drop a variant or accept reduced statistical power; document honestly in `method.md`.

---

## R-004 · Delta A non-significant (p ≥ 0.05) 🟠

**Phase**: Act IV stat test.

**Manifestation**: The mechanism did not clearly beat the Day-1 baseline on the sealed partition.

**Why it matters**: The primary grading signal for Act IV. But honest reporting is penalized less than the alternatives.

**Mitigations**:

- Ablation C (variant with different threshold) may outperform B if B was over-tuned; having it prepared rescues the run at no extra cost.
- If budget allows one reconfigured re-run: tune the mechanism's hyperparameter based on Act III trigger-rate evidence, re-run, document both attempts in `method.md`.
- If re-run is not possible, Skeptic's Appendix on memo Page 2 acknowledges the failure and explains what was learned. The probe library originality may still carry the submission.

**Trigger → action**: do not fabricate. Write it up honestly.

---

## R-005 · Memo exceeds 2 pages 🟠

**Phase**: Act V.

**Manifestation**: `memo.pdf` is 3 pages after render. The renderer refuses to output.

**Why it matters**: Hard constraint from the challenge brief.

**Mitigations**:

- Draft Page 1 and Page 2 in separate markdown files; render each alone to verify they fit before concatenating.
- Typography is in `config.yaml`, not adjustable to cheat the constraint.
- Skeptic's Appendix is the first compression target if something must yield.

**Trigger → action**: cut ruthlessly; preserve the executive summary and kill-switch clause above all else.

---

## R-006 · 200-company crawl cap exceeded 🟠

**Phase**: Acts II–III.

**Manifestation**: `data/crawl_counter.json` hits 201; scraper raises `PolicyViolation`.

**Why it matters**: Policy violation. Not disqualifying if caught by the counter, but disqualifying if bypassed.

**Mitigations**:

- Prefer the frozen April-2026 snapshot for all hiring-velocity signals.
- Live-crawl only when the snapshot delta warrants.
- Counter is atomic; no race condition can push past 200.
- Budget 30–50 crawls per week for enrichment iteration; rest reserved for probe fixtures.

**Trigger → action**: the scraper halts; investigate what is consuming the budget; rebalance.

---

## R-007 · Webhook URL rotation 🟡

**Phase**: Ongoing.

**Manifestation**: ngrok/Cloudflare Tunnel rotates the URL; inbound webhooks go stale; provider webhooks error silently.

**Mitigations**:

- Persistent subdomain or reserved tunnel if available.
- Re-register webhooks via a `make update_webhooks` target whenever the URL changes.
- Health probe: `curl` the webhook URL every 30 minutes during development; alert on failure.

**Trigger → action**: re-register; re-run a test message through each channel.

---

## R-008 · HubSpot MCP install friction 🟡

**Phase**: Pre-flight, Act II.

**Manifestation**: MCP install fails or behavior drifts from spec.

**Mitigations**:

- `agent/hubspot/client.py` abstracts over MCP vs direct REST via `HUBSPOT_USE_MCP`.
- If MCP fails, fall back to REST; interface contract is the same.

**Trigger → action**: flip the env var, re-run smoke test.

---

## R-009 · Screenshot tokens leaked 🟡

**Phase**: Interim and final submission.

**Manifestation**: A screenshot in the PDF report exposes an API token visible in a browser URL or a backend panel.

**Mitigations**:

- Review every screenshot in a preview tool before committing; redact.
- Prefer screenshots from a dedicated test account with throwaway credentials.
- Grep committed screenshots for common token prefixes.

**Trigger → action**: rotate the token immediately; re-take the screenshot; invalidate the old one.

---

## R-010 · Tone-check regeneration loops 🟡

**Phase**: Act II.

**Manifestation**: The tone-check model is too strict; drafts regenerate beyond the max count; throughput collapses.

**Mitigations**:

- Max 1 retry per spec; second failure flags for human review.
- Log flagged drafts to `eval/runs/tone_flagged.jsonl` for prompt tuning.
- If regeneration rate > 20% across a run, the tone-check prompt needs a calibration pass.

**Trigger → action**: tune the tone-check prompt on the flagged-drafts log; re-test before resuming the run.

---

## R-011 · Classifier miscalibration on edge cases 🟡

**Phase**: Acts II–III.

**Manifestation**: Segment 2 classified as Segment 1 (or vice versa) on layoff+funding prospects; probe category 1 trigger rate >15%.

**Mitigations**:

- Ordered-rules implementation in `agent/classifier.py` matches the spec's explicit order.
- Unit tests for each rule permutation using synthetic-prospect fixtures.
- Probe library measures the observed trigger rate; Act IV mechanism addresses if it exceeds tolerance.

**Trigger → action**: treat as evidence for Act III target-failure selection.

---

## R-012 · Stretch displaces Act V 🟠

**Phase**: Late final.

**Manifestation**: Market-space map consumes time that should have polished the memo or re-recorded the demo video.

**Mitigations**:

- The stretch is explicitly opt-in (`market_space.enabled: false` by default).
- [`08-stretch-market-space.md`](08-stretch-market-space.md) has a hard gate: don't start until Act V is effectively complete.

**Trigger → action**: abandon the stretch immediately; return to Act V polish.

---

## R-013 · Reproduction drift on τ²-Bench 🟡

**Phase**: Act I, revisit at Act IV.

**Manifestation**: Reproduction CI does not overlap the published reference; re-run with different seeds does not match.

**Mitigations**:

- Pin every seed the harness touches.
- Lock the tau2-bench SHA in `config.yaml`; fail hard on drift.
- If drift persists, debug with a single-task verbose run.

**Trigger → action**: investigate before Act II closes; a broken harness at Act IV time is fatal.

---

## R-014 · Cost-per-qualified-lead above $8 penalty threshold 🟡

**Phase**: Act V memo rendering.

**Manifestation**: `invoice_summary.json` shows cost-per-lead > $8.

**Mitigations**:

- Monitor the rolling metric in Langfuse dashboards during Act II.
- If approaching $8, tune the tone-check regeneration loop; cheap dev-tier composer calls over expensive ones.
- The memo can justify above-$8 if the value (reply-rate gain, brand protection) offsets.

**Trigger → action**: check the denominator (are the "qualified leads" really qualified?); adjust the definition honestly, don't inflate the count.

---

## R-015 · Provider outage during demo recording 🟢

**Phase**: Act V.

**Manifestation**: Resend or HubSpot has an outage during the live-demo recording.

**Mitigations**:

- Pre-record enrichment and τ²-Bench segments before live-recording the email thread.
- If a live segment fails, narrate over a traced replay from Langfuse ("this is the same thread from yesterday; the trace view is live").

**Trigger → action**: reschedule the live-demo segment; the pre-recorded segments are unaffected.

---

## R-016 · Policy acknowledgement delayed 🟢

**Phase**: Pre-flight.

**Manifestation**: Program staff confirmation is slow; Act I is gated.

**Mitigations**:

- File the acknowledgement first thing.
- In the meantime, advance non-gated tasks (repo scaffolding, account provisioning, tau2-bench clone).

**Trigger → action**: ping program staff; don't wait idle.

---

## R-017 · Framework migration mid-project 🟢

**Phase**: Act III or IV.

**Manifestation**: The hand-rolled agent state machine hits a wall; migration to LangGraph or PydanticAI tempting.

**Mitigations**:

- D-010 defers this decision but sets a boundary: migration is scoped to three modules if it happens.
- Evaluate the actual friction vs. a surgical fix before migrating.

**Trigger → action**: write the decision in [`00-decisions.md`](00-decisions.md); migrate only if the friction is repeated, not one-off.

---

## R-018 · Cross-thread context leakage 🟠

**Phase**: Acts II–III.

**Manifestation**: Messages to the co-founder reference content from the VP-Eng thread at the same company. Probe category 5 trigger rate >0.

**Mitigations**:

- D-005: key thread state by prospect email, never by company domain.
- CI lint greps for `company_domain` in context-loading code paths.
- Probe category 5 measures; zero-tolerance is the target.

**Trigger → action**: fix before Act III closes; a non-zero trigger rate at the memo stage is fatal.

---

## Risk review cadence

- Beginning of each phase: re-read this register; check whether the phase's relevant risks have new evidence.
- On any 🔴 trigger: stop and report.
- End of project: write a post-mortem section to the inheritor README with which risks materialized and how they were handled.
