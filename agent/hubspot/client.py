"""Thin HubSpot client — REST or MCP or local file fallback.

Falls back to `data/hubspot_local/` JSON files when no credentials set, so
dev and tests run without a HubSpot sandbox.

Token-bucket rate limiter caps at 100 calls / 10s.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.config import settings


# ────────────────────────────────────────────────────────────────────────────
# Rate limiter (token bucket)
# ────────────────────────────────────────────────────────────────────────────


class _TokenBucket:
    def __init__(self, rate: int, window_s: float) -> None:
        self.rate = rate
        self.window_s = window_s
        self._calls: collections.deque[float] = collections.deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            while self._calls and (now - self._calls[0]) > self.window_s:
                self._calls.popleft()
            if len(self._calls) >= self.rate:
                sleep_for = self.window_s - (now - self._calls[0])
                time.sleep(max(0.0, sleep_for))
            self._calls.append(time.monotonic())


_RATE = _TokenBucket(rate=100, window_s=10.0)


# ────────────────────────────────────────────────────────────────────────────
# Client
# ────────────────────────────────────────────────────────────────────────────


class HubSpotClient:
    """Unified HubSpot surface — MCP (preferred), REST, or local-file.

    Mode selection:
      1. `mcp`    — HUBSPOT_USE_MCP=true AND HUBSPOT_PRIVATE_APP_TOKEN set.
                    Day-0 readiness path. The MCP server must install and
                    start cleanly; a failure here raises, it does NOT fall
                    back to REST.
      2. `rest`   — HUBSPOT_USE_MCP=false AND HUBSPOT_PRIVATE_APP_TOKEN set.
                    Opt-in legacy mode; not Day-0-acceptable on its own.
      3. `local`  — no token. Writes to data/hubspot_local/ so tests run
                    offline. Never used against a real portal.
    """

    def __init__(self) -> None:
        self.token = settings.HUBSPOT_PRIVATE_APP_TOKEN
        self.base_url = settings.HUBSPOT_BASE_URL.rstrip("/")
        self._mcp: Any = None
        if self.token and settings.HUBSPOT_USE_MCP:
            # Share one stdio-bridged @hubspot/mcp-server subprocess across
            # every HubSpotClient instance in the process. Spawning two
            # bridges races their atexit shutdowns and emits EPIPE.
            from agent.hubspot.mcp_client import get_mcp
            self._mcp = get_mcp()        # raises on failure; no REST fallback
            self.mode = "mcp"
        elif self.token:
            self.mode = "rest"
        else:
            self.mode = "local"
            self._local_dir = Path("data/hubspot_local")
            self._local_dir.mkdir(parents=True, exist_ok=True)

    # ─── health ─────────────────────────────────────────────────────────
    def healthcheck(self) -> bool:
        if self.mode == "mcp":
            return self._mcp.healthcheck()
        if self.mode == "rest":
            try:
                import httpx
                r = httpx.get(
                    f"{self.base_url}/crm/v3/objects/contacts?limit=1",
                    headers=self._headers(), timeout=15,
                )
                return r.status_code == 200
            except Exception:  # noqa: BLE001
                return False
        return True  # local-mode is always healthy

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    # ─── properties ────────────────────────────────────────────────────
    # HubSpot property `groupName` per object type. Engagement object types
    # (`emails`, `tasks`, `meetings`) accept the synthetic group name
    # `<object>information`, which HubSpot creates on first write.
    _GROUP_BY_OBJECT = {
        "contacts": "contactinformation",
        "deals": "dealinformation",
        "emails": "emailinformation",
        "tasks": "taskinformation",
        "meetings": "meetinginformation",
    }

    def ensure_property(self, object_type: str, *, name: str, type: str, options: list[str] | None = None) -> bool:
        """Create a custom property on `object_type` if it does not exist.

        Supported object types: `contacts`, `deals`, `emails`, `tasks`,
        `meetings`. Returns True iff a new property was created.
        """
        return self._ensure_property(object_type, name=name, type=type, options=options)

    # Back-compat helpers — older callers reach for these directly.
    def ensure_contact_property(self, *, name: str, type: str, options: list[str] | None = None) -> bool:
        return self._ensure_property("contacts", name=name, type=type, options=options)

    def ensure_deal_property(self, *, name: str, type: str, options: list[str] | None = None) -> bool:
        return self._ensure_property("deals", name=name, type=type, options=options)

    def _ensure_property(self, object_type: str, *, name: str, type: str, options: list[str] | None) -> bool:
        if self.mode == "mcp":
            return self._mcp.ensure_property(object_type, name=name, type=type, options=options)
        if self.mode == "local":
            path = self._local_dir / f"schema_{object_type}.json"
            existing = self._read_json(path, default=[])
            if any(p.get("name") == name for p in existing):
                return False
            existing.append({"name": name, "type": type, "options": options or []})
            self._write_json(path, existing)
            return True
        # REST mode
        _RATE.acquire()
        import httpx
        r = httpx.get(
            f"{self.base_url}/crm/v3/properties/{object_type}/{name}",
            headers=self._headers(), timeout=15,
        )
        if r.status_code == 200:
            return False
        body: dict[str, Any] = {
            "name": name, "label": name,
            "type": "number" if type == "number" else ("datetime" if type == "datetime" else "string"),
            "fieldType": "text" if type == "string" else ("number" if type == "number" else "date"),
            "groupName": self._GROUP_BY_OBJECT.get(object_type, f"{object_type}information"),
        }
        if type == "enumeration" and options:
            body["type"] = "enumeration"
            body["fieldType"] = "select"
            body["options"] = [{"label": o, "value": o} for o in options]
        if type == "bool":
            body["type"] = "enumeration"
            body["fieldType"] = "booleancheckbox"
            body["options"] = [{"label": "true", "value": "true"}, {"label": "false", "value": "false"}]
        r = httpx.post(
            f"{self.base_url}/crm/v3/properties/{object_type}",
            headers=self._headers(), json=body, timeout=15,
        )
        return r.status_code in (200, 201)

    # ─── contacts / engagements ────────────────────────────────────────
    def upsert_contact(self, properties: dict[str, Any], *, email: str) -> str:
        if self.mode == "mcp":
            return self._mcp.upsert_contact(properties, email=email)
        if self.mode == "local":
            cid = self._local_upsert("contacts", key="email", value=email, properties=properties)
            return cid
        _RATE.acquire()
        import httpx
        body = {"properties": {**properties, "email": email}}
        r = httpx.post(
            f"{self.base_url}/crm/v3/objects/contacts",
            headers=self._headers(), json=body, timeout=15,
        )
        if r.status_code == 409:
            # exists: search and patch
            sr = httpx.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self._headers(),
                json={"filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}]},
                timeout=15,
            )
            cid = sr.json().get("results", [{}])[0].get("id", "")
            if cid:
                httpx.patch(
                    f"{self.base_url}/crm/v3/objects/contacts/{cid}",
                    headers=self._headers(), json={"properties": properties}, timeout=15,
                )
                return cid
        r.raise_for_status()
        return r.json().get("id", "")

    def create_engagement(self, engagement_type: str, body: dict[str, Any], *, associations: list[dict[str, Any]] | None = None) -> str:
        if self.mode == "mcp":
            return self._mcp.create_engagement(engagement_type, body, associations=associations)
        if self.mode == "local":
            payload = {
                "id": f"eng-{uuid.uuid4().hex[:12]}",
                "type": engagement_type,
                "body": body,
                "associations": associations or [],
                "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            path = self._local_dir / "engagements.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
            return payload["id"]
        _RATE.acquire()
        import httpx
        # HubSpot v3 engagements
        r = httpx.post(
            f"{self.base_url}/crm/v3/objects/{engagement_type.lower()}s",
            headers=self._headers(),
            json={"properties": body, "associations": associations or []},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("id", "")

    def create_deal(self, properties: dict[str, Any], *, contact_id: str | None = None) -> str:
        if self.mode == "mcp":
            return self._mcp.create_deal(properties, contact_id=contact_id)
        if self.mode == "local":
            did = self._local_upsert("deals", key="id", value=f"deal-{uuid.uuid4().hex[:12]}", properties=properties)
            return did
        _RATE.acquire()
        import httpx
        body = {"properties": properties}
        r = httpx.post(
            f"{self.base_url}/crm/v3/objects/deals",
            headers=self._headers(), json=body, timeout=15,
        )
        r.raise_for_status()
        return r.json().get("id", "")

    # ─── local-mode helpers ────────────────────────────────────────────
    def _local_upsert(self, bucket: str, *, key: str, value: str, properties: dict[str, Any]) -> str:
        path = self._local_dir / f"{bucket}.jsonl"
        rows: list[dict[str, Any]] = []
        if path.exists():
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
        idx = next((i for i, r in enumerate(rows) if r.get(key) == value or r.get("properties", {}).get(key) == value), None)
        if idx is None:
            record = {"id": f"{bucket}-{uuid.uuid4().hex[:12]}", key: value, "properties": properties,
                      "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
            rows.append(record)
        else:
            rows[idx]["properties"] = {**rows[idx].get("properties", {}), **properties}
            rows[idx]["updated_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return rows[idx if idx is not None else -1]["id"]

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
