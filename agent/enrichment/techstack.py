"""Tech-stack signal — BuiltWith optional, fixture fallback.

Reads `data/techstack/<domain>.json` shape: `{"items": ["dbt", "Snowflake", ...]}`.
Degrades gracefully when missing.
"""
from __future__ import annotations

import json
import pathlib


_DIR = pathlib.Path("data/techstack")

_BENCH_STACK_MAP = {
    "python": ["dbt", "airflow", "prefect", "pandas", "dagster"],
    "data": ["snowflake", "bigquery", "databricks", "postgres", "duckdb"],
    "ml": ["weights & biases", "w&b", "mlflow", "ray", "vllm", "huggingface"],
    "infra": ["kubernetes", "terraform", "aws", "gcp", "azure"],
}


def fetch(domain: str) -> dict:
    p = _DIR / f"{domain.lower()}.json"
    if not p.exists():
        return {"items": [], "bench_matches": [], "confidence": 0.0}
    data = json.loads(p.read_text())
    items = [i for i in data.get("items", [])]
    lower = {i.lower() for i in items}
    matches: list[str] = []
    for bench, stacks in _BENCH_STACK_MAP.items():
        if any(s in lower for s in stacks):
            matches.append(bench)
    return {"items": items, "bench_matches": matches, "confidence": round(min(0.35 + 0.1 * len(items), 0.9), 2)}
