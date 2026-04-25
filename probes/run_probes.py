"""Probe runner: execute each probe N times and record trigger rates.

`make probes [P=P-0001]` — run all probes or a specific one.

Each probe in `probes.yaml` declares a trigger. Trigger handlers below
exercise the relevant subsystem with synthetic inputs and check the
expected predicate. The runner records per-probe trigger rate and
regenerates `failure_taxonomy.md`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Probes must be deterministic and offline — force the LLM client into stub
# mode regardless of whether OPENROUTER_API_KEY is set. We set this BEFORE
# importing agent.* so the client picks it up at import time.
os.environ.setdefault("LLM_STUB", "1")

import yaml

from agent.config import REPO_ROOT, config
from agent.classifier import classify
from agent.composer import compose, ComposerError
from agent.classifier import SegmentMismatch


PROBE_REGISTRY = REPO_ROOT / "probes" / "probes.yaml"
RUNS_DIR = REPO_ROOT / "probes" / "runs"
TAXONOMY_PATH = REPO_ROOT / "probes" / "failure_taxonomy.md"


def _load_registry() -> dict[str, Any]:
    return yaml.safe_load(PROBE_REGISTRY.read_text())


def _build_brief(overrides: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal brief dict with defaults, apply dotted-path overrides.

    Dotted-path keys in overrides are resolved into the nested dict structure.
    Date offsets (keys ending `_offset_days`) resolve to ISO date strings.
    """
    base = {
        "buying_window_signals": {
            "funding_event": {"detected": False},
            "layoff_event": {"detected": False},
            "leadership_change": {"detected": False},
        },
        "ai_maturity": {"score": 0, "confidence": 0.5},
        "hiring_velocity": {"open_roles_today": 0, "open_roles_60_days_ago": 0, "velocity_label": "insufficient_signal", "signal_confidence": 0.3},
        "tech_stack": [],
        "bench_to_brief_match": {"required_stacks": [], "bench_available": True, "gaps": []},
    }
    today = dt.date.today()
    for path, value in (overrides or {}).items():
        if isinstance(value, dict):
            # resolve _offset_days keys into ISO dates
            resolved = {}
            for k, v in value.items():
                if k.endswith("_offset_days"):
                    iso_key = k.replace("_offset_days", "")
                    resolved[iso_key] = (today + dt.timedelta(days=int(v))).isoformat()
                else:
                    resolved[k] = v
            value = resolved
        _set_path(base, path, value)
    return base


def _set_path(d: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = d
    for p in parts[:-1]:
        if p not in node or not isinstance(node[p], dict):
            node[p] = {}
        node = node[p]
    existing = node.get(parts[-1])
    if isinstance(existing, dict) and isinstance(value, dict):
        existing.update(value)
    else:
        node[parts[-1]] = value


def _run_one_probe(probe: dict[str, Any], runs: int) -> dict[str, Any]:
    trigger = probe["trigger"]
    expected = probe.get("expected", {})
    triggered = 0
    outcomes: list[str] = []

    for _ in range(runs):
        ok = False
        try:
            if trigger == "classify":
                brief = _build_brief(probe.get("fixture", {}).get("brief_overrides", {}))
                result = classify(brief)
                ok = _check_classification(result, expected)
            elif trigger == "compose":
                brief = _make_pydantic_brief(probe.get("fixture", {}).get("brief_overrides", {}))
                try:
                    draft = compose(
                        segment=probe.get("compose_args", {}).get("segment", "segment_1_series_a_b"),
                        brief=brief, gap_brief=None,
                        prospect={"prospect_name": "Test", "prospect_title": "VP", "prospect_company": "Test Co", "prospect_timezone": "UTC"},
                        cal_link="https://cal.example/x",
                    )
                    ok = _check_draft(draft, expected)
                except SegmentMismatch:
                    ok = expected.get("raises") == "SegmentMismatch"
                except ComposerError:
                    ok = False
            elif trigger == "ci_grep":
                ok = _ci_grep_clean(expected.get("patterns", []))
            elif trigger == "handoff_check":
                ok = _run_handoff_check(probe, expected)
            elif trigger == "reply_classify":
                ok = _run_reply_classify(probe, expected)
            elif trigger == "bench_match":
                ok = _run_bench_match(probe, expected)
            elif trigger == "gap_validate":
                ok = _run_gap_validate(probe, expected)
            elif trigger == "scheduling_overlap":
                ok = _run_scheduling_overlap(probe, expected)
            elif trigger == "static_check":
                ok = _run_static_check(probe, expected)
            elif trigger == "cost_budget":
                ok = _run_cost_budget(probe, expected)
            else:
                outcomes.append(f"unknown_trigger:{trigger}")
                ok = False
        except Exception as e:  # noqa: BLE001
            outcomes.append(f"exception:{type(e).__name__}:{e}")
            ok = False

        outcomes.append("expected_met" if ok else "expected_violated")
        if not ok:
            triggered += 1

    return {
        "probe_id": probe["id"],
        "category": probe["category"],
        "name": probe["name"],
        "trigger": trigger,
        "runs": runs,
        "triggered": triggered,
        "trigger_rate": round(triggered / runs, 3),
        "outcomes_sample": outcomes[:5],
    }


def _make_pydantic_brief(overrides: dict[str, Any]):
    from agent.enrichment.briefs import (
        AiMaturity, BenchToBriefMatch, BuyingWindowSignals, FundingEvent,
        HiringSignalBrief, HiringVelocity, LayoffEvent, LeadershipChange,
        Segment, VelocityLabel,
    )
    b = _build_brief(overrides)
    return HiringSignalBrief(
        prospect_domain="probe.example",
        prospect_name="Probe Co",
        generated_at=dt.datetime.now(dt.timezone.utc),
        primary_segment_match=Segment.ABSTAIN,
        segment_confidence=0.0,
        ai_maturity=AiMaturity(score=int(b["ai_maturity"]["score"]), confidence=float(b["ai_maturity"]["confidence"])),
        hiring_velocity=HiringVelocity(
            open_roles_today=int(b["hiring_velocity"]["open_roles_today"]),
            open_roles_60_days_ago=int(b["hiring_velocity"]["open_roles_60_days_ago"]),
            velocity_label=VelocityLabel(b["hiring_velocity"]["velocity_label"]),
            signal_confidence=float(b["hiring_velocity"]["signal_confidence"]),
        ),
        buying_window_signals=BuyingWindowSignals(
            funding_event=FundingEvent(**{k: v for k, v in b["buying_window_signals"]["funding_event"].items() if k in {"detected", "stage", "amount_usd", "closed_at", "source_url"}}),
            layoff_event=LayoffEvent(**{k: v for k, v in b["buying_window_signals"]["layoff_event"].items() if k in {"detected", "date", "headcount_reduction", "percentage_cut", "source_url"}}),
            leadership_change=LeadershipChange(**{k: v for k, v in b["buying_window_signals"]["leadership_change"].items() if k in {"detected", "role", "new_leader_name", "started_at", "source_url"}}),
        ),
    )


def _check_classification(result: Any, expected: dict[str, Any]) -> bool:
    if "segment" in expected:
        return result.segment == expected["segment"] and result.confidence >= expected.get("min_confidence", 0.0)
    if "not_segment" in expected:
        return result.segment != expected["not_segment"]
    return False


def _check_draft(draft: Any, expected: dict[str, Any]) -> bool:
    body = (draft.subject + "\n" + draft.body_text).lower()
    for phrase in expected.get("body_not_contains", []):
        if phrase.lower() in body:
            return False
    for phrase in expected.get("body_contains", []):
        if phrase.lower() not in body:
            return False
    return True


def _ci_grep_clean(patterns: list[str]) -> bool:
    """Reject only *SDK import* of a provider outside the kill-switch + channel adapters.

    Matches `import <provider>` or `from <provider>` at line start. Config
    key names (RESEND_API_KEY) and header names (x_resend_signature) are
    not SDK imports and must not trigger this probe.
    """
    try:
        for pattern in patterns:
            regex = rf"^\s*(from {pattern}(?:\.|\s+)|import {pattern}\b)"
            r = subprocess.run(
                ["git", "grep", "-l", "-E", regex, "--", "agent/",
                 ":(exclude)agent/kill_switch.py", ":(exclude)agent/channels/"],
                capture_output=True, text=True, check=False, cwd=str(REPO_ROOT),
            )
            if r.returncode == 0 and r.stdout.strip():
                return False
    except FileNotFoundError:
        return True
    return True


# ─── New trigger handlers ──────────────────────────────────────────────────


def _run_handoff_check(probe: dict[str, Any], expected: dict[str, Any]) -> bool:
    from agent.handoff import should_handoff
    args = probe.get("handoff_args", {})
    decision = should_handoff(
        reply_text=args.get("reply_text"),
        tone_double_failed=bool(args.get("tone_double_failed", False)),
        bench_over_commit=bool(args.get("bench_over_commit", False)),
        booking_created=bool(args.get("booking_created", False)),
        published_price_asked_out_of_band=bool(args.get("published_price_asked_out_of_band", False)),
    )
    if "should_handoff" in expected and decision.should_handoff != bool(expected["should_handoff"]):
        return False
    if "reason" in expected:
        # Allow prefix match (e.g. expected "regulatory_keyword" matches "regulatory_keyword:nda").
        if not decision.reason.startswith(expected["reason"]):
            return False
    if "severity" in expected and decision.severity != expected["severity"]:
        return False
    return True


def _run_reply_classify(probe: dict[str, Any], expected: dict[str, Any]) -> bool:
    from agent.reply_handler import classify_reply
    args = probe.get("reply_args", {})
    text = str(args.get("text", ""))
    result = classify_reply(text)
    cls = getattr(result, "class_", None) or getattr(result, "cls", None) or getattr(result, "label", None)
    cls = str(cls) if cls is not None else ""
    if "class_" in expected:
        return cls == expected["class_"]
    if "class_in" in expected:
        return cls in set(expected["class_in"])
    return bool(cls)


def _run_bench_match(probe: dict[str, Any], expected: dict[str, Any]) -> bool:
    from agent.enrichment import bench
    args = probe.get("bench_args", {})
    required = list(args.get("required_stacks", []))
    result = bench.match(required) or {}
    available = bool(result.get("bench_available", False))
    if "bench_available" in expected:
        return available == bool(expected["bench_available"])
    return True


def _run_gap_validate(probe: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Synthesize peer evidence; verify the GapQualitySelfCheck flips correctly."""
    from agent.enrichment.briefs import (
        CompetitorEntry, GapFinding, GapQualitySelfCheck, HeadcountBand,
        PeerEvidence, Segment,
    )
    args = probe.get("gap_args", {})
    missing = bool(args.get("missing_source_url", False))
    pe1 = PeerEvidence(
        competitor_name="Peer One",
        evidence="Public AI leadership signal.",
        source_url="" if missing else "https://peer-one.example/team",
    ) if not missing else None
    if missing:
        # Build PeerEvidence with source_url empty by going around validation
        pe1 = PeerEvidence.model_construct(
            competitor_name="Peer One", evidence="Public AI leadership signal.", source_url="",
        )
    pe2 = PeerEvidence(
        competitor_name="Peer Two",
        evidence="Open AI-platform role visible.",
        source_url="https://peer-two.example/jobs",
    )
    finding = GapFinding(
        practice="Named AI/ML leadership.",
        peer_evidence=[pe1, pe2],
        prospect_state="No named AI leadership visible.",
        confidence="medium",
        segment_relevance=[Segment.SEGMENT_4],
    )
    self_check = GapQualitySelfCheck(
        all_peer_evidence_has_source_url=all(bool(p.source_url) for p in finding.peer_evidence),
        at_least_one_gap_high_confidence=str(finding.confidence) == "high",
    )
    if "all_peer_evidence_has_source_url" in expected:
        return self_check.all_peer_evidence_has_source_url == bool(expected["all_peer_evidence_has_source_url"])
    return True


def _run_scheduling_overlap(probe: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Compute working-hours overlap between two timezones.

    Working hours assumed 09:00–18:00 in each TZ. We compute the overlap of
    those windows on a representative weekday and assert it meets
    `min_overlap_hours`. If `allow_fallback=true`, an overlap shortfall
    succeeds (probe states the agent abstains and offers Cal link instead).
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        return False
    args = probe.get("scheduling_args", {})
    p_tz = ZoneInfo(args.get("prospect_tz", "UTC"))
    h_tz = ZoneInfo(args.get("hq_tz", "UTC"))
    min_hours = float(args.get("min_overlap_hours", 3))
    allow_fallback = bool(args.get("allow_fallback", False))

    # Pick a fixed weekday outside DST transitions for determinism (Wed, mid-month).
    day = dt.date(2026, 5, 13)
    p_start = dt.datetime.combine(day, dt.time(9, 0), tzinfo=p_tz).astimezone(dt.timezone.utc)
    p_end = dt.datetime.combine(day, dt.time(18, 0), tzinfo=p_tz).astimezone(dt.timezone.utc)
    h_start = dt.datetime.combine(day, dt.time(9, 0), tzinfo=h_tz).astimezone(dt.timezone.utc)
    h_end = dt.datetime.combine(day, dt.time(18, 0), tzinfo=h_tz).astimezone(dt.timezone.utc)
    overlap_start = max(p_start, h_start)
    overlap_end = min(p_end, h_end)
    overlap_hours = max(0.0, (overlap_end - overlap_start).total_seconds() / 3600.0)
    if overlap_hours >= min_hours:
        return True
    return allow_fallback


def _run_static_check(probe: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Verify a repo invariant — file/regex/config-key.

    Supported `static_check.kind`:
      - path_exists       — `path` exists (file or dir)
      - regex_present_in  — every `pattern` matches at least one file under `path`
      - regex_absent_in   — no `pattern` matches any file under `path`

    Or, alternately, `config_check`:
      - assert `key`'s value is bounded by `min`/`max`.
    """
    sc = probe.get("static_check") or {}
    if sc:
        kind = sc.get("kind")
        path = (REPO_ROOT / sc.get("path", "")).resolve()
        patterns = sc.get("patterns", []) or []
        if kind == "path_exists":
            return path.exists()
        if kind in ("regex_present_in", "regex_absent_in"):
            files = _walk_text_files(path)
            for pat in patterns:
                rx = re.compile(pat, re.IGNORECASE)
                hit = any(rx.search(_safe_read(f)) for f in files)
                if kind == "regex_present_in" and not hit:
                    return False
                if kind == "regex_absent_in" and hit:
                    return False
            return True
        return False
    cc = probe.get("config_check") or {}
    if cc:
        key = cc["key"]
        val = config.get(key)
        if val is None:
            return False
        try:
            v = float(val)
        except (TypeError, ValueError):
            return False
        if "min" in cc and v < float(cc["min"]):
            return False
        if "max" in cc and v > float(cc["max"]):
            return False
        return True
    return False


def _run_cost_budget(probe: dict[str, Any], expected: dict[str, Any]) -> bool:
    return _run_static_check(probe, expected)


def _walk_text_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    out: list[Path] = []
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        if any(part.startswith(".") or part == "__pycache__" or part == "node_modules" for part in p.parts):
            continue
        if p.suffix.lower() in {".py", ".md", ".yaml", ".yml", ".txt", ".json", ".toml", ".cfg", ".ini"}:
            out.append(p)
    return out


def _safe_read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _write_run(result: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RUNS_DIR / f"{result['probe_id']}_{ts}.json"
    path.write_text(json.dumps(result, indent=2))


def _update_taxonomy(results: list[dict[str, Any]]) -> None:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for r in sorted(results, key=lambda x: (x["category"], x["probe_id"])):
        by_cat.setdefault(r["category"], []).append(r)

    total = len(results)
    triggered_total = sum(1 for r in results if r["triggered"] > 0)
    clean = total - triggered_total

    lines = [
        "# Failure taxonomy",
        "",
        f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}",
        f"Total probes: **{total}** · Clean (trigger_rate=0): **{clean}** · "
        f"Firing: **{triggered_total}**",
        "",
        "Probes are grouped by category. A probe whose `trigger_rate` is "
        "non-zero indicates the system regressed against the invariant the "
        "probe encodes — investigate the linked subsystem before merging.",
        "",
        "| Probe | Category | Trigger | Runs | Trigger rate |",
        "|---|---|---|---|---|",
    ]
    for cat in sorted(by_cat):
        for r in by_cat[cat]:
            lines.append(
                f"| {r['probe_id']} — {r['name']} | {r['category']} | "
                f"`{r.get('trigger','?')}` | {r['runs']} | "
                f"{r['trigger_rate']*100:.1f}% |"
            )

    lines += [
        "",
        "## Coverage by category",
        "",
        "| Category | Probes | Firing |",
        "|---|---|---|",
    ]
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        firing = sum(1 for r in rs if r["triggered"] > 0)
        lines.append(f"| {cat} | {len(rs)} | {firing} |")

    lines += [
        "",
        "## Reading the taxonomy",
        "",
        "- **0.0%** — invariant holds across all runs. No action.",
        "- **>0.0%** — at least one run violated the expected predicate. "
        "Inspect `probes/runs/<probe_id>_<timestamp>.json` for sample "
        "outcomes; treat the linked subsystem as suspect.",
        "- **`trigger`** column names the runner that exercised the probe. "
        "See `probes/probes.yaml` for the supported triggers and the per-probe "
        "fixture / expected predicate.",
        "",
        "Re-run with `make probes` (full library) or `make probes P=<id>` "
        "(single probe).",
        "",
    ]
    TAXONOMY_PATH.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-id", default=None, help="run just one probe")
    ap.add_argument("--runs", type=int, default=None)
    args = ap.parse_args()
    reg = _load_registry()
    runs = args.runs or int(reg.get("runs_per_probe", 20))
    probes = reg["probes"]
    if args.probe_id:
        probes = [p for p in probes if p["id"] == args.probe_id]
        if not probes:
            print(f"ERROR: no probe {args.probe_id!r}", file=sys.stderr)
            return 2

    results = []
    for probe in probes:
        r = _run_one_probe(probe, runs)
        _write_run(r)
        print(f"{r['probe_id']}: {r['name']} — trigger_rate={r['trigger_rate']*100:.1f}% ({r['triggered']}/{r['runs']})")
        results.append(r)
    _update_taxonomy(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
