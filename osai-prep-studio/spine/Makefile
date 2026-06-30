PY ?= python3

# Run the spine test suite (stdlib + pytest only).
test:
	$(PY) -m pytest -q

# Print the canonical taxonomy registry (detectors + OWASP + agentic).
catalog:
	$(PY) -m osai_spine.cli catalog

# Validate every lab manifest against the taxonomy registry (the binding rule).
validate:
	$(PY) -m osai_spine.cli validate-manifests

# End-to-end smoke: derive a flag, then two-signal grade a passing submission.
smoke:
	@$(PY) -c "import json,subprocess,sys; \
from osai_spine import flags; \
print('flag:', flags.derive_flag('demo-seed','alice','L01'))"

.PHONY: test catalog validate smoke
