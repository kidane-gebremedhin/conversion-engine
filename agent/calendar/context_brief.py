"""Discovery-call context brief synthesizer.

Produces the 10-section markdown brief from:
  - hiring_signal_brief.json
  - competitor_gap_brief.json (may be null)
  - email thread
  - bench_summary.json

See tenacious_sales_data/schemas/discovery_call_context_brief.md.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from agent.config import REPO_ROOT, settings
from agent.enrichment import bench
from agent.llm import client as llm


def render(
    *,
    prospect: dict[str, Any],
    brief: Any,
    gap_brief: Any | None,
    thread: list[dict[str, Any]],
    booking: dict[str, Any],
    trace_url: str,
) -> str:
    b = brief.model_dump() if hasattr(brief, "model_dump") else brief

    gap_text = _render_gap(gap_brief)
    ai = b.get("ai_maturity", {})
    thread_text = "\n".join(f"- [{t.get('direction','?')}] {t.get('subject','')}: {t.get('body_text','')[:200]}" for t in thread) or "(no thread history)"
    bench_json = json.dumps({s: bench.available(s) for s in bench.all_stacks()}, indent=2)

    subs = {
        "STYLE_MARKERS": _style_markers(),
        "PROSPECT_NAME": prospect.get("prospect_name", ""),
        "PROSPECT_TITLE": prospect.get("prospect_title", ""),
        "PROSPECT_COMPANY": prospect.get("prospect_company", ""),
        "SEGMENT": str(b.get("primary_segment_match", "abstain")),
        "SEGMENT_CONFIDENCE": f"{b.get('segment_confidence', 0.0):.2f}",
        "AI_SCORE": str(ai.get("score", 0)),
        "AI_CONFIDENCE": f"{ai.get('confidence', 0.0):.2f}",
        "THREAD_SUMMARY": thread_text,
        "GAP_FINDINGS": gap_text,
        "BENCH_JSON": bench_json,
        "TRACE_URL": trace_url,
    }

    template = llm.load_prompt("context_brief_synthesizer")
    rendered_prompt = template
    for k, v in subs.items():
        rendered_prompt = rendered_prompt.replace("{{" + k + "}}", v)

    resp = llm.call(rendered_prompt, tier="dev", json_mode=False, temperature=0.2, max_tokens=2000)
    text = resp.text.strip()
    if not text or text.startswith("[llm-stub"):
        text = _fallback_brief(prospect, b, gap_brief, booking, trace_url)
    return text


def _render_gap(gap_brief: Any | None) -> str:
    if not gap_brief:
        return "(no competitor gap brief generated)"
    g = gap_brief.model_dump() if hasattr(gap_brief, "model_dump") else gap_brief
    lines: list[str] = []
    for f in g.get("gap_findings", []):
        ev = "; ".join(f"{e['competitor_name']}: {e['evidence']}" for e in f.get("peer_evidence", [])[:2])
        lines.append(f"- [{f.get('confidence','?')}] {f.get('practice')} — {ev}")
    return "\n".join(lines) if lines else "(no findings)"


def _style_markers() -> str:
    from agent.composer import _style_markers as _sm
    return _sm()


def _fallback_brief(prospect: dict[str, Any], b: dict[str, Any], gap_brief: Any | None, booking: dict[str, Any], trace_url: str) -> str:
    """Deterministic brief used when LLM is stubbed."""
    lines = [
        f"# Discovery Call Context — {prospect.get('prospect_company')}",
        "",
        "## 1. Meeting",
        f"- Prospect: {prospect.get('prospect_name')} ({prospect.get('prospect_title')})",
        f"- Scheduled: {booking.get('start_time_utc')} ({booking.get('prospect_timezone')})",
        f"- Delivery lead: {booking.get('lead_email')}",
        "",
        "## 2. Segment and confidence",
        f"- Segment: {b.get('primary_segment_match')} · confidence {b.get('segment_confidence', 0.0):.2f}",
        "",
        "## 3. Hiring signal summary",
        f"- Open roles: {b.get('hiring_velocity', {}).get('open_roles_today', 0)} today / {b.get('hiring_velocity', {}).get('open_roles_60_days_ago', 0)} sixty days ago",
        f"- Velocity: {b.get('hiring_velocity', {}).get('velocity_label', '?')}",
        "",
        "## 4. Gap findings",
        _render_gap(gap_brief),
        "",
        "## 5. Bench alignment",
        f"- Required stacks: {b.get('bench_to_brief_match', {}).get('required_stacks', [])}",
        f"- Gaps: {b.get('bench_to_brief_match', {}).get('gaps', [])}",
        "",
        "## 6. Thread summary",
        "(to be filled from the email thread)",
        "",
        "## 7. Objections & price bands quoted",
        "(to be filled from the thread)",
        "",
        "## 8. Suggested opening & next step",
        "- Opening: acknowledge the signal that got them on the call.",
        "- Next step: propose one concrete deliverable for the following week.",
        "",
        "## 9. Do NOT",
        "- Do not over-commit bench capacity beyond what bench_summary.json shows.",
        "- Do not speculate on layoff motivations.",
        "- Do not promise specific engineers by name.",
        "",
        "## 10. Confidence",
        f"- Langfuse trace: {trace_url}",
        f"- Overall brief confidence: {b.get('segment_confidence', 0.0):.2f}",
    ]
    return "\n".join(lines)
