# Contributing

Thanks for taking a look. This is a portfolio repo, but it's built like real
software — tested, linted-by-convention, and easy to extend. Contributions and
forks are welcome.

## Project layout

```
projects/llm-log-triage/   # the flagship — Python + SQL detection pipeline
reference/                 # OWASP LLM Top 10, MITRE ATLAS, glossary
red-team/                  # PyRIT / garak / promptfoo + an offline harness
docs/                      # interview-prep dossier
```

## Setup

The flagship uses **only the Python standard library** at runtime; the sole dev
dependency is `pytest`.

```bash
cd projects/llm-log-triage
python -m pip install -r requirements.txt   # just pytest
python -m pytest -q                          # 83 tests, ~1s
python -m src.cli run --db /tmp/t.db --logs data/sample_logs.jsonl   # end-to-end demo
make demo | make test | make queries         # convenience targets
```

CI (`.github/workflows/ci.yml`) runs the test suite and an end-to-end smoke test
on Python 3.10–3.12 for every push and PR.

## Adding a detector

The detection engine (`src/detectors.py`) is intentionally easy to extend:

1. Add a `Detector` (usually a `RegexDetector` with `applies_to_roles` /
   `applies_to_sources` gates, or a small subclass for custom logic).
2. Map it to an **OWASP LLM Top 10 (2025)** id and a **MITRE ATLAS** technique —
   every finding carries both. See [`reference/`](reference/) for the taxonomies.
3. Append it to `ALL_DETECTORS`. Nothing else needs to change — `detect()`,
   the DB layer, and the catalog pick it up automatically.
4. Add tests in `tests/` for both true positives **and** benign non-matches.
   New detectors should also be exercised by the synthetic generator
   (`src/generate_logs.py`) so the end-to-end pipeline has signal.

Run `python red-team/local_redteam_harness.py` to see new detectors grade a
red-team battery.

## Conventions

- **Match the surrounding style** — small, explainable units; every finding has a
  matched snippet and a plain-English rationale.
- **No silent false negatives in tests** — when you tighten a pattern to kill a
  false positive, add the benign case that must now stay quiet.
- **Keep the runtime dependency-free** — reach for the standard library first.
- **Accuracy over polish in docs** — if you change a detector or query, update
  the affected README/reference tables in the same change.

## Pull requests

1. Branch from `main`.
2. Make sure `python -m pytest -q` is green and the demo still runs.
3. Describe what changed and why; link the OWASP/ATLAS class if you touched detection.
