SHELL := /bin/bash
PYTHON ?= python3
VENV := .venv
ACTIVATE := . $(VENV)/bin/activate

.PHONY: help
help:
	@echo "Conversion Engine — development targets"
	@echo ""
	@echo "  setup              Create venv, install deps, copy .env.example → .env, init config.yaml"
	@echo "  smoke              Run infra/smoke_test.sh (kill-switch, sink, HubSpot, Cal.com, Langfuse)"
	@echo "  ensure-data        Materialise data/ sources (crunchbase, jobposts, layoffs) if missing"
	@echo "  enrich DOMAIN=x    Run the enrichment pipeline for one prospect domain"
	@echo "  compose-and-send DOMAIN=x"
	@echo "                     End-to-end one synthetic prospect (kill-switch enforced)"
	@echo "  tau2-baseline      Reproduce the τ²-Bench retail baseline on the dev slice"
	@echo "  tau2-eval          Run sealed held-out (eval-tier) — guarded by TAU2_SEALED_ACCESS=1 + EVAL_TIER_ENABLED=1"
	@echo "  tau2-ablation      Run Act IV ablation (A_baseline + B_mechanism + C_ablation) → method/{ablation_results.json,held_out_traces.jsonl,stat_test.md}"
	@echo "  probes             Execute the probe library against synthetic prospects"
	@echo "  memo               Render memo.md → memo.pdf (strict 2-page check)"
	@echo "  ack                Drop infra/acknowledgement_signed.txt with a UTC timestamp"
	@echo "  server             Start the FastAPI inbound server on :8000"
	@echo "  audit              Run scripts/audit_week.py against Langfuse traces"
	@echo "  test               Run pytest"
	@echo "  lint               Run ruff"
	@echo "  final-check        Pre-submission gauntlet"
	@echo "  clean              Remove caches and build artifacts"

.PHONY: setup
setup:
	@echo "→ Creating venv at $(VENV)"
	@$(PYTHON) -m venv $(VENV)
	@$(ACTIVATE) && pip install --upgrade pip
	@$(ACTIVATE) && pip install -r agent/requirements.txt
	@[ -f .env ] || cp .env.example .env && echo "→ Created .env from .env.example; fill in secrets before running smoke"
	@[ -f config.yaml ] || cp config.example.yaml config.yaml && echo "→ Created config.yaml from config.example.yaml"
	@$(ACTIVATE) && playwright install chromium || true
	@echo "→ Done. Edit .env, then run 'make smoke'."

.PHONY: smoke
smoke:
	@bash infra/smoke_test.sh

.PHONY: ensure-data
ensure-data:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/ensure_data.py

.PHONY: enrich
enrich: ensure-data
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/enrich.py --domain $(DOMAIN)

.PHONY: compose-and-send
compose-and-send: ensure-data
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/compose_and_send.py --domain $(DOMAIN)

# τ²-Bench harness — overridable knobs:
#   make tau2-baseline                                 # defaults: retail_dev_30, 5 trials, dev tier
#   make tau2-baseline TAU2_TRIALS=1                   # override one flag
#   make tau2-baseline TAU2_PARTITION=retail_dev_30 TAU2_TRIALS=5 TAU2_TIER=dev
#   make tau2-baseline TAU2_ARGS="--max-concurrency 8 --max-steps 50 --model qwen/qwen3-next-80b-a3b"
TAU2_PARTITION ?= retail_dev_30
TAU2_TRIALS    ?= 5
TAU2_TIER      ?= dev
TAU2_ARGS      ?=

.PHONY: tau2-baseline
tau2-baseline:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) -m eval.harness --partition $(TAU2_PARTITION) --trials $(TAU2_TRIALS) --tier $(TAU2_TIER) $(TAU2_ARGS)

.PHONY: tau2-eval
tau2-eval: TAU2_PARTITION = retail_sealed_20
tau2-eval: TAU2_TIER = eval
tau2-eval:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) -m eval.harness --partition $(TAU2_PARTITION) --trials $(TAU2_TRIALS) --tier $(TAU2_TIER) $(TAU2_ARGS)

# Act IV ablation — runs A_baseline + B_mechanism + C_ablation on the same
# partition and writes method/{ablation_results.json, held_out_traces.jsonl,
# stat_test.md}. Defaults to the dev partition + dev tier so iteration is
# cheap; flip to sealed + eval when ready (and after setting the dual guard).
#
#   make tau2-ablation                                       # iterate cheaply
#   make tau2-ablation TAU2_ABLATION_PARTITION=retail_sealed_20 TAU2_ABLATION_TIER=eval
#   make tau2-ablation TAU2_ABLATION_ARGS="--trials 1 --max-concurrency 8"
TAU2_ABLATION_PARTITION ?= retail_dev_30
TAU2_ABLATION_TIER      ?= dev
TAU2_ABLATION_TRIALS    ?= 5
TAU2_ABLATION_ARGS      ?=

.PHONY: tau2-ablation
tau2-ablation:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) -m method.run_ablations \
	    --partition $(TAU2_ABLATION_PARTITION) \
	    --trials $(TAU2_ABLATION_TRIALS) \
	    --tier $(TAU2_ABLATION_TIER) \
	    $(if $(filter retail_dev_30,$(TAU2_ABLATION_PARTITION)),--skip-guard,) \
	    $(TAU2_ABLATION_ARGS)

.PHONY: probes
probes:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) probes/run_probes.py $(if $(P),--probe-id $(P),)

.PHONY: memo
memo:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) memo/render.py

.PHONY: ack
ack:
	@date -u +"%Y-%m-%dT%H:%M:%SZ" > infra/acknowledgement_signed.txt
	@cp infra/acknowledgement_signed.txt policy/acknowledgement_signed.txt
	@echo "→ Acknowledgement timestamp written to infra/ and policy/"

.PHONY: server
server:
	@$(ACTIVATE) && PYTHONPATH=. uvicorn agent.server:app --host 0.0.0.0 --port 8000 --reload

.PHONY: audit
audit:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/audit_week.py

.PHONY: test
test:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) -m pytest tests/ -v

.PHONY: lint
lint:
	@$(ACTIVATE) && ruff check agent/ eval/ probes/ scripts/ tests/

.PHONY: final-check
final-check: smoke test
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/final_check.py

.PHONY: day0-hubspot day0-calcom day0-playwright day0-email
day0-hubspot:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/hubspot_smoke.py

day0-calcom:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/calcom_smoke.py

day0-playwright:
	@$(ACTIVATE) && playwright install chromium
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) -m agent.enrichment.jobposts_smoke

day0-email:
	@$(ACTIVATE) && PYTHONPATH=. $(PYTHON) scripts/email_smoke.py $(if $(TO),--to $(TO),)

.PHONY: clean
clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
