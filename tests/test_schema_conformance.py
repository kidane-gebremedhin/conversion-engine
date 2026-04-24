"""Schema conformance: Pydantic briefs match tenacious_sales_data/schemas/*.schema.json."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from agent.config import REPO_ROOT


SCHEMA_DIR = REPO_ROOT / "tenacious_sales_data" / "schemas"


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text())


def test_hiring_signal_sample_validates():
    schema = _load_schema("hiring_signal_brief.schema.json")
    sample = json.loads((SCHEMA_DIR / "sample_hiring_signal_brief.json").read_text())
    jsonschema.validate(sample, schema)


def test_competitor_gap_sample_validates():
    schema = _load_schema("competitor_gap_brief.schema.json")
    sample = json.loads((SCHEMA_DIR / "sample_competitor_gap_brief.json").read_text())
    jsonschema.validate(sample, schema)


def test_pipeline_output_validates_against_hiring_schema():
    """End-to-end: run the pipeline and validate the output JSON against the schema."""
    from agent.enrichment.pipeline import enrich
    schema = _load_schema("hiring_signal_brief.schema.json")
    brief, _ = enrich("orrin-labs.example")
    data = json.loads(brief.model_dump_json(exclude_none=True))
    # Datetimes serialize to strings by default; schema tolerates string types.
    jsonschema.validate(data, schema)
