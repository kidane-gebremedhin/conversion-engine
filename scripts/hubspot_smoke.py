"""Day-0 HubSpot MCP proof: create one test contact via the HubSpot MCP server.

Day-0 readiness requires the MCP path. This script refuses to proceed
with REST — flip `HUBSPOT_USE_MCP=true` and make sure the MCP server
installs cleanly. See infra/hubspot_mcp.md.

Usage:
    PYTHONPATH=. python3 scripts/hubspot_smoke.py
"""
from __future__ import annotations

import sys
import uuid

from agent.config import settings
from agent.hubspot.client import HubSpotClient
from agent.hubspot.schema import ensure_all


def main() -> int:
    if not settings.HUBSPOT_USE_MCP:
        print(
            "ERROR: HUBSPOT_USE_MCP is not set. Day-0 requires the MCP path — "
            "REST is not an acceptable substitute. See infra/hubspot_mcp.md.",
            file=sys.stderr,
        )
        return 2
    if not settings.HUBSPOT_PRIVATE_APP_TOKEN:
        print(
            "ERROR: HUBSPOT_PRIVATE_APP_TOKEN is unset. The MCP server refuses to start without it.",
            file=sys.stderr,
        )
        return 2

    client = HubSpotClient()
    if client.mode != "mcp":
        print(
            f"ERROR: client.mode={client.mode!r} — expected 'mcp'. "
            "Something demoted the client. Refuse to run.",
            file=sys.stderr,
        )
        return 3

    if not client.healthcheck():
        print("ERROR: HubSpot MCP healthcheck failed. See infra/hubspot_mcp.md.", file=sys.stderr)
        return 4

    created_props = ensure_all(client)
    if created_props:
        head = ", ".join(created_props[:5])
        tail = "..." if len(created_props) > 5 else ""
        print(f"→ created {len(created_props)} tenacious_* properties: {head}{tail}")
    else:
        print("→ tenacious_* properties already present")

    # Use example.com (IANA-reserved, passes HubSpot's TLD validator).
    # The .example TLD fails HubSpot's INVALID_EMAIL check even though it's
    # valid per RFC 2606. Synthetic prospects use .example for the kill-switch
    # allowlist; this Day-0 smoke has to land in a real HubSpot portal.
    test_email = f"daytest+{uuid.uuid4().hex[:8]}@example.com"
    contact_id = client.upsert_contact(
        {
            "firstname": "Day0",
            "lastname": "Test",
            "company": "Tenacious Day-0 Smoke",
            "tenacious_status": "draft",
            "tenacious_segment": "abstain",
        },
        email=test_email,
    )
    print(f"→ MCP server started via `npx -y @hubspot/mcp-server`")
    print(f"✓ created test contact id={contact_id!r} email={test_email} via mcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
