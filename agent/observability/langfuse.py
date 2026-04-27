"""Langfuse wrapper — spans, trace attributes, local-file fallback.

Every network call is best-effort: observability must never break the agent.
When Langfuse credentials are missing, spans are appended to
`data/local_traces.jsonl` instead so a dev loop works offline.

When `LANGFUSE_DEBUG=1` is set in the environment, transport errors are
re-raised so misconfigured credentials surface immediately instead of
silently disabling the integration.

See __specs/10-observability.md for the trace attribute contract.
"""
from __future__ import annotations

import atexit
import contextvars
import datetime as dt
import json
import os
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator

from agent.config import settings, config


_ALLOWED_ATTRS: set[str] = set(config.get("observability.allowed_attributes", []))
_DEBUG = os.environ.get("LANGFUSE_DEBUG", "").lower() in ("1", "true", "yes")


def _warn(msg: str) -> None:
    """Single-line warning to stderr — used once per process."""
    sys.stderr.write(f"[langfuse] {msg}\n")
    sys.stderr.flush()


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
_atexit_registered = False


def _get_client() -> Any | None:
    """Return a Langfuse client if credentials are set, importable, and the
    auth check passes. Returns None on any failure and disables further
    attempts. With LANGFUSE_DEBUG=1 the failure is also re-raised.
    """
    global _langfuse_client, _langfuse_disabled, _atexit_registered
    if _langfuse_disabled:
        return None
    if _langfuse_client is not None:
        return _langfuse_client
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        _langfuse_disabled = True
        if _DEBUG:
            _warn("disabled: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set in .env")
        return None
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        # Verify creds NOW so a 401 surfaces here, not silently in a
        # background flush that drops events without telling the caller.
        ok = False
        try:
            ok = bool(client.auth_check())
        except Exception as e:  # noqa: BLE001
            _warn(f"auth_check raised: {type(e).__name__}: {e}")
            if _DEBUG:
                raise
        if not ok:
            _warn(
                f"auth_check failed against {settings.LANGFUSE_HOST}. "
                "Verify LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY in .env "
                "(both must come from the same Langfuse project)."
            )
            _langfuse_disabled = True
            return None
        _langfuse_client = client
        # Make sure buffered events flush before the process exits — without
        # this, short-lived CLI scripts (make enrich / compose-and-send) lose
        # every trace because the background sender hasn't run yet.
        if not _atexit_registered:
            atexit.register(_flush_at_exit)
            _atexit_registered = True
        return _langfuse_client
    except Exception as e:  # noqa: BLE001
        _warn(f"client init failed: {type(e).__name__}: {e}")
        _langfuse_disabled = True
        if _DEBUG:
            raise
        return None


def _flush_at_exit() -> None:
    if _langfuse_client is None:
        return
    try:
        _langfuse_client.flush()
    except Exception as e:  # noqa: BLE001
        _warn(f"flush at exit failed: {type(e).__name__}: {e}")


def flush() -> None:
    """Block until buffered events are sent. Safe to call from anywhere."""
    if _langfuse_client is None:
        return
    try:
        _langfuse_client.flush()
    except Exception as e:  # noqa: BLE001
        _warn(f"flush failed: {type(e).__name__}: {e}")
        if _DEBUG:
            raise


def verify_trace(trace_id: str, retries: int = 0, delay_s: float = 0) -> bool:  # noqa: ARG001
    """Return True if Langfuse is enabled and we just flushed.

    Earlier versions polled `fetch_trace` after `flush()`, but Langfuse Cloud
    has ~10–15s of read-after-write replica lag, so polling either gave
    false negatives or made every CLI run sleep 20s. Instead we now treat
    a successful `flush()` as authoritative — the SDK raises if the
    ingestion POST fails. To inspect the push live, re-run with
    `LANGFUSE_DEBUG=1` and look for `successfully uploaded batch of N items`.
    """
    if _langfuse_client is None:
        return False
    try:
        _langfuse_client.flush()
    except Exception as e:  # noqa: BLE001
        _warn(f"flush failed during verify: {type(e).__name__}: {e}")
        if _DEBUG:
            raise
        return False
    return True


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class TraceHandle:
    trace_id: str
    prefix: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def url(self) -> str:
        """Best authoritative URL we can produce.

        - With a live client, `client.get_trace_url(trace_id)` returns the
          server-resolved URL using the host the SDK negotiated and the real
          project id. Use that — it always points to a real trace.
        - Otherwise fall back to a constructed URL (host + configured project
          id), prefixed with `(langfuse disabled) ` so callers and humans
          can't mistake it for a working link.
        """
        client = _langfuse_client  # do NOT call _get_client(); url() is read-only
        if client is not None:
            try:
                resolved = client.get_trace_url(trace_id=self.trace_id)
                if resolved:
                    return resolved
            except Exception:  # noqa: BLE001
                pass
        host = settings.LANGFUSE_HOST.rstrip("/")
        project = settings.LANGFUSE_PROJECT_ID or "local"
        prefix = "" if client is not None else "(langfuse disabled) "
        return f"{prefix}{host}/project/{project}/traces/{self.trace_id}"


# Context-local "current trace" so LLM and MCP wrappers can attach
# automatically without callers having to thread a TraceHandle through
# every function. `new_trace()` and `span()`/`generation()` push the
# active trace onto this stack for the duration of the block.
_current_trace: contextvars.ContextVar[TraceHandle | None] = contextvars.ContextVar(
    "current_trace", default=None,
)


def current_trace() -> TraceHandle | None:
    """Return the in-scope trace (or None if no `new_trace()` / `span(trace=)` is active)."""
    return _current_trace.get()


def new_trace(name: str, attributes: dict[str, Any] | None = None) -> TraceHandle:
    trace_id = f"{settings.LANGFUSE_TRACE_PREFIX}_{uuid.uuid4().hex[:12]}"
    attrs = _filter_attrs(attributes or {})
    handle = TraceHandle(trace_id=trace_id, prefix=name, attributes=attrs)

    client = _get_client()
    if client is not None:
        try:
            client.trace(id=trace_id, name=name, metadata=attrs)
        except Exception as e:  # noqa: BLE001
            _warn(f"trace() failed: {type(e).__name__}: {e}")
            if _DEBUG:
                raise

    _local_trace_append({
        "kind": "trace_start",
        "trace_id": trace_id,
        "name": name,
        "attributes": attrs,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    # Make this the in-scope trace for the rest of the calling frame.
    # Callers that want narrower scoping can wrap with using_trace().
    _current_trace.set(handle)
    return handle


@contextmanager
def using_trace(trace: TraceHandle) -> Iterator[TraceHandle]:
    """Bind `trace` as the current trace for the duration of the block.

    Use when you want to scope auto-attachment narrowly:

        trace = new_trace("compose_and_send", ...)
        with using_trace(trace):
            compose(...)  # LLM calls inside auto-attach to `trace`
    """
    token = _current_trace.set(trace)
    try:
        yield trace
    finally:
        _current_trace.reset(token)


# Reserved keys callers can set on the mutable span dict to forward
# Langfuse-native fields (input/output/model/usage) without having them
# stripped by the metadata allowlist filter.
_LF_INPUT = "_lf_input"
_LF_OUTPUT = "_lf_output"
_LF_MODEL = "_lf_model"
_LF_USAGE = "_lf_usage"  # ModelUsage-shaped dict: {input, output, total, unit}
_LF_RESERVED = {_LF_INPUT, _LF_OUTPUT, _LF_MODEL, _LF_USAGE}


def _split_lf_reserved(mutable: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pop Langfuse-native fields off `mutable` so they're not filtered as metadata."""
    reserved = {k: mutable.pop(k) for k in list(mutable) if k in _LF_RESERVED}
    return mutable, reserved


@contextmanager
def span(name: str, trace: TraceHandle | None = None, **attributes: Any) -> Iterator[dict[str, Any]]:
    """Context manager around a unit of agent work.

    Usage:
        with span("composer.draft", trace=trace, prospect_domain=d) as s:
            ...
            s["cost.usd"] = 0.012
            s[_LF_INPUT] = prompt   # optional: shows as input in Langfuse UI
            s[_LF_OUTPUT] = draft   # optional: shows as output in Langfuse UI
    """
    yield from _emit("span", name, trace, attributes)


@contextmanager
def generation(name: str, trace: TraceHandle | None = None, **attributes: Any) -> Iterator[dict[str, Any]]:
    """Context manager around an LLM call. Same as `span()` but emits a
    Langfuse `generation` so model/usage/cost render in the dedicated cost
    column. Set `_lf_model`, `_lf_usage`, `_lf_input`, `_lf_output` on the
    mutable dict to populate those native fields.
    """
    yield from _emit("generation", name, trace, attributes)


def _emit(kind: str, name: str, trace: TraceHandle | None, attributes: dict[str, Any]) -> Iterator[dict[str, Any]]:
    span_id = uuid.uuid4().hex[:12]
    start = dt.datetime.now(dt.timezone.utc)
    # If the caller didn't pass a trace, inherit the in-scope one so nested
    # LLM / MCP wrappers attach automatically.
    if trace is None:
        trace = _current_trace.get()
    trace_id = trace.trace_id if trace else None
    trace_attrs = trace.attributes if trace else {}
    span_attrs = _filter_attrs({**trace_attrs, **attributes})
    mutable: dict[str, Any] = {**span_attrs}

    # Make this trace current for the body, so deeper-nested calls inherit.
    token = _current_trace.set(trace) if trace is not None else None
    try:
        yield mutable
        status = "ok"
        error = None
    except Exception as e:  # noqa: BLE001 - record and re-raise
        status = "error"
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        if token is not None:
            _current_trace.reset(token)
        end = dt.datetime.now(dt.timezone.utc)
        duration_ms = int((end - start).total_seconds() * 1000)

        # Pop Langfuse-native fields before metadata filtering, so they don't
        # have to be on the allowlist (turns/prompts can be large).
        meta, lf = _split_lf_reserved(mutable)

        payload = {
            "kind": kind,
            "span_id": span_id,
            "trace_id": trace_id,
            "name": name,
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            "attributes": _filter_attrs(meta),
        }
        _local_trace_append(payload)

        client = _get_client()
        if client is not None:
            try:
                if kind == "generation":
                    usage = lf.get(_LF_USAGE)
                    client.generation(
                        trace_id=trace_id,
                        name=name,
                        start_time=start,
                        end_time=end,
                        metadata=payload["attributes"],
                        level="ERROR" if status == "error" else "DEFAULT",
                        status_message=error,
                        input=lf.get(_LF_INPUT),
                        output=lf.get(_LF_OUTPUT),
                        model=lf.get(_LF_MODEL),
                        usage=usage,
                    )
                else:
                    client.span(
                        trace_id=trace_id,
                        name=name,
                        start_time=start,
                        end_time=end,
                        metadata=payload["attributes"],
                        level="ERROR" if status == "error" else "DEFAULT",
                        status_message=error,
                        input=lf.get(_LF_INPUT),
                        output=lf.get(_LF_OUTPUT),
                    )
            except Exception as e:  # noqa: BLE001
                _warn(f"{kind}() failed: {type(e).__name__}: {e}")
                if _DEBUG:
                    raise


def update_trace(trace: TraceHandle, **attributes: Any) -> None:
    """Merge attributes into an existing trace's metadata.

    Used to roll up totals onto the parent trace at end of run (e.g.
    `trace.total_cost_usd`, `tau2.cost_per_task_usd`). Filtered through the
    allowlist like span attributes.
    """
    new_attrs = _filter_attrs(attributes)
    trace.attributes.update(new_attrs)

    _local_trace_append({
        "kind": "trace_update",
        "trace_id": trace.trace_id,
        "attributes": new_attrs,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    })

    client = _get_client()
    if client is not None:
        try:
            # Upsert by id — Langfuse merges metadata.
            client.trace(id=trace.trace_id, metadata=trace.attributes)
        except Exception as e:  # noqa: BLE001
            _warn(f"update_trace() failed: {type(e).__name__}: {e}")
            if _DEBUG:
                raise


def record_score(trace: TraceHandle, name: str, value: float | str, comment: str | None = None) -> None:
    """Attach a Langfuse score (e.g. pass@1) to the parent trace."""
    _local_trace_append({
        "kind": "score",
        "trace_id": trace.trace_id,
        "name": name,
        "value": value,
        "comment": comment,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    })

    client = _get_client()
    if client is not None:
        try:
            client.score(trace_id=trace.trace_id, name=name, value=value, comment=comment)
        except Exception as e:  # noqa: BLE001
            _warn(f"record_score() failed: {type(e).__name__}: {e}")
            if _DEBUG:
                raise


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
