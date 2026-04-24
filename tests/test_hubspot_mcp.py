"""HubSpot MCP-path wiring.

These tests exercise the routing logic (mode selection, mcp-call dispatch)
WITHOUT spinning up a real MCP server. A stub MCP object is injected into
HubSpotClient so the call surface can be verified offline.

The real Day-0 proof runs via `make day0-hubspot` against a live server
and is not part of the pytest suite.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.config import settings
from agent.hubspot import client as hubspot_client


@pytest.fixture
def stubbed_mcp_client(monkeypatch):
    """HubSpotClient that uses a MagicMock in place of HubSpotMcp.

    Bypasses MCP server startup so the test suite stays fully offline.
    """
    monkeypatch.setattr(settings, "HUBSPOT_USE_MCP", True)
    monkeypatch.setattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", "test-token")

    stub = MagicMock()
    stub.healthcheck.return_value = True
    stub.upsert_contact.return_value = "mcp-contact-123"
    stub.create_engagement.return_value = "mcp-eng-456"
    stub.ensure_contact_property.return_value = True

    class _FakeMcp:
        def __new__(cls):
            return stub

    monkeypatch.setattr("agent.hubspot.mcp_client.HubSpotMcp", _FakeMcp)

    c = hubspot_client.HubSpotClient()
    return c, stub


def test_mode_is_mcp_when_configured(stubbed_mcp_client):
    c, _ = stubbed_mcp_client
    assert c.mode == "mcp"


def test_upsert_contact_routes_through_mcp(stubbed_mcp_client):
    c, stub = stubbed_mcp_client
    cid = c.upsert_contact({"firstname": "Ann"}, email="ann@example.com")
    assert cid == "mcp-contact-123"
    stub.upsert_contact.assert_called_once()


def test_engagement_routes_through_mcp(stubbed_mcp_client):
    c, stub = stubbed_mcp_client
    eid = c.create_engagement("email", {"subject": "x"})
    assert eid == "mcp-eng-456"
    stub.create_engagement.assert_called_once()


def test_healthcheck_uses_mcp(stubbed_mcp_client):
    c, stub = stubbed_mcp_client
    assert c.healthcheck() is True
    stub.healthcheck.assert_called_once()


def test_no_token_falls_to_local_mode(monkeypatch):
    monkeypatch.setattr(settings, "HUBSPOT_USE_MCP", True)
    monkeypatch.setattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", "")
    c = hubspot_client.HubSpotClient()
    assert c.mode == "local"


def test_rest_path_active_when_mcp_disabled(monkeypatch):
    monkeypatch.setattr(settings, "HUBSPOT_USE_MCP", False)
    monkeypatch.setattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", "test-token")
    c = hubspot_client.HubSpotClient()
    assert c.mode == "rest"
