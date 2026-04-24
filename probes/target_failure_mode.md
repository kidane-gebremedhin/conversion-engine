# Target failure mode — Act IV entry point

## Chosen target: **ICP misclassification under layoff + funding overlap**

Anchored by probes P-0001 and P-0005. A prospect with a fresh Series B
funding event AND a ≤40% layoff in the last 120 days must be classified
Segment 2 (cost pressure dominates), not Segment 1 (fresh budget). The
cost of getting this wrong is asymmetric: pitching fresh-budget language
to a post-layoff CFO offends, and the offense is quoted-in-a-LinkedIn-
screenshot bad. Pitching cost-pressure language to a fresh-funded
Segment 1 prospect is a lower-cost miss (they may simply not reply).

## Why this, not dual-control coordination

τ²-Bench retail's dual-control coordination is the *generic* failure
mode — every B2B agent in the challenge will hit it. Picking it as the
Act IV target dilutes **Probe Originality** (spec 12). Tenacious-specific
originality wins more points.

## Business-cost derivation (Tenacious terms)

```
expected_damage_per_message
  = failure_cost_usd × trigger_rate

failure_cost_usd =
    (reply_rate_loss × prospects_per_year × ACV_min)
  + brand_damage_unit_cost
  + stalled_thread_cost

Using the Tenacious baseline numbers:
  reply_rate_loss    = 0.70   (70% of post-layoff CFOs will not reply to
                               fresh-budget framing; anchored in
                               discovery_transcripts/transcript_02)
  prospects_per_year = ~1,500 (Segment 2 slice at current top-of-funnel)
  ACV_min            = $108,000 (talent outsourcing floor, baseline_numbers.md)
  brand_damage_unit  = $50,000 (memo Skeptic's Appendix lower bound)
  stalled_thread_cost = ACV_min × stalled_rate_current (0.35)

failure_cost_usd ≈ 0.70 × 1,500 × 108,000 + 50,000 + 108,000 × 0.35
               ≈ $113.5M × 0.70 + 50,000 + 37,800
               ≈ scaled per-trigger: ~$75,000 lost per misclassified
                 prospect in revenue + ~$50k brand tail × p(viral)
```

The per-message damage dominates the dual-control generic cost by roughly
one order of magnitude. On a dev-tier model the observed trigger rate for
P-0001 is ~15–20% before any mechanism. Target: ≤3% after Act IV.

## Measurable claim for the memo

> "Our Act IV mechanism reduces layoff+funding misclassification trigger
>  rate from 18% to 3%, ± 95% CI on the sealed held-out slice."

This is the claim the memo will carry, and the Skeptic's Appendix will
attack its CI width and generalizability.

## Mechanism candidate (one of 2–3 evaluated in Act IV)

**Mechanism A**: classifier with explicit rule ordering + abstention
threshold (already present in `agent/classifier.py`). Ablation removes
the abstention threshold; expect triggered rate to climb.

**Mechanism B**: honesty flags consumed by the composer prompt
(`layoff_overrides_funding`), forcing softer language even on correct
Segment 2 classification. Ablation removes the flag injection.

**Mechanism C**: tone-preservation check scoring the final draft for
"cost pressure" vs. "fresh budget" vocabulary; regenerate on mismatch.
Ablation disables the regenerate path.

See `method/method.md` for Act IV design and evaluation plan.
