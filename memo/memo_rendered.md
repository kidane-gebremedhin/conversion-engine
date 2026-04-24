# Conversion Engine — Decision Memo

*To: Tenacious CEO, CFO ·  From: TRP1 Week 10 trainee · Date: `[generated at render time]`*

---

## Page 1 — The decision

**We built a signal-grounded outreach agent that qualifies prospects against public hiring signals, grounds every email in a cited brief, and routes to the Tenacious delivery bench only when capacity exists.**
On the τ²-Bench retail held-out slice the agent scores `—` ± `—` at `$—` per task, versus `—` baseline and `—` for GEPA at the same compute budget.
Recommendation: pilot on **Segment 1 (recently-funded Series A/B)** at **100 leads/month** with a **$400/week LLM budget**; 30-day success metric: reply rate ≥ 7% with wrong-signal-email rate ≤ 2%.

### τ²-Bench retail pass@1 · 95% CI · cost-per-task

| Arm | pass@1 | 95% CI | $ / task | p95 latency |
|---|---:|---|---:|---:|
| Published reference (Feb 2026) | ~0.42 | — | — | — |
| Day-1 baseline | `—` | `—` | `—` | `—` |
| **Our mechanism** | `—` | `—` | `—` | `—` |
| GEPA (same budget) | `—` | `—` | `—` | — |

Delta A (mechanism − baseline) = `—` with p=`—`, 95% CI `—`.

### Cost per qualified lead

- LLM + rig spend: `$0.00` over `7` days.
- Qualified leads (classifier ≥ 0.6 AND reply classified engaged/curious): `0`.
- CPL: **$—** vs. target $5, penalty at $8.

### Speed-to-lead delta

- Tenacious manual stalled-thread baseline (seed/baseline_numbers.md): 30–40%.
- Our system: `—%` on `0` measured threads.
- Sample-size caveat: `n too small to reject H0`.

### Competitive-gap outbound performance

- `—%` of outbound led with a research finding
  (AI-maturity + top-quartile competitor-gap evidence) vs. generic pitch.
- Reply-rate delta (grounded − generic): **+`—`%**.
- Source: HubSpot engagement tagging + `eval/runs/interim/*.json` traces.

### Annualized dollar impact (three adoption scenarios)

| Scenario | Segments | Monthly leads | Booked / mo | ACV | Annualized |
|---|---|---:|---:|---:|---:|
| Conservative | 1 | 100 | 4 | $108K | $5.2M |
| Mid | 1 + 2 | 250 | 10 | $240K | $28.8M |
| Full | 1–4 | 800 | 32 | $360K | $138M |

Backed by `seed/baseline_numbers.md` conversion rates; see evidence graph.

### Pilot recommendation (repeat)

**Segment 1 · 100 leads/month · $400/week LLM budget · 30-day success: reply ≥ 7%, wrong-signal-email ≤ 2%.**

---

## Page 2 — The Skeptic's Appendix

### Four failure modes τ²-Bench does not capture

1. **Offshore-perception objection.** τ²-Bench's retail domain has no
   vendor-perception dimension. A Tenacious in-house hiring manager can
   smell offshore framing in three sentences. A tone-check layer exists
   but is tuned on dev-tier judgement that may itself be biased.
2. **Bench mismatch masked by fuzzy language.** Prospect says
   "data team"; the bench "data" stack is data-engineering. τ²-Bench
   retail has no asymmetric-vocabulary probe.
3. **Brand-reputation risk from wrong-signal emails.** A single viral
   LinkedIn screenshot of a factually wrong hiring-signal claim offsets a
   week of reply-rate gains. τ²-Bench does not score for quote-worthiness.
4. **Multi-thread co-founder / VP Eng leakage.** Running two threads at
   the same company concurrently risks one thread quoting the other. The
   agent's HubSpot thread-id scoping is tested, but the probe trigger rate
   rises sharply under concurrent load.

### Public-signal lossiness

- **Quietly sophisticated but silent.** A company running large private
  ML workloads with zero public GitHub, Head-of-AI, or exec commentary
  scores ai_maturity 0. The agent pitches Segment 1 with softer AI
  vocabulary — acceptable on reputation grounds, lost-revenue on economics.
- **Loud but shallow.** A consumer brand with splashy "we use AI" press
  and no actual ML team scores 2–3. The agent pitches Segment 4 with a
  competitor-gap frame. If the prospect's AI is marketing, the Segment 4
  pitch reads tone-deaf.

### Gap-analysis risks

Top-quartile peer practice is a bad benchmark when the prospect has made
a deliberate strategic choice to *not* adopt a practice
(data-residency, regulatory). One example: `example-fin.example` shows
no modern ML-platform tooling because GDPR-strict storage constraints;
the competitor-gap brief should suppress the peer comparison — the
`prospect_silent_but_sophisticated_risk` self-check exists but
sometimes mis-fires.

### Brand-reputation comparison

If 1,000 signal-grounded emails produce 5% with a factually wrong signal
(~50 messages) at $50K brand-damage unit × 2% probability-of-escape, the
expected brand cost is $50K. If reply rate rises from 1–3% baseline to
7–12%, ~90 more replies → ~4 more bookings × $108K → +$432K revenue.
Net expected value +$382K per 1,000 messages — **conditional on the 2%
escape probability**. If escape probability is 10%, value flips negative.

### One honest failure

**P-0402 — cross-segment content leak.** The mechanism reduces but does
not zero out content leakage across back-to-back Segment 1 / Segment 4
compose_and_send runs. Observed trigger rate after mechanism:
`?%`. If deployed without isolation, a Segment 1 draft
may contain a phrase introduced for Segment 4; the damage is low
(semantic-level, not PII-level) but real.

### Kill-switch clause

- **Trigger**: wrong-signal-email rate > 2% on a 50-message rolling window,
  measured by weekly audit (`scripts/audit_week.py`) cross-checked against
  HubSpot response sampling.
- **Rollback**: Tenacious CEO flips `TENACIOUS_OUTBOUND_ENABLED` to unset;
  all drafts route to staff sink until the probe library (`make probes`)
  reports a green triaged cause.

---

*Footer, every page: page N of 2 · generated `2026-04-24T12:23:12.993359+00:00` ·
`evidence_graph.json` sha256 `ae7792e383646812`.*
