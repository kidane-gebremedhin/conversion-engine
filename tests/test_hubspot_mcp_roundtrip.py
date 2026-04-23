"""MCP stdio round-trip — spawn the in-repo server, call each tool, verify
that `HubSpotClient` receives back the expected id / ok payload.

The REST layer is monkey-patched inside the subprocess via an env-indirected
import shim (`CONVERGINE_HUBSPOT_REST_STUB=1`). No HubSpot network calls.
"""
from __future__ import annotations

import os
import sys
import textwrap

import pytest


@pytest.fixture
def stubbed_env(tmp_path, monkeypatch):
    """Write a tiny sitecustomize that patches hubspot_rest before the server imports it."""
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    (shim_dir / "sitecustomize.py").write_text(textwrap.dedent(
        """
        import os
        if os.environ.get("CONVERGINE_HUBSPOT_REST_STUB") == "1":
            import sys, types
            mod = types.ModuleType("agent.integrations.hubspot_rest")
            def _ret_id(token, **kw): return "stub-id-" + (kw.get("email") or kw.get("crunchbase_uuid") or "x")
            mod.rest_upsert_company = lambda token, **kw: "company-" + kw["crunchbase_uuid"]
            mod.rest_find_company_by_crunchbase_uuid = lambda token, uuid: "company-" + uuid
            mod.rest_upsert_contact = lambda token, **kw: "contact-" + kw["email"].replace("@", "_at_")
            mod.rest_create_deal = lambda token, **kw: "deal-" + kw["dealname"].replace(" ", "_")
            mod.rest_advance_deal_stage = lambda token, **kw: None
            mod.rest_log_event = lambda token, **kw: None
            sys.modules["agent.integrations.hubspot_rest"] = mod
        """
    ))

    existing = os.environ.get("PYTHONPATH", "")
    new_pp = f"{shim_dir}{os.pathsep}{existing}" if existing else str(shim_dir)
    monkeypatch.setenv("PYTHONPATH", new_pp)
    monkeypatch.setenv("CONVERGINE_HUBSPOT_REST_STUB", "1")
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "stub-token")
    monkeypatch.setenv("HUBSPOT_CLIENT_MODE", "mcp")
    return shim_dir


def test_mcp_roundtrip(stubbed_env):
    pytest.importorskip("mcp", reason="mcp SDK not installed")

    from agent.integrations.hubspot_mcp import (
        CompanyUpsert,
        ContactUpsert,
        ConversationEvent,
        DealCreate,
        HubSpotClient,
    )

    client = HubSpotClient(token="stub-token")
    try:
        assert client.mode == "mcp"

        company_id = client.upsert_company(CompanyUpsert(
            crunchbase_uuid="cb-123", name="Acme", domain=None, industry=None,
            country=None, employees=None, convergine={},
        ))
        assert company_id == "company-cb-123"

        assert client.find_company_by_crunchbase_uuid("cb-123") == "company-cb-123"

        contact_id = client.upsert_contact(ContactUpsert(
            email="x@sink.convergine.local", first_name="X", last_name="Y",
            job_title="CTO", company_id=company_id,
        ))
        assert contact_id.startswith("contact-")

        deal_id = client.create_deal(DealCreate(
            company_id=company_id, contact_id=contact_id,
            dealname="Convergine discovery", amount=10000,
            convergine_segment=1, convergine_thread_id="t-1",
        ))
        assert deal_id.startswith("deal-")

        client.advance_deal_stage(deal_id, "closedwon")
        client.log_event(ConversationEvent(
            event_id="e-1", contact_id=contact_id, company_id=company_id,
            event_type="email_sent", channel="email", trace_id="tr-1",
            payload_json={"k": "v"}, draft=True,
        ))
    finally:
        client.close()
