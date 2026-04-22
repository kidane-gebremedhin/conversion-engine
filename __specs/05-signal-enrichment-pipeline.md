# 05 — Signal Enrichment Pipeline

**Source:** Challenge document — "What replaces CFPB complaints — the hiring signal brief", "AI maturity scoring in more detail", "How AI maturity changes the pitch", "Signal enrichment pipeline".

## 1. Purpose

Before the agent composes the first outreach, the enrichment pipeline produces three artifacts per prospect:

1. `hiring_signal_brief.json` — verifiable public-signal snapshot.
2. `ai_maturity_score.json` — 0–3 integer with per-input justification and confidence.
3. `competitor_gap_brief.json` — 5–10 top-quartile peers, prospect position, 2–3 gap practices.

All three are produced once per prospect and cached for 24 h in `data/briefs_cache/<crunchbase_uuid>/`.

## 2. Pipeline steps (ordered)

```python
# agent/enrichment/pipeline.py

def enrich(crunchbase_uuid: str, *, force: bool = False) -> EnrichmentResult:
    p = crunchbase.fetch(crunchbase_uuid)                      # step 1: firmographics
    funding = crunchbase.funding_events(uuid, since_days=180)  # step 2
    jobs_now  = jobposts.crawl(p.domain)                       # step 3 (respects robots.txt)
    jobs_prior = jobposts.snapshot_60d_prior(p.domain)
    velocity = jobposts.velocity(jobs_now, jobs_prior)
    layoff   = layoffs.find_by_company(p.name, since_days=120) # step 4
    leader   = leadership.detect(p, since_days=90)             # step 5
    stack    = techstack.fetch(p.domain)                       # step 6
    maturity = ai_maturity.score(p, jobs_now, stack)           # step 7
    gap      = competitor_gap.build(p, sector=p.industries[0], maturity=maturity)  # step 8
    brief    = build_brief(p, funding, velocity, layoff, leader, stack, maturity)
    persist(brief, maturity, gap, uuid)
    return EnrichmentResult(brief, maturity, gap)
```

## 3. `hiring_signal_brief.json` schema

```json
{
  "version": "1.0",
  "crunchbase_uuid": "e4b1...",
  "company": {
    "name": "Acme AI",
    "domain": "acme.ai",
    "country": "US",
    "industries": ["Artificial Intelligence", "Data Infrastructure"],
    "employee_count_range": "51-100",
    "founded": 2022
  },
  "signals": {
    "funding": {
      "latest_round": "Series B",
      "amount_usd": 14_000_000,
      "date": "2026-02-18",
      "recency_days": 63,
      "confidence": 0.95,
      "evidence": [
        {"source": "crunchbase", "url": "https://crunchbase.com/..."},
        {"source": "press_release", "url": "https://acme.ai/press/series-b"}
      ]
    },
    "job_post_velocity": {
      "open_roles_now": 17,
      "open_roles_60d_ago": 5,
      "ratio": 3.4,
      "ai_adjacent_fraction": 0.47,
      "confidence": 0.78,
      "qualifies_for_aggressive_hiring_claim": true,
      "evidence": [
        {"source": "builtin.com/companies/acme/jobs", "captured_at": "2026-04-20T09:12:00Z"}
      ]
    },
    "layoff": {
      "detected": false,
      "confidence": 0.92
    },
    "leadership_change": {
      "detected": false,
      "confidence": 0.70
    },
    "tech_stack": {
      "items": ["dbt", "Snowflake", "Weights & Biases"],
      "bench_matches": ["Python/data", "ML"],
      "confidence": 0.65
    }
  },
  "generated_at": "2026-04-22T09:15:04Z"
}
```

## 4. Signal-confidence-aware phrasing (enforced in [06-agent-design.md](06-agent-design.md))

Per-signal confidence drives the grammar of the outreach. The agent **must**:

| Signal | Confidence ≥ 0.75 | 0.50 ≤ conf < 0.75 | < 0.50 |
|--------|-------------------|----------------------|---------|
| Funding | Assert ("you closed a $14M Series B in February") | Soften ("we noticed your Series B earlier this year") | Ask ("did you recently close a round?") |
| Job-post velocity | Assert *only* if `qualifies_for_aggressive_hiring_claim` | Soften ("hiring has picked up") | Do not reference |
| Layoff | Assert if `detected && conf ≥ 0.8` | Soften to "restructuring" | Do not reference |
| Leadership change | Assert if press release + Crunchbase agree | "I saw the recent leadership update" | Do not reference |

The `qualifies_for_aggressive_hiring_claim` gate (≥ 5 open roles AND ≥ 2.0× ratio) is **hard-coded**: the agent cannot assert "aggressive hiring" below the threshold, regardless of prompt pressure.

## 5. AI-maturity scoring (0–3)

### Inputs and weights

| Signal | Weight | Max contribution |
|--------|--------|------------------|
| AI-adjacent open roles (fraction of engineering openings + absolute count) | High | 1.0 |
| Named AI/ML leadership (Head of AI, VP Data, Chief Scientist) | High | 1.0 |
| Public GitHub org activity on AI repos | Medium | 0.6 |
| Executive AI commentary last 12 months | Medium | 0.6 |
| Modern data/ML stack (dbt, Snowflake, Databricks, W&B, Ray, vLLM) | Low | 0.3 |
| Strategic communications (annual reports, investor letters) | Low | 0.3 |

### Formula

```
raw = Σ (weight_i × evidence_strength_i ∈ [0, 1])
score = clip(round(raw / normaliser), 0, 3)
confidence = 1 - stdev(weight_i × evidence_strength_i) / max_possible
```

### `ai_maturity_score.json` schema

```json
{
  "version": "1.0",
  "crunchbase_uuid": "e4b1...",
  "score": 2,
  "confidence": 0.62,
  "confidence_band": "medium",      // low (<0.5), medium (0.5–0.75), high (≥0.75)
  "justification": [
    {
      "signal": "ai_adjacent_open_roles",
      "weight": "high",
      "evidence": "8 of 17 open engineering roles are AI-adjacent (47 %)",
      "contribution": 0.85
    },
    {
      "signal": "named_ai_leadership",
      "weight": "high",
      "evidence": "VP Data Science listed on team page since 2024",
      "contribution": 0.90
    },
    {
      "signal": "github_activity",
      "weight": "medium",
      "evidence": "no public AI repos found",
      "contribution": 0.00,
      "caveat": "absence of public signal is not absence of activity"
    }
  ],
  "generated_at": "2026-04-22T09:15:04Z"
}
```

### Score-to-pitch mapping

| Score | Segment 1 language | Segment 2 language | Segment 4 gate |
|-------|-------------------|-------------------|----------------|
| 0 | "stand up your first AI function with a dedicated squad" | "keep delivery capacity while restructuring" | **Blocked** |
| 1 | "expand your early AI team" | "preserve AI delivery while restructuring" | **Blocked** |
| 2 | "accelerate your AI roadmap beyond in-house hiring" | "consolidate AI delivery at lower cost" | Allowed |
| 3 | "scale your AI team faster than in-house hiring can support" | "shift cost without losing AI velocity" | Allowed |

Segment 3 (leadership transition) is independent of the score — the new leader's AI stance is the variable that matters.

### Confidence-band behaviour

- **low**: never quote the score in the email; phrase everything as a question.
- **medium**: mention the score implicitly ("you look like an early AI shop") but do not state the integer.
- **high**: quote the score only inside the context brief attached to the Cal.com invite, not in outbound prose.

## 6. Competitor gap brief

### Goal
Convert outbound from a vendor pitch into a research finding. Instead of "Tenacious offers X", the first message says "three companies in your sector at your stage are doing X and you are not — here is what the difference looks like".

### Steps

1. **Peer set.** Sector = primary Crunchbase industry. Size band = nearest Crunchbase `employee_count_range` tier. Sample 20–40 peers from the ODM sample, filter to top-quartile by funding recency × size, dedupe to 5–10.
2. **Score peers** on the same AI-maturity rubric.
3. **Position prospect** — quartile rank of the prospect within this peer set on AI maturity.
4. **Gap practices.** For each of the top 2–3 most frequently seen practices in the top-quartile peers that are **absent** from the prospect's public signal, record:
   - practice name (e.g., "dedicated ML platform team")
   - evidence source for the peers
   - evidence source for the prospect's absence
   - confidence of the gap claim

### `competitor_gap_brief.json` schema

```json
{
  "version": "1.0",
  "crunchbase_uuid": "e4b1...",
  "sector": "Data Infrastructure",
  "size_band": "51-100",
  "peers": [
    {"name": "Beta Data", "crunchbase_uuid": "...", "ai_maturity_score": 3, "ai_maturity_confidence": 0.81},
    {"name": "Gamma Pipeline", "crunchbase_uuid": "...", "ai_maturity_score": 2, "ai_maturity_confidence": 0.72},
    ...
  ],
  "prospect_position": {
    "score": 2,
    "quartile": 3,                 // 1 = top, 4 = bottom
    "pct_peers_at_or_above": 0.40
  },
  "gap_practices": [
    {
      "practice": "dedicated ML platform team",
      "peers_with": ["Beta Data", "Delta Infra"],
      "prospect_has": false,
      "peer_evidence": [{"source": "peer job post", "url": "..."}],
      "prospect_evidence": [{"source": "prospect team page", "url": "..."}],
      "confidence": 0.78
    }
  ],
  "generated_at": "2026-04-22T09:16:12Z"
}
```

### Gap-over-claiming guard

- A `gap_practice` with `confidence < 0.65` is **dropped**, not softened.
- The agent cites at most **one** gap in the first email, even if the brief surfaces three — it is a hook, not an indictment.
- Gap phrasing must be comparative ("some peers in your sector are doing X"), not prescriptive ("you should be doing X"). This is enforced by the `tone_check` policy ([06 §4](06-agent-design.md)).

## 7. Lossiness modes (carried into memo's skeptic's appendix)

| Mode | What happens | Business impact |
|------|--------------|-----------------|
| **Quiet-sophisticated-but-silent** (big AI function, no public signal) | Score = 0 or 1; agent pitches wrong register | Condescending first message; brand damage |
| **Loud-but-shallow** (conference talks, no product) | Score = 2 or 3; agent over-assumes readiness | Wrong pitch, wastes conversation on segment-4 topics the prospect cannot absorb |
| **Alias mismatch on layoffs.fyi** | False positive layoff detection | Wrong segment, condescending phrasing; counted toward brand-reputation cost |
| **Stale job-post snapshot** | Velocity understated | Under-pitches segment 1; missed opportunity |

Each of these has a probe in [12-probe-library.md](12-probe-library.md) and appears in the memo's Skeptic's Appendix (Page 2, [14](14-memo-specification.md)).

## 8. Pipeline runtime budget

- Per-prospect enrichment: **< 20 s p50**, **< 60 s p95**. Parallelise jobposts + layoffs + leadership checks.
- Memory budget: < 256 MB per worker.
- Cost: the only LLM call is the `ai_maturity` justification synthesis (~200 tokens completion), ≤ $0.002 per prospect.

## 9. Acceptance tests

- Given a fixture prospect with known signals, the pipeline produces the three JSON artifacts matching a golden snapshot.
- Given a prospect with < 5 open roles, the brief never marks `qualifies_for_aggressive_hiring_claim = true`.
- Given a prospect with AI maturity 0 and segment-4 build signal, the ICP classifier (see [03](03-icp-and-segments.md)) abstains.
- Given a prospect with conflicting layoff + funding signals, the brief flags both and the classifier prefers segment 2 with `rationale` explaining the tie-break.
