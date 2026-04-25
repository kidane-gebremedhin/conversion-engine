"""Shared pytest setup: repo root on sys.path + force offline/stub mode.

Tests must not make real provider calls (email send, HubSpot MCP, LLM,
Resend, Africa's Talking, Cal.com, Langfuse) regardless of what the
user has in `.env`. This module clears provider credentials before
agent modules import so every channel adapter falls back to its local
sink and the LLM client uses the deterministic stub.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Clear secrets BEFORE pydantic-settings constructs the Settings singleton.
for _key in (
    "RESEND_API_KEY", "MAILERSEND_API_KEY",
    "AT_API_KEY",
    "HUBSPOT_PRIVATE_APP_TOKEN",
    "CALCOM_API_KEY",
    "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
):
    os.environ[_key] = ""
os.environ["TENACIOUS_OUTBOUND_ENABLED"] = "false"
os.environ["EVAL_TIER_ENABLED"] = "false"
os.environ["TAU2_SEALED_ACCESS"] = "false"
os.environ["HUBSPOT_USE_MCP"] = "false"
os.environ["LLM_STUB"] = "1"

# Sink defaults for tests — independent of whatever the user has in .env.
# The kill switch refuses to dispatch to an empty recipient (PolicyViolation),
# so these must be non-empty for `deliver()` smoke tests.
os.environ["EMAIL_SINK_ADDRESS"] = "sink@staff.example.com"
os.environ["SMS_SINK_NUMBER"] = "+10000000000"
os.environ["VOICE_SINK_NUMBER"] = "+10000000000"

# Point pydantic-settings away from the user's .env so populated secrets
# in the dev environment don't bleed into tests via its env_file load.
os.environ["PYDANTIC_SETTINGS_ENV_FILE"] = "/dev/null"
