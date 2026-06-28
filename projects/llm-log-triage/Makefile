# Convenience targets for the LLM Log Triage flagship project.
# Usage: `make demo`, `make test`, `make queries`, `make clean`.

PY ?= python3
DB ?= triage.db
LOGS ?= data/sample_logs.jsonl

.PHONY: help demo test queries data clean

help:
	@echo "Targets:"
	@echo "  make demo     - ingest the sample logs, run detectors, print the triage report"
	@echo "  make test     - run the pytest suite"
	@echo "  make queries  - run every analyst SQL query against the demo DB"
	@echo "  make data     - regenerate the messy sample dataset"
	@echo "  make clean    - remove generated databases"

demo:
	$(PY) -m src.cli run --db $(DB) --logs $(LOGS)

test:
	$(PY) -m pytest -q

queries: demo
	@for q in sql/analysis/*.sql; do \
		echo "\n==================== $$q ===================="; \
		$(PY) -m src.cli query --db $(DB) --sql $$q; \
	done

data:
	$(PY) -m src.cli generate --rows 800 --out $(LOGS) --seed 7

clean:
	rm -f *.db *.db-wal *.db-shm
