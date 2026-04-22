"""Langfuse-shaped tracing primitive with local JSONL fallback.

For the interim, we always write to `data/local_traces.jsonl` (Langfuse fallback)
so the harness + orchestrator generate real artifacts even without a Langfuse key.
Spans form a tree; the root span is flushed once closed.
"""
from __future__ import annotations

import contextlib
import json
import pathlib
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator


_TRACE_LOG_PATH = pathlib.Path("data/local_traces.jsonl")
_LOCK = threading.Lock()


@dataclass
class Span:
    name: str
    start_ms: float
    elapsed_ms: float = 0.0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    attrs: dict[str, Any] = field(default_factory=dict)
    children: list["Span"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "name": self.name,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "cost_usd": round(self.cost_usd, 6),
        }
        if self.tokens_in:
            d["tokens_in"] = self.tokens_in
        if self.tokens_out:
            d["tokens_out"] = self.tokens_out
        if self.attrs:
            d["attrs"] = self.attrs
        return d


@dataclass
class Trace:
    trace_id: str
    root_name: str
    start_ts: str
    end_ts: str = ""
    tags: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    root: Span | None = None
    _stack: list[Span] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        spans_flat: list[dict[str, Any]] = []

        def walk(s: Span) -> None:
            spans_flat.append(s.to_dict())
            for c in s.children:
                walk(c)

        if self.root:
            walk(self.root)

        return {
            "trace_id": self.trace_id,
            "thread_id": self.tags.get("thread_id"),
            "crunchbase_uuid": self.tags.get("crunchbase_uuid"),
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "root_span": self.root_name,
            "spans": spans_flat,
            "outcome": self.outcome,
            "tags": self.tags,
        }


_current: threading.local = threading.local()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_trace() -> Trace | None:
    return getattr(_current, "trace", None)


@contextlib.contextmanager
def trace(root_name: str, *, tags: dict[str, Any] | None = None) -> Iterator[Trace]:
    t = Trace(trace_id=str(uuid.uuid4()), root_name=root_name, start_ts=_now_iso(), tags=dict(tags or {}))
    _current.trace = t
    root = Span(name=root_name, start_ms=time.perf_counter() * 1000)
    t.root = root
    t._stack.append(root)
    try:
        yield t
    finally:
        root.elapsed_ms = time.perf_counter() * 1000 - root.start_ms
        t._stack.pop()
        t.end_ts = _now_iso()
        _flush(t)
        _current.trace = None


@contextlib.contextmanager
def span(name: str, **attrs: Any) -> Iterator[Span]:
    t = get_trace()
    if t is None:
        # operating outside a trace; create a degenerate one so callers still work
        with trace(name, tags={}) as t_inner:
            yield t_inner.root  # type: ignore[misc]
        return
    s = Span(name=name, start_ms=time.perf_counter() * 1000, attrs=dict(attrs))
    t._stack[-1].children.append(s)
    t._stack.append(s)
    try:
        yield s
    finally:
        s.elapsed_ms = time.perf_counter() * 1000 - s.start_ms
        t._stack.pop()


def add_cost(cost_usd: float, tokens_in: int = 0, tokens_out: int = 0) -> None:
    t = get_trace()
    if not t or not t._stack:
        return
    s = t._stack[-1]
    s.cost_usd += cost_usd
    s.tokens_in += tokens_in
    s.tokens_out += tokens_out


def set_outcome(**kv: Any) -> None:
    t = get_trace()
    if t is None:
        return
    t.outcome.update(kv)


def _flush(t: Trace) -> None:
    _TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, _TRACE_LOG_PATH.open("a") as f:
        f.write(json.dumps(t.to_dict(), default=str) + "\n")
