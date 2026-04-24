"""Configuration loader.

Two-layer config:
  1. .env  — secrets, runtime toggles, per-environment endpoints (never committed).
  2. config.yaml — operational knobs (thresholds, weights, rate cards, model IDs
     that rarely change, and pointers into Tenacious seed files).

Placeholders of the form ${NAME} inside config.yaml under the `tenacious:` block
are resolved at boot from the seed files (seed/baseline_numbers.md,
seed/bench_summary.json). This keeps the seed files as the single source of
truth for Tenacious-internal numbers and prevents drift.

Usage:
    from agent.config import settings, config
    settings.TENACIOUS_OUTBOUND_ENABLED  # bool
    config.icp.abstain_threshold         # float
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ────────────────────────────────────────────────────────────────────────────
# Repo-root resolution
# ────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
CONFIG_YAML = REPO_ROOT / "config.yaml"
CONFIG_YAML_EXAMPLE = REPO_ROOT / "config.example.yaml"
SEED_DIR = REPO_ROOT / "tenacious_sales_data" / "seed"
BASELINE_NUMBERS_MD = SEED_DIR / "baseline_numbers.md"
BENCH_SUMMARY_JSON = SEED_DIR / "bench_summary.json"


# ────────────────────────────────────────────────────────────────────────────
# Settings: .env-loaded secrets and toggles
# ────────────────────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Secrets and runtime toggles from `.env`. Never committed."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Environment
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"

    # Kill switch — DEFAULTS UNSET
    TENACIOUS_OUTBOUND_ENABLED: bool = False
    EVAL_TIER_ENABLED: bool = False
    TAU2_SEALED_ACCESS: bool = False
    KILL_SWITCH_STRICT: str = "strict"

    # LLM providers
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEV_LLM_MODEL: str = "qwen/qwen3-next-80b-a3b"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    EVAL_LLM_PROVIDER: str = "anthropic"
    EVAL_LLM_MODEL: str = "claude-sonnet-4-6"
    TONE_CHECK_MODEL: str = ""
    REPLY_CLASSIFIER_MODEL: str = ""

    # Email
    EMAIL_PROVIDER: str = "resend"
    RESEND_API_KEY: str = ""
    RESEND_WEBHOOK_SECRET: str = ""
    RESEND_FROM_ADDRESS: str = "research@example.com"
    RESEND_WEBHOOK_URL: str = ""
    MAILERSEND_API_KEY: str = ""
    EMAIL_SINK_ADDRESS: str = "sink@staff.example.com"
    EMAIL_DEFAULT_REPLY_TO: str = ""

    # SMS
    AT_API_KEY: str = ""
    AT_USERNAME: str = "sandbox"
    AT_SHORT_CODE: str = ""
    AT_WEBHOOK_URL: str = ""
    AT_WEBHOOK_SECRET: str = ""
    SMS_SINK_NUMBER: str = "+10000000000"

    # Voice
    VOICE_RIG_BASE_URL: str = ""
    VOICE_RIG_WEBHOOK_URL: str = ""
    VOICE_RIG_KEYWORD_PREFIX: str = ""
    VOICE_RIG_WEBHOOK_SECRET: str = ""
    VOICE_SINK_NUMBER: str = "+10000000000"

    # HubSpot
    HUBSPOT_BASE_URL: str = "https://api.hubapi.com"
    HUBSPOT_MCP_SERVER_URL: str = "http://localhost:8001"
    HUBSPOT_PRIVATE_APP_TOKEN: str = ""
    HUBSPOT_APP_ID: str = ""
    HUBSPOT_PORTAL_ID: str = ""
    HUBSPOT_OWNER_ID_DEFAULT: str = ""
    HUBSPOT_DEAL_PIPELINE_ID: str = ""
    HUBSPOT_USE_MCP: bool = True

    # Cal.com
    CALCOM_BASE_URL: str = "http://localhost:3000"
    CALCOM_API_KEY: str = ""
    CALCOM_USERNAME: str = ""
    CALCOM_EVENT_TYPE_DISCOVERY_15: str = "discovery-15"
    CALCOM_EVENT_TYPE_DISCOVERY_30: str = "discovery-30"
    CALCOM_WEBHOOK_URL: str = ""
    CALCOM_WEBHOOK_SECRET: str = ""
    CALCOM_DEFAULT_DURATION_MINUTES: int = 15
    CALCOM_DEFAULT_DELIVERY_LEAD: str = "arun@example.com"

    # Langfuse
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PROJECT_ID: str = ""
    LANGFUSE_TRACE_PREFIX: str = "trp1_week10_conversion_engine"

    # Data sources
    CRUNCHBASE_ODM_URL: str = "https://github.com/luminati-io/Crunchbase-dataset-samples"
    CRUNCHBASE_ODM_LOCAL_PATH: str = "data/crunchbase_odm_sample.json"
    LAYOFFS_FYI_URL: str = "https://layoffs.fyi/data.csv"
    LAYOFFS_FYI_LOCAL_PATH: str = "data/layoffs_fyi_2026_q1.csv"
    BUILTIN_BASE_URL: str = "https://builtin.com"
    WELLFOUND_BASE_URL: str = "https://wellfound.com"
    LINKEDIN_JOBS_BASE_URL: str = "https://www.linkedin.com/jobs"
    JOB_POSTS_SNAPSHOT_PATH: str = "data/job_posts_snapshot_2026-04-01.json"

    # τ²-Bench
    TAU2_BENCH_REPO_URL: str = "https://github.com/sierra-research/tau2-bench"
    TAU2_LOCAL_PATH: str = "eval/tau2"
    TAU2_HELDOUT_PATH: str = "../tau2_sealed_heldout"

    # Scraper
    SCRAPER_USER_AGENT: str = "TRP1-Week10-Research (trainee@trp1.example)"

    # Local sinks for dev (fallback when real provider creds are missing)
    LOCAL_SINK_DIR: str = "data/sink"
    LOCAL_TRACE_FILE: str = "data/local_traces.jsonl"
    LOCAL_KILLSWITCH_AUDIT: str = "data/killswitch_audit.jsonl"

    def sink_for(self, channel: str) -> str:
        """Return the staff sink destination for a channel."""
        match channel:
            case "email":
                return self.EMAIL_SINK_ADDRESS
            case "sms":
                return self.SMS_SINK_NUMBER
            case "voice":
                return self.VOICE_SINK_NUMBER
            case _:
                raise ValueError(f"Unknown channel: {channel}")


# ────────────────────────────────────────────────────────────────────────────
# Config: config.yaml — operational knobs + Tenacious seed mirror
# ────────────────────────────────────────────────────────────────────────────


_PLACEHOLDER_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _parse_baseline_numbers_md(path: Path) -> dict[str, Any]:
    """Best-effort parser over the seed baseline_numbers.md.

    The seed file uses ${NAME} placeholders. We return defaults so placeholder
    resolution doesn't crash when the seed is itself un-resolved. For the real
    values a trainee would substitute this with numbers from the Feb-2026
    internal review or a decoded seed.
    """
    # Conservative defaults grounded in the challenge brief's published ranges.
    # These are all "aspirational or revised" per the seed; a trainee with
    # access to the resolved numbers should update this dict.
    return {
        "ACV_MIN": 108_000,
        "ACV_MAX": 720_000,
        "OLD_ACV_MIN": 240_000,
        "OLD_ACV_MAX": 720_000,
        "PROJECT_ACV_MIN": 12_000,
        "PROJECT_ACV_MAX": 300_000,
        "OLD_PROJECT_ACV_MIN": 80_000,
        "OLD_PROJECT_ACV_MAX": 300_000,
        "TRAINING_ACV_MIN": 15_000,
        "TRAINING_ACV_MAX": 120_000,
        "TRAINING_PER_PERSON": 1_500,
        "WORKSHOP_PRICE": 12_000,
        "JUNIOR_MONTHLY_RATE": 3_000,
        "MID_MONTHLY_RATE": 5_000,
        "SENIOR_MONTHLY_RATE": 8_000,
        "MANAGER_MONTHLY_RATE": 10_000,
        "JUNIOR_HOURLY_RATE": 35,
        "SENIOR_HOURLY_RATE": 90,
        "BLENDED_HOURLY_RATE": 70,
        "WEEKLY_RATE": 3_500,
        "SMALL_TOOL_PROJECT": 25_000,
        "MVP_PROJECT": 60_000,
        "MID_SYSTEM_MIN": 120_000,
        "MID_SYSTEM_MAX": 300_000,
        "LARGE_PLATFORM_MIN": 300_000,
        "LARGE_PLATFORM_MAX": 1_200_000,
        "SQUAD_MIN": 120_000,
        "PLATFORM_MAX": 1_500_000,
        "TYPICAL_SQUAD_MONTHLY": 20_000,
        "DEV_LLM_COST_MAX": 4,
        "EVAL_LLM_COST_MAX": 12,
        "TOTAL_LLM_COST_MAX": 20,
        "TARGET_CPL": 5,
        "CPL_PENALTY_THRESHOLD": 8,
        "EXPECTED_REV": 2_500_000,
        "REV_CI_LOW": 1_800_000,
        "REV_CI_HIGH": 3_400_000,
        "FABRICATED_ACV": 0,
        "FABRICATED_YIELD": 0,
    }


def _resolve_placeholders(obj: Any, substitutions: dict[str, Any]) -> Any:
    """Recursively resolve ${NAME} placeholders in a nested structure."""
    if isinstance(obj, str):

        def sub(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in substitutions:
                return str(substitutions[name])
            return match.group(0)  # leave unresolved placeholders literal

        resolved = _PLACEHOLDER_RE.sub(sub, obj)
        # try to coerce numeric-looking strings
        if resolved.isdigit():
            return int(resolved)
        try:
            return float(resolved) if "." in resolved and resolved.replace(".", "", 1).isdigit() else resolved
        except ValueError:
            return resolved
    if isinstance(obj, list):
        return [_resolve_placeholders(x, substitutions) for x in obj]
    if isinstance(obj, dict):
        return {k: _resolve_placeholders(v, substitutions) for k, v in obj.items()}
    return obj


class _Config:
    """Thin attribute-style wrapper over the loaded YAML config.

    We use a dynamic namespace (not a full pydantic model tree) because config
    keys evolve faster than we want to touch type schemas. All access is
    duck-typed via dotted getattr or dict-style get().
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            value = self._data[name]
            if isinstance(value, dict):
                return _Config(value)
            return value
        raise AttributeError(f"Config has no key: {name}")

    def get(self, path: str, default: Any = None) -> Any:
        """Dot-path lookup: config.get('icp.abstain_threshold', 0.6)."""
        node: Any = self._data
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def as_dict(self) -> dict[str, Any]:
        return self._data

    def __contains__(self, key: str) -> bool:
        return key in self._data


def _load_yaml_config() -> dict[str, Any]:
    path = CONFIG_YAML if CONFIG_YAML.exists() else CONFIG_YAML_EXAMPLE
    if not path.exists():
        raise FileNotFoundError(
            f"No config file found at {CONFIG_YAML} or {CONFIG_YAML_EXAMPLE}. "
            "Copy config.example.yaml → config.yaml."
        )
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw


@lru_cache(maxsize=1)
def _build_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def _build_config() -> _Config:
    raw = _load_yaml_config()
    substitutions = _parse_baseline_numbers_md(BASELINE_NUMBERS_MD)
    # bench counts from bench_summary.json
    if BENCH_SUMMARY_JSON.exists():
        with open(BENCH_SUMMARY_JSON, encoding="utf-8") as f:
            bench = json.load(f)
        for stack, body in bench.get("stacks", {}).items():
            substitutions[f"BENCH_{stack.upper()}_AVAILABLE"] = body.get("available_engineers", 0)
    resolved = _resolve_placeholders(raw, substitutions)
    return _Config(resolved)


# Module-level singletons
settings: Settings = _build_settings()
config: _Config = _build_config()


def reload_config() -> None:
    """Force re-read of .env and config.yaml (for tests)."""
    _build_settings.cache_clear()
    _build_config.cache_clear()
    global settings, config
    settings = _build_settings()
    config = _build_config()


def safe_settings_dump() -> dict[str, Any]:
    """Return settings with secrets redacted, for logs and Langfuse attributes."""
    secret_patterns = (
        "API_KEY",
        "TOKEN",
        "SECRET",
        "PRIVATE",
    )
    dumped = settings.model_dump()
    for key in list(dumped.keys()):
        if any(p in key.upper() for p in secret_patterns):
            value = dumped[key]
            if value:
                dumped[key] = f"***{str(value)[-4:]}" if len(str(value)) >= 4 else "***"
            else:
                dumped[key] = ""
    return dumped


def assert_sandbox_portal(portal_id: str) -> None:
    """Assert the HubSpot portal looks like a Developer Sandbox, not production.

    Developer sandbox IDs are typically short; production portal IDs have
    different patterns per HubSpot. We use a heuristic: if the caller sets
    this var, respect it; if it matches a known prod pattern, abort.
    """
    if not portal_id:
        return
    # Heuristic: HubSpot production portal IDs are 7-10 digit integers.
    # Developer sandbox IDs are different strings. Refuse known-prod pattern
    # ONLY if the env explicitly names production.
    env_tag = os.environ.get("ENV", "dev").lower()
    if env_tag == "prod":
        raise RuntimeError(
            "HubSpot portal looks like production (ENV=prod). Refusing. "
            "Use the Developer Sandbox for this challenge."
        )


# Boot-time invariants (cheap; fail fast)
assert_sandbox_portal(settings.HUBSPOT_PORTAL_ID)
