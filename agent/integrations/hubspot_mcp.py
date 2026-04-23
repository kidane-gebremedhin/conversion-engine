"""HubSpot client — MCP primary, REST fallback, local fixture for no-token dev.

Mode selection (HUBSPOT_CLIENT_MODE overrides; auto otherwise):
  - ``mcp``   — spawn the in-repo MCP server as a subprocess, speak stdio MCP.
                Default when HUBSPOT_PRIVATE_APP_TOKEN is set.
  - ``rest``  — direct REST with the same Private App token (no MCP hop).
  - ``local`` — write JSON fixtures under data/hubspot_local/. No token needed.
                Default when no token is set.

The MCP server implementation lives in ``hubspot_mcp_server.py``; REST helpers
in ``hubspot_rest.py``. See __specs/08 for the tool-surface contract.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import threading
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from agent import tracing
from agent.integrations import hubspot_rest

_LOCAL = pathlib.Path("data/hubspot_local")
_LOCK = threading.Lock()


@dataclass
class CompanyUpsert:
    crunchbase_uuid: str
    name: str
    domain: str | None
    industry: str | None
    country: str | None
    employees: str | None
    convergine: dict[str, Any]


@dataclass
class ContactUpsert:
    email: str
    first_name: str
    last_name: str
    job_title: str
    company_id: str
    preferred_channel: str = "email"
    synthetic: bool = True


@dataclass
class DealCreate:
    company_id: str
    contact_id: str
    dealname: str
    amount: int
    convergine_segment: int | None
    convergine_thread_id: str


@dataclass
class ConversationEvent:
    event_id: str
    contact_id: str
    company_id: str
    event_type: str
    channel: str
    trace_id: str
    payload_json: dict[str, Any]
    draft: bool


class MissingCrunchbaseUuid(Exception):
    pass


# --------------------------------------------------------------------------- #
# MCP bridge — runs an asyncio loop in a background thread and forwards
# synchronous tool calls from the main agent loop into it.
# --------------------------------------------------------------------------- #

class _McpBridge:
    def __init__(self, token: str, *, startup_timeout: float = 15.0) -> None:
        self._token = token
        self._loop = asyncio.new_event_loop()
        self._session: Any = None
        self._exit_stack: AsyncExitStack | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="hubspot-mcp-bridge")
        self._thread.start()
        if not self._ready.wait(timeout=startup_timeout):
            raise RuntimeError("HubSpot MCP bridge failed to start within timeout")
        if self._startup_error:
            raise self._startup_error

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._startup())
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            return
        self._loop.run_forever()

    async def _startup(self) -> None:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        self._exit_stack = AsyncExitStack()
        server_env = {**os.environ, "HUBSPOT_PRIVATE_APP_TOKEN": self._token}
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agent.integrations.hubspot_mcp_server"],
            env=server_env,
        )
        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        self._ready.set()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        async def _call() -> Any:
            return await self._session.call_tool(name, arguments)

        fut = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        result = fut.result(timeout=30)
        if getattr(result, "isError", False):
            raise RuntimeError(f"MCP tool {name} returned error: {result}")
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text is not None:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"text": text}
        return None

    def close(self) -> None:
        if self._exit_stack is not None:
            try:
                fut = asyncio.run_coroutine_threadsafe(self._exit_stack.aclose(), self._loop)
                fut.result(timeout=5)
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)


# --------------------------------------------------------------------------- #

def _resolve_mode(token: str | None) -> str:
    explicit = os.environ.get("HUBSPOT_CLIENT_MODE", "").strip().lower()
    if explicit in {"mcp", "rest", "local"}:
        return explicit
    return "mcp" if token else "local"


class HubSpotClient:
    def __init__(self, *, mcp_url: str | None = None, token: str | None = None) -> None:
        self.mcp_url = mcp_url
        self.token = token
        self.mode = _resolve_mode(token)
        self._bridge: _McpBridge | None = None
        if self.mode == "mcp":
            # Token is required in mcp mode; fall through to local otherwise.
            if not token:
                self.mode = "local"
            else:
                self._bridge = _McpBridge(token)
        if self.mode == "local":
            _LOCAL.mkdir(parents=True, exist_ok=True)
            for sub in ("companies", "contacts", "deals", "events"):
                (_LOCAL / sub).mkdir(exist_ok=True)

    def close(self) -> None:
        if self._bridge is not None:
            self._bridge.close()
            self._bridge = None

    # --- companies --------------------------------------------------------- #

    def upsert_company(self, c: CompanyUpsert) -> str:
        if not c.crunchbase_uuid:
            raise MissingCrunchbaseUuid
        with tracing.span("hubspot.upsert_company", crunchbase_uuid=c.crunchbase_uuid):
            if self.mode == "mcp":
                return self._bridge.call_tool(
                    "upsert_company",
                    {
                        "crunchbase_uuid": c.crunchbase_uuid,
                        "name": c.name,
                        "domain": c.domain,
                        "industry": c.industry,
                        "country": c.country,
                        "employees": c.employees,
                        "convergine": c.convergine,
                    },
                )["id"]
            if self.mode == "rest":
                return hubspot_rest.rest_upsert_company(
                    self.token,  # type: ignore[arg-type]
                    crunchbase_uuid=c.crunchbase_uuid,
                    name=c.name,
                    domain=c.domain,
                    industry=c.industry,
                    country=c.country,
                    employees=c.employees,
                    convergine=c.convergine,
                )
            return self._local_upsert("companies", c.crunchbase_uuid, _company_doc(c))

    def find_company_by_crunchbase_uuid(self, uuid_: str) -> str | None:
        if self.mode == "mcp":
            return self._bridge.call_tool(
                "find_company_by_crunchbase_uuid", {"crunchbase_uuid": uuid_}
            )["id"]
        if self.mode == "rest":
            return hubspot_rest.rest_find_company_by_crunchbase_uuid(self.token, uuid_)  # type: ignore[arg-type]
        p = _LOCAL / "companies" / f"{uuid_}.json"
        return uuid_ if p.exists() else None

    # --- contacts ---------------------------------------------------------- #

    def upsert_contact(self, contact: ContactUpsert) -> str:
        with tracing.span("hubspot.upsert_contact"):
            if self.mode == "mcp":
                return self._bridge.call_tool(
                    "upsert_contact",
                    {
                        "email": contact.email,
                        "first_name": contact.first_name,
                        "last_name": contact.last_name,
                        "job_title": contact.job_title,
                        "company_id": contact.company_id,
                        "preferred_channel": contact.preferred_channel,
                        "synthetic": contact.synthetic,
                    },
                )["id"]
            if self.mode == "rest":
                return hubspot_rest.rest_upsert_contact(
                    self.token,  # type: ignore[arg-type]
                    email=contact.email,
                    first_name=contact.first_name,
                    last_name=contact.last_name,
                    job_title=contact.job_title,
                    company_id=contact.company_id,
                    preferred_channel=contact.preferred_channel,
                    synthetic=contact.synthetic,
                )
            key = contact.email.replace("@", "_at_")
            return self._local_upsert("contacts", key, _contact_doc(contact))

    # --- deals ------------------------------------------------------------- #

    def create_deal(self, deal: DealCreate) -> str:
        with tracing.span("hubspot.create_deal"):
            if self.mode == "mcp":
                return self._bridge.call_tool(
                    "create_deal",
                    {
                        "company_id": deal.company_id,
                        "contact_id": deal.contact_id,
                        "dealname": deal.dealname,
                        "amount": deal.amount,
                        "convergine_segment": deal.convergine_segment,
                        "convergine_thread_id": deal.convergine_thread_id,
                    },
                )["id"]
            if self.mode == "rest":
                return hubspot_rest.rest_create_deal(
                    self.token,  # type: ignore[arg-type]
                    company_id=deal.company_id,
                    contact_id=deal.contact_id,
                    dealname=deal.dealname,
                    amount=deal.amount,
                    convergine_segment=deal.convergine_segment,
                    convergine_thread_id=deal.convergine_thread_id,
                )
            deal_id = f"deal_{uuid.uuid4().hex[:10]}"
            return self._local_upsert("deals", deal_id, _deal_doc(deal, deal_id))

    def advance_deal_stage(self, deal_id: str, stage: str) -> None:
        with tracing.span("hubspot.advance_deal_stage"):
            if self.mode == "mcp":
                self._bridge.call_tool("advance_deal_stage", {"deal_id": deal_id, "stage": stage})
                return
            if self.mode == "rest":
                hubspot_rest.rest_advance_deal_stage(self.token, deal_id=deal_id, stage=stage)  # type: ignore[arg-type]
                return
            p = _LOCAL / "deals" / f"{deal_id}.json"
            if p.exists():
                doc = json.loads(p.read_text())
                doc["dealstage"] = stage
                p.write_text(json.dumps(doc, indent=2))

    # --- events ------------------------------------------------------------ #

    def log_event(self, ev: ConversationEvent) -> None:
        with tracing.span("hubspot.log_event", event_type=ev.event_type):
            if self.mode == "mcp":
                self._bridge.call_tool(
                    "log_event",
                    {
                        "event_id": ev.event_id,
                        "contact_id": ev.contact_id,
                        "company_id": ev.company_id,
                        "event_type": ev.event_type,
                        "channel": ev.channel,
                        "trace_id": ev.trace_id,
                        "payload_json": ev.payload_json,
                        "draft": ev.draft,
                    },
                )
                return
            if self.mode == "rest":
                hubspot_rest.rest_log_event(
                    self.token,  # type: ignore[arg-type]
                    event_id=ev.event_id,
                    contact_id=ev.contact_id,
                    company_id=ev.company_id,
                    event_type=ev.event_type,
                    channel=ev.channel,
                    trace_id=ev.trace_id,
                    payload_json=ev.payload_json,
                    draft=ev.draft,
                )
                return
            self._local_upsert("events", ev.event_id, _event_doc(ev))

    # --- local helpers ----------------------------------------------------- #

    def _local_upsert(self, kind: str, key: str, doc: dict[str, Any]) -> str:
        with _LOCK:
            p = _LOCAL / kind / f"{key}.json"
            p.write_text(json.dumps(doc, indent=2))
        return key


# --------------------------------------------------------------------------- #

def _company_doc(c: CompanyUpsert) -> dict[str, Any]:
    return {
        "name": c.name,
        "domain": c.domain,
        "industry": c.industry,
        "country": c.country,
        "numberofemployees": c.employees,
        "convergine_crunchbase_uuid": c.crunchbase_uuid,
        **{f"convergine_{k}": v for k, v in c.convergine.items()},
    }


def _contact_doc(contact: ContactUpsert) -> dict[str, Any]:
    return {
        "email": contact.email,
        "firstname": contact.first_name,
        "lastname": contact.last_name,
        "jobtitle": contact.job_title,
        "associatedcompanyid": contact.company_id,
        "convergine_preferred_channel": contact.preferred_channel,
        "convergine_synthetic": contact.synthetic,
    }


def _deal_doc(deal: DealCreate, deal_id: str) -> dict[str, Any]:
    return {
        "id": deal_id,
        "company_id": deal.company_id,
        "contact_id": deal.contact_id,
        "dealname": deal.dealname,
        "pipeline": "default",
        "dealstage": "appointmentscheduled",
        "amount": deal.amount,
        "convergine_segment": deal.convergine_segment,
        "convergine_thread_id": deal.convergine_thread_id,
    }


def _event_doc(ev: ConversationEvent) -> dict[str, Any]:
    return {
        "event_id": ev.event_id,
        "contact_id": ev.contact_id,
        "company_id": ev.company_id,
        "event_type": ev.event_type,
        "channel": ev.channel,
        "trace_id": ev.trace_id,
        "payload_json": ev.payload_json,
        "draft": ev.draft,
    }
