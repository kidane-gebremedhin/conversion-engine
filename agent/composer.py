"""Tone-aware composer — the one place the LLM drafts prospect-facing email.

Input: a segment + briefs + a prospect row. Output: a dict with subject,
body_text, and briefs_referenced (for grounding audit). Deterministic
post-checks enforce style rules before the draft goes to the tone check.

See __specs/06-agent-design.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.classifier import SegmentMismatch
from agent.config import REPO_ROOT, config
from agent.enrichment import bench
from agent.llm import client as llm


@dataclass
class Draft:
    subject: str
    body_text: str
    briefs_referenced: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    segment: str = ""
    prompt_id: str = ""
    llm_call: Any = None


class ComposerError(RuntimeError):
    pass


_ALLOWED_SUBJECT_FIRSTS = tuple(
    w.lower() for w in config.get("composer.cold.subject_first_word_allowed", [
        "Context", "Note", "Request", "Congrats", "Question", "Follow-up",
    ])
)
_FORBIDDEN_SUBJECT_FIRSTS = tuple(
    w.lower() for w in config.get("composer.cold.subject_first_word_forbidden", [
        "Quick", "Just", "Hey", "Checking",
    ])
)
_DISALLOWED_PHRASES = tuple(p.lower() for p in config.get("composer.disallowed_phrases", []))


def _load_prompt(prompt_id: str) -> str:
    return llm.load_prompt(prompt_id)


def _style_markers() -> str:
    p = REPO_ROOT / "agent" / "prompts" / "_style_markers.txt"
    return p.read_text(encoding="utf-8")


def _subject_valid(subject: str) -> tuple[bool, str]:
    if not subject:
        return False, "empty subject"
    if len(subject) > int(config.get("composer.cold.subject_max_chars", 60)):
        return False, f"subject > {config.get('composer.cold.subject_max_chars', 60)} chars"
    first = subject.strip().split(" ", 1)[0].lower().rstrip(":,")
    if first in _FORBIDDEN_SUBJECT_FIRSTS:
        return False, f"subject first word forbidden: {first!r}"
    return True, "ok"


def _word_count(s: str) -> int:
    return len(re.findall(r"\b\w+\b", s))


def _max_body_words(segment: str, sequence_position: str) -> int:
    if sequence_position.startswith("warm_"):
        cls = sequence_position.replace("warm_", "")
        if cls == "engaged":
            return int(config.get("composer.warm.engaged_max_words", 150))
        if cls == "curious":
            return int(config.get("composer.warm.curious_max_words", 90))
        if cls == "soft_defer":
            return int(config.get("composer.warm.soft_defer_max_words", 60))
    if sequence_position == "cold_1":
        return int(config.get("composer.cold.email_1_max_words", 120))
    if sequence_position == "cold_2":
        return int(config.get("composer.cold.email_2_max_words", 100))
    if sequence_position == "cold_3":
        return int(config.get("composer.cold.email_3_max_words", 70))
    return int(config.get("composer.cold.email_1_max_words", 120))


def _contains_disallowed(text: str) -> list[str]:
    low = text.lower()
    return [p for p in _DISALLOWED_PHRASES if p in low]


def _prompt_for(segment: str) -> str:
    mapping = {
        "segment_1_series_a_b": "composer_segment_1",
        "segment_2_mid_market_restructure": "composer_segment_2",
        "segment_3_leadership_transition": "composer_segment_3",
        "segment_4_specialized_capability": "composer_segment_4",
        "abstain": "composer_abstain",
    }
    return mapping.get(segment, "composer_abstain")


def _render_prompt(
    template: str,
    *,
    brief: Any,
    gap_brief: Any,
    prospect: dict[str, Any],
    cal_link: str,
) -> str:
    b = brief.model_dump() if hasattr(brief, "model_dump") else brief
    funding = b.get("buying_window_signals", {}).get("funding_event") or {}
    layoff = b.get("buying_window_signals", {}).get("layoff_event") or {}
    lead = b.get("buying_window_signals", {}).get("leadership_change") or {}
    velocity = b.get("hiring_velocity") or {}
    ai = b.get("ai_maturity") or {}
    stacks = ", ".join(sorted(s for s, n in {s: bench.available(s) for s in bench.all_stacks()}.items() if n > 0))

    gap_text = ""
    top_q = ""
    if gap_brief is not None:
        g = gap_brief.model_dump() if hasattr(gap_brief, "model_dump") else gap_brief
        top_q = f"{g.get('sector_top_quartile_benchmark'):.1f}"
        for i, gf in enumerate(g.get("gap_findings", []) or []):
            evs = gf.get("peer_evidence") or []
            ev_str = "; ".join(f"{e.get('competitor_name')}: {e.get('evidence')}" for e in evs[:2])
            gap_text += f"  [{i}] ({gf.get('confidence')}) {gf.get('practice')} — {ev_str}\n"

    subs = {
        "STYLE_MARKERS": _style_markers(),
        "PROSPECT_NAME": prospect.get("prospect_name", ""),
        "PROSPECT_TITLE": prospect.get("prospect_title", ""),
        "PROSPECT_COMPANY": prospect.get("prospect_company", ""),
        "PROSPECT_SECTOR": b.get("prospect_name", ""),
        "OPEN_ROLES_TODAY": str(velocity.get("open_roles_today", 0)),
        "OPEN_ROLES_60D_AGO": str(velocity.get("open_roles_60_days_ago", 0)),
        "VELOCITY_LABEL": str(velocity.get("velocity_label", "insufficient_signal")),
        "FUNDING_STAGE": str(funding.get("stage") or "—"),
        "FUNDING_AMOUNT_USD": str(funding.get("amount_usd") or "—"),
        "FUNDING_CLOSED_AT": str(funding.get("closed_at") or "—"),
        "LAYOFF_DATE": str(layoff.get("date") or "—"),
        "LAYOFF_PCT": f"{(layoff.get('percentage_cut') or 0) * 100:.0f}" if layoff.get("detected") else "—",
        "NEW_LEADER_ROLE": str(lead.get("role") or "—"),
        "NEW_LEADER_NAME": str(lead.get("new_leader_name") or "—"),
        "LEADERSHIP_STARTED_AT": str(lead.get("started_at") or "—"),
        "AI_SCORE": str(ai.get("score", 0)),
        "AI_CONFIDENCE": f"{ai.get('confidence', 0.0):.2f}",
        "BENCH_STACKS": stacks or "(none currently)",
        "CAL_LINK": cal_link,
        "TOP_QUARTILE_BENCHMARK": top_q,
        "GAP_FINDINGS": gap_text or "  (none)",
    }
    out = template
    for k, v in subs.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    # find outermost {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ComposerError(f"LLM did not return JSON: {text[:200]!r}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ComposerError(f"LLM JSON parse failed: {e}; text={text[:200]!r}") from e


def compose(
    *,
    segment: str,
    brief: Any,
    gap_brief: Any | None,
    prospect: dict[str, Any],
    cal_link: str,
    sequence_position: str = "cold_1",
    tier: str = "dev",
    rewrite_hint: str = "",
) -> Draft:
    """Produce one draft for the given (segment, briefs, prospect) tuple.

    `rewrite_hint`, when non-empty, is appended to the rendered prompt to
    steer the LLM on a regeneration attempt — typically the `rewrite_hint`
    field returned by tone_check on a failed first pass.

    Raises:
        SegmentMismatch: if segment == 4 and AI-maturity < 2 (spec 03 hard gate).
        ComposerError:   on irrecoverable LLM output issues.
    """
    ai_score = int((brief.model_dump() if hasattr(brief, "model_dump") else brief)
                   .get("ai_maturity", {}).get("score", 0))
    if segment == "segment_4_specialized_capability" and ai_score < 2:
        raise SegmentMismatch(
            f"Segment 4 requires AI-maturity ≥2; prospect score={ai_score}. "
            "Per __specs/03-icp-and-segments.md this is refused at composer input."
        )

    prompt_id = _prompt_for(segment)
    template = _load_prompt(prompt_id)
    rendered = _render_prompt(
        template, brief=brief, gap_brief=gap_brief, prospect=prospect, cal_link=cal_link,
    )
    if rewrite_hint:
        rendered += (
            "\n\n=== REWRITE GUIDANCE (from tone-check on prior draft) ===\n"
            "The previous draft failed the tone check. Address each item below\n"
            "in the new draft while keeping all factual claims grounded in the\n"
            "brief above. Do not invent new numbers.\n\n"
            f"{rewrite_hint.strip()}\n"
        )

    resp = llm.call(
        rendered, tier=tier, json_mode=True,
        max_tokens=int(config.get("composer.cold.max_tokens", 800)) if False else 800,
        temperature=0.3,
    )

    parsed = _parse_llm_json(resp.text)
    subject = str(parsed.get("subject", "")).strip()
    body = str(parsed.get("body_text", "")).strip()
    briefs_ref = list(parsed.get("briefs_referenced", []))

    # In stub mode the LLM returns {"stub": True,...}; synthesize a safe draft.
    if parsed.get("stub") or not subject or not body:
        subject, body = _fallback_draft(segment, prospect, cal_link)

    # Deterministic post-checks
    ok, reason = _subject_valid(subject)
    if not ok:
        raise ComposerError(f"Subject failed post-check: {reason}; subject={subject!r}")
    max_words = _max_body_words(segment, sequence_position)
    wc = _word_count(body)
    if wc > max_words:
        raise ComposerError(f"Body word count {wc} > {max_words} for {segment}/{sequence_position}")
    bad = _contains_disallowed(subject + "\n" + body)
    if bad:
        raise ComposerError(f"Disallowed phrases in draft: {bad}")

    return Draft(
        subject=subject, body_text=body,
        briefs_referenced=briefs_ref,
        notes=[f"words={wc}/{max_words}"],
        segment=segment,
        prompt_id=prompt_id,
        llm_call=resp,
    )


def _fallback_draft(segment: str, prospect: dict[str, Any], cal_link: str) -> tuple[str, str]:
    """Safe, deterministic, policy-compliant draft used when the LLM is stubbed.

    Does not reference brief numerics. Reads as a softly-framed exploratory
    note. Good enough to exercise the kill-switch and post-check plumbing;
    real drafts replace this when OPENROUTER_API_KEY is set.
    """
    first = str(prospect.get("prospect_name", "")).split(" ", 1)[0]
    company = prospect.get("prospect_company", "")
    if segment == "segment_3_leadership_transition":
        subject = "Congrats on the appointment"
        body = (
            f"Hi {first}, congrats on the new role at {company}. "
            "When the team shape is settled, we help engineering leaders stand up "
            "delivery capacity on a monthly pricing model. No rush — happy to be "
            "useful when useful. "
            f"If you'd prefer to book 15 minutes directly: {cal_link}"
        )
    else:
        subject = f"Context: engineering capacity at {company}"
        body = (
            f"Hi {first}, reaching out with a narrow question about how {company} "
            "scopes delivery capacity. We run a small engineering team on monthly "
            "pricing — useful when in-house hiring is the bottleneck. "
            f"If helpful: {cal_link}"
        )
    return subject, body
