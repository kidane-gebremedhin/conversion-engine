"""Reply classifier: opt-out fast-path and ambiguous-routing."""
from __future__ import annotations

from agent.reply_handler import classify_reply


def test_opt_out_patterns_become_hard_no():
    for text in ("Please remove me from this list",
                 "not interested, stop emailing",
                 "unsubscribe"):
        r = classify_reply(text)
        assert r.class_ == "hard_no"
        assert r.suggested_action == "suppress"


def test_stub_mode_routes_to_handoff():
    """In stub mode the classifier LLM returns 'ambiguous' at low conf.
    The pipeline MUST route ambiguous to handoff (not reply)."""
    r = classify_reply("Interesting but can we follow up in Q3?")
    # In stub mode, low confidence is expected; any ambiguous result → handoff
    if r.class_ == "ambiguous":
        assert r.suggested_action == "handoff"
    else:
        # If a real LLM is wired, any decisive class is acceptable.
        assert r.class_ in ("engaged", "curious", "hard_no", "soft_defer", "objection", "ambiguous")
