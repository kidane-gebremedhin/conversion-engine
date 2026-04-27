"""Synthesise `data/job_posts_snapshot_<date>.json` from the Crunchbase ODM sample.

Live job-post scraping is gated by the policy crawler (≤200 companies/week,
robots-respecting). For local dev and eval we derive a deterministic snapshot
from each Crunchbase record's firmographics + sub-niche + tech stack +
leadership roster, so every CB-allowlisted domain has *some* job-post signal.

Outputs are deterministic in the CB rows: same input → same JSON. Re-running
this script never produces churn unless the underlying CB data changes.

Run from repo root:
    python -m scripts.build_jobposts_snapshot
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from agent.config import REPO_ROOT, settings

CB_PATH = REPO_ROOT / settings.CRUNCHBASE_ODM_LOCAL_PATH
OUT_PATH = REPO_ROOT / settings.JOB_POSTS_SNAPSHOT_PATH
SNAPSHOT_DATE = "2026-04-01"
COMPARISON_60D_PRIOR = "2026-02-01"

# Headcount band → (min_roles_today, max_roles_today)
ROLES_BY_BAND = {
    "1_to_15":     (2, 5),
    "15_to_80":    (5, 15),
    "80_to_200":   (10, 25),
    "200_to_500":  (15, 30),
    "500_to_2000": (20, 40),
    "2000_plus":   (25, 50),
}

# Sub-niche / category → AI-adjacency ratio used when synthesising role mix.
AI_RATIO_BY_SUBNICHE = {
    "agentic_systems":      0.55,
    "workflow_analytics":   0.30,
    "workflow_platform":    0.25,
    "healthcare_platform":  0.20,
    "payments":             0.20,
    "energy_software":      0.15,
    "retail_platform":      0.15,
}
# CB industry display strings that signal AI focus
AI_CATEGORY_TOKENS = {
    "artificial intelligence", "machine learning", "generative ai",
    "deep learning", "natural language", "computer vision", "ai",
}

AI_TITLES = [
    "ML Engineer", "Senior ML Engineer", "Machine Learning Engineer",
    "AI Platform Engineer", "LLM Engineer", "Data Engineer",
    "Senior Data Engineer", "Data Platform Engineer", "MLOps Engineer",
    "Applied Scientist", "Research Engineer", "AI Product Engineer",
]
NON_AI_TITLES = [
    "Backend Engineer", "Senior Backend Engineer", "Frontend Engineer",
    "Senior Frontend Engineer", "Full-Stack Engineer", "DevOps Engineer",
    "SRE", "Platform Engineer", "Engineering Manager", "Product Engineer",
    "Mobile Engineer", "iOS Engineer", "Android Engineer",
    "Senior Go Engineer", "Rust Engineer", "Python Developer",
]
SOURCES = ["wellfound", "linkedin_public", "builtin"]

# Modern stack tokens we surface into builtwith[] when seen in tech_stack_detected.
MODERN_STACK_TOKENS = {
    "snowflake", "databricks", "dbt", "ray", "airflow", "dagster",
    "kafka", "spark", "redshift", "bigquery", "kubernetes", "terraform",
    "react", "next.js", "nextjs", "typescript", "go", "rust",
    "postgresql", "postgres", "mongodb", "redis", "elasticsearch",
    "tensorflow", "pytorch", "huggingface", "openai", "anthropic",
    "langchain", "pinecone", "weaviate", "qdrant", "milvus", "vllm",
    "weights and biases", "mlflow", "kubeflow",
}


def _seed(domain: str) -> int:
    return int(hashlib.sha256(domain.encode("utf-8")).hexdigest(), 16)


def _u01(seed: int, salt: int) -> float:
    """Deterministic uniform [0, 1) from seed and salt."""
    return ((seed >> salt) & 0xFFFFFFFF) / 0x100000000


def _int_in(seed: int, salt: int, lo: int, hi: int) -> int:
    if hi <= lo:
        return lo
    return lo + int(_u01(seed, salt) * (hi - lo + 1))


def _ai_ratio(record: dict[str, Any]) -> float:
    sub = record.get("sub_niche")
    if sub and sub in AI_RATIO_BY_SUBNICHE:
        return AI_RATIO_BY_SUBNICHE[sub]
    cats = " ".join(record.get("categories") or []).lower()
    if any(t in cats for t in AI_CATEGORY_TOKENS):
        return 0.35
    return 0.07  # baseline non-AI company


def _posted_at(seed: int, salt: int, snapshot: dt.date) -> str:
    """Deterministic date in the 90 days before the snapshot."""
    days_ago = _int_in(seed, salt, 1, 90)
    return (snapshot - dt.timedelta(days=days_ago)).isoformat()


def _open_roles(record: dict[str, Any], snapshot: dt.date) -> list[dict[str, Any]]:
    band = record.get("headcount_band")
    if not band or band not in ROLES_BY_BAND:
        # Companies without a headcount band still get a small roster
        # so the velocity signal is not a flat zero everywhere.
        lo, hi = (1, 4)
    else:
        lo, hi = ROLES_BY_BAND[band]
    seed = _seed(record["domain"])
    total = _int_in(seed, 0, lo, hi)
    ratio = _ai_ratio(record)
    n_ai = int(round(total * ratio))
    n_other = total - n_ai

    roles: list[dict[str, Any]] = []
    for i in range(n_ai):
        roles.append({
            "title": AI_TITLES[(seed >> (8 + i)) % len(AI_TITLES)],
            "posted_at": _posted_at(seed, 16 + i * 4, snapshot),
            "ai_adjacent": True,
            "source": SOURCES[(seed >> (4 + i)) % len(SOURCES)],
        })
    for i in range(n_other):
        roles.append({
            "title": NON_AI_TITLES[(seed >> (32 + i)) % len(NON_AI_TITLES)],
            "posted_at": _posted_at(seed, 64 + i * 4, snapshot),
            "ai_adjacent": False,
            "source": SOURCES[(seed >> (12 + i)) % len(SOURCES)],
        })
    return roles


def _open_60d_ago(seed: int, today_count: int) -> int:
    """A multiplier in [0.6, 1.4] of today's count, so the velocity ratio is
    close to flat with company-specific drift."""
    factor = 0.6 + _u01(seed, 96) * 0.8
    return max(0, int(round(today_count * factor)))


def _builtwith_modern(tech_stack: list[str]) -> list[str]:
    out = []
    seen: set[str] = set()
    for t in tech_stack or []:
        tl = t.lower()
        for tok in MODERN_STACK_TOKENS:
            if tok in tl and tok not in seen:
                out.append(tok)
                seen.add(tok)
    return out


def _ai_ml_leadership_named(record: dict[str, Any]) -> bool:
    for leader in record.get("leadership", []) or []:
        if leader.get("role") in ("head_of_ai", "chief_data_officer"):
            return True
    return False


def _exec_commentary(record: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    """Surface an exec-commentary entry when the company is in an AI-leaning niche."""
    sub = record.get("sub_niche")
    cats = " ".join(record.get("categories") or []).lower()
    is_ai = sub == "agentic_systems" or any(t in cats for t in AI_CATEGORY_TOKENS)
    if not is_ai:
        return []
    # ~50% of AI-leaning companies surface exec commentary in the synthesised view.
    if _u01(seed, 100) < 0.5:
        return []
    title = "Agentic Systems as Strategy" if sub == "agentic_systems" else "Our AI Roadmap"
    days_ago = _int_in(seed, 104, 14, 365)
    date = (dt.date.fromisoformat(SNAPSHOT_DATE) - dt.timedelta(days=days_ago)).isoformat()
    return [{
        "title": title,
        "url": f"https://{record['domain']}/blog/ai-strategy",
        "date": date,
    }]


def _github_public_org(record: dict[str, Any], seed: int, ai_ratio: float) -> dict[str, Any]:
    domain = record["domain"]
    handle = domain.split(".")[0]
    total = _int_in(seed, 108, 0, 25)
    if total == 0:
        return {}
    ai_repos_recent = max(0, int(round(total * ai_ratio * 0.4)))
    return {
        "url": f"https://github.com/{handle}",
        "ai_repos_recent": ai_repos_recent,
        "total_repos": total,
    }


def transform(record: dict[str, Any]) -> dict[str, Any] | None:
    domain = record.get("domain")
    if not domain:
        return None
    snapshot = dt.date.fromisoformat(SNAPSHOT_DATE)
    seed = _seed(domain)
    roles_today = _open_roles(record, snapshot)
    return {
        "open_roles_today": roles_today,
        "open_roles_60d_ago_count": _open_60d_ago(seed, len(roles_today)),
        "ai_ml_leadership_named": _ai_ml_leadership_named(record),
        "exec_commentary_last_12m": _exec_commentary(record, seed),
        "github_public_org": _github_public_org(record, seed, _ai_ratio(record)),
        "builtwith": _builtwith_modern(record.get("tech_stack_detected", [])),
    }


def main() -> int:
    if not CB_PATH.exists():
        sys.stderr.write(f"ERROR: {CB_PATH} not found. Run scripts/build_crunchbase_odm.py first.\n")
        return 2
    with open(CB_PATH, encoding="utf-8") as f:
        records = json.load(f)
    companies: dict[str, dict[str, Any]] = {}
    for r in records:
        entry = transform(r)
        if entry is None:
            continue
        companies[r["domain"]] = entry
    out = {
        "snapshot_date": SNAPSHOT_DATE,
        "comparison_window_60d_prior_date": COMPARISON_60D_PRIOR,
        "notes": (
            "Deterministic synthesis from the Crunchbase ODM sample. "
            "Role counts and AI-adjacency ratios derived from headcount band, "
            "sub-niche, and categories. Re-run with build_jobposts_snapshot.py."
        ),
        "companies": companies,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    sys.stderr.write(f"Wrote {len(companies)} jobposts entries → {OUT_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
