"""D0 smoke test — spawn the in-repo MCP server, call `upsert_contact`.

Satisfies the "test contact created via API" artifact of D0 pre-flight
(__plans/01-d0-to-d3-interim-path.md).

Run:
  HUBSPOT_PRIVATE_APP_TOKEN=pat-na1-... python -m scripts.hubspot_smoke

Exits 0 on a valid contact id, 1 otherwise.
"""
from __future__ import annotations

import os
import sys

from agent.integrations.hubspot_mcp import ContactUpsert, HubSpotClient


def main() -> int:
    token = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN")
    if not token:
        print("HUBSPOT_PRIVATE_APP_TOKEN not set", file=sys.stderr)
        return 1

    client = HubSpotClient(token=token)
    try:
        if client.mode != "mcp":
            print(
                f"expected mode=mcp, got {client.mode!r} — check HUBSPOT_CLIENT_MODE",
                file=sys.stderr,
            )
            return 1

        contact_id = client.upsert_contact(
            ContactUpsert(
                email="smoke-test@sink.convergine.local",
                first_name="Smoke",
                last_name="Test",
                job_title="QA",
                company_id="",
                preferred_channel="email",
                synthetic=True,
            )
        )
    finally:
        client.close()

    if not contact_id:
        print("no contact id returned", file=sys.stderr)
        return 1
    print(f"ok — contact_id={contact_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
