# 05 — Signal Enrichment Pipeline

The signal enrichment pipeline runs **before** the agent composes the first outreach. It produces two grounded research artifacts that every subsequent composer call binds to.

## Pipeline contract

**Input**: a Crunchbase company record (resolved by domain).
**Output**: two JSON files on disk and two engagements on the HubSpot contact record:

- `eval/briefs/<domain>/hiring_signal_brief.json` — validates against [`schemas/hiring_signal_brief.schema.json`](../tenacious_sales_data/schemas/hiring_signal_brief.schema.json).
- `eval/briefs/<domain>/competitor_gap_brief.json` — validates against [`schemas/competitor_gap_brief.schema.json`](../tenacious_sales_data/schemas/competitor_gap_brief.schema.json).

**Honesty invariant**: every field in the output brief is sourced from a `data_sources_checked` entry. Claims without a source are either omitted or marked `status = "no_data"`. The composer reads only from the briefs; it has no direct access to raw sources.

## Pipeline DAG

```
                 ┌───────────────┐
                 │ crunchbase    │
                 │ firmographics │
                 └───────┬───────┘
                         │
         ┌───────────────┼─────────────────────┐
         ▼               ▼                     ▼
  ┌──────────┐    ┌──────────────┐     ┌────────────────┐
  │ funding  │    │ layoffs.fyi  │     │ leadership     │
  │ (last    │    │ (last 120d)  │     │ change (last   │
  │ 180d)    │    │              │     │ 90d CTO/VPE)   │
  └────┬─────┘    └──────┬───────┘     └────────┬───────┘
       │                 │                      │
       └────────┬────────┴──────────────────────┘
                ▼
    ┌────────────────────────────┐
    │ job-post velocity          │
    │ (today vs 60d prior)       │
    │ + AI-adjacent role ratio   │
    └────────────┬───────────────┘
                 ▼
    ┌────────────────────────────┐
    │ AI-maturity score 0–3      │
    │ (6 signal inputs, weighted)│
    │ + per-input confidence     │
    └────────────┬───────────────┘
                 ▼
    ┌────────────────────────────┐
    │ tech-stack inference       │
    │ (BuiltWith/Wappalyzer/     │
    │  job-post mentions)        │
    └────────────┬───────────────┘
                 ▼
    ┌────────────────────────────┐
    │ bench-to-brief match       │
    │ (required stacks vs.       │
    │  bench_summary.json)       │
    └────────────┬───────────────┘
                 ▼
    ┌────────────────────────────┐
    │ ICP classifier             │
    │ (segment + confidence)     │
    └────────────┬───────────────┘
                 ▼
    ┌────────────────────────────┐
    │ hiring_signal_brief.json   │
    └────────────┬───────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ competitor gap brief       │
    │  • sector peer selection   │
    │  • peer AI-maturity score  │
    │  • top-quartile benchmark  │
    │  • 2–3 gap findings        │
    └────────────┬───────────────┘
                 ▼
    ┌────────────────────────────┐
    │ competitor_gap_brief.json  │
    └────────────────────────────┘
```

## Step-by-step

### 1. Firmographics (`agent/enrichment/crunchbase.py`)

Lookup by normalized domain. Emit `prospect_domain`, `prospect_name`, `headcount_band`, `hq_country`, `sector` (Crunchbase `categories` field, narrowed to a sub-niche where useful).

### 2. Funding events (`agent/enrichment/crunchbase.py`)

Scan `funding_rounds` for events in the last `funding.window_days` (default 180) where `amount_usd ∈ [funding.min_usd, funding.max_usd]` (default 5M–30M, configurable). Populate `buying_window_signals.funding_event`.

### 3. Layoffs (`agent/enrichment/layoffs.py`)

Match company to layoffs.fyi by normalized name. If an event exists within `layoffs.window_days` (default 120), populate `buying_window_signals.layoff_event` with `date`, `headcount_reduction`, `percentage_cut`, `source_url`.

### 4. Leadership change (`agent/enrichment/leadership.py`)

Detect new CTO or VP Engineering appointments in the last `leadership.window_days` (default 90). Sources, in order of confidence:

- Crunchbase People change records (highest confidence, preferred).
- Press release scraping (medium confidence).
- LinkedIn "started a new position" public-page match (lower confidence, harder to verify).

Interim / acting leaders do **not** fire this signal. See [spec 03](03-icp-and-segments.md) Segment 3 disqualifiers.

### 5. Job-post velocity (`agent/enrichment/jobposts.py`)

For each of BuiltIn, Wellfound, LinkedIn company page, and the prospect's own `/careers` page:

- Count currently open engineering roles.
- Read the 60-day-prior snapshot count from the frozen data file.
- Emit `velocity_label` per thresholds in `config.yaml`. Defaults:
  - `tripled_or_more` if ratio ≥ 3
  - `doubled` if ratio ≥ 2
  - `increased_modestly` if ratio ≥ 1.25
  - `flat` if 0.8 ≤ ratio < 1.25
  - `declined` if ratio < 0.8
  - `insufficient_signal` if `open_roles_today < 5` (hard override)

### 6. AI-maturity scoring (`agent/enrichment/ai_maturity.py`)

Six signal inputs, weighted (weights configurable in `config.yaml > ai_maturity.weights`; defaults match the challenge brief):

| Signal input | Weight | Source |
|---|---|---|
| AI-adjacent open roles | high | job-post scrape |
| Named AI/ML leadership | high | team page / LinkedIn |
| Public GitHub org activity | medium | github API (no login, rate-limited) |
| Executive commentary | medium | company blog, press |
| Modern data/ML stack | low | BuiltWith, Wappalyzer |
| Strategic communications | low | fundraising press, investor letters |

Scoring:

```
raw_score     = Σ weight_i × strength_i    (strength_i ∈ {0, 1, 2, 3})
normalized    = raw_score / max_possible_raw_score × 3
score         = round(clip(normalized, 0, 3))   ∈ {0, 1, 2, 3}
confidence    = mean(high_weight_inputs_with_strong_evidence)
                 where missing high-weight inputs deduct confidence linearly
```

For every `justifications` entry, emit `signal`, `status` (free-text description of what was or was not found), `weight`, `confidence ∈ {high, medium, low}`, and `source_url` (when signal is positive). Absence-of-evidence is explicitly acceptable — the policy requires honesty, not false positives.

**Score 0** = no public signal. **Score 3** = active AI function with named leadership, open AI roles, and recent exec commitment.

### 7. Tech stack inference (`agent/enrichment/tech_stack.py`)

Union of BuiltWith/Wappalyzer detections and tech names mentioned in the prospect's open job posts. Normalized to the canonical stack taxonomy in `config.yaml > bench.stacks` (Python, Go, data, ML, infra, frontend, fullstack_nestjs).

`honesty_flags += ["tech_stack_inferred_not_confirmed"]` when only job-post mentions are available.

### 8. Bench-to-brief match (`agent/enrichment/ai_maturity.py` → continues)

Inputs: `tech_stack` + `segment` + current [`bench_summary.json`](../tenacious_sales_data/seed/bench_summary.json).

```
required_stacks = derive_from(tech_stack, segment)    # e.g., {python, data} for a Python-heavy Series B
bench_available = all(bench_summary[s].available_engineers > 0 for s in required_stacks)
gaps            = [s for s in required_stacks if bench_summary[s].available_engineers == 0]
```

If `bench_available is False`, the composer **must not** pitch specific staffing for the missing stack; it routes to the human handoff path or abstains. See [spec 06](06-agent-design.md).

### 9. ICP classification

Applies rules 1–5 from [spec 03](03-icp-and-segments.md). Outputs `primary_segment_match` and `segment_confidence`.

### 10. Competitor gap brief (`agent/enrichment/competitor_gap.py`)

The competitor gap brief is the second research artifact. It converts outreach from vendor pitch to research finding.

**Peer selection**:

- Crunchbase records in the same `sector` (or the narrower `sub_niche` when set in `config.yaml > competitor_gap.sub_niche_overrides`).
- Same `headcount_band` as the prospect (the bands are from the schema's enum).
- Exclude the prospect itself, Tenacious competitors from the disqualifier list, and any company that is the prospect's acquirer/subsidiary.
- Select 5–10 peers ranked by domain-authority proxy (available from Crunchbase `rank_score` or a static heuristic; configurable).

**Peer scoring**: apply the same AI-maturity rubric to each peer. For each peer, record `ai_maturity_score`, `ai_maturity_justification`, `headcount_band`, and all `sources_checked` URLs.

**Top quartile**: peers with `ai_maturity_score >= ceil(top_quartile(scores))` marked `top_quartile = true`. `sector_top_quartile_benchmark = mean(ai_maturity_score) for top_quartile_peers`.

**Gap findings**: 1–3 specific practices where the top-quartile peers show public signal that the prospect does not. Each finding must include ≥2 peer-evidence entries with URLs. Low-confidence findings force the agent's phrasing to `ask`. Findings are graded on specificity: "they use AI" is useless; "three peers have opened named MLOps-platform-engineer roles in the last 60 days" is valuable.

**Suggested pitch shift**: a short prompt-engineering hint (e.g., "Shift from generic talent pitch to specialized capability gap: stand up your first MLOps function with a dedicated squad"). Used as a soft guide, not a hard constraint.

**Self-check fields**:

- `all_peer_evidence_has_source_url` — boolean, enforced in the schema validator.
- `at_least_one_gap_high_confidence` — if false, Email 2 (Day 5 follow-up, see [spec 07](07-channels.md)) is suppressed for Segment 4.
- `prospect_silent_but_sophisticated_risk` — true when the prospect shows internal sophistication (recent technical blog posts, modern data stack) despite low public AI-maturity signal. Forces softer gap language.

## Honesty flags (set at pipeline end)

| Flag | When it fires | Composer behavior |
|---|---|---|
| `weak_hiring_velocity_signal` | `open_roles_today < 5` | Never asserts "aggressive hiring"; asks rather than asserts. |
| `weak_ai_maturity_signal` | AI-maturity `confidence < 0.5` | Never pitches Segment 4; softens AI language in 1/2. |
| `conflicting_segment_signals` | Layoff + fresh funding, or leadership change + layoff | Composer defers to the classification-rules priority; logs the conflict in HubSpot. |
| `layoff_overrides_funding` | Set when rule #1 fires (layoff + funding) | Segment 2 language, not Segment 1. |
| `bench_gap_detected` | `bench_to_brief_match.bench_available == false` | Composer must not commit specific staffing; route to handoff. |
| `tech_stack_inferred_not_confirmed` | Tech stack from job posts only, no BuiltWith | Composer phrases tech-stack references as "based on your open roles" rather than asserting. |

## Per-source failure handling

Each source emits a `data_sources_checked` entry with `status ∈ {success, partial, no_data, error, rate_limited}`. The pipeline never fails the whole brief on a single source error; it records the failure and proceeds. **`rate_limited` is an explicit status (not an error)** — it is required by the data-handling policy (see [spec 16](16-data-handling-and-kill-switch.md)).

If the Crunchbase lookup fails entirely (no record), the pipeline aborts and the prospect is flagged `no_outreach_possible`. No synthesized firmographics.

## Caching and reproducibility

- Each brief is written with a `generated_at` UTC timestamp. Briefs are stale after 7 days; any outreach referencing a brief must confirm `now - generated_at < 7d`.
- Briefs are keyed by `(prospect_domain, generated_at_day)` and cached under `eval/briefs/<domain>/<iso_date>/`. Re-runs on the same day reuse the existing brief unless `--force` is set.
- The 60-day-prior job-post snapshot is the single source of truth for hiring velocity. Re-computing velocity against a live fetch without updating the snapshot is a bug.

## What the pipeline must NOT do

- Fabricate a funding round, layoff, leadership change, or peer evidence.
- Emit a `high` confidence on an input backed only by inference.
- Skip the `data_sources_checked` log for a source it did not successfully call.
- Contact more than 200 distinct companies via live crawl across the challenge week.
- Write a brief referencing a competitor not in the Crunchbase sample (all peers must be traceable).
