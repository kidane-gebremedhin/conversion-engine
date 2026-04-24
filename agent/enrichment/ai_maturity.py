"""AI-maturity scoring (0–3) with per-input justifications.

Six weighted inputs per the challenge brief. Every justification carries
signal, status (free-text), weight, confidence, and optional source_url.
Absence of evidence is explicitly acceptable — the policy requires honesty,
not false positives.
"""
from __future__ import annotations

from typing import Any

from agent.config import config
from agent.enrichment import jobposts


# Numeric mapping for weight names
_WEIGHT_TO_NUM = {"high": 3, "medium": 2, "low": 1}


def _score_ai_adjacent_open_roles(record: dict[str, Any]) -> tuple[int, str, str]:
    """Returns (strength 0..3, status description, confidence)."""
    domain = record["domain"]
    entry = jobposts.company_jobposts(domain)
    if not entry:
        return 0, "No job-post data available for this company.", "low"
    roles = entry.get("open_roles_today", [])
    total = len(roles)
    adjacent = sum(1 for r in roles if r.get("ai_adjacent"))
    if total == 0:
        return 0, "No open engineering roles found.", "medium"
    ratio = adjacent / total
    if ratio >= 0.25:
        return 3, f"{adjacent} of {total} open engineering roles ({ratio:.0%}) are AI-adjacent.", "high"
    if ratio >= 0.1:
        return 2, f"{adjacent} of {total} open engineering roles ({ratio:.0%}) are AI-adjacent.", "high"
    if adjacent >= 1:
        return 1, f"{adjacent} of {total} open roles is AI-adjacent.", "medium"
    return 0, "No AI-adjacent roles among current openings.", "high"


def _score_named_ai_ml_leadership(record: dict[str, Any]) -> tuple[int, str, str]:
    entry = jobposts.company_jobposts(record["domain"])
    leaders = (entry or {}).get("ai_ml_leaders", []) if entry else []
    # Also check Crunchbase leadership entries for ML-titles
    crunchbase_titles = [
        (leader.get("role") or "") for leader in (record.get("leadership") or [])
    ]
    has_ai_leader_crunchbase = any(
        title in ("head_of_ai", "chief_data_officer") for title in crunchbase_titles
    )
    if leaders or has_ai_leader_crunchbase:
        if leaders:
            names = ", ".join(l.get("name", "?") + " (" + l.get("title", "?") + ")" for l in leaders)
            return 3, f"Public AI/ML leadership named: {names}.", "high"
        return 2, "AI/ML leadership named in Crunchbase (not corroborated on team page).", "medium"
    return 0, "No public Head of AI, VP Data, or Chief Scientist on team page or Crunchbase.", "high"


def _score_github_org_activity(record: dict[str, Any]) -> tuple[int, str, str]:
    entry = jobposts.company_jobposts(record["domain"])
    gh = (entry or {}).get("github_public_org", {}) if entry else {}
    ai_repos = int(gh.get("ai_repos_recent", 0))
    total = int(gh.get("total_repos", 0))
    if ai_repos >= 3:
        return 3, f"Public GitHub org has {ai_repos} recent AI/ML repos out of {total}.", "high"
    if ai_repos >= 1:
        return 2, f"Public GitHub org has {ai_repos} recent AI/ML repo(s).", "medium"
    if total > 0:
        return 0, f"Public GitHub org has {total} repos, none AI-related (absence is not proof).", "medium"
    return 0, "No public GitHub org activity found.", "low"


def _score_executive_commentary(record: dict[str, Any]) -> tuple[int, str, str]:
    entry = jobposts.company_jobposts(record["domain"])
    commentary = (entry or {}).get("exec_commentary_last_12m", []) if entry else []
    if not commentary:
        return 0, "No executive commentary on AI strategy in the last 12 months.", "medium"
    if len(commentary) >= 2:
        return 3, f"{len(commentary)} exec posts naming AI as strategic in last 12m.", "high"
    return 2, f"One exec post on AI strategy ({commentary[0].get('title')}).", "medium"


def _score_modern_data_ml_stack(record: dict[str, Any]) -> tuple[int, str, str]:
    entry = jobposts.company_jobposts(record["domain"])
    bw = (entry or {}).get("builtwith", []) if entry else []
    mod_tools = {"databricks", "weights and biases", "vllm", "ray"}
    present = [t for t in bw if t.lower() in mod_tools]
    baseline = {"dbt", "snowflake"}
    baseline_present = [t for t in bw if t.lower() in baseline]
    if len(present) >= 2:
        return 3, f"Modern ML-platform stack detected: {', '.join(present)}.", "high"
    if present:
        return 2, f"Some modern ML tooling detected: {', '.join(present)}.", "medium"
    if baseline_present:
        return 1, f"Modern-data stack detected: {', '.join(baseline_present)}. No ML-platform tools.", "high"
    return 0, "No modern data/ML stack signal from BuiltWith/Wappalyzer.", "medium"


def _score_strategic_communications(record: dict[str, Any]) -> tuple[int, str, str]:
    # Without investor letters in seed data, use category signal as a weak proxy
    cats = [c.lower() for c in (record.get("categories") or [])]
    if "ai" in cats:
        return 2, "Company categorized as AI in Crunchbase categories.", "medium"
    return 0, "No strategic-communications signal found.", "low"


_SCORERS = [
    ("ai_adjacent_open_roles", _score_ai_adjacent_open_roles),
    ("named_ai_ml_leadership", _score_named_ai_ml_leadership),
    ("github_org_activity", _score_github_org_activity),
    ("executive_commentary", _score_executive_commentary),
    ("modern_data_ml_stack", _score_modern_data_ml_stack),
    ("strategic_communications", _score_strategic_communications),
]


def score(record: dict[str, Any]) -> dict[str, Any]:
    """Return {score:int, confidence:float, justifications:list} for a prospect."""
    weights_cfg = config.get("ai_maturity.weights", {})
    justifications: list[dict[str, Any]] = []
    weighted_sum = 0.0
    max_sum = 0.0
    high_conf_high_weight_inputs = 0

    for signal_name, scorer in _SCORERS:
        strength, status, conf = scorer(record)
        weight_name = weights_cfg.get(signal_name, "low")
        weight_num = _WEIGHT_TO_NUM.get(weight_name, 1)

        weighted_sum += strength * weight_num
        max_sum += 3 * weight_num
        if weight_name == "high" and conf == "high" and strength >= 2:
            high_conf_high_weight_inputs += 1

        justifications.append({
            "signal": signal_name,
            "status": status,
            "weight": weight_name,
            "confidence": conf,
            "source_url": _justification_source_url(record, signal_name),
        })

    normalized = (weighted_sum / max_sum) * 3 if max_sum else 0.0
    rounded = max(0, min(3, round(normalized)))

    # confidence: grows with # high-weight high-conf inputs with strong strength
    if high_conf_high_weight_inputs >= 2:
        confidence = 0.85
    elif high_conf_high_weight_inputs == 1:
        confidence = 0.65
    else:
        confidence = 0.45

    return {
        "score": int(rounded),
        "confidence": float(round(confidence, 2)),
        "justifications": justifications,
    }


def _justification_source_url(record: dict[str, Any], signal: str) -> str | None:
    entry = jobposts.company_jobposts(record["domain"])
    if not entry:
        return None
    if signal == "ai_adjacent_open_roles":
        # point at any builtin-sourced role
        for role in entry.get("open_roles_today", []):
            if role.get("source") == "builtin":
                return f"https://builtin.com/company/{_slug(record.get('name',''))}/jobs"
    if signal == "named_ai_ml_leadership":
        leaders = entry.get("ai_ml_leaders", [])
        if leaders:
            return leaders[0].get("url")
    if signal == "github_org_activity":
        return (entry.get("github_public_org") or {}).get("url")
    if signal == "executive_commentary":
        posts = entry.get("exec_commentary_last_12m", [])
        if posts:
            return posts[0].get("url")
    return None


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
