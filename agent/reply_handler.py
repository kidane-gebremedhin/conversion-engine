"""Reply classifier + class-specific handlers.

Inbound reply → classifier → class-specific compose OR suppress OR handoff.
Ambiguous (confidence < 0.7) → handoff, no reply. hard_no → suppress.

See __specs/06-agent-design.md, capabilities 2 and 3.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agent.config import config
from agent.llm import client as llm


@dataclass
class ReplyClassification:
    class_: str
    confidence: float
    rationale: str = ""
    objection_topic: str | None = None
    suggested_action: str = "reply"


_AMBIGUOUS_THRESHOLD = float(config.get("reply.ambiguous_threshold", 0.70))
_OPT_OUT_PATTERNS = tuple(config.get("reply.opt_out_patterns", []))


def _pre_classify_hard_no(text: str) -> bool:
    low = (text or "").lower()
    return any(p.lower() in low for p in _OPT_OUT_PATTERNS)


def classify_reply(reply_text: str) -> ReplyClassification:
    # Fast-path opt-out detection — model calls are never trusted for this.
    if _pre_classify_hard_no(reply_text):
        return ReplyClassification(
            class_="hard_no", confidence=1.0,
            rationale="opt-out pattern matched via rule",
            suggested_action="suppress",
        )

    prompt = llm.load_prompt("reply_classifier").replace("{{REPLY_TEXT}}", reply_text)
    resp = llm.call(prompt, tier="dev", json_mode=True, temperature=0.0, max_tokens=400)
    try:
        obj = _extract_json(resp.text)
    except ValueError:
        return ReplyClassification(
            class_="ambiguous", confidence=0.0,
            rationale="classifier parse failed — routed to human",
            suggested_action="handoff",
        )

    cls = str(obj.get("class", "ambiguous"))
    conf = float(obj.get("confidence", 0.0))
    action = str(obj.get("suggested_action", "reply"))
    if cls == "ambiguous" or conf < _AMBIGUOUS_THRESHOLD:
        return ReplyClassification(
            class_="ambiguous", confidence=conf,
            rationale=str(obj.get("rationale", "low confidence")),
            suggested_action="handoff",
        )
    if cls == "hard_no":
        action = "suppress"
    return ReplyClassification(
        class_=cls, confidence=conf,
        rationale=str(obj.get("rationale", "")),
        objection_topic=obj.get("objection_topic"),
        suggested_action=action,
    )


# ────────────────────────────────────────────────────────────────────────────
# Class-specific response composition
# ────────────────────────────────────────────────────────────────────────────


def compose_warm_reply(
    *,
    classification: ReplyClassification,
    reply_text: str,
    prospect: dict[str, Any],
    cal_link: str,
    slots: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """Return {subject, body_text, ...meta}."""
    if classification.class_ == "engaged":
        return _compose_engaged(reply_text, prospect, cal_link, slots)
    if classification.class_ == "curious":
        return _compose_curious(reply_text, prospect, cal_link)
    if classification.class_ == "soft_defer":
        return _compose_soft_defer(reply_text, prospect)
    if classification.class_ == "objection":
        return _compose_objection(reply_text, prospect, cal_link, classification.objection_topic)
    # Should never be called for hard_no / ambiguous
    raise ValueError(f"No warm-reply path for class {classification.class_!r}")


def _compose_engaged(reply_text: str, prospect: dict[str, Any], cal_link: str, slots: tuple[str, str] | None) -> dict[str, Any]:
    prompt = llm.load_prompt("reply_engaged")
    prompt = _fill(prompt, {
        "STYLE_MARKERS": _style_markers(),
        "REPLY_TEXT": reply_text,
        "PROSPECT_TIMEZONE": prospect.get("prospect_timezone", "UTC"),
        "CAL_LINK": cal_link,
        "SLOT_1": (slots or ("",))[0],
        "SLOT_2": (slots or ("", ""))[1] if slots else "",
    })
    resp = llm.call(prompt, tier="dev", json_mode=True, temperature=0.3, max_tokens=500)
    return _parse_or_fallback(resp.text, prospect, cal_link, kind="engaged")


def _compose_curious(reply_text: str, prospect: dict[str, Any], cal_link: str) -> dict[str, Any]:
    from agent.enrichment import bench

    stacks = ", ".join(sorted(s for s, n in {s: bench.available(s) for s in bench.all_stacks()}.items() if n > 0))
    prompt = llm.load_prompt("reply_curious")
    prompt = _fill(prompt, {
        "STYLE_MARKERS": _style_markers(),
        "REPLY_TEXT": reply_text,
        "BENCH_STACKS": stacks,
        "CAL_LINK": cal_link,
    })
    resp = llm.call(prompt, tier="dev", json_mode=True, temperature=0.3, max_tokens=400)
    return _parse_or_fallback(resp.text, prospect, cal_link, kind="curious")


def _compose_soft_defer(reply_text: str, prospect: dict[str, Any]) -> dict[str, Any]:
    prompt = llm.load_prompt("reply_soft_defer")
    prompt = _fill(prompt, {
        "STYLE_MARKERS": _style_markers(),
        "REPLY_TEXT": reply_text,
        "REENGAGE_WINDOW": "45 days",
    })
    resp = llm.call(prompt, tier="dev", json_mode=True, temperature=0.3, max_tokens=300)
    parsed = _parse_or_fallback(resp.text, prospect, "", kind="soft_defer")
    return parsed


def _compose_objection(reply_text: str, prospect: dict[str, Any], cal_link: str, topic: str | None) -> dict[str, Any]:
    prompt = llm.load_prompt("reply_objection")
    prompt = _fill(prompt, {
        "STYLE_MARKERS": _style_markers(),
        "REPLY_TEXT": reply_text,
        "OBJECTION_TOPIC": topic or "unknown",
        "CAL_LINK": cal_link,
    })
    resp = llm.call(prompt, tier="dev", json_mode=True, temperature=0.3, max_tokens=500)
    return _parse_or_fallback(resp.text, prospect, cal_link, kind="objection")


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _style_markers() -> str:
    from agent.composer import _style_markers as _sm

    return _sm()


def _fill(t: str, subs: dict[str, str]) -> str:
    for k, v in subs.items():
        t = t.replace("{{" + k + "}}", v)
    return t


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON")
    return json.loads(m.group(0))


def _parse_or_fallback(text: str, prospect: dict[str, Any], cal_link: str, *, kind: str) -> dict[str, Any]:
    try:
        obj = _extract_json(text)
        if obj.get("stub"):
            raise ValueError("stub")
        subject = str(obj.get("subject", "")).strip() or "Re: your note"
        body = str(obj.get("body_text", "")).strip() or _fallback_body(kind, prospect, cal_link)
        obj["subject"] = subject
        obj["body_text"] = body
        return obj
    except Exception:
        return {
            "subject": "Re: your note",
            "body_text": _fallback_body(kind, prospect, cal_link),
        }


def _fallback_body(kind: str, prospect: dict[str, Any], cal_link: str) -> str:
    first = str(prospect.get("prospect_name", "")).split(" ", 1)[0]
    if kind == "engaged":
        return (f"Thanks {first}. Happy to do 15 minutes this week or next. "
                f"Pick any time that works: {cal_link}")
    if kind == "curious":
        return (f"Short answer, {first} — we run a small engineering team on monthly pricing; "
                f"most engagements run 2–6 engineers across Python, data, and infra. "
                f"If useful, 15 minutes here: {cal_link}")
    if kind == "objection":
        return (f"Thanks {first} — understood. Happy to share specific numbers on a short call; "
                f"no pressure to commit. {cal_link}")
    if kind == "soft_defer":
        return (f"Understood, {first}. I'll reach back in about six weeks with one specific "
                f"peer-group signal worth your time.")
    return "Thanks — will follow up shortly."
