"""Tech-stack inference.

Union of BuiltWith/Wappalyzer detections (frozen in Crunchbase record +
job-post snapshot) and tech mentions in open job posts. Normalized to the
canonical stack taxonomy in config.yaml > bench.stacks.
"""
from __future__ import annotations

from typing import Any

from agent.config import config
from agent.enrichment import jobposts


# Mapping from detected tech → canonical bench stack name
_STACK_MAP: dict[str, str] = {
    # python family
    "python": "python",
    "django": "python",
    "flask": "python",
    "fastapi": "python",
    "sqlalchemy": "python",
    # go
    "go": "go",
    "golang": "go",
    "kafka": "go",  # common Go use-case in the bench
    # data
    "dbt": "data",
    "snowflake": "data",
    "databricks": "data",
    "fivetran": "data",
    "airflow": "data",
    "timescaledb": "data",
    "powerbi": "data",
    "quicksight": "data",
    # ml
    "pytorch": "ml",
    "weights and biases": "ml",
    "langchain": "ml",
    "langgraph": "ml",
    "vllm": "ml",
    # infra
    "terraform": "infra",
    "aws": "infra",
    "gcp": "infra",
    "kubernetes": "infra",
    "docker": "infra",
    # frontend
    "react": "frontend",
    "next.js": "frontend",
    "typescript": "frontend",
    # fullstack_nestjs
    "nestjs": "fullstack_nestjs",
    "node.js": "fullstack_nestjs",
    "prisma": "fullstack_nestjs",
    "typeorm": "fullstack_nestjs",
}


def infer_stacks(record: dict[str, Any]) -> tuple[list[str], list[str], bool]:
    """Return (detected_tokens, inferred_bench_stacks, inferred_not_confirmed).

    - detected_tokens: the raw string tokens (unnormalized) for display.
    - inferred_bench_stacks: canonical bench-stack names (from config taxonomy).
    - inferred_not_confirmed: True when signal comes ONLY from job-post title mentions
      (no BuiltWith / Wappalyzer).
    """
    tokens: set[str] = set()
    bw_present = False

    for t in record.get("tech_stack_detected", []) or []:
        tokens.add(t)
        bw_present = True

    domain = record.get("domain", "")
    jp_entry = jobposts.company_jobposts(domain)
    if jp_entry:
        for t in jp_entry.get("builtwith", []) or []:
            tokens.add(t)
            bw_present = True
        # crude mention harvest from role titles
        for role in jp_entry.get("open_roles_today", []) or []:
            title = role.get("title", "")
            for key in _STACK_MAP.keys():
                if key.lower() in title.lower():
                    tokens.add(key)

    canonical_stacks = config.get("bench.stacks", [])
    inferred_set: set[str] = set()
    for t in tokens:
        stack = _STACK_MAP.get(t.lower())
        if stack and stack in canonical_stacks:
            inferred_set.add(stack)

    return sorted(tokens), sorted(inferred_set), (not bw_present and bool(tokens))
