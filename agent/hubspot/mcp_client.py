"""HubSpot MCP client.

Spawns the official HubSpot MCP server (`@hubspot/mcp-server`) over stdio
and issues CRM tool calls via the Model Context Protocol. The Python
agent imports HubSpotMcp and uses the same method surface as the REST
client, but every call routes through the MCP session.

Day-0 readiness requires the MCP path to be live. If the server process
cannot start, this module raises — we do NOT silently fall back to REST.

Install the server once per machine:

    npm install -g @hubspot/mcp-server

Then set in .env:

    HUBSPOT_USE_MCP=true
    HUBSPOT_PRIVATE_APP_TOKEN=<token>   # mirrored into PRIVATE_APP_ACCESS_TOKEN
                                        # for the upstream server process.

See infra/hubspot_mcp.md.

Tool-name mapping (verified against @hubspot/mcp-server as of April 2026):

    hubspot-get-user-details           — auth + owner-id lookup
    hubspot-search-objects             — search contacts/deals/etc.
    hubspot-batch-create-objects       — create (wraps single create in inputs[])
    hubspot-batch-update-objects       — update by id
    hubspot-batch-read-objects         — read by id
    hubspot-get-property               — probe schema for a property
    hubspot-create-property            — create custom property
    hubspot-create-engagement          — create NOTE / TASK only
                                         (emails/meetings use batch-create-objects
                                          with objectType=emails/meetings)
"""
from __future__ import annotations

import asyncio
import atexit
import datetime as dt
import json
import os
import re
import time
from typing import Any

from agent.config import settings
from agent.observability.langfuse import _LF_INPUT, _LF_OUTPUT, span


class HubSpotMcpError(RuntimeError):
    """Raised when the MCP path is unavailable. Does not fall back."""


_singleton: "HubSpotMcp | None" = None


def get_mcp() -> "HubSpotMcp":
    """Return the process-wide HubSpot MCP client.

    The @hubspot/mcp-server is a stdio-bridged Node subprocess. Spawning two
    of them in one Python process leads to EPIPE on shutdown when the
    atexit hooks race each other's pipes. One subprocess per process is
    sufficient, so all HubSpotClient instances share the same bridge.
    """
    global _singleton
    if _singleton is None:
        _singleton = HubSpotMcp()
    return _singleton


class HubSpotMcp:
    """Stdio-bridged HubSpot MCP client.

    The MCP Python SDK is async-native; this class wraps the session in a
    private event loop so the synchronous agent can keep its interface.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: Any = None
        self._client_ctx: Any = None
        self._stdio_ctx: Any = None
        self._owner_id: int | None = None
        # HubSpot object types the private-app token cannot manage (403).
        # Populated by `_ensure_property`; consulted by engagement writers
        # to strip custom `tenacious_*` properties before the write.
        self.unsupported_object_types: set[str] = set()
        self._ensure_deps()
        self._start()
        atexit.register(self._shutdown_sync)

    # ─── lifecycle ─────────────────────────────────────────────────────
    def _ensure_deps(self) -> None:
        try:
            import mcp  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise HubSpotMcpError(
                "Python `mcp` SDK not installed. `pip install -r agent/requirements.txt`."
            ) from e
        if not settings.HUBSPOT_PRIVATE_APP_TOKEN:
            raise HubSpotMcpError(
                "HUBSPOT_PRIVATE_APP_TOKEN unset. The MCP server refuses to start without it."
            )

    def _start(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._loop = asyncio.new_event_loop()
        # @hubspot/mcp-server reads PRIVATE_APP_ACCESS_TOKEN.
        env = {
            **os.environ,
            "PRIVATE_APP_ACCESS_TOKEN": settings.HUBSPOT_PRIVATE_APP_TOKEN,
            "HUBSPOT_PRIVATE_APP_TOKEN": settings.HUBSPOT_PRIVATE_APP_TOKEN,
        }
        params = StdioServerParameters(
            command="npx", args=["-y", "@hubspot/mcp-server"], env=env,
        )

        async def _open() -> None:
            self._stdio_ctx = stdio_client(params)
            read, write = await self._stdio_ctx.__aenter__()
            self._client_ctx = ClientSession(read, write)
            self._session = await self._client_ctx.__aenter__()
            await self._session.initialize()

        try:
            self._loop.run_until_complete(_open())
        except Exception as e:  # noqa: BLE001
            raise HubSpotMcpError(
                f"Failed to start HubSpot MCP server via `npx -y @hubspot/mcp-server`: {e}. "
                "Confirm Node.js is installed and `npm install -g @hubspot/mcp-server` succeeded. "
                "See infra/hubspot_mcp.md."
            ) from e

    def _shutdown_sync(self) -> None:
        if self._loop is None or self._loop.is_closed():
            return

        async def _close() -> None:
            try:
                if self._client_ctx is not None:
                    await self._client_ctx.__aexit__(None, None, None)
            finally:
                if self._stdio_ctx is not None:
                    await self._stdio_ctx.__aexit__(None, None, None)

        try:
            self._loop.run_until_complete(_close())
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._loop.close()

    # ─── core call ─────────────────────────────────────────────────────
    def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        assert self._session is not None and self._loop is not None

        async def _call() -> Any:
            res = await self._session.call_tool(tool_name, arguments=arguments)
            parts = res.content or []
            # @hubspot/mcp-server marks some not-found cases with isError=False
            # and a text body like "Unknown tool" — check text bodies too.
            first_text = None
            if parts:
                first_text = getattr(parts[0], "text", None)
            if getattr(res, "isError", False):
                raise HubSpotMcpError(_friendly(tool_name, first_text or str(parts)))
            if first_text is not None:
                if first_text.startswith("Unknown tool"):
                    raise HubSpotMcpError(f"MCP tool {tool_name!r} errored: {first_text}")
                # @hubspot/mcp-server returns HTTP errors as TEXT (not isError),
                # so we detect the HubSpot error envelope in the body.
                if _looks_like_hubspot_api_error(first_text):
                    raise HubSpotMcpError(_friendly(tool_name, first_text))
                try:
                    return json.loads(first_text)
                except json.JSONDecodeError:
                    return first_text
            return parts

        # Auto-attached span: every MCP tool invocation gets a Langfuse span
        # with tool_name + arguments (input) + result (output) + retry-aware
        # latency + status. Picks up the in-scope trace from contextvar.
        with span(f"hubspot.mcp.{tool_name}", **{"hubspot.tool_name": tool_name}) as s:
            s[_LF_INPUT] = arguments

            # Retry transient transport errors (Node `fetch failed`, DNS hiccups,
            # 502/503/504, socket resets). Logical HubSpot errors (validation,
            # missing scopes, property-not-found) bubble up immediately.
            last_err: HubSpotMcpError | None = None
            attempts = 0
            for attempt in range(3):
                attempts = attempt + 1
                try:
                    result = self._loop.run_until_complete(_call())
                    s[_LF_OUTPUT] = result
                    s["hubspot.attempts"] = attempts
                    return result
                except HubSpotMcpError as e:
                    if not _is_transient(str(e)) or attempt == 2:
                        s["hubspot.attempts"] = attempts
                        raise
                    last_err = e
                    time.sleep(0.6 * (2 ** attempt))
            assert last_err is not None
            s["hubspot.attempts"] = attempts
            raise last_err

    # ─── health + owner ────────────────────────────────────────────────
    def healthcheck(self) -> bool:
        try:
            self.call("hubspot-get-user-details", {})
            return True
        except Exception:  # noqa: BLE001
            return False

    def _get_owner_id(self) -> int:
        if self._owner_id is not None:
            return self._owner_id
        if settings.HUBSPOT_OWNER_ID_DEFAULT:
            try:
                self._owner_id = int(settings.HUBSPOT_OWNER_ID_DEFAULT)
                return self._owner_id
            except ValueError:
                pass
        info = self.call("hubspot-get-user-details", {})
        candidate = _extract_owner_id(info)
        if candidate is None:
            raise HubSpotMcpError(
                "Could not determine HubSpot owner id from get-user-details "
                f"(received {type(info).__name__}: {str(info)[:200]!r}). "
                "Set HUBSPOT_OWNER_ID_DEFAULT in .env to bypass auto-detection — "
                "find the id at HubSpot → Settings → Users & Teams → click your "
                "user → the URL contains the id."
            )
        self._owner_id = int(candidate)
        return self._owner_id

    # ─── properties ────────────────────────────────────────────────────
    # Property `groupName` per HubSpot object type. Engagement types use
    # the synthetic `<object>information` group, which HubSpot accepts and
    # creates on first write.
    _GROUP_BY_OBJECT = {
        "contacts": "contactinformation",
        "deals": "dealinformation",
        "emails": "emailinformation",
        "tasks": "taskinformation",
        "meetings": "meetinginformation",
    }

    def ensure_property(self, object_type: str, *, name: str, type: str, options: list[str] | None = None) -> bool:
        return self._ensure_property(object_type, name=name, type=type, options=options)

    def ensure_contact_property(self, *, name: str, type: str, options: list[str] | None = None) -> bool:
        return self._ensure_property("contacts", name=name, type=type, options=options)

    def ensure_deal_property(self, *, name: str, type: str, options: list[str] | None = None) -> bool:
        return self._ensure_property("deals", name=name, type=type, options=options)

    # Engagement object types — custom properties on these are best-effort:
    # default property groups (e.g. `meetinginformation`) don't exist on every
    # portal, and several private-app scopes are needed to even view the
    # schema. If anything goes wrong while ensuring a property here, we mark
    # the object type unsupported and let the engagement writer strip
    # `tenacious_*` keys from the body.
    _ENGAGEMENT_OBJECT_TYPES = frozenset({"emails", "meetings", "tasks", "calls", "notes"})

    def _ensure_property(self, object_type: str, *, name: str, type: str, options: list[str] | None) -> bool:
        # Memoised per-process: object types the token can't manage are
        # silently skipped. Engagement writers consult this set and strip
        # `tenacious_*` properties before attempting the write.
        if object_type in self.unsupported_object_types:
            return False
        is_engagement = object_type in self._ENGAGEMENT_OBJECT_TYPES
        try:
            self.call("hubspot-get-property", {"objectType": object_type, "propertyName": name})
            return False
        except HubSpotMcpError as e:
            msg = str(e)
            if _looks_like_object_scope_denied(msg):
                # Token lacks scope to view this object's property schema. Skip
                # and remember — we cannot create the property either.
                self.unsupported_object_types.add(object_type)
                return False
            # Treat "property not found" as missing. For engagement types
            # tolerate any other read error (validation / scope quirks) and
            # try the create anyway; if that fails too, mark unsupported.
            if not _looks_like_property_missing(msg) and not is_engagement:
                raise
        payload: dict[str, Any] = {
            "objectType": object_type,
            "name": name,
            "label": name,
            "groupName": self._GROUP_BY_OBJECT.get(object_type, f"{object_type}information"),
            "type": _normalize_prop_type(type, options),
            "fieldType": _normalize_field_type(type, options),
        }
        if type == "enumeration" and options:
            payload["options"] = [{"label": o, "value": o} for o in options]
        if type == "bool":
            payload["options"] = [{"label": "true", "value": "true"}, {"label": "false", "value": "false"}]
        try:
            self.call("hubspot-create-property", payload)
            return True
        except HubSpotMcpError as e:
            if is_engagement or _looks_like_object_scope_denied(str(e)):
                # Engagements: any failure (group missing, scope, validation)
                # is recoverable — strip `tenacious_*` from the eventual write.
                self.unsupported_object_types.add(object_type)
                return False
            raise

    # ─── contacts ──────────────────────────────────────────────────────
    def upsert_contact(self, properties: dict[str, Any], *, email: str) -> str:
        props = _stringify(properties)
        props["email"] = email

        search = self.call(
            "hubspot-search-objects",
            {
                "objectType": "contacts",
                "filterGroups": [
                    {"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}
                ],
                "properties": ["email"],
                "limit": 1,
            },
        ) or {}
        results = search.get("results") if isinstance(search, dict) else None

        if results:
            cid = str(results[0].get("id") or "")
            self.call(
                "hubspot-batch-update-objects",
                {"objectType": "contacts", "inputs": [{"id": cid, "properties": props}]},
            )
            return cid

        created = self.call(
            "hubspot-batch-create-objects",
            {"objectType": "contacts", "inputs": [{"properties": props}]},
        )
        return _first_id(created)

    # ─── deals ─────────────────────────────────────────────────────────
    def create_deal(self, properties: dict[str, Any], *, contact_id: str | None = None) -> str:
        props = _stringify(properties)
        input_obj: dict[str, Any] = {"properties": props}
        if contact_id:
            input_obj["associations"] = [{
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
                "to": {"id": str(contact_id)},
            }]
        created = self.call(
            "hubspot-batch-create-objects",
            {"objectType": "deals", "inputs": [input_obj]},
        )
        return _first_id(created)

    # ─── engagements ───────────────────────────────────────────────────
    def create_engagement(
        self,
        engagement_type: str,
        body: dict[str, Any],
        *,
        associations: list[dict[str, Any]] | None = None,
    ) -> str:
        """Unified engagement create surface.

        HubSpot MCP splits engagement creation:
          - NOTE, TASK               → hubspot-create-engagement
          - EMAIL, MEETING, CALL     → hubspot-batch-create-objects with
                                        objectType in {emails, meetings, calls}
        """
        et = (engagement_type or "").lower()
        contact_ids = _contact_ids_from(associations or [])

        if et in ("note", "task"):
            metadata = _engagement_metadata_for_note_task(et, body)
            payload: dict[str, Any] = {
                "type": et.upper(),
                "ownerId": self._get_owner_id(),
                "associations": {"contactIds": contact_ids},
                "metadata": metadata,
            }
            ts = body.get("hs_timestamp") or body.get("timestamp")
            if ts:
                payload["timestamp"] = _to_epoch_ms(ts)
            created = self.call("hubspot-create-engagement", payload)
            return str((created or {}).get("engagementId") or (created or {}).get("id") or "")

        # Email / meeting / call: batch-create-objects with typed properties.
        object_type = {"email": "emails", "meeting": "meetings", "call": "calls"}.get(et, et + "s")
        props = _stringify(body)
        if object_type in self.unsupported_object_types:
            # Token can't manage custom properties on this object type. Drop
            # `tenacious_*` keys and embed the metadata into the body text
            # so trace_id / message_id / tone_scores are still recoverable.
            props = self._strip_tenacious_props(props, object_type)
        input_obj: dict[str, Any] = {"properties": props}
        if contact_ids:
            input_obj["associations"] = [
                {
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": _contact_assoc_type(et)}],
                    "to": {"id": str(cid)},
                }
                for cid in contact_ids
            ]
        try:
            created = self.call(
                "hubspot-batch-create-objects",
                {"objectType": object_type, "inputs": [input_obj]},
            )
        except HubSpotMcpError as e:
            # If the schema check passed earlier (or wasn't run) but the write
            # still hits PROPERTY_DOESNT_EXIST, mark the object type unsupported
            # and retry once with `tenacious_*` keys stripped.
            if not _looks_like_property_missing(str(e)):
                raise
            self.unsupported_object_types.add(object_type)
            input_obj["properties"] = self._strip_tenacious_props(props, object_type)
            created = self.call(
                "hubspot-batch-create-objects",
                {"objectType": object_type, "inputs": [input_obj]},
            )
        return _first_id(created)

    @staticmethod
    def _strip_tenacious_props(props: dict[str, Any], object_type: str) -> dict[str, Any]:
        """Remove tenacious_* keys; preserve their values in a body field so
        the trace remains recoverable from HubSpot UI."""
        keep: dict[str, Any] = {}
        dropped: dict[str, Any] = {}
        for k, v in props.items():
            if k.startswith("tenacious_"):
                dropped[k] = v
            else:
                keep[k] = v
        if not dropped:
            return keep
        # Stash the dropped meta in the most appropriate body field per object.
        body_field = {
            "emails": "hs_email_text",
            "meetings": "hs_meeting_body",
            "tasks": "hs_task_body",
        }.get(object_type, "hs_email_text")
        existing = str(keep.get(body_field, "") or "")
        meta = " ".join(f"{k}={v}" for k, v in sorted(dropped.items()))
        keep[body_field] = (existing + ("\n\n" if existing else "") +
                            f"---\n[tenacious-meta] {meta}")
        return keep


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _extract_owner_id(info: Any) -> str | int | None:
    """Pull a HubSpot owner / user id out of whatever shape MCP returned.

    `hubspot-get-user-details` returns a dict on some releases and a plain
    text string on others (sometimes JSON-encoded inside that string,
    sometimes a free-form `"User: 12345 ..."` blurb). Handle all three.
    """
    if isinstance(info, dict):
        return (
            info.get("user_id") or info.get("userId") or info.get("ownerId")
            or info.get("owner_id") or (info.get("user") or {}).get("id")
        )
    if isinstance(info, str) and info:
        try:
            parsed = json.loads(info)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            cand = _extract_owner_id(parsed)
            if cand is not None:
                return cand
        # Last resort: pull the first plausibly id-shaped integer (6-12 digits).
        m = re.search(r"\b(\d{6,12})\b", info)
        if m:
            return m.group(1)
    return None


def _looks_like_hubspot_api_error(text: str) -> bool:
    return "HubSpot API Error:" in text or '"category":"VALIDATION_ERROR"' in text or '"category":"MISSING_SCOPES"' in text


_TRANSIENT_MARKERS = (
    "fetch failed", "econnreset", "etimedout", "enotfound", "eai_again",
    "socket hang up", "network error", "request timeout",
    "503 service", "502 bad gateway", "504 gateway", "429",
)


def _is_transient(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _TRANSIENT_MARKERS)


def _looks_like_property_missing(text: str) -> bool:
    low = text.lower()
    return (
        "property_doesnt_exist" in low
        or "property does not exist" in low
        or '"propertyname"' in low and "does not exist" in low
        or "no property named" in low
        or "404" in low and "property" in low
    )


def _looks_like_object_scope_denied(text: str) -> bool:
    """403 because the private-app token lacks scope to view/manage this object type."""
    low = text.lower()
    return (
        "403" in low and (
            "do not have permissions" in low
            or "missing_scopes" in low
            or "requires one of" in low
        )
    )


def _friendly(tool_name: str, raw: str) -> str:
    """Translate common HubSpot API errors into actionable messages."""
    low = raw.lower()
    if "missing_scopes" in low or "required scopes" in low:
        return (
            f"MCP tool {tool_name!r} got 403 MISSING_SCOPES from HubSpot. "
            "The private-app token is missing scopes required for this operation. "
            "Grant every scope listed in infra/hubspot_mcp.md → 'Required private-app scopes', "
            "regenerate the token, and update HUBSPOT_PRIVATE_APP_TOKEN in .env. "
            f"Raw response: {raw[:400]}"
        )
    if "invalid_email" in low:
        return (
            f"MCP tool {tool_name!r} got 400 INVALID_EMAIL from HubSpot. "
            "HubSpot rejects `.example`, `.test`, `.invalid` TLDs; use `@example.com` "
            f"for Day-0 smoke. Raw: {raw[:300]}"
        )
    if "property_doesnt_exist" in low or "does not exist" in low and '"propertyname"' in low:
        return (
            f"MCP tool {tool_name!r} got 400 PROPERTY_DOESNT_EXIST. "
            "Create the missing tenacious_* custom property first via "
            "agent.hubspot.schema.ensure_all(client). See infra/hubspot_mcp.md. "
            f"Raw: {raw[:300]}"
        )
    return f"MCP tool {tool_name!r} errored: {raw[:500]}"


def _normalize_prop_type(t: str, options: list[str] | None) -> str:
    if t == "number":
        return "number"
    if t == "datetime":
        return "datetime"
    if t == "date":
        return "date"
    if t == "enumeration" and options:
        return "enumeration"
    if t == "bool":
        return "enumeration"   # MCP server expects enum+booleancheckbox for bool
    return "string"


def _normalize_field_type(t: str, options: list[str] | None) -> str:
    if t == "number":
        return "number"
    if t == "datetime" or t == "date":
        return "date"
    if t == "enumeration" and options:
        return "select"
    if t == "bool":
        return "booleancheckbox"
    return "text"


def _stringify(properties: dict[str, Any]) -> dict[str, str]:
    """All property values in HubSpot batch-create/update must be strings."""
    out: dict[str, str] = {}
    for k, v in properties.items():
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = "true" if v else "false"
        elif isinstance(v, (int, float)):
            out[k] = str(v)
        elif isinstance(v, (dict, list)):
            out[k] = json.dumps(v, default=str)
        else:
            out[k] = str(v)
    return out


def _first_id(batch_response: Any) -> str:
    if not isinstance(batch_response, dict):
        return ""
    results = batch_response.get("results") or []
    if not results:
        return ""
    return str(results[0].get("id") or "")


def _contact_ids_from(associations: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    for a in associations or []:
        to = a.get("to_id") or a.get("to", {}).get("id")
        if not to:
            continue
        try:
            ids.append(int(to))
        except (TypeError, ValueError):
            # Skip non-numeric IDs (e.g. local-mode fake ids); the real
            # HubSpot path requires numeric object IDs.
            continue
    return ids


def _contact_assoc_type(engagement_type: str) -> int:
    # HubSpot default association-type IDs between contacts and engagements
    # (from the HubSpot associations reference).
    return {
        "email": 198,      # contact_to_email
        "meeting": 200,    # contact_to_meeting
        "call": 194,       # contact_to_call
    }.get(engagement_type, 1)


def _engagement_metadata_for_note_task(et: str, body: dict[str, Any]) -> dict[str, Any]:
    if et == "note":
        return {"body": str(body.get("hs_note_body") or body.get("body") or "")}
    # task
    return {
        "body": str(body.get("hs_task_body") or body.get("body") or ""),
        "subject": str(body.get("hs_task_subject") or body.get("subject") or "(no subject)"),
        "status": str(body.get("hs_task_status") or "NOT_STARTED"),
        "priority": str(body.get("hs_task_priority") or "MEDIUM"),
        "forObjectType": "CONTACT",
    }


def _to_epoch_ms(ts: Any) -> int:
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        try:
            return int(dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
