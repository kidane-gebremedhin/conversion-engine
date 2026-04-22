# 03 — ICP Definition and Segment Classifier

**Source:** Challenge document — "Who Tenacious sells to", "ICP classifier with abstention".

## 1. Four fixed segments

Segment **names** are immutable (grading-fixed). Filters may be refined; the taxonomy may not.

```yaml
# agent/icp/segments.yaml
segments:
  - id: 1
    name: "Recently-funded Series A/B startups"
    qualifiers:
      funding_round_in: [Series A, Series B]
      funding_amount_usd_min: 5_000_000
      funding_amount_usd_max: 30_000_000
      funding_recency_days_max: 180
      headcount_min: 15
      headcount_max: 80
    disqualifiers:
      layoff_recency_days_max: 120    # push to segment 2 instead
    why_they_buy: "Hiring velocity outstrips in-house recruiting; runway is the clock."
    pitch_register:
      ai_maturity_high: "scale your AI team faster than in-house hiring can support"
      ai_maturity_low: "stand up your first AI function with a dedicated squad"

  - id: 2
    name: "Mid-market platforms restructuring cost"
    qualifiers:
      headcount_min: 200
      headcount_max: 2_000
      layoff_recency_days_max: 120
      company_stage_in: [late_stage, public]
    disqualifiers:
      funding_recency_days_max: 180   # only disqualify if fresh raise dominates narrative
    why_they_buy: "Replace higher-cost roles with offshore equivalents; quiet signal of operational discipline."
    pitch_register:
      ai_maturity_high: "shift cost structure without losing AI delivery velocity"
      ai_maturity_low: "maintain delivery capacity while reducing burn"

  - id: 3
    name: "Engineering-leadership transitions"
    qualifiers:
      leadership_change_role_in: [CTO, VP Engineering, SVP Engineering, Head of Engineering]
      leadership_change_recency_days_max: 90
    disqualifiers: {}
    why_they_buy: "New leaders reassess vendor contracts and offshore mix in first 6 months — narrow high-conversion window."
    pitch_register:
      default: "As you reassess vendor mix, here is what the top quartile in your sector is doing differently."

  - id: 4
    name: "Specialized capability gaps"
    qualifiers:
      build_signal_in: [ml_platform_migration, agentic_systems, data_contracts, rag_infra, llm_evals]
      ai_maturity_min: 2              # HARD GATE — do not pitch segment 4 below this
    disqualifiers:
      ai_maturity_max_exclusive: 2    # belt + braces
    why_they_buy: "Project-based consulting, higher margin, shorter commitment."
    pitch_register:
      default: "Your public work on {{ build_signal }} suggests a specific infrastructure gap we have delivered on three times."
```

## 2. Classifier with abstention

**Motivation:** A mis-segmented first email damages the brand more than a generic-exploratory email. Low classifier confidence triggers the generic variant.

### Inputs
- `hiring_signal_brief.json` (see [05](05-signal-enrichment-pipeline.md))
- `ai_maturity_score.json`
- ICP `segments.yaml`

### Algorithm

```python
def classify(brief: HiringSignalBrief) -> IcpClassification:
    scores = {s.id: score_segment(brief, s) for s in SEGMENTS}
    top = max(scores, key=scores.get)
    second = sorted(scores.values(), reverse=True)[1]
    margin = scores[top] - second

    if scores[top] < cfg.icp.confidence_threshold:        # default 0.55
        return IcpClassification(segment=None, mode="abstain",
                                 reason="top score below threshold")
    if margin < cfg.icp.margin_threshold:                  # default 0.10
        return IcpClassification(segment=None, mode="abstain",
                                 reason=f"ambiguous between {top} and {second}")
    if top == 4 and brief.ai_maturity.score < 2:
        return IcpClassification(segment=None, mode="abstain",
                                 reason="segment 4 gated below maturity 2")
    return IcpClassification(segment=top, mode="confident",
                             confidence=scores[top], margin=margin)
```

### Scoring function
Weighted sum over segment qualifiers, each scored in [0, 1]:

| Signal → Segment | Weight |
|------------------|--------|
| Funding recency × size → 1 | 0.45 |
| Layoff recency + headcount band → 2 | 0.40 |
| Leadership change recency → 3 | 0.60 |
| Build-signal presence + maturity ≥ 2 → 4 | 0.55 |

Plus **penalty terms** per segment disqualifier (e.g., a layoff in last 120 days penalises segment 1 by 0.30).

### Outputs
```json
{
  "segment": 2,
  "mode": "confident",
  "confidence": 0.78,
  "margin": 0.31,
  "scores": {"1": 0.12, "2": 0.78, "3": 0.47, "4": 0.05},
  "rationale": [
    "layoff on 2026-03-14 (38 days ago) — +0.40 to segment 2",
    "headcount 640 within 200–2000 band — +0.15",
    "no Series A/B round in last 180 days — penalty 0.00 to segment 1"
  ]
}
```

## 3. Behaviour under abstention

When `mode == "abstain"`:

1. Agent sends a **generic-exploratory** email variant (shorter, no segment-specific pitch, no competitor gap claim).
2. Trace is tagged `outbound_variant=exploratory` so the memo can measure the reply-rate delta vs. `outbound_variant=signal_grounded`.
3. HubSpot contact record stores `icp_segment=null, icp_mode=abstain`.
4. Thread can be re-classified after the prospect replies — new signals from the reply may lift confidence above threshold.

## 4. Corner cases the classifier must get right

| Case | Expected behaviour | Probe reference |
|------|-------------------|-----------------|
| Post-layoff company that also raised a recent bridge round | Segment 2, **not** 1; layoff dominates pitch register | `icp_misclass_layoff_plus_bridge.yaml` |
| New CTO at a freshly funded startup | Segments 1 and 3 both qualify; prefer 3 (higher conversion) | `icp_misclass_segments_overlap.yaml` |
| 1500-person co with ML-platform RFP but no layoff | Segment 4 if maturity ≥ 2, else abstain | `icp_misclass_segment4_gate.yaml` |
| Private company, no public funding signal, no layoffs, ≤ 50 people | Abstain (insufficient evidence) | `icp_misclass_insufficient.yaml` |

## 5. Adapting filters (allowed, bounded)

The agent **may** adjust:
- Numeric thresholds (headcount bands, recency windows) based on sector distribution from the Crunchbase ODM sample.
- Weight vector via held-out calibration.

The agent **must not**:
- Invent a fifth segment.
- Rename any segment.
- Drop the AI-maturity gate on segment 4.
- Re-purpose `segment_id` integers.

## 6. Output contract

Every prospect must produce an `icp_classification.json` with the shape above, stored in `data/briefs_cache/<crunchbase_id>/icp_classification.json` and attached to the HubSpot contact as a custom property.
