"""Run N synthetic prospects through enrichment + cold outreach, for latency + trace volume.

Used by `make run-batch N=20`. Prospects are drawn from the fixture file and
cycled; each run produces at least one `email.send` span with a real elapsed_ms
so the latency report has ≥ 20 interactions.
"""
from __future__ import annotations

import argparse
import pathlib

import yaml

from agent.main import build_deps, load_prospect
from agent.orchestrator import Orchestrator


def main() -> int:
    p = argparse.ArgumentParser("run_batch")
    p.add_argument("--n", type=int, default=20)
    args = p.parse_args()

    prospects = yaml.safe_load(pathlib.Path("tests/fixtures/synthetic_prospects.yaml").read_text())["prospects"]
    aliases = [row["alias"] for row in prospects]

    _, _, deps = build_deps()
    orch = Orchestrator(deps)
    for i in range(args.n):
        alias = aliases[i % len(aliases)]
        prospect = load_prospect(alias)
        state = orch.run_cold(prospect)
        # Drive a reply on every second run to generate reply-classification spans.
        if i % 2 == 0:
            orch.handle_email_reply(state, prospect, "Thanks — Thursday 2pm works, send a calendar link.")
        print(f"[batch {i+1}/{args.n}] alias={alias} final={state.stage.value} seg={state.segment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
