# 18 — Configuration

**Source:** Challenge document — "The Production Stack", "Data Handling Policy" (kill-switch), consolidated across all specs.

## 1. Principles

- **Secrets in env vars, tunables in YAML.** Every external-service secret lives in `.env` (template in [.env.example](.env.example)). Every application-level behaviour knob lives in `config.yaml` (template in [config.example.yaml](config.example.yaml)).
- **12-factor.** No secrets in code, no secrets in git, no secrets in logs.
- **Fail fast on missing keys.** Startup validates that every required env var is present (via pydantic-settings); missing values abort boot with a named error.
- **Kill-switch default = unset.** Boot logs `killswitch.enabled=false` prominently.
- **Eval-tier keys isolated.** Eval-tier LLM API key only loaded during `make held-out` runs; dev-tier key is the default elsewhere. Prevents accidental eval-tier spend.

## 2. Loader

```python
# agent/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, AnyHttpUrl
import yaml, pathlib

class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    # LLM
    openrouter_api_key: SecretStr
    anthropic_api_key: SecretStr | None = None          # eval tier only
    openai_api_key: SecretStr | None = None             # eval tier alt

    # Email
    resend_api_key: SecretStr | None = None
    resend_webhook_secret: SecretStr | None = None

    # SMS
    africastalking_username: str | None = None
    africastalking_api_key: SecretStr | None = None
    africastalking_shortcode: str | None = None
    africastalking_webhook_secret: SecretStr | None = None

    # HubSpot
    hubspot_mcp_url: AnyHttpUrl
    hubspot_private_app_token: SecretStr

    # Cal.com
    calcom_base_url: AnyHttpUrl = "http://localhost:3000"
    calcom_api_key: SecretStr
    calcom_webhook_secret: SecretStr

    # Langfuse
    langfuse_public_key: SecretStr
    langfuse_secret_key: SecretStr
    langfuse_host: AnyHttpUrl = "https://cloud.langfuse.com"

    # Voice (bonus)
    voice_rig_webhook_url: AnyHttpUrl | None = None
    voice_rig_keyword_prefix: str | None = None

    # Crunchbase ODM (local file; no secret needed)
    # layoffs.fyi (local CSV; no secret needed)
    # BuiltWith (optional API key)
    builtwith_api_key: SecretStr | None = None

    # Kill-switch
    convergine_enable_real_outbound: bool = False        # belt + braces, must be True to flip switch

def load_config() -> AppConfig:
    cfg_path = pathlib.Path("config.yaml")
    data = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    return AppConfig(**data)
```

## 3. Config schema (`config.yaml`)

See [config.example.yaml](config.example.yaml) for the full template. Sections:

| Section | Purpose |
|---------|---------|
| `llm` | Model pins, provider routing, prices, retry |
| `killswitch` | Enabled flag, sink email, sink short-code, audit log path |
| `channels.email` | Provider selection, from address, subject/template config |
| `channels.sms` | Provider selection, short-code, keyword prefix, body cap |
| `channels.voice` | Rig URL, keyword prefix (bonus) |
| `crm.hubspot` | Object/property mappings, rate-limit budget |
| `calendar.calcom` | Event-type slugs, booking buffer |
| `observability.langfuse` | Project name, flush interval |
| `enrichment` | Recency windows, velocity thresholds, confidence thresholds |
| `icp` | Confidence + margin thresholds, segment filters overlay |
| `eval.tau2_bench` | Repo, pinned tag, slice sizes, trials, seed |
| `method` | Selected mechanism name, hyperparameters |
| `market_space` | Weights, bands |
| `costs` | Per-model USD/1k in/out for cost attribution |

## 4. Secret rotation

- Every API key is valid for the challenge week only.
- End-of-week purge (`scripts/end_of_week_purge.sh`) revokes:
  - Resend API key.
  - Africa's Talking API key.
  - HubSpot private-app token.
  - Langfuse keys.
  - OpenRouter key (if this environment isolated to the challenge).
- The purge script writes to `data/purge_audit.jsonl` confirming each revocation.

## 5. Boot-time validation

```python
def validate(secrets: Secrets, cfg: AppConfig) -> None:
    if cfg.killswitch.enabled and not secrets.convergine_enable_real_outbound:
        raise SystemExit("killswitch.enabled=true but CONVERGINE_ENABLE_REAL_OUTBOUND not set")
    if cfg.channels.email.provider == "resend" and not secrets.resend_api_key:
        raise SystemExit("resend selected but RESEND_API_KEY missing")
    # ... one check per provider × feature combination
```

## 6. Environment-specific overrides

Three environments:

| Environment | Purpose | Config overlay |
|-------------|---------|----------------|
| `local` (default) | Developer laptops | `config.local.yaml` overrides dev-tier models, loud logging |
| `ci` | CI runs | `config.ci.yaml` uses fixture traces, zero-cost mocks |
| `eval` | Held-out eval runs | `config.eval.yaml` flips to eval-tier model, higher budget cap |

Overlay precedence (later wins): `config.yaml` → `config.<env>.yaml` → env vars.

## 7. Secret hygiene in logs

- Pydantic `SecretStr` + `model_dump(exclude={secrets})`.
- A `scripts/lint_logs.py` scan fails the build if any `eval/*.jsonl` or `data/*` file contains a substring matching known-secret regexes (`sk-ant-*`, `sk-or-*`, `re_*`).

## 8. Acceptance tests

- Boot with missing `OPENROUTER_API_KEY` fails with a clear error referencing `.env`.
- Boot with `killswitch.enabled=true` and `CONVERGINE_ENABLE_REAL_OUTBOUND=0` refuses.
- Swapping `config.yaml` overlay to `config.eval.yaml` selects Claude Sonnet 4.6 as the model and raises the cost cap to the eval-tier value.
- `scripts/lint_logs.py` catches a fixture secret leaked into a JSONL.
