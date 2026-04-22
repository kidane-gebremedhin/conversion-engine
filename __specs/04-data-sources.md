# 04 — Data Sources

**Source:** Challenge document — "The Data", "Restriction" notes, "Data Handling Policy".

## 1. Summary

| # | Source | License | Role | Path |
|---|--------|---------|------|------|
| 1 | Crunchbase ODM sample (1 001 records) | Apache 2.0 | Primary firmographics; every lead references a record | `data/crunchbase_odm/companies.json` |
| 2 | layoffs.fyi | CC-BY | Layoff signal → segment 2 classification | `data/layoffs_fyi/layoffs.csv` |
| 3 | Public job posts (BuiltIn / Wellfound / LinkedIn) | Public HTML; respect `robots.txt` | Hiring velocity signal | `data/jobposts_snapshot/` |
| 4 | τ²-Bench (retail + telecom) | MIT (Sierra Research) | Ground-truth conversation benchmark | `eval/tau2-bench/` |

Supporting public signals (not primary sources, but read by the enrichment pipeline):
- Crunchbase press-release feed for funding + leadership events.
- BuiltWith / Wappalyzer public endpoints for tech stack.
- Public GitHub org pages for AI-maturity commits signal.
- Company team pages + LinkedIn public pages for "Head of AI" / "VP Data" detection.

## 2. Crunchbase ODM sample

### What it is
1 001 real Crunchbase company records with firmographics, funding history, founders, industry, location.

### Where to get it
`https://github.com/luminati-io/Crunchbase-dataset-samples`

### Loader contract
```python
# agent/enrichment/crunchbase.py
class CrunchbaseRecord(BaseModel):
    uuid: str
    name: str
    domain: HttpUrl | None
    country: str
    region: str | None
    industries: list[str]
    founded_on: date | None
    employee_count_range: str | None   # e.g., "11-50"
    total_funding_usd: int | None
    last_funding_type: str | None
    last_funding_amount_usd: int | None
    last_funding_date: date | None
    founders: list[str]
    ceo: str | None
    linkedin_url: HttpUrl | None
    crunchbase_url: HttpUrl
    raw: dict                           # original JSON row, for audit

def load_all() -> list[CrunchbaseRecord]: ...
def by_domain(domain: str) -> CrunchbaseRecord | None: ...
def funding_events(uuid: str, since_days: int = 180) -> list[FundingEvent]: ...
```

### Constraints
- Every HubSpot `Company` object **must** carry `crunchbase_uuid` as a custom property. This is non-optional — it is the evidence-graph root for every lead.
- No record may be mutated in place; enriched fields live in the brief, not in the ODM file.

## 3. layoffs.fyi

### What it is
Weekly-updated CC-BY CSV — company name, date, headcount impacted, percentage cut, source link.

### Where to get it
- Canonical: `https://layoffs.fyi` (downloadable CSV on the page).
- HuggingFace mirror: search `layoffs.fyi` on HF datasets.
- For this project, snapshot into `data/layoffs_fyi/layoffs.csv` at week start and treat as immutable.

### Loader contract
```python
class LayoffEvent(BaseModel):
    company_name: str
    date: date
    headcount: int | None
    percentage: float | None
    source_url: HttpUrl | None

def load_snapshot() -> list[LayoffEvent]: ...
def find_by_company(name: str, since_days: int = 120) -> list[LayoffEvent]: ...
```

### Matching strategy
- Primary: exact normalised company-name match (lowercase, strip legal suffixes).
- Secondary: domain match via a small hand-curated alias table (`data/layoffs_fyi/aliases.yaml`).
- **Tertiary allowed only with manual confirmation** — fuzzy matches without review produce high false-positive rates and the agent must not over-claim restructuring on a fuzzy hit.

## 4. Public job posts

### Restrictions (HARD)
- **Public pages only.** Do **not** log in. Do **not** bypass captchas. Respect `robots.txt`.
- For the challenge week: prefer the **frozen early-April 2026 snapshot** in `data/jobposts_snapshot/`. Any live crawl is capped at **200 companies**.

### Sources
- BuiltIn (`builtin.com/companies/<slug>/jobs`)
- Wellfound (`wellfound.com/company/<slug>/jobs`)
- LinkedIn company page public job feed (unauthenticated only)
- Company career pages (generic adapter, JSON-LD `@type=JobPosting` parsing)

### Scraper contract
```python
class JobPost(BaseModel):
    company_domain: str
    title: str
    posted_at: date
    location: str | None
    department: str | None
    role_category: Literal["engineering", "ml", "data", "design", "gtm", "ops", "other"]
    url: HttpUrl

def crawl(company_domain: str, *, since_days: int = 60) -> list[JobPost]: ...
def velocity(company_domain: str, *, window_60d: int, window_60d_prior: int) -> VelocityReport: ...
```

### Velocity metric
Return `(open_roles_now, open_roles_60d_ago, ratio)`. The agent may only assert "aggressive hiring" when `open_roles_now ≥ 5` **and** `ratio ≥ 2.0`. Weaker signal → ask rather than assert (see [05 §4 confidence-aware phrasing](05-signal-enrichment-pipeline.md)).

### AI-adjacent role filter
Titles containing any of: `machine learning`, `ml engineer`, `applied scientist`, `research scientist`, `llm`, `ai engineer`, `data platform`, `data engineer` (with ML/AI context), `AI product manager`. Case-insensitive, word-boundary.

## 5. τ²-Bench

### What it is
Sierra Research's dual-control conversational agent benchmark. Retail domain is our closest analog to B2B qualification; telecom supplies secondary probes.

### Where to get it
`https://github.com/sierra-research/tau2-bench`

### Our usage
- Clone into `eval/tau2-bench/` (submodule or pinned tag).
- Pin retail and telecom domain versions in `config.yaml` → `eval.tau2_bench.pinned_tag`.
- Accept program-delivered **sealed held-out partition** (20 tasks); work only on the 30-task dev slice until final.
- Wrap the harness (`eval/harness.py`) to emit `trace_log.jsonl` to Langfuse and update `score_log.json`.

### Contracts — see [11-tau2-bench-harness.md](11-tau2-bench-harness.md).

## 6. Supporting enrichment endpoints

| Signal | Endpoint/source | Notes |
|--------|-----------------|-------|
| Leadership change | Crunchbase key-people diff + press-release scrape | Title-match list matches segments.yaml §3 |
| Tech stack | BuiltWith public API key; Wappalyzer CLI | Gated behind `bench_check` — only stacks Tenacious bench supports are quotable |
| GitHub org | `https://api.github.com/orgs/<slug>/repos?sort=pushed` (unauthenticated) | Used as low-weight AI-maturity signal; absence is **not** evidence of absence |
| Executive commentary | Google programmable search over `<company> AI site:blog.<domain>` and similar; RSS of known exec-voice sources | Cached results stored in `data/briefs_cache/<uuid>/execs/` |

## 7. Data handling policy (enforced at load time)

- All loaders mark every record with `synthetic: bool` on egress; only synthetic records may flow to `channels.email.send` when kill-switch unset.
- PII present in Crunchbase ODM (founder names) is **not exported** in any outbound content — the draft must refer to role ("the CEO", "the VP Engineering") unless the name is already public in the sales deck's allowlist.
- See [16-data-handling-and-kill-switch.md](16-data-handling-and-kill-switch.md) for the full policy.

## 8. Caching

- Brief cache TTL: 24 h per `crunchbase_uuid`.
- Invalidation: `make enrich PROSPECT=<uuid> --force` bypasses cache.
- All cache writes atomic (`tmp` + rename) to tolerate crashes during enrichment.
