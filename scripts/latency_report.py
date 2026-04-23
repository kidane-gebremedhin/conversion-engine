"""p50/p95 latency report from eval/trace_log.jsonl (and data/local_traces.jsonl).

Covers ≥ 20 synthetic prospect interactions. Per __specs/10 §6.
"""
from __future__ import annotations

import json
import math
import pathlib
from typing import Iterable


_STAGES = (
    "email.send",
    "sms.send",
    "agent.prompt.classify_reply",
    "agent.prompt.draft_outreach",
    "enrich.full",
    "enrich.jobposts",
    "enrich.ai_maturity",
    "enrich.competitor_gap",
    "hubspot.upsert_company",
    "hubspot.log_event",
    "calcom.book",
    "tau2_bench.task",
)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (q / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _spans(trace: dict) -> Iterable[dict]:
    return trace.get("spans", [])


def main() -> int:
    sources = [pathlib.Path("eval/trace_log.jsonl"), pathlib.Path("data/local_traces.jsonl")]
    traces: list[dict] = []
    seen_ids: set[str] = set()
    for src in sources:
        if not src.exists():
            continue
        for line in src.read_text().splitlines():
            if not line.strip():
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = t.get("trace_id")
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)
            traces.append(t)

    distinct_trace_ids = len(seen_ids)

    report: dict = {
        "distinct_traces": distinct_trace_ids,
        "stages": {},
    }
    for stage in _STAGES:
        durations = [s.get("elapsed_ms", 0.0) for t in traces for s in _spans(t) if s.get("name") == stage]
        if not durations:
            continue
        report["stages"][stage] = {
            "n": len(durations),
            "p50_ms": round(_percentile(durations, 50), 2),
            "p95_ms": round(_percentile(durations, 95), 2),
            "mean_ms": round(sum(durations) / len(durations), 2),
        }

    out = pathlib.Path("eval/latency_report.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"[latency] distinct traces: {distinct_trace_ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
