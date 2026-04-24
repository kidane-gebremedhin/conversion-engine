"""Tone-preservation check.

A second LLM scores a draft 1–5 on each of the five Tenacious tone markers.
Any marker <4 triggers a regenerate (up to `tone_check.max_regenerations`).
On second failure the draft is flagged for human review and logged to
`eval/runs/tone_flagged.jsonl`.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from agent.config import config, REPO_ROOT
from agent.llm import client as llm


@dataclass
class ToneResult:
    scores: dict[str, int] = field(default_factory=dict)
    overall_ok: bool = False
    flags: list[str] = field(default_factory=list)
    rewrite_hint: str = ""
    regen_count: int = 0
    llm_call: Any = None


def _prompt_template() -> str:
    return llm.load_prompt("tone_preservation")


def _render(draft_subject: str, draft_body: str, brief_summary: str) -> str:
    t = _prompt_template()
    from agent.composer import _style_markers  # reuse single file
    return (t
            .replace("{{BRIEF_JSON_SUMMARY}}", brief_summary[:1200])
            .replace("{{SUBJECT}}", draft_subject)
            .replace("{{BODY_TEXT}}", draft_body))


def check(subject: str, body: str, *, brief_summary: str = "", regen_count: int = 0) -> ToneResult:
    prompt = _render(subject, body, brief_summary)
    model = None  # fallback to DEV_LLM_MODEL (override via TONE_CHECK_MODEL env later if set)
    resp = llm.call(prompt, tier="dev", model=model, json_mode=True, temperature=0.0, max_tokens=400)
    try:
        parsed = _extract_json(resp.text)
    except ValueError:
        # Parser failure = treat as pass to avoid blocking on infra issue,
        # but record a flag for audit.
        return ToneResult(
            scores={}, overall_ok=True, flags=["tone_check_parser_failed"],
            rewrite_hint="", regen_count=regen_count, llm_call=resp,
        )

    markers = config.get("tone_check.markers", [])
    min_score = int(config.get("tone_check.per_marker_min_score", 4))
    scores: dict[str, int] = {}
    flags: list[str] = list(parsed.get("flags", []) or [])
    ok = True
    for m in markers:
        s = int(parsed.get(m, 5))
        scores[m] = s
        if s < min_score:
            ok = False
            flags.append(f"{m}_below_min_{s}")

    return ToneResult(
        scores=scores,
        overall_ok=bool(parsed.get("overall_ok", ok)) and ok,
        flags=flags,
        rewrite_hint=str(parsed.get("rewrite_hint", "")),
        regen_count=regen_count,
        llm_call=resp,
    )


def log_flagged(draft: dict[str, Any], result: ToneResult, trace_id: str | None) -> None:
    path = REPO_ROOT / "eval" / "runs" / "tone_flagged.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "trace_id": trace_id,
        "draft": draft,
        "scores": result.scores,
        "flags": result.flags,
        "rewrite_hint": result.rewrite_hint,
        "regen_count": result.regen_count,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON in tone-check output: {text[:200]!r}")
    return json.loads(m.group(0))
