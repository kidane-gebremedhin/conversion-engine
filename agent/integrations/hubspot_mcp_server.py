"""HubSpot MCP server (FastMCP, stdio transport).

This is the "HubSpot MCP server installed" artifact of the D0 pre-flight
(__plans/01-d0-to-d3-interim-path.md). We ship our own thin server because
no community server covers deals + the Conversation Event custom object we
need per __specs/08.

Run directly:
    python -m agent.integrations.hubspot_mcp_server          # stdio
    python -m agent.integrations.hubspot_mcp_server --http   # streamable HTTP on :4000

Env:
    HUBSPOT_PRIVATE_APP_TOKEN  — required
    HUBSPOT_CONVERSATION_EVENT_OBJECT_TYPE  — defaults to convergine_conversation_event
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from agent.integrations.hubspot_rest import (
    rest_advance_deal_stage,
    rest_create_deal,
    rest_find_company_by_crunchbase_uuid,
    rest_log_event,
    rest_upsert_company,
    rest_upsert_contact,
)

_server = FastMCP("convergine-hubspot")


def _token() -> str:
    tok = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN")
    if not tok:
        raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN not set in MCP server env")
    return tok


@_server.tool()
def upsert_company(
    crunchbase_uuid: str,
    name: str,
    domain: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    employees: str | None = None,
    convergine: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Create or update a Company keyed by convergine_crunchbase_uuid."""
    return {
        "id": rest_upsert_company(
            _token(),
            crunchbase_uuid=crunchbase_uuid,
            name=name,
            domain=domain,
            industry=industry,
            country=country,
            employees=employees,
            convergine=convergine or {},
        )
    }


@_server.tool()
def find_company_by_crunchbase_uuid(crunchbase_uuid: str) -> dict[str, str | None]:
    """Return the HubSpot company id matching a Crunchbase UUID, or null."""
    return {"id": rest_find_company_by_crunchbase_uuid(_token(), crunchbase_uuid)}


@_server.tool()
def upsert_contact(
    email: str,
    first_name: str,
    last_name: str,
    job_title: str,
    company_id: str,
    preferred_channel: str = "email",
    synthetic: bool = True,
) -> dict[str, str]:
    """Create or update a Contact keyed by email; associate to company_id."""
    return {
        "id": rest_upsert_contact(
            _token(),
            email=email,
            first_name=first_name,
            last_name=last_name,
            job_title=job_title,
            company_id=company_id,
            preferred_channel=preferred_channel,
            synthetic=synthetic,
        )
    }


@_server.tool()
def create_deal(
    company_id: str,
    contact_id: str,
    dealname: str,
    amount: int,
    convergine_segment: int | None = None,
    convergine_thread_id: str = "",
) -> dict[str, str]:
    """Create a deal and associate it to the given company + contact."""
    return {
        "id": rest_create_deal(
            _token(),
            company_id=company_id,
            contact_id=contact_id,
            dealname=dealname,
            amount=amount,
            convergine_segment=convergine_segment,
            convergine_thread_id=convergine_thread_id,
        )
    }


@_server.tool()
def advance_deal_stage(deal_id: str, stage: str) -> dict[str, bool]:
    """Update the dealstage property on an existing deal."""
    rest_advance_deal_stage(_token(), deal_id=deal_id, stage=stage)
    return {"ok": True}


@_server.tool()
def log_event(
    event_id: str,
    contact_id: str,
    company_id: str,
    event_type: str,
    channel: str,
    trace_id: str,
    payload_json: dict[str, Any],
    draft: bool,
) -> dict[str, bool]:
    """Append a Conversation Event custom-object record; idempotent on event_id."""
    rest_log_event(
        _token(),
        event_id=event_id,
        contact_id=contact_id,
        company_id=company_id,
        event_type=event_type,
        channel=channel,
        trace_id=trace_id,
        payload_json=payload_json,
        draft=draft,
    )
    return {"ok": True}


def main() -> None:
    p = argparse.ArgumentParser("convergine-hubspot-mcp")
    p.add_argument("--http", action="store_true", help="Serve Streamable HTTP on :4000 instead of stdio")
    p.add_argument("--port", type=int, default=4000)
    args = p.parse_args()

    if args.http:
        _server.settings.port = args.port
        _server.run(transport="streamable-http")
    else:
        _server.run(transport="stdio")


if __name__ == "__main__":
    sys.exit(main() or 0)
