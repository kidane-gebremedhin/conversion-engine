# Inheritor README — next trainee

If you're picking this up after this trainee rolls off, here is what you
need to know in under five minutes.

## What runs today

- `make smoke` — green, 5 checks, ~30s.
- `make enrich DOMAIN=<d>` — produces briefs in `eval/briefs/<d>/`.
- `make compose-and-send DOMAIN=<d>` — end-to-end one prospect; routes to
  staff sink while `TENACIOUS_OUTBOUND_ENABLED` is unset.
- `make tau2-baseline` — τ²-Bench harness (mock mode if tau2-bench not
  installed, else real; either way writes `eval/score_log.json`).
- `make probes` — runs the probe library and refreshes `probes/failure_taxonomy.md`.
- `make memo` — substitutes claim tokens, renders PDF (or markdown
  fallback).

## The three non-negotiables

1. **Kill switch defaults unset.** Never flip without program-staff approval.
2. **No real customer contact.** Only sink + synthetic prospects.
3. **Grounded or silent.** Every claim in the memo must trace to a file.

## What's stubbed and needs real work

- `eval/harness.py` mock-runs τ²-Bench when the library isn't installed;
  drop in a real adapter at `_run_task_real` once `eval/tau2/` is cloned
  and pinned.
- LLM client falls back to a deterministic stub without an API key;
  flip to real calls by setting `OPENROUTER_API_KEY`.
- GEPA baseline numbers in `ablation_results.json` are placeholders.
  Plug in real numbers from a GEPA run at the same dollar budget.
- Production metrics for the memo are drawn from
  `eval/runs/interim/production_metrics.json` — that file is aggregated
  by a small script you should write next (walks traces, counts).

## Useful paths

- Kill switch: [`agent/kill_switch.py`](../agent/kill_switch.py)
- Classifier: [`agent/classifier.py`](../agent/classifier.py)
- Composer: [`agent/composer.py`](../agent/composer.py)
- Pipeline: [`agent/enrichment/pipeline.py`](../agent/enrichment/pipeline.py)
- Harness: [`eval/harness.py`](../eval/harness.py)
- Probes: [`probes/run_probes.py`](../probes/run_probes.py)
- Memo: [`memo/render.py`](render.py)
