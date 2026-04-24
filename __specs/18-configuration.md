# 18 — Configuration

**No base URL, API key, LLM model ID, price, threshold, window, or rate card is hard-coded.** Every such value is pulled from the environment (`.env`) for secrets and runtime toggles, or from `config.yaml` for operational knobs. The implementation fails fast on boot if a required value is missing.

## Layered configuration

Two layers, in precedence order (higher overrides lower):

1. **`.env`** (loaded via `python-dotenv` or `pydantic-settings`) — secrets, runtime toggles, per-environment endpoints.
2. **`config.yaml`** (loaded via `pydantic`) — operational knobs that rarely change and are safe to commit (thresholds, windows, weights, prompt IDs).

A `config.example.yaml` ships with placeholder values and extensive comments. Same for `.env.example`.

## Configuration categories

### 1. Secrets (env only; never committed)

- LLM provider keys: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`.
- Email provider: `RESEND_API_KEY` / `MAILERSEND_API_KEY`, `RESEND_WEBHOOK_SECRET`.
- SMS: `AT_API_KEY`, `AT_USERNAME`, `AT_WEBHOOK_SECRET`.
- Voice rig: `VOICE_RIG_WEBHOOK_SECRET`.
- HubSpot: `HUBSPOT_PRIVATE_APP_TOKEN`.
- Langfuse: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.
- Cal.com: `CALCOM_API_KEY`, `CALCOM_WEBHOOK_SECRET`.

### 2. Runtime toggles (env only)

- `TENACIOUS_OUTBOUND_ENABLED` — kill switch. Defaults to unset.
- `EVAL_TIER_ENABLED` — guards eval-tier model usage. Defaults to unset.
- `TAU2_SEALED_ACCESS` — guards the sealed held-out partition. Defaults to unset.
- `KILL_SWITCH_STRICT` — runtime assertion level. Defaults to `strict`.
- `ENV` — `dev` / `staging` / `prod`. Defaults to `dev`.

### 3. Base URLs and endpoints (env only)

- `OPENROUTER_BASE_URL`, `ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL` — LLM provider endpoints.
- `HUBSPOT_BASE_URL`, `HUBSPOT_MCP_SERVER_URL`.
- `CALCOM_BASE_URL`.
- `LANGFUSE_HOST`.
- `CRUNCHBASE_ODM_URL`, `LAYOFFS_FYI_URL`, `TAU2_BENCH_REPO_URL` — data source URLs.
- `BUILTIN_BASE_URL`, `WELLFOUND_BASE_URL`, `LINKEDIN_JOBS_BASE_URL` — scraping targets.

### 4. Identifiers and addresses (env only)

- `RESEND_FROM_ADDRESS`, `EMAIL_SINK_ADDRESS`, `EMAIL_DEFAULT_REPLY_TO`.
- `AT_SHORT_CODE`, `SMS_SINK_NUMBER`, `VOICE_SINK_NUMBER`.
- `HUBSPOT_PORTAL_ID`, `HUBSPOT_OWNER_ID_DEFAULT`, `HUBSPOT_DEAL_PIPELINE_ID`.
- `CALCOM_DEFAULT_DELIVERY_LEAD`, `CALCOM_EVENT_TYPE_DISCOVERY_15`, `CALCOM_EVENT_TYPE_DISCOVERY_30`.
- `VOICE_RIG_KEYWORD_PREFIX`.

### 5. LLM model IDs (env — different per account/provider)

- `DEV_LLM_MODEL` — e.g., `qwen/qwen3-next-80b-a3b` or `deepseek/deepseek-v3.2`.
- `EVAL_LLM_MODEL` — e.g., `anthropic/claude-sonnet-4.6` or `openai/gpt-5`.
- `TONE_CHECK_MODEL` — may be a cheaper model for the second-pass tone check.
- `REPLY_CLASSIFIER_MODEL` — may differ from composer.

### 6. Operational knobs (YAML)

All numeric thresholds, windows, weights, and rate cards live in `config.yaml`:

- `icp.*` — abstain threshold, per-segment filter weights.
- `funding.*`, `layoffs.*`, `leadership.*` — windows and amount bands.
- `jobposts.*` — velocity-label thresholds, AI-adjacent titles.
- `ai_maturity.*` — signal weights.
- `bench.stacks` — canonical stack taxonomy.
- `competitor_gap.*` — peer selection rules, sub-niche overrides.
- `composer.*` — word limits, subject first-word rules, disallowed phrases.
- `tone_check.*` — per-marker threshold, regeneration count.
- `reply.ambiguous_threshold`.
- `handoff.default_lead_email`.
- `scraper.*` — rate limit, concurrent tabs, crawl cap.
- `budgets.*` — dev LLM max, eval LLM max, total max, target CPL, penalty CPL.
- `timezone.default`.
- `observability.allowed_attributes`.
- `llm.rate_cards` — per-model USD per 1M tokens (input and output).
- `market_space.*` — oxygen-score weights, validation sample size.
- `memo.typography` — font, margins, line-height.

### 7. Tenacious-specific numbers (YAML, mirror of seed files)

**Rates, ACV ranges, engagement minimums, and bench counts are authoritative in the seed files**. For code to read them, `config.yaml > tenacious` mirrors the seed values with explicit cross-references:

```yaml
tenacious:
  # Mirrored from seed/baseline_numbers.md — source of truth.
  # Do NOT edit these values here; regenerate from seed on seed update.
  acv:
    talent_outsourcing_min_usd: ${ACV_MIN}           # Resolved at boot from seed
    talent_outsourcing_max_usd: ${ACV_MAX}
    project_consulting_min_usd: ${PROJECT_ACV_MIN}
    project_consulting_max_usd: ${PROJECT_ACV_MAX}
    training_min_usd: ${TRAINING_ACV_MIN}
    training_max_usd: ${TRAINING_ACV_MAX}
  rates:
    junior_monthly_usd: ${JUNIOR_MONTHLY_RATE}
    mid_monthly_usd: ${MID_MONTHLY_RATE}
    senior_monthly_usd: ${SENIOR_MONTHLY_RATE}
    manager_monthly_usd: ${MANAGER_MONTHLY_RATE}
    blended_hourly_usd: ${BLENDED_HOURLY_RATE}
    weekly_fractional_usd: ${WEEKLY_RATE}
  conversions:
    discovery_to_proposal_min: 0.35
    discovery_to_proposal_max: 0.50
    proposal_to_close_min: 0.25
    proposal_to_close_max: 0.40
    stalled_thread_rate: 0.35   # Midpoint of 30–40%
  bench:
    # Mirrored from seed/bench_summary.json — source of truth.
    as_of: "2026-04-21"
    # (Actual counts resolved at boot; never hard-coded.)
```

The `${ACV_MIN}` etc. placeholders in the YAML are resolved at boot from `seed/baseline_numbers.md` via a small parser in `agent/config.py`. This keeps the seed file as the single source of truth and prevents the common failure mode of "config drifted from seed."

### 8. Prompt IDs and template paths (YAML)

- `prompts.classifier_path`, `prompts.composer_segment_1_path`, etc. — relative paths into `agent/prompts/`.
- `templates.email.cold_signal_grounded` etc. — relative paths into `agent/channels/email/templates/`.

## Boot-time validation

`agent/config.py` uses `pydantic-settings` to:

1. Load `.env` into a `Settings` model.
2. Load `config.yaml` into a `Config` model.
3. Resolve `${...}` placeholders in the YAML against seed files.
4. Assert every required field is non-empty, every URL parses, every model ID exists in the provider's catalog (lazy-check on first call), every numeric range is self-consistent (min ≤ max).
5. Emit the resolved config as a redacted JSON to the Langfuse trace (with secrets masked) for reproducibility.

Boot fails fast on any missing required value.

## Secret rotation

- All secrets are stored in `.env`; none in YAML.
- A `.env.example` ships with the repo; a real `.env` is created on first run by `make setup`, with placeholders.
- Rotation requires editing `.env` and restarting; no code change.

## Configuration precedence for prices

The Tenacious pricing sheet and bench summary use bracketed placeholders (e.g., `$[JUNIOR_MONTHLY_RATE]`) in the seed files. The implementation:

- **Seed files are authoritative.** The YAML `tenacious.*` block references them, not vice versa.
- **Agent-facing copy** (email templates, composer prompts) references symbolic names (`$JUNIOR_MONTHLY_RATE`) that resolve from `config.yaml > tenacious.rates` at render time.
- **No numeric literal** for price, ACV, conversion rate, or bench count appears anywhere in `agent/` or `eval/` source code.

## What must NOT be in configuration

- Any text that resembles a real prospect email, phone number, or name.
- Any HubSpot portal ID matching a known production-portal pattern.
- Any prompt content with client-branded case-study names beyond `seed/case_studies.md`.
- Any fabricated Tenacious number. The only Tenacious numbers permitted are those mirrored from `seed/baseline_numbers.md` and `seed/bench_summary.json`.

## Example .env and config.yaml

See [`.env.example`](.env.example) and [`config.example.yaml`](config.example.yaml) in this directory.
