"""Derive `data/synthetic_prospects.json` from the Crunchbase ODM sample.

Synthetic prospects power two things:
  1. Kill-switch allowlist (`agent.kill_switch`) — only these emails / phones
     are permitted as live recipients outside the staff sink.
  2. `make compose-and-send DOMAIN=<x>` lookup (`scripts.compose_and_send`).

Outputs are fully deterministic in the Crunchbase rows so re-runs produce
the same file. Names, emails, and phones are obviously synthetic and
namespaced so they cannot collide with real contacts.

Run from repo root:
    python -m scripts.build_synthetic_prospects
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from agent.config import REPO_ROOT, settings

CB_PATH = REPO_ROOT / settings.CRUNCHBASE_ODM_LOCAL_PATH
OUT_PATH = REPO_ROOT / "data" / "synthetic_prospects.json"

# Synthetic name pool — deliberately fictional, rotated by deterministic hash
# of the company domain so each prospect is stable across rebuilds.
FIRST_NAMES = [
    "Avery", "Blair", "Cameron", "Drew", "Emerson", "Finley", "Hayden",
    "Jordan", "Kai", "Logan", "Morgan", "Parker", "Quinn", "Reese",
    "Sage", "Skyler", "Taylor", "Wren",
]
LAST_NAMES = [
    "Aoki", "Bauer", "Costa", "Dvorak", "Engel", "Faraday", "Garza",
    "Holm", "Ibarra", "Jain", "Klein", "Larkin", "Mensah", "Novak",
    "Okafor", "Patel", "Quinn", "Rao", "Singh", "Tomar", "Ueno",
    "Vega", "Wahl",
]
TITLES_HIGH_AI = ["VP Engineering", "CTO", "Head of AI", "Chief Data Officer"]
TITLES_MID_AI = ["VP Engineering", "Director of Engineering", "Head of Platform"]
TITLES_LOW_AI = ["VP Engineering", "Director of Engineering", "Head of Operations"]

# country_code → IANA timezone (best-effort; used purely for prospect metadata)
TZ_BY_COUNTRY = {
    "US": "America/Los_Angeles",
    "CA": "America/Toronto",
    "GB": "Europe/London",
    "IE": "Europe/Dublin",
    "DE": "Europe/Berlin",
    "FR": "Europe/Paris",
    "NL": "Europe/Amsterdam",
    "ES": "Europe/Madrid",
    "IT": "Europe/Rome",
    "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo",
    "DK": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "PL": "Europe/Warsaw",
    "CH": "Europe/Zurich",
    "AT": "Europe/Vienna",
    "BE": "Europe/Brussels",
    "PT": "Europe/Lisbon",
    "AU": "Australia/Sydney",
    "NZ": "Pacific/Auckland",
    "JP": "Asia/Tokyo",
    "CN": "Asia/Shanghai",
    "HK": "Asia/Hong_Kong",
    "SG": "Asia/Singapore",
    "IN": "Asia/Kolkata",
    "AE": "Asia/Dubai",
    "IL": "Asia/Jerusalem",
    "BR": "America/Sao_Paulo",
    "MX": "America/Mexico_City",
    "AR": "America/Argentina/Buenos_Aires",
    "ZA": "Africa/Johannesburg",
    "KE": "Africa/Nairobi",
    "NG": "Africa/Lagos",
    "EG": "Africa/Cairo",
}

# country_code → E.164 country prefix
PHONE_PREFIX = {
    "US": "+1", "CA": "+1", "GB": "+44", "IE": "+353", "DE": "+49",
    "FR": "+33", "NL": "+31", "ES": "+34", "IT": "+39", "SE": "+46",
    "NO": "+47", "DK": "+45", "FI": "+358", "PL": "+48", "CH": "+41",
    "AT": "+43", "BE": "+32", "PT": "+351", "AU": "+61", "NZ": "+64",
    "JP": "+81", "CN": "+86", "HK": "+852", "SG": "+65", "IN": "+91",
    "AE": "+971", "IL": "+972", "BR": "+55", "MX": "+52", "AR": "+54",
    "ZA": "+27", "KE": "+254", "NG": "+234", "EG": "+20",
}

# Modern-stack tokens used to estimate AI maturity from tech_stack_detected.
# Mirrors logic in agent/enrichment/ai_maturity.py at a coarser level so the
# synthetic ground-truth label tracks what the pipeline would compute.
AI_TOKENS = {
    "openai", "anthropic", "huggingface", "hugging face", "langchain",
    "vectordb", "pinecone", "weaviate", "milvus", "qdrant", "snowflake",
    "databricks", "mlflow", "kubeflow", "vertex ai", "sagemaker",
    "tensorflow", "pytorch", "ray", "airflow", "dagster", "dbt",
    "kafka", "spark", "redshift", "bigquery",
}


def _seed(domain: str) -> int:
    return int(hashlib.sha256(domain.encode("utf-8")).hexdigest(), 16)


def _pick(lst: list[str], seed: int, salt: int) -> str:
    return lst[(seed >> salt) % len(lst)]


def _email_local(first: str, last: str) -> str:
    return f"{first.lower()}.{last.lower()}"


def _phone(domain: str, country_code: str | None) -> str:
    seed = _seed(domain)
    prefix = PHONE_PREFIX.get((country_code or "US").upper(), "+1")
    digits = str(seed)[-10:].rjust(10, "0")
    return f"{prefix}{digits}"


def _ai_maturity_score(tech_stack: list[str]) -> int:
    """Coarse 0–3 score from tech-stack tokens. Mirrors the enrichment heuristic."""
    if not tech_stack:
        return 0
    tokens_lower = {t.lower() for t in tech_stack}
    hits = sum(1 for t in AI_TOKENS if any(t in tok for tok in tokens_lower))
    if hits >= 4:
        return 3
    if hits >= 2:
        return 2
    if hits >= 1:
        return 1
    return 0


def _segment(record: dict[str, Any], ai_score: int) -> str:
    """Best-effort segment label. The real classifier will override; this is
    just an "expected" hint for eval scoring."""
    band = record.get("headcount_band") or ""
    sub = record.get("sub_niche")
    if sub == "agentic_systems" or ai_score == 3:
        return "segment_4_specialized_capability"
    if band in ("500_to_2000", "200_to_500", "2000_plus"):
        return "segment_2_scaling_systems"
    if band in ("80_to_200",):
        return "segment_3_workflow_automation"
    if band in ("1_to_15", "15_to_80"):
        return "segment_1_growth_stage"
    return "abstain"


def _title(ai_score: int, seed: int) -> str:
    pool = TITLES_HIGH_AI if ai_score >= 2 else TITLES_MID_AI if ai_score == 1 else TITLES_LOW_AI
    return _pick(pool, seed, 24)


def transform(record: dict[str, Any]) -> dict[str, Any] | None:
    domain = record.get("domain") or ""
    name = record.get("name") or ""
    if not domain or not name:
        return None
    seed = _seed(domain)
    first = _pick(FIRST_NAMES, seed, 0)
    last = _pick(LAST_NAMES, seed, 8)
    ai_score = _ai_maturity_score(record.get("tech_stack_detected", []) or [])
    cc = (record.get("hq_country") or "US").upper()
    return {
        "prospect_email": f"{_email_local(first, last)}@{domain}",
        "prospect_name": f"{first} {last}",
        "prospect_title": _title(ai_score, seed),
        "prospect_company": name,
        "company_domain": domain,
        "prospect_phone": _phone(domain, cc),
        "prospect_timezone": TZ_BY_COUNTRY.get(cc, "UTC"),
        "expected_segment": _segment(record, ai_score),
        "expected_ai_maturity_score": ai_score,
        "notes": f"HC ~{record.get('headcount_point') or 'unknown'}; synthetic prospect built from Crunchbase ODM",
    }


def main() -> int:
    if not CB_PATH.exists():
        sys.stderr.write(f"ERROR: {CB_PATH} not found. Run scripts/build_crunchbase_odm.py first.\n")
        return 2
    with open(CB_PATH, encoding="utf-8") as f:
        records = json.load(f)
    prospects: list[dict[str, Any]] = []
    seen_emails: set[str] = set()
    for r in records:
        p = transform(r)
        if p is None:
            continue
        if p["prospect_email"] in seen_emails:
            continue
        seen_emails.add(p["prospect_email"])
        prospects.append(p)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(prospects, f, indent=2, ensure_ascii=False)
    sys.stderr.write(f"Wrote {len(prospects)} synthetic prospects → {OUT_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
