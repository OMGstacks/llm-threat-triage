.PHONY: validate validate-sources check-ip factstore-validate quiz-validate quiz-holdout-validate quiz-export-scan learner-demo ingest-check test ci

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

# PR-8a quiz-engine gate: gold-item grounding, answer-key isolation, hash-drift,
# near-duplicate stems.
quiz-validate:
	python3 -m cc_spine.cli quiz validate

# PR-8c holdout lane: same item gates + physical partition + no leakage into practice.
quiz-holdout-validate:
	python3 -m cc_spine.cli quiz validate-holdout

# PR-8a.1 leakage scan: the learner export must carry no answer-bearing field. grep
# returns 0 on a match, so a match makes this target fail.
quiz-export-scan:
	python3 -m cc_spine.cli quiz export-learner > /tmp/cc_learner_export.json
	! grep -qE '"(correct_index|correct|answer|answer_key_ref|answer_key_hash|item_hash|rationale_refs|rationales|distractor_misconceptions|fact_ids|expected_keywords|source_policy|status|holdout|misconception_tags)"[[:space:]]*:' /tmp/cc_learner_export.json
	@echo "OK   learner export carries no answer-bearing field"

# PR-9 learner-state demo: replay the synthetic attempt stream (no learner data written).
learner-demo:
	python3 -m cc_spine.cli learner replay --attempts tests/fixtures/synthetic_attempt_stream.json --now 5

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
ci: validate validate-sources check-ip factstore-validate quiz-validate quiz-holdout-validate quiz-export-scan learner-demo test ingest-check
