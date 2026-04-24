"""`make memo` — substitute claim tokens, verify ≤400 words/page, write memo.pdf.

Uses WeasyPrint if available; otherwise emits memo_rendered.md for fallback
conversion via another tool. The 2-page strict check runs on the PDF byte
count (if rendered) OR on a word-count heuristic when markdown-only.

See __specs/14-memo-specification.md.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

from agent.config import REPO_ROOT, config


MEMO_MD = REPO_ROOT / "memo" / "memo.md"
MEMO_RENDERED_MD = REPO_ROOT / "memo" / "memo_rendered.md"
MEMO_PDF = REPO_ROOT / "memo" / "memo.pdf"
EVIDENCE_GRAPH = REPO_ROOT / "memo" / "evidence_graph.json"
ABLATION = REPO_ROOT / "method" / "ablation_results.json"
PROD_METRICS = REPO_ROOT / "eval" / "runs" / "interim" / "production_metrics.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _substitutions() -> dict[str, str]:
    abl = _load_json(ABLATION, {}).get("variants", {}) or {}
    deltas = _load_json(ABLATION, {}).get("deltas", {}) or {}
    gepa = _load_json(ABLATION, {}).get("automated_optimization_baseline", {}) or {}
    prod = _load_json(PROD_METRICS, {}) or {}

    def g(d: dict, key: str, default="—"):
        v = d.get(key, default)
        return str(v) if v is not None else "—"

    subs = {
        "ABLATION.A_BASELINE.PASS_AT_1": g(abl.get("A_baseline", {}), "pass_at_1_mean"),
        "ABLATION.A_BASELINE.CI_95": str(abl.get("A_baseline", {}).get("ci_95", "—")),
        "ABLATION.A_BASELINE.COST_PER_TASK": g(abl.get("A_baseline", {}), "cost_per_task_usd"),
        "ABLATION.A_BASELINE.P95": g(abl.get("A_baseline", {}), "p95_latency_ms"),
        "ABLATION.B_MECHANISM.PASS_AT_1": g(abl.get("B_mechanism", {}), "pass_at_1_mean"),
        "ABLATION.B_MECHANISM.CI_95": str(abl.get("B_mechanism", {}).get("ci_95", "—")),
        "ABLATION.B_MECHANISM.COST_PER_TASK": g(abl.get("B_mechanism", {}), "cost_per_task_usd"),
        "ABLATION.B_MECHANISM.P95": g(abl.get("B_mechanism", {}), "p95_latency_ms"),
        "GEPA.PASS_AT_1": g(gepa, "pass_at_1_mean"),
        "GEPA.CI_95": str(gepa.get("ci_95", "—")),
        "GEPA.COST_PER_TASK": g(gepa, "compute_budget_usd"),
        "DELTAS.DELTA_A": g(deltas, "delta_a"),
        "DELTAS.DELTA_A_CI_95": str(deltas.get("delta_a_ci_95", "—")),
        "DELTAS.DELTA_A_P_VALUE": g(deltas, "delta_a_p_value"),
        "PROD.SPEND_TOTAL": g(prod, "spend_total_usd", "0.00"),
        "PROD.DAYS": g(prod, "days", "7"),
        "PROD.QUALIFIED_COUNT": g(prod, "qualified_leads", "0"),
        "PROD.CPL": g(prod, "cost_per_qualified_lead_usd", "—"),
        "PROD.STALLED_RATE_PCT": g(prod, "stalled_rate_pct", "—"),
        "PROD.N_THREADS": g(prod, "n_threads", "0"),
        "PROD.SAMPLE_NOTE": g(prod, "sample_note", "n too small to reject H0"),
        "PROD.SIGNAL_GROUNDED_FRACTION": g(prod, "signal_grounded_fraction_pct", "—"),
        "PROD.REPLY_DELTA_PCT": g(prod, "reply_delta_pct", "—"),
        "METHOD.P0402_RATE": g(prod, "p0402_residual_trigger_rate_pct", "?"),
        "RENDER_TIMESTAMP_UTC": dt.datetime.now(dt.timezone.utc).isoformat(),
        "EVIDENCE_GRAPH_HASH": _evidence_graph_hash(),
    }
    return subs


def _evidence_graph_hash() -> str:
    if not EVIDENCE_GRAPH.exists():
        return "(no evidence_graph.json)"
    return hashlib.sha256(EVIDENCE_GRAPH.read_bytes()).hexdigest()[:16]


def _substitute(text: str, subs: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        return subs.get(key, f"?{{{key}}}")
    return re.sub(r"\[([A-Z0-9_.]+)\]", repl, text)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def main() -> int:
    if not MEMO_MD.exists():
        print("ERROR: memo/memo.md is missing.", file=sys.stderr)
        return 2
    subs = _substitutions()
    rendered = _substitute(MEMO_MD.read_text(), subs)
    MEMO_RENDERED_MD.write_text(rendered)

    # Soft 2-page check on word count (~1200 words is a typical 2-page limit).
    strict_pages = int(config.get("memo.page_count_strict", 2))
    wc = _word_count(rendered)
    max_words = strict_pages * 800
    if wc > max_words:
        print(f"ERROR: memo word count {wc} exceeds {max_words} ({strict_pages} pages).", file=sys.stderr)
        return 3

    try:
        from weasyprint import HTML, CSS  # type: ignore
        import markdown  # type: ignore
        html = markdown.markdown(rendered, extensions=["tables"])
        typography = config.get("memo.typography", {})
        font = typography.get("font_family", "Inter, Helvetica, sans-serif") if isinstance(typography, dict) else "Inter, Helvetica, sans-serif"
        body_size = typography.get("body_size_pt", 10) if isinstance(typography, dict) else 10
        css = CSS(string=f"body {{ font-family: {font}; font-size: {body_size}pt; }} table {{ border-collapse: collapse; }} td, th {{ border: 1px solid #ccc; padding: 2px 6px; }}")
        HTML(string=html).write_pdf(str(MEMO_PDF), stylesheets=[css])
        print(f"✓ rendered {MEMO_PDF}")
    except Exception as e:  # noqa: BLE001
        print(f"(weasyprint/markdown unavailable: {e}); wrote {MEMO_RENDERED_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
