PY ?= python3

.PHONY: help setup bootstrap baseline run run-batch enrich probe memo latency health clean

help:
	@echo "Conversion Engine — Makefile targets"
	@echo "  make setup           install Python deps"
	@echo "  make bootstrap       seed synthetic prospects + fixture HubSpot/Cal.com state"
	@echo "  make baseline        τ²-Bench dev-slice pass@1 × N trials → eval/score_log.json"
	@echo "  make run PROSPECT=<uuid>          full COLD → BOOKED on one prospect"
	@echo "  make run-batch N=20  run N prospects for latency + trace volume"
	@echo "  make enrich PROSPECT=<uuid>       run enrichment pipeline for one prospect"
	@echo "  make latency         compute p50/p95 from eval/trace_log.jsonl"
	@echo "  make health          agent --healthcheck"
	@echo "  make clean           drop caches, audit logs, local traces"

setup:
	$(PY) -m pip install -e .

bootstrap:
	$(PY) -m scripts.seed_synthetic_prospects

baseline:
	$(PY) -m eval.run_baseline --trials 5

run:
	@test -n "$$PROSPECT" || (echo "usage: make run PROSPECT=<crunchbase_uuid>"; exit 2)
	$(PY) -m agent.main --prospect $$PROSPECT

run-batch:
	$(PY) -m scripts.run_batch --n $${N:-20}

enrich:
	@test -n "$$PROSPECT" || (echo "usage: make enrich PROSPECT=<crunchbase_uuid>"; exit 2)
	$(PY) -m agent.main --enrich $$PROSPECT

latency:
	$(PY) -m scripts.latency_report

probe:
	@echo "Act III deliverable — see __plans/02-d4-act3-probes.md"

memo:
	@echo "Act V deliverable — see __plans/04-d7-act5-memo-demo.md"

health:
	$(PY) -m agent.main --healthcheck

clean:
	rm -rf data/briefs_cache data/sink data/hubspot_local data/calcom_local \
	       data/killswitch_audit.jsonl data/local_traces.jsonl \
	       eval/score_log.json eval/trace_log.jsonl eval/latency_report.json
	find . -name __pycache__ -type d -exec rm -rf {} +
