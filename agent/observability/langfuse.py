"""Langfuse wrapper — spans, trace attributes, local-file fallback.

Every network call is best-effort: observability must never break the agent.
When Langfuse credentials are missing, spans are appended to
`data/local_traces.jsonl` instead so a dev loop works offline.

See __specs/10-observability.md for the trace attribute contract.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator

from agent.config import settings, config


_ALLOWED_ATTRS: set[str] = set(config.get("observability.allowed_attributes", []))


# ────────────────────────────────────────────────────────────────────────────
# Local fallback
# ────────────────────────────────────────────────────────────────────────────


def _local_trace_append(record: dict[str, Any]) -> None:
    path = Path(settings.LOCAL_TRACE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


# ────────────────────────────────────────────────────────────────────────────
# Langfuse client (lazy)
# ────────────────────────────────────────────────────────────────────────────


_langfuse_client = None
_langfuse_disabled = False


def _get_client() -> Any | None:
    """Return a Langfuse client if credentials are set and import succeeds.

    Never raises; returns None on any failure. Disables further attempts.
    """
    global _langfuse_client, _langfuse_disabled
    if _langfuse_disabled:
        return None
    if _langfuse_client is not None:
        return _langfuse_client
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        _langfuse_disabled = True
        return None
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        return _langfuse_client
    except Exception:  # noqa: BLE001
        _langfuse_disabled = True
        return None


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class TraceHandle:
    trace_id: str
    prefix: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def url(self) -> str:
        host = settings.LANGFUSE_HOST.rstrip("/")
        project = settings.LANGFUSE_PROJECT_ID or "local"
        return f"{host}/project/{project}/traces/{self.trace_id}"


def new_trace(name: str, attributes: dict[str, Any] | None = None) -> TraceHandle:
    trace_id = f"{settings.LANGFUSE_TRACE_PREFIX}_{uuid.uuid4().hex[:12]}"
    attrs = _filter_attrs(attributes or {})
    handle = TraceHandle(trace_id=trace_id, prefix=name, attributes=attrs)

    client = _get_client()
    if client is not None:
        try:
            client.trace(id=trace_id, name=name, metadata=attrs)
        except Exception:  # noqa: BLE001
            pass

    _local_trace_append({
        "kind": "trace_start",
        "trace_id": trace_id,
        "name": name,
        "attributes": attrs,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    return handle


@contextmanager
def span(name: str, trace: TraceHandle | None = None, **attributes: Any) -> Iterator[dict[str, Any]]:
    """Context manager around a unit of agent work.

    Usage:
        with span("composer.draft", trace=trace, prospect_domain=d) as s:
            ...
            s["cost.usd"] = 0.012
    """
    span_id = uuid.uuid4().hex[:12]
    start = dt.datetime.now(dt.timezone.utc)
    trace_id = trace.trace_id if trace else None
    trace_attrs = trace.attributes if trace else {}
    span_attrs = _filter_attrs({**trace_attrs, **attributes})
    mutable: dict[str, Any] = {**span_attrs}

    try:
        yield mutable
        status = "ok"
        error = None
    except Exception as e:  # noqa: BLE001 - record and re-raise
        status = "error"
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        end = dt.datetime.now(dt.timezone.utc)
        duration_ms = int((end - start).total_seconds() * 1000)

        payload = {
            "kind": "span",
            "span_id": span_id,
            "trace_id": trace_id,
            "name": name,
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            "attributes": _filter_attrs(mutable),
        }
        _local_trace_append(payload)

        client = _get_client()
        if client is not None:
            try:
                client.event(
                    trace_id=trace_id,
                    name=name,
                    start_time=start,
                    end_time=end,
                    metadata=payload["attributes"],
                    level="ERROR" if status == "error" else "DEFAULT",
                )
            except Exception:  # noqa: BLE001
                pass


def deliver_span(channel: str, to: str, sink: bool, payload: Any) -> None:
    """Emit a deliver.<channel> span. Called from the kill switch only."""
    with span(
        f"deliver.{channel}",
        **{
            "channel": channel,
            "to_resolved": to,
            "kill_switch.state": "sink" if sink else "live",
        },
    ):
        # The work is the delivery itself; we just record.
        return


def healthcheck() -> bool:
    """Return True if Langfuse is reachable OR local-mode is working."""
    # Local mode is always true if we can write the trace file.
    try:
        path = Path(settings.LOCAL_TRACE_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        _local_trace_append({
            "kind": "healthcheck",
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
    except Exception:  # noqa: BLE001
        return False
    return True


def _filter_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Drop non-allowlisted attributes per spec 10.

    An empty allowlist passes everything through (dev mode). A populated
    allowlist drops keys not on it so traces never leak raw brief content.
    """
    if not _ALLOWED_ATTRS:
        return dict(attrs)
    return {k: v for k, v in attrs.items() if k in _ALLOWED_ATTRS or "." in k and k.split(".")[0] in _ALLOWED_ATTRS}
