.PHONY: validate validate-sources check-ip factstore-validate ingest-check test ci

# PR-1 scaffold gate.
validate:
	python3 -m cc_spine.scaffold_validate

# PR-2 source-registry freshness guard.
validate-sources:
	python3 -m cc_spine.cli validate-sources

# PR-2 IP-boundary support-span guard.
check-ip:
	python3 -m cc_spine.cli check-ip

# PR-3 fact-store validator: provenance, drift, tombstones, eligibility,
# answer-key quarantine, unsupported_claim_guard.
factstore-validate:
	python3 -m cc_spine.cli factstore validate

# PR-2 ingestion determinism smoke: ingest the fixture twice, prove byte-identical.
ingest-check:
	python3 -m cc_spine.cli ingest --source tests/fixtures/sample_transcript.txt \
		--source-doc-id sample-transcript --out /tmp/cc_note_a.md
	python3 -m cc_spine.cli ingest --source tests/fixtures/sample_transcript.txt \
		--source-doc-id sample-transcript --out /tmp/cc_note_b.md
	cmp /tmp/cc_note_a.md /tmp/cc_note_b.md && echo "OK   ingestion is deterministic"

# Full stdlib test suite (no third-party dependencies).
test:
	python3 -m unittest discover -s tests -v

# Everything CI runs, in order.
ci: validate validate-sources check-ip factstore-validate test ingest-check
