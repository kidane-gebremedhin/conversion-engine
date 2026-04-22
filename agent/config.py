"""Config + secrets loader.

See __specs/18-configuration.md. Secrets → env/.env via pydantic-settings.
Tunables → config.yaml (+ optional config.<env>.yaml overlay).
"""
from __future__ import annotations

import os
import pathlib
from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr


class Secrets(BaseModel):
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    resend_api_key: SecretStr | None = None
    resend_from_domain: str = "convergine-sandbox.invalid"
    resend_from_address: str = "outbound@convergine-sandbox.invalid"
    resend_webhook_secret: SecretStr | None = None
    mailersend_api_key: SecretStr | None = None

    africastalking_username: str = "sandbox"
    africastalking_api_key: SecretStr | None = None
    africastalking_shortcode: str = "22222"
    africastalking_webhook_secret: SecretStr | None = None

    hubspot_mcp_url: str = "http://localhost:4000"
    hubspot_private_app_token: SecretStr | None = None

    calcom_base_url: str = "http://localhost:3000"
    calcom_api_key: SecretStr | None = None
    calcom_webhook_secret: SecretStr | None = None

    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_project: str = "convergine-local"

    builtwith_api_key: SecretStr | None = None

    voice_rig_webhook_url: str | None = None
    voice_rig_keyword_prefix: str | None = None

    convergine_enable_real_outbound: bool = False
    convergine_env: str = "local"
    convergine_llm_mode: str = "mock"  # mock | live

    @classmethod
    def from_env(cls) -> "Secrets":
        _load_dotenv()
        data: dict[str, Any] = {}
        for name, _field in cls.model_fields.items():
            env_val = os.environ.get(name.upper())
            if env_val is None:
                continue
            if name == "convergine_enable_real_outbound":
                data[name] = env_val not in ("0", "", "false", "False")
            else:
                data[name] = env_val
        return cls(**data)


class AppConfig(BaseModel):
    """Thin wrapper over the yaml tree — we keep it loose (dict) for interim."""

    version: int = 1
    raw: dict[str, Any] = Field(default_factory=dict)

    def get(self, *path: str, default: Any = None) -> Any:
        node: Any = self.raw
        for p in path:
            if not isinstance(node, dict) or p not in node:
                return default
            node = node[p]
        return node


def _load_dotenv(path: str = ".env") -> None:
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=1)
def load_config(path: str = "config.yaml") -> AppConfig:
    base = _load_yaml(pathlib.Path(path))
    env = os.environ.get("CONVERGINE_ENV", base.get("env", "local"))
    overlay = _load_yaml(pathlib.Path(f"config.{env}.yaml"))
    merged = _deep_merge(base, overlay)
    return AppConfig(version=merged.get("version", 1), raw=merged)


@lru_cache(maxsize=1)
def load_secrets() -> Secrets:
    return Secrets.from_env()


def validate(secrets: Secrets, cfg: AppConfig) -> None:
    """Boot-time guardrail. Raises SystemExit on misconfig."""
    ks = cfg.get("killswitch", default={}) or {}
    if ks.get("enabled") and not secrets.convergine_enable_real_outbound:
        raise SystemExit(
            "killswitch.enabled=true but CONVERGINE_ENABLE_REAL_OUTBOUND not set — refusing to boot"
        )
    mode = secrets.convergine_llm_mode
    if mode == "live" and not secrets.openrouter_api_key:
        raise SystemExit("CONVERGINE_LLM_MODE=live but OPENROUTER_API_KEY is not set")
