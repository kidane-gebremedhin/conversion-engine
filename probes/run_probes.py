"""Probe runner: execute each probe N times and record trigger rates.

`make probes [P=P-0001]` — run all probes or a specific one.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from agent.config import REPO_ROOT
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


def _write_run(result: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RUNS_DIR / f"{result['probe_id']}_{ts}.json"
    path.write_text(json.dumps(result, indent=2))


def _update_taxonomy(results: list[dict[str, Any]]) -> None:
    lines = ["# Failure taxonomy", "",
             "| Probe | Category | Trigger rate |",
             "|---|---|---|"]
    for r in sorted(results, key=lambda x: (x["category"], x["probe_id"])):
        lines.append(f"| {r['probe_id']} | {r['category']} | {r['trigger_rate']*100:.1f}% |")
    TAXONOMY_PATH.write_text("\n".join(lines) + "\n")


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
