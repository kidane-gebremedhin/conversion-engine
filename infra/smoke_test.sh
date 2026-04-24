#!/usr/bin/env bash
# Conversion Engine — smoke test
#
# Verifies the kill switch gate is wired before the agent processes outbound.
# Five green checks:
#   1. Acknowledgement filed
#   2. Kill switch unset
#   3. Email sink path (via deliver())
#   4. SMS sink path (via deliver())
#   5. Local file sinks or external providers reachable
#
# Runs under 3 minutes. Exits non-zero on any failure.

set -euo pipefail

cd "$(dirname "$0")/.."

# The smoke test verifies agent-internal routing (kill switch, draft header,
# recipient allowlist, local sinks). It does NOT exercise real provider
# sends — those are validated by the manual Day-0 checks (make day0-hubspot,
# make day0-calcom, make day0-playwright) with real credentials. Force
# local-sink mode here so a populated .env doesn't make the smoke try to
# hit Resend / Africa's Talking / HubSpot live.
export RESEND_API_KEY=""
export MAILERSEND_API_KEY=""
export AT_API_KEY=""
export HUBSPOT_PRIVATE_APP_TOKEN=""
export HUBSPOT_USE_MCP="false"
export CALCOM_API_KEY=""
export TENACIOUS_OUTBOUND_ENABLED="false"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}!${NC} $1"; }

echo "==> Conversion Engine smoke test"
echo

# ─── 1. Acknowledgement ───────────────────────────────────────────────────────
if [ -f infra/acknowledgement_signed.txt ] && [ -f policy/acknowledgement_signed.txt ]; then
    pass "Policy acknowledgement filed"
else
    fail "Missing infra/acknowledgement_signed.txt or policy/acknowledgement_signed.txt (run 'make ack')"
fi

# ─── 2. Kill switch unset ─────────────────────────────────────────────────────
if [ -f .env ]; then
    if grep -E '^TENACIOUS_OUTBOUND_ENABLED=' .env >/dev/null 2>&1; then
        fail "TENACIOUS_OUTBOUND_ENABLED is set in .env — must be unset or commented out"
    fi
    pass "Kill switch TENACIOUS_OUTBOUND_ENABLED is unset"
else
    warn ".env not present; using defaults (kill switch unset by default)"
fi

# ─── 3. Synthetic prospects fixture ───────────────────────────────────────────
if [ -f data/synthetic_prospects.json ]; then
    count=$(python3 -c "import json; print(len(json.load(open('data/synthetic_prospects.json'))))")
    pass "Synthetic prospects fixture present ($count entries)"
else
    fail "Missing data/synthetic_prospects.json"
fi

# ─── 4. Email via deliver() routes to sink ────────────────────────────────────
python3 <<'PY' || exit 1
from agent.kill_switch import deliver, EmailPayload
payload = EmailPayload(
    subject="Smoke test",
    body_text="smoke test body",
    headers={"X-Tenacious-Status": "draft"},
)
# Use sink address directly — deliver() will enforce kill-switch + draft header.
from agent.config import settings
result = deliver("email", settings.EMAIL_SINK_ADDRESS, payload)
assert result.sink, "expected kill-switch to route to sink"
print(f"→ email sink test ok: message_id={result.message_id} provider={result.provider}")
PY
pass "Email deliver() routes to sink"

# ─── 5. SMS via deliver() routes to sink ──────────────────────────────────────
python3 <<'PY' || exit 1
from agent.kill_switch import deliver, SmsPayload
from agent.config import settings
payload = SmsPayload(body="smoke test sms")
result = deliver("sms", settings.SMS_SINK_NUMBER, payload)
assert result.sink, "expected kill-switch to route to sink"
print(f"→ sms sink test ok: message_id={result.message_id} provider={result.provider}")
PY
pass "SMS deliver() routes to sink"

# ─── 6. HubSpot reachable — MCP required when credentials are set ─────────────
# Day-0 readiness requires mode=mcp when a token is configured. REST mode is
# only acceptable under the `HUBSPOT_USE_MCP=false` opt-out, which fails
# `make final-check`. In the offline dev loop (no token) local mode is fine.
python3 <<'PY' || exit 1
from agent.hubspot.client import HubSpotClient
from agent.config import settings
c = HubSpotClient()
ok = c.healthcheck()
assert ok, "hubspot client healthcheck failed"
if settings.HUBSPOT_PRIVATE_APP_TOKEN and settings.HUBSPOT_USE_MCP:
    assert c.mode == "mcp", f"expected mode=mcp for Day-0, got {c.mode!r}"
print(f"→ hubspot ok: mode={c.mode}")
PY
pass "HubSpot client reachable (mode=mcp if credentials set)"

# ─── 7. Cal.com reachable or local fallback ───────────────────────────────────
python3 <<'PY' || exit 1
from agent.calendar.client import CalComClient
c = CalComClient()
ok = c.healthcheck()
assert ok, "calcom client healthcheck failed"
print(f"→ calcom ok: mode={c.mode}")
PY
pass "Cal.com client reachable (or local-mode fallback)"

# ─── 8. Langfuse reachable or local fallback ──────────────────────────────────
python3 <<'PY' || exit 1
from agent.observability.langfuse import healthcheck
ok = healthcheck()
assert ok, "langfuse healthcheck failed"
print("→ langfuse ok")
PY
pass "Langfuse reachable (or local-mode fallback)"

echo
echo -e "${GREEN}All checks passed${NC}"
