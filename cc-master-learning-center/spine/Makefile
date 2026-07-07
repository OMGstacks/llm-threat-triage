.PHONY: validate validate-sources check-ip factstore-validate quiz-validate quiz-holdout-validate quiz-export-scan quiz-render-scan learner-demo mock-validate mock-render variant-check dashboard-check dashboard-html-check cram-sheet-check cram-sheet-html-check ingest-check test ci

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

# PR-10.3 render scan: the per-attempt shuffled quiz must also carry no answer/order secret.
quiz-render-scan:
	python3 -m cc_spine.cli quiz render --attempt-seed ci-attempt > /tmp/cc_render.json
	! grep -qE '"(correct_index|correct|answer|answer_key_ref|answer_key_hash|item_hash|rationale_refs|rationales|distractor_misconceptions|fact_ids|expected_keywords|source_policy|status|holdout|misconception_tags|choice_order)"[[:space:]]*:' /tmp/cc_render.json
	@echo "OK   presented (shuffled) quiz carries no answer-bearing field"

# PR-9 learner-state demo: replay the synthetic attempt stream (no learner data written).
learner-demo:
	python3 -m cc_spine.cli learner replay --attempts tests/fixtures/synthetic_attempt_stream.json --now 5

# PR-10 mock-exam assembler gate: draw a mock and check policy conformance.
mock-validate:
	python3 -m cc_spine.cli mock validate --draw-key ci-mock --count 15

# PR-10.2 exposure-receipt gate: the render path must emit the burn receipt AND leak no content.
# grep returns 0 on a match, so a match (a content/answer-bearing field) makes this target fail.
mock-render:
	python3 -m cc_spine.cli mock render --draw-key ci-mock --count 15 > /tmp/cc_mock_receipt.json
	grep -q '"exposed_holdout_ids"' /tmp/cc_mock_receipt.json
	! grep -qE '"(stem|choices|correct_index|correct|answer|answer_key_ref|rationale_refs|item_hash|distractor_misconceptions)"[[:space:]]*:' /tmp/cc_mock_receipt.json
	@echo "OK   mock render emits the burn receipt and carries no content"

# PR-10.4b variant-intake gate: the locked prompt is byte-deterministic; a good candidate
# ingests to a NON-committable dir; the keyed-wrong-choice attack candidate is rejected.
variant-check:
	python3 -m cc_spine.cli variant prompt --item-id D1.1.4.scenario.0001 --draw-key ci-variant > /tmp/cc_vprompt_a.txt
	python3 -m cc_spine.cli variant prompt --item-id D1.1.4.scenario.0001 --draw-key ci-variant > /tmp/cc_vprompt_b.txt
	cmp /tmp/cc_vprompt_a.txt /tmp/cc_vprompt_b.txt
	rm -rf /tmp/cc_variant_drafts
	python3 -m cc_spine.cli variant ingest --item-id D1.1.4.scenario.0001 --draw-key ci-variant \
		--candidate tests/fixtures/variant_candidate_good.json --out /tmp/cc_variant_drafts
	! python3 -m cc_spine.cli variant ingest --item-id D1.1.4.scenario.0001 --draw-key ci-variant \
		--candidate tests/fixtures/variant_candidate_keyed_wrong_choice.json --out /tmp/cc_variant_drafts
	@echo "OK   variant intake: deterministic prompt, good candidate drafts, attack candidate rejected"

# PR-11a dashboard gate: the readiness dashboard is byte-deterministic and carries no answer/PII.
dashboard-check:
	python3 -m cc_spine.cli dashboard --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 > /tmp/cc_dash_a.json
	python3 -m cc_spine.cli dashboard --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 > /tmp/cc_dash_b.json
	cmp /tmp/cc_dash_a.json /tmp/cc_dash_b.json
	! grep -qE '"(stem|choices|correct_index|correct|answer|answer_key_ref|answer_key_hash|item_hash|rationale_refs|correction|one_sentence_rule|trap|distractor_misconceptions|selected_index|fact_ids|expected_keywords|name|email|user|username)"[[:space:]]*:' /tmp/cc_dash_a.json
	@echo "OK   dashboard is deterministic and carries no answer/PII field"

# PR-11b dashboard HTML gate: the visual render is byte-deterministic and carries no answer field.
dashboard-html-check:
	python3 -m cc_spine.cli dashboard --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 --html > /tmp/cc_dash_a.html
	python3 -m cc_spine.cli dashboard --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 --html > /tmp/cc_dash_b.html
	cmp /tmp/cc_dash_a.html /tmp/cc_dash_b.html
	! grep -qE 'correct_index|answer_key_ref|answer_key_hash|item_hash|rationale_refs|distractor_misconceptions|selected_index|choices|fact_ids|expected_keywords' /tmp/cc_dash_a.html
	@echo "OK   dashboard HTML is deterministic and carries no answer-bearing field"

# PR-11c cram-sheet gate: deliberately content-bearing (trap/correction/rule), but still no
# isolated-key field, no choices, and no selected_index. JSON shape.
cram-sheet-check:
	python3 -m cc_spine.cli cram-sheet --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 > /tmp/cc_cram_a.json
	python3 -m cc_spine.cli cram-sheet --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 > /tmp/cc_cram_b.json
	cmp /tmp/cc_cram_a.json /tmp/cc_cram_b.json
	! grep -qE '"(choices|correct_index|answer_key_ref|rationale_refs|distractor_misconceptions|answer_key_hash|item_hash|selected_index|fact_ids|expected_keywords)"[[:space:]]*:' /tmp/cc_cram_a.json
	@echo "OK   cram sheet is deterministic and carries no answer-key/PII field"

# PR-11c cram-sheet HTML gate: same deterministic + no-answer-key-field proof over the render.
cram-sheet-html-check:
	python3 -m cc_spine.cli cram-sheet --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 --html > /tmp/cc_cram_a.html
	python3 -m cc_spine.cli cram-sheet --attempts tests/fixtures/synthetic_attempt_stream.json --now 5 --html > /tmp/cc_cram_b.html
	cmp /tmp/cc_cram_a.html /tmp/cc_cram_b.html
	! grep -qE 'correct_index|answer_key_ref|answer_key_hash|item_hash|rationale_refs|distractor_misconceptions|selected_index|choices|fact_ids|expected_keywords' /tmp/cc_cram_a.html
	@echo "OK   cram sheet HTML is deterministic and carries no answer-bearing field"

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
ci: validate validate-sources check-ip factstore-validate quiz-validate quiz-holdout-validate quiz-export-scan quiz-render-scan learner-demo mock-validate mock-render variant-check dashboard-check dashboard-html-check cram-sheet-check cram-sheet-html-check test ingest-check
