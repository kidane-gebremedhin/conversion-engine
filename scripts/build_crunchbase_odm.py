"""Fetch the public Crunchbase ODM sample CSV and project it into the
local schema consumed by `agent.enrichment.crunchbase`.

Source: https://github.com/luminati-io/Crunchbase-dataset-samples
Output: data/crunchbase_odm_sample.json (path from settings.CRUNCHBASE_ODM_LOCAL_PATH)

Run from repo root:
    python -m scripts.build_crunchbase_odm
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_URL = (
    "https://raw.githubusercontent.com/luminati-io/"
    "Crunchbase-dataset-samples/main/crunchbase-companies-information.csv"
)
OUT_PATH = REPO_ROOT / "data" / "crunchbase_odm_sample.json"

# num_employees → (band label, midpoint)
EMP_BAND = {
    "1-10": ("1_to_15", 5),
    "11-50": ("15_to_80", 30),
    "51-100": ("80_to_200", 75),
    "101-250": ("80_to_200", 175),
    "251-500": ("200_to_500", 375),
    "501-1000": ("500_to_2000", 750),
    "1001-5000": ("500_to_2000", 3000),
    "5001-10000": ("2000_plus", 7500),
    "10001+": ("2000_plus", 15000),
}

# Industry-id (snake-cased) → sub_niche tag the rest of the system recognises.
SUB_NICHE_MAP = {
    "fintech": "payments",
    "payments": "payments",
    "financial-services": "payments",
    "banking": "payments",
    "health-care": "healthcare_platform",
    "medical": "healthcare_platform",
    "biotechnology": "healthcare_platform",
    "wellness": "healthcare_platform",
    "e-commerce": "retail_platform",
    "retail": "retail_platform",
    "marketplace": "retail_platform",
    "shopping": "retail_platform",
    "energy": "energy_software",
    "renewable-energy": "energy_software",
    "clean-energy": "energy_software",
    "oil-and-gas": "energy_software",
    "artificial-intelligence-ai": "agentic_systems",
    "machine-learning": "agentic_systems",
    "generative-ai": "agentic_systems",
    "saas": "workflow_platform",
    "enterprise-software": "workflow_platform",
    "productivity-tools": "workflow_platform",
    "collaboration": "workflow_platform",
    "analytics": "workflow_analytics",
    "business-intelligence": "workflow_analytics",
    "big-data": "workflow_analytics",
    "data-visualization": "workflow_analytics",
}

STAGE_RE = [
    (re.compile(r"\bpre[- ]?seed\b", re.I), "pre_seed"),
    (re.compile(r"\bseed\b", re.I), "seed"),
    (re.compile(r"\bseries[ -]?a\b", re.I), "series_a"),
    (re.compile(r"\bseries[ -]?b\b", re.I), "series_b"),
    (re.compile(r"\bseries[ -]?c\b", re.I), "series_c"),
    (re.compile(r"\bseries[ -]?d\b", re.I), "series_d"),
    (re.compile(r"\bseries[ -]?e\b", re.I), "series_e"),
    (re.compile(r"\b(angel)\b", re.I), "angel"),
    (re.compile(r"\b(grant|equity crowdfunding|crowdfunding)\b", re.I), "grant"),
    (re.compile(r"\b(debt|convertible)\b", re.I), "debt"),
    (re.compile(r"\b(post[- ]?ipo)\b", re.I), "post_ipo"),
    (re.compile(r"\b(private equity|secondary)\b", re.I), "private_equity"),
    (re.compile(r"\bventure round\b", re.I), "venture_round"),
]


def _parse_json_field(raw: str) -> Any:
    if not raw or raw in ("[]", "{}", "null"):
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _normalize_domain(website: str, fallback_id: str) -> str:
    d = (website or "").strip().lower()
    if not d:
        return f"{fallback_id}.example.com"
    for prefix in ("http://", "https://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    if d.startswith("www."):
        d = d[4:]
    return d.split("/")[0].split("?")[0] or f"{fallback_id}.example.com"


def _categories(industries_raw: str) -> tuple[list[str], list[str]]:
    """Return (display_categories, industry_ids)."""
    parsed = _parse_json_field(industries_raw) or []
    cats, ids = [], []
    for item in parsed:
        if isinstance(item, dict):
            v = item.get("value")
            i = item.get("id")
            if v:
                cats.append(v)
            if i:
                ids.append(i)
    return cats, ids


def _sub_niche(industry_ids: list[str]) -> str | None:
    for iid in industry_ids:
        if iid in SUB_NICHE_MAP:
            return SUB_NICHE_MAP[iid]
    return None


def _founded_year(raw: str) -> int | None:
    if not raw:
        return None
    m = re.match(r"(\d{4})", raw)
    return int(m.group(1)) if m else None


def _stage_from_title(title: str) -> str:
    for pat, label in STAGE_RE:
        if pat.search(title or ""):
            return label
    return "unknown"


def _money_usd(money: Any) -> int:
    """Pull a USD integer out of a Crunchbase money sub-object.

    Shape: {"currency": "USD", "value": 2800000, "value_usd": 2800000}.
    Prefer `value_usd` (already converted); fall back to `value` only when
    the row is already in USD.
    """
    if not isinstance(money, dict):
        return 0
    v = money.get("value_usd")
    if v is None and (money.get("currency") or "").upper() == "USD":
        v = money.get("value")
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _funding_rounds(raw: str) -> list[dict[str, Any]]:
    parsed = _parse_json_field(raw) or []
    rounds: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        rid = item.get("id") or ""
        title = item.get("title") or ""
        rounds.append({
            "stage": _stage_from_title(title),
            "amount_usd": _money_usd(item.get("money_raised")),
            "closed_at": item.get("announced_on"),
            "source_url": f"https://www.crunchbase.com/funding_round/{rid}" if rid else "",
        })
    return rounds


# Builtwith entries that are not real tech-stack signal:
#   - geographic / availability indicators (where the server lives)
#   - generic page metadata picked up by the crawler
#   - currency strings detected on payment pages
_TECH_NOISE_NAMES = {
    "Domain Not Resolving",
    "U.S. Server Location", "EU Server Location", "Asian Server Location",
    "Amazon Virginia Region", "Amazon Oregon Region", "Amazon Ireland Region",
    "Amazon Frankfurt Region", "Amazon Singapore Region", "Amazon Tokyo Region",
    "Amazon Sydney Region", "Amazon California Region", "Amazon Mumbai Region",
    "German Server Location", "French Server Location", "Dutch Server Location",
    "British Server Location", "Japanese Server Location", "Indian Server Location",
    "Chinese Server Location", "Italian Server Location", "Spanish Server Location",
    "Canadian Server Location", "Australian Server Location", "Brazilian Server Location",
    "IPv6", "SSL by Default", "HSTS",
    "Person Schema", "Organization Schema", "WebSite Schema",
    "COVID-19",
    "Pound Sterling", "Japanese Yen", "Euro", "Swiss Franc", "Australian Dollar",
    "Canadian Dollar", "Indian Rupee", "Brazilian Real", "Mexican Peso",
    "Global Site Tag",
}
# Whole categories that are pure DNS/email plumbing — drop unconditionally.
_TECH_NOISE_CATEGORIES = {"ns", "mx"}


def _tech_stack(raw: str) -> list[str]:
    """Extract the signal-bearing builtwith entries.

    The Bright Data export bundles real stack tells (Cloudflare, AWS, nginx,
    React, etc.) alongside crawl-side noise (server-location indicators, page
    schema markers, currency strings detected on a checkout page). This filter
    drops the obvious noise so the brief's `tech_stack` section reflects what
    a human reader would call the company's stack.
    """
    parsed = _parse_json_field(raw) or []
    names: list[str] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name or name in _TECH_NOISE_NAMES:
            continue
        cats = set(item.get("technology_category") or [])
        if cats and cats <= _TECH_NOISE_CATEGORIES:
            continue
        names.append(name)
    # de-dup, keep first occurrence
    seen: set[str] = set()
    uniq: list[str] = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        uniq.append(n)
    return uniq


# title substring → canonical leadership role enum (matches `LeadershipRole`).
# Order matters: more specific titles must come before generic ones.
_TITLE_ROLE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bhead of (ai|ml)\b|\bchief ai officer\b|\bvp[, ]+ai\b", re.I), "head_of_ai"),
    (re.compile(r"\bchief data officer\b|\bcdo\b|\bvp[, ]+data\b|\bhead of data\b", re.I), "chief_data_officer"),
    (re.compile(r"\bvp[, ]+engineering\b|\bvice president[, ]+engineering\b|\bsvp[, ]+engineering\b", re.I), "vp_engineering"),
    (re.compile(r"\bcto\b|\bchief technology officer\b", re.I), "cto"),
    (re.compile(r"\bceo\b|\bchief executive officer\b", re.I), "ceo"),
    (re.compile(r"\bcoo\b|\bchief operating officer\b", re.I), "coo"),
    (re.compile(r"\bcfo\b|\bchief financial officer\b", re.I), "cfo"),
    (re.compile(r"\bpresident\b", re.I), "president"),
    (re.compile(r"\bfounder\b|\bco[- ]?founder\b", re.I), "founder"),
]


def _role_from_title(title: str) -> str | None:
    if not title:
        return None
    for pat, role in _TITLE_ROLE_RULES:
        if pat.search(title):
            return role
    return None


def _is_interim(title: str) -> bool:
    return bool(re.search(r"\b(interim|acting)\b", title or "", re.I))


def _leadership(current_employees_raw: str, founders_raw: str) -> list[dict[str, Any]]:
    """Build a leadership roster from `current_employees` and `founders`.

    The Bright Data export does not carry a `started_at` per leader, so the
    `leadership_change` buying-window signal cannot fire from this source —
    but the AI-maturity scorer still uses the role list to detect named
    AI/ML leadership, so populating it adds real signal.
    """
    out: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    employees = _parse_json_field(current_employees_raw) or []
    for emp in employees:
        if not isinstance(emp, dict):
            continue
        name = (emp.get("name") or "").strip()
        title = (emp.get("title") or "").strip()
        role = _role_from_title(title)
        if not name or not role:
            continue
        if name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        out.append({
            "role": role,
            "name": name,
            "title": title,
            "started_at": None,  # not exposed by this export
            "is_interim": _is_interim(title),
        })

    # Founders: roster-level only, so map to role="founder" unless we already
    # captured them with a more specific title via current_employees.
    founders = _parse_json_field(founders_raw) or []
    for f in founders:
        if not isinstance(f, dict):
            continue
        name = (f.get("value") or "").strip()
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        out.append({
            "role": "founder",
            "name": name,
            "title": "Founder",
            "started_at": None,
            "is_interim": False,
        })
    return out


def _leadership_hire_events(raw: str) -> list[dict[str, Any]]:
    """Press-event feed: `leadership_hire` carries dated 'X named CEO' headlines.

    Useful as a fallback for the leadership_change buying-window signal when
    `current_employees` lacks a `started_at`. We surface the event metadata
    so downstream code can decide whether to use it.
    """
    parsed = _parse_json_field(raw) or []
    out: list[dict[str, Any]] = []
    for ev in parsed:
        if not isinstance(ev, dict):
            continue
        date = ev.get("key_event_date")
        label = ev.get("label") or ""
        link = ev.get("link") or ""
        if not date or not label:
            continue
        out.append({"date": date, "label": label, "source_url": link})
    return out


def _rank_score(cb_rank_raw: str) -> float:
    """Map cb_rank (lower is better, integer) → [0.0, 1.0] (higher is better).

    Uses a log scale so the long tail of huge ranks doesn't crush the spread.
    """
    try:
        rank = int(cb_rank_raw)
    except (TypeError, ValueError):
        return 0.0
    if rank <= 0:
        return 1.0
    # Normalise against ~3.2M companies in the full ODM (per dataset README).
    score = 1.0 - math.log10(rank) / math.log10(3_200_000)
    return round(max(0.0, min(1.0, score)), 2)


def transform_row(row: dict[str, str]) -> dict[str, Any]:
    industries_display, industry_ids = _categories(row.get("industries", ""))
    band, point = EMP_BAND.get(row.get("num_employees", ""), (None, None))
    return {
        "name": row.get("name", "").strip(),
        "domain": _normalize_domain(row.get("website", ""), row.get("id", "unknown")),
        "categories": industries_display,
        "sub_niche": _sub_niche(industry_ids),
        "headcount_band": band,
        "headcount_point": point,
        "hq_country": row.get("country_code", "").strip() or None,
        "founded_year": _founded_year(row.get("founded_date", "")),
        "funding_rounds": _funding_rounds(row.get("funding_rounds_list", "")),
        "leadership": _leadership(
            row.get("current_employees", ""),
            row.get("founders", ""),
        ),
        "leadership_hire_events": _leadership_hire_events(row.get("leadership_hire", "")),
        "tech_stack_detected": _tech_stack(row.get("builtwith_tech", "")),
        "corporate_investors_only": False,
        "anti_offshore_public_stance": False,
        "listed_as_competitor_client": False,
        "rank_score": _rank_score(row.get("cb_rank", "")),
    }


def main() -> int:
    print(f"Fetching {CSV_URL} ...", file=sys.stderr)
    with urllib.request.urlopen(CSV_URL) as resp:  # noqa: S310 (trusted public dataset)
        raw_bytes = resp.read()
    text = raw_bytes.decode("utf-8")

    reader = csv.DictReader(text.splitlines())
    records = [transform_row(r) for r in reader if r.get("name")]
    # Drop duplicates by domain, keeping the highest rank_score.
    by_domain: dict[str, dict[str, Any]] = {}
    for rec in records:
        d = rec["domain"]
        if d not in by_domain or rec["rank_score"] > by_domain[d]["rank_score"]:
            by_domain[d] = rec
    out = sorted(by_domain.values(), key=lambda r: r["rank_score"], reverse=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(out)} records → {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
