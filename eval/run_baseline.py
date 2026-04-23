"""Run the τ²-Bench dev-slice baseline + reproduction check.

Emits `eval/score_log.json` and appends trajectories to `eval/trace_log.jsonl`.
Per __specs/11 §5 / §9.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
from dataclasses import asdict
from datetime import datetime, timezone

from agent.config import load_config, load_secrets, validate
from agent.llm.client import LlmClient
from eval.harness import ScoreReport, Tau2BenchHarness


_EVAL_DIR = pathlib.Path("eval")
_TRACE_LOG = _EVAL_DIR / "trace_log.jsonl"
_SCORE_LOG = _EVAL_DIR / "score_log.json"
_LOCAL_TRACES = pathlib.Path("data/local_traces.jsonl")


def run(trials: int, seed: int) -> dict:
    cfg = load_config()
    secrets = load_secrets()
    validate(secrets, cfg)
    llm = LlmClient(
        mode=secrets.convergine_llm_mode,
        api_key=(secrets.openrouter_api_key.get_secret_value() if secrets.openrouter_api_key else None),
        base_url=secrets.openrouter_base_url,
        dev_tier_model=(cfg.get("llm", "models", "dev_tier", "primary", "name") or "qwen/qwen3-next-80b-a3b-instruct"),
        prices=cfg.get("llm", "prices", default={}),
        seed=seed,
    )
    # Clear local traces so the eval run is clean for trace_log.
    _LOCAL_TRACES.unlink(missing_ok=True)

    runs: list[ScoreReport] = []
    for method in ("day1_baseline", "reproduction_check"):
        harness = Tau2BenchHarness(
            slice_file="eval/dev_slice.json",
            llm=llm,
            trials=trials,
            seed=seed,
        )
        res = harness.run_slice(method)
        runs.append(harness.score(res))

    # Copy accumulated local traces into the eval trace log.
    _EVAL_DIR.mkdir(exist_ok=True)
    if _LOCAL_TRACES.exists():
        shutil.copy(_LOCAL_TRACES, _TRACE_LOG)

    score_log = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "trials": trials,
        "published_reference": {
            "source": "Sierra Research τ²-Bench retail baseline",
            "pass_at_1": 0.42,
            "note": "~42% published voice-agent ceiling (challenge document baseline table)",
        },
        "runs": [asdict(r) for r in runs],
    }
    _SCORE_LOG.write_text(json.dumps(score_log, indent=2))
    return score_log


def main() -> int:
    p = argparse.ArgumentParser("tau2_bench_baseline")
    p.add_argument("--trials", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    out = run(args.trials, args.seed)
    # Terse stdout summary.
    for r in out["runs"]:
        print(
            f"[{r['method']}] n_tasks={r['n_tasks']} "
            f"pass@1={r['mean_pass_at_1']:.4f} "
            f"95% CI=[{r['ci_lower_95']:.4f}, {r['ci_upper_95']:.4f}] "
            f"p50={r['p50_latency_ms']}ms p95={r['p95_latency_ms']}ms "
            f"total_cost=${r['total_cost_usd']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
