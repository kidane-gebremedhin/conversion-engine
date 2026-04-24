# 03 — ICP and Segments

The canonical ICP lives in [`tenacious_sales_data/seed/icp_definition.md`](../tenacious_sales_data/seed/icp_definition.md). This spec defines how the implementation consumes and enforces that definition. **Segment names are fixed for grading.** Filters may be refined in the classifier with justification in `method/method.md`; segments may not be renamed, merged, split, or extended.

## The four segments (fixed)

| Segment | Name | Primary signal | Service line |
|---|---|---|---|
| **1** | Recently-funded Series A/B startups | Series A/B in last 180d, $5–30M, HC 15–80, ≥5 open eng roles | Talent outsourcing |
| **2** | Mid-market platforms restructuring cost | HC 200–2000, layoff in last 120d OR restructure press in last 90d, ≥3 open eng roles post-event | Talent outsourcing |
| **3** | Engineering-leadership transitions | New CTO or VP Eng in last 90d, HC 50–500, no concurrent CFO/CEO transition | Talent outsourcing (often) |
| **4** | Specialized capability gaps | Stuck specialist req 60+d OR strategic announcement without team-page change, **AI-maturity ≥2 required** | Project consulting |

## Classification rules (ordered)

The classifier applies rules in this order and stops at the first match. Conflict resolution is part of grading — Segment 1/2 confusion on a layoff+funding prospect is a standard probe target.

1. **Layoff in last 120 days AND fresh funding in last 180 days** → **Segment 2** (cost pressure dominates).
2. **New CTO / VP Eng in last 90 days** → **Segment 3** (transition window dominates).
3. **Specialized-capability signal AND AI-maturity ≥ 2** → **Segment 4**.
4. **Fresh funding in last 180 days (no layoff, no leadership change)** → **Segment 1**.
5. **Otherwise → abstain**. The agent sends a generic exploratory email rather than a segment-specific pitch.

## Qualifying and disqualifying filters

The qualifying and disqualifying filters per segment are the canonical ones in `icp_definition.md`. Implementation notes:

- Qualifying filters are **positive evidence** that must be present for the segment to fire. Missing one filter drops `segment_confidence` proportionally to its weight.
- Disqualifying filters are **hard negatives**. Any single disqualifying filter fires → segment is ruled out regardless of positive evidence.
- "Already listed as client of a direct Tenacious competitor" disqualifier (Segment 1): check Andela / Turing / Revelo / TopTal public case studies. Implementation: a static YAML list of competitor case-study URLs, scraped once per week (≤ 4 domains → within the 200-company cap).
- "Explicitly anti-offshore founder public stance" (Segment 1): a soft signal that requires a text-classifier LLM call over the founder's recent public posts. If the post-corpus is empty or ambiguous, this filter does **not** fire.
- "Layoff percentage above 40% in a single event" (Segment 2 disqualifier): parsed from layoffs.fyi `percentage_cut` field.
- "Interim / acting CTO appointment" (Segment 3 disqualifier): string match against announcement text (`interim`, `acting`, `interim CTO`, `acting VP Engineering`).

## Confidence scoring

`segment_confidence ∈ [0, 1]`:

```
qualifying_evidence   = Σ weight_i × I(filter_i fires)   for qualifying filters in segment
qualifying_maximum    = Σ weight_i                        over the same set
segment_confidence    = qualifying_evidence / qualifying_maximum
                        × (1 − penalty_for_missing_hard_filters)
```

Weights and thresholds live in [`config.example.yaml`](config.example.yaml) under `icp.segment_<n>.filter_weights`. **Default confidence abstention threshold is 0.6** (configurable via `icp.abstain_threshold`). Below threshold, `primary_segment_match = "abstain"`.

## Abstention is a first-class outcome

Abstention is **not** a failure path. It is the correct behavior when signal is weak, and the probe library (spec 12) measures abstention correctness. An abstained prospect:

- Is still eligible for a generic exploratory email (one touch) — but only if firmographics pass baseline sanity (is a real company on Crunchbase, in a supported geography, not on the competitor-client list).
- Is flagged in the HubSpot contact property `tenacious_segment = abstain` and `tenacious_status = draft`.
- Contributes to the abstention-rate metric tracked in [spec 10](10-observability.md).

## Pitch language shifts

Per segment, the composer selects language based on the AI-maturity score:

| Segment | High AI-readiness (2–3) | Low AI-readiness (0–1) |
|---|---|---|
| **1** | "scale your AI team faster than in-house hiring can support" | "stand up your first AI function with a dedicated squad" |
| **2** | "preserve your AI delivery capacity while reshaping cost structure" | "maintain platform delivery velocity through the restructure" |
| **3** | AI-maturity **does not shift** pitch. Lead with the appointment, let the new leader direct technical language. | (same) |
| **4** | Only pitched at score ≥2. Pitch grounded in the specific capability gap from `competitor_gap_brief.json`. | **Not pitched.** Compose as Segment 1 or 2 with softer AI vocabulary. |

Implementation: the composer receives `(segment, ai_maturity_score, ai_maturity_confidence)` and loads the corresponding prompt from `agent/prompts/composer_segment_<n>.txt`. Low-confidence + high-score combinations force "ask rather than assert" phrasing — the agent softens verbs (*we noticed* → *is this something you're actively scoping?*).

## Segment 4 — AI-maturity gating

A score-0 or score-1 prospect **must not** receive a Segment 4 pitch. The composer checks:

```
if segment == 4 and ai_maturity.score < 2:
    raise SegmentMismatch("Segment 4 requires AI maturity ≥2")
```

This is enforced at composer input, not at post-hoc tone check — reaching out to a score-0 prospect with a Segment 4 pitch wastes the contact and damages the brand (per `icp_definition.md`).

## Per-segment sequence adjustments

Email-sequence behavior is in [spec 07](07-channels.md) and the templates. Per-segment deviations:

- **Segment 2**: soften urgency in Email 1. Post-restructure CFOs are wary of high-energy outbound.
- **Segment 4**: Email 2 competitor-gap content is the core value proposition and **must** have at least one `high` confidence gap finding in `competitor_gap_brief.json` or the follow-up is suppressed.
- **Low AI-readiness prospects in any segment**: default to Segment 1 or 2 framing with softer AI-adjacent vocabulary; never use Segment 4 pitch language.

## Bench-to-brief match

Every segment's pitch is gated on `bench_summary.json`. The composer's draft may reference specific stacks only when the stack has at least one available engineer on the bench. See [spec 05](05-signal-enrichment-pipeline.md) for the bench-gate implementation and [spec 12](12-probe-library.md) for the bench-over-commitment probe.

## What the implementation must NOT do

- Rename, merge, split, or add segments.
- Silently re-classify a Segment 2 prospect as Segment 1 because the funding signal is more attractive to pitch (layoff overrides funding — see rule #1 above).
- Use a Segment 4 pitch on a score-0 prospect.
- Hard-code segment thresholds in Python source (all thresholds are in YAML config).
