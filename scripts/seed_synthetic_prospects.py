"""Seeds the local environment — verifies fixtures load + runs enrichment on all prospects.

Used by `make bootstrap`. Warm-enriches all synthetic prospects so the demo
starts from a populated `data/briefs_cache/` state.
"""
from __future__ import annotations

import json
import pathlib

import yaml

from agent.enrichment.crunchbase import load_all
from agent.enrichment.pipeline import enrich


def main() -> int:
    prospects = yaml.safe_load(pathlib.Path("tests/fixtures/synthetic_prospects.yaml").read_text())["prospects"]
    print(f"[seed] {len(prospects)} fixture prospects, {len(load_all())} Crunchbase rows")

    enriched = 0
    for row in prospects:
        try:
            enrich(row["crunchbase_uuid"], force=True)
            enriched += 1
        except KeyError as e:
            print(f"[seed] skip {row['alias']}: {e}")
    print(f"[seed] enrichment complete for {enriched} prospects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
