# 04 — Data Sources

Four data sources ground the enrichment pipeline and τ²-Bench harness. **No source requires a credit card; no source requires a US phone number; no source requires login.** Every source URL, API key, and freshness window is in `.env` or `config.yaml` — nothing is hard-coded.

## Data source 1 — Crunchbase ODM sample

| Field | Value |
|---|---|
| **Provider** | luminati-io (Apache-2.0 license) |
| **URL (configurable)** | `CRUNCHBASE_ODM_URL` in `.env` — default: `github.com/luminati-io/Crunchbase-dataset-samples` |
| **Records** | 1,001 real Crunchbase company records |
| **Fields** | Firmographics (name, domain, HC band, HQ), funding rounds, founders, industry categories, locations |
| **Use** | Primary firmographic source. **Every HubSpot lead object must reference a Crunchbase record.** |
| **Freshness** | Frozen snapshot downloaded on Day 0 and stored in `data/crunchbase_odm_sample.json`. No live lookups. |

Implementation (`agent/enrichment/crunchbase.py`):

- Loads the JSON once on process start; exposes a `lookup_by_domain(domain)` function backed by an in-memory dict.
- Normalizes domain casing (lowercase, strip `www.`).
- If the domain is not in the sample, the enrichment pipeline returns a `no_data` status and the prospect is logged to `data/unmatched_domains.log`; no outreach fires.

## Data source 2 — layoffs.fyi

| Field | Value |
|---|---|
| **Provider** | layoffs.fyi (CC-BY license) |
| **URL (configurable)** | `LAYOFFS_FYI_URL` — layoffs.fyi downloadable CSV or HuggingFace mirror |
| **Records** | Structured dataset of tech-industry layoffs, updated weekly |
| **Fields** | `company`, `date`, `headcount_reduction`, `percentage_cut`, `source_url` |
| **Use** | Layoff signal for Segment 2 classification; disqualifier for Segment 1 (>15% cut in 90d) |
| **Freshness** | Downloaded weekly. Frozen snapshot as `data/layoffs_fyi_2026_q1.csv`. |

Implementation (`agent/enrichment/layoffs.py`):

- CSV is parsed on first lookup per-process, indexed by normalized company name. The `company` column is matched using: exact → lowercase → token-set-ratio ≥ 0.9 with domain cross-check.
- `within_window(layoff_date, window_days)` returns events within a rolling window (default `120` for Segment 2, `90` for Segment 1 disqualifier — both in `config.yaml`).

## Data source 3 — Public job posts

| Field | Value |
|---|---|
| **Provider** | BuiltIn, Wellfound, LinkedIn company pages |
| **Scraping tool** | Playwright + FastAPI wrapper (`TinyFish` alternative acceptable) |
| **URLs (configurable)** | `BUILTIN_BASE_URL`, `WELLFOUND_BASE_URL`, `LINKEDIN_JOBS_BASE_URL` |
| **Use** | Hiring velocity signal (open-roles today vs. 60 days ago). AI-adjacent role count for AI-maturity scoring. |
| **Freshness** | Frozen April 2026 snapshot in `data/job_posts_snapshot_2026-04-01.json`; an optional small live crawl of **no more than 200 companies** during the challenge week. |

Scraping rules (policy-enforced — see [spec 16](16-data-handling-and-kill-switch.md)):

- Public pages only. No login. No stored cookies or session tokens for gated content.
- Captchas are a hard stop. If a captcha appears, mark `data_sources_checked[source].status = "rate_limited"` and move on.
- `robots.txt` is checked on first contact per domain and cached for 24 hours.
- Rate limit: **at least 2 seconds between requests to the same domain; at most 3 concurrent tabs per domain**.
- User agent: `TRP1-Week10-Research (trainee@trp1.example)` — configurable via `SCRAPER_USER_AGENT`, never impersonates a browser or a named crawler.
- Live-crawl cap: 200 companies per challenge week, tracked in `data/crawl_counter.json`.

Velocity computation (`agent/enrichment/jobposts.py`):

- `open_roles_today = count(role.status == "open" as of latest snapshot or live fetch)`.
- `open_roles_60_days_ago = count(role.status == "open" in the 60-day-prior snapshot)`.
- `velocity_label ∈ {tripled_or_more, doubled, increased_modestly, flat, declined, insufficient_signal}`. Thresholds in `config.yaml`. `insufficient_signal` fires when `open_roles_today < 5` and forces "ask rather than assert" phrasing.
- `ai_adjacent_ratio = ai_adjacent_role_count / total_role_count`. AI-adjacent roles: ML Engineer, Applied Scientist, LLM Engineer, AI Product Manager, Data Platform Engineer, MLOps Engineer. The canonical list is in `config.yaml` under `ai_maturity.ai_adjacent_titles`.

## Data source 4 — τ²-Bench

| Field | Value |
|---|---|
| **Provider** | Sierra Research |
| **URL (configurable)** | `TAU2_BENCH_REPO_URL` — default: `github.com/sierra-research/tau2-bench` |
| **Content** | Dual-control conversational benchmark; B2B-conversational-agent reference |
| **Partitions** | 30-task dev slice (ships with benchmark); 20-task sealed held-out (delivered by program staff) |
| **Use** | Ground-truth reproduction (Act I), reproduction check (Act II), mechanism evaluation (Act IV) |
| **Freshness** | Pinned git SHA in `config.yaml` under `tau2.pinned_sha` for reproducibility. |

Retail is the closest public analog to B2B qualification conversation and is the primary evaluation domain. Telecom domain supplies useful secondary probes (time-zone edge cases, escalation phrasing).

## Secondary data sources (AI-maturity scoring)

Five weaker sources feed AI-maturity scoring only. These do not gate the enrichment pipeline; if any fail, `data_sources_checked` records the error and the affected `ai_maturity.justifications` entries carry `confidence: low`.

| Source | Purpose | Weight in AI-maturity |
|---|---|---|
| BuiltWith / Wappalyzer public data | Modern data/ML stack signal | low |
| Public GitHub org | Recent commits to model-training or inference repos | medium |
| Company blog / press | Executive commentary on AI strategy | medium |
| Team page | Named AI/ML leadership | high |
| Investor letters / fundraising press | Strategic AI positioning | low |

Configuration lives under `ai_maturity.weights` in `config.yaml`. See [spec 05](05-signal-enrichment-pipeline.md) for the scoring rubric.

## Data licensing and redistribution

Every source is either CC-BY, Apache-2.0, or public-page-with-robots-compliance. The implementation may:

- Read, cache, and derive signals from these sources inside the repo for the duration of the challenge.
- Quote source URLs in the `evidence_graph.json` and in the outreach emails (for public URLs only).

The implementation may **not**:

- Commit raw layoffs.fyi or Crunchbase dumps outside `data/` with a clear CC-BY or Apache-2.0 attribution.
- Post scraped job-post data to any public location.
- Include named prospect contacts (even synthetic) in any committed file outside `data/synthetic_prospects.json`.

## Freshness windows

| Source | Refresh policy |
|---|---|
| Crunchbase ODM | Never during the challenge week; the snapshot is frozen. |
| layoffs.fyi | Weekly refresh from CSV; re-downloaded each Monday morning. |
| Public job posts | Frozen snapshot primary; live crawl of ≤200 companies across the full week if needed. |
| τ²-Bench | Pinned git SHA; never updated mid-week. |
| HubSpot / Cal.com / Langfuse | Live (these are our own systems, not external data). |
