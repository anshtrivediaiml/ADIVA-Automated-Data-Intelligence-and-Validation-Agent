import backend.agents.validator.logic as validator_logic
from backend.agents.validator.logic import ValidationAgent
from backend.validation_service import decide_validation_outcome, summarize_validation_report


def test_overlapping_truth_test_does_not_create_duplicate_issue(monkeypatch):
    agent = ValidationAgent()
    monkeypatch.setattr(agent, "_save_report", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.agents.validator.logic.config.VALIDATION_ENABLE_TRUTH_TESTS", True)

    monkeypatch.setattr(
        agent,
        "_check_logical_consistency",
        lambda data, doc_type: [
            validator_logic.ValidationError(
                pillar=validator_logic.ValidationPillar.LOGICAL_CONSISTENCY,
                severity=validator_logic.Severity.ERROR,
                field="total",
                message="Subtotal plus tax does not match total.",
                expected="110.00",
                actual="100.00",
            )
        ],
    )
    monkeypatch.setattr(agent, "_check_contextual_sanity", lambda data, doc_type: [])
    monkeypatch.setattr(agent, "_normalise_data", lambda data: (data, []))
    monkeypatch.setattr(
        agent,
        "_generate_truth_tests",
        lambda data, doc_type: [
            validator_logic.TruthTestResult(
                test_name="total_matches_subtotal_plus_tax",
                field="total",
                assertion="Subtotal plus tax equals total",
                passed=False,
                detail="Expected 110.00 but total is 100.00",
                expected_value="110.00",
                actual_value="100.00",
            )
        ],
    )

    report = agent.validate_data(
        {"total": 100.0, "subtotal": 100.0, "tax": 10.0},
        source_file="invoice.json",
        document_type="invoice",
    )

    assert len(report.truth_tests) == 1
    assert len(report.error_log) == 1
    assert report.error_log[0].pillar == validator_logic.ValidationPillar.LOGICAL_CONSISTENCY

    summary = summarize_validation_report(report, decide_validation_outcome(report))
    assert summary["failed_truth_tests"] == 1
    assert len(summary["truth_test_failures"]) == 1
    assert len(summary["review_reasons"]) == 1


def test_unique_truth_test_failure_is_preserved_and_compacted(monkeypatch):
    agent = ValidationAgent()
    monkeypatch.setattr(agent, "_save_report", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.agents.validator.logic.config.VALIDATION_ENABLE_TRUTH_TESTS", True)

    monkeypatch.setattr(agent, "_check_logical_consistency", lambda data, doc_type: [])
    monkeypatch.setattr(agent, "_check_contextual_sanity", lambda data, doc_type: [])
    monkeypatch.setattr(
        agent,
        "_normalise_data",
        lambda data: (
            data,
            [
                validator_logic.NormalisationChange(
                    field="invoice_date",
                    original_value="04/03/2026",
                    normalised_value="2026-03-04",
                    rule_applied="iso_date",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        agent,
        "_generate_truth_tests",
        lambda data, doc_type: [
            validator_logic.TruthTestResult(
                test_name="missing_due_date_pairing",
                field="due_date",
                assertion="If invoice_date is present, due_date should also be present",
                passed=False,
                detail="Invoice date exists but due date is missing",
                expected_value="due_date present",
                actual_value="missing",
            ),
            validator_logic.TruthTestResult(
                test_name="missing_due_date_pairing_duplicate",
                field="due_date",
                assertion="If invoice_date is present, due_date should also be present",
                passed=False,
                detail="Invoice date exists but due date is missing",
                expected_value="due_date present",
                actual_value="missing",
            ),
            validator_logic.TruthTestResult(
                test_name="invoice_date_format",
                field="invoice_date",
                assertion="Invoice date is normalized",
                passed=True,
                detail=None,
                expected_value="2026-03-04",
                actual_value="2026-03-04",
            ),
        ],
    )

    report = agent.validate_data(
        {"invoice_date": "2026-03-04"},
        source_file="invoice.json",
        document_type="invoice",
    )

    truth_test_issues = [item for item in report.error_log if item.pillar == validator_logic.ValidationPillar.TRUTH_TEST]
    assert len(report.truth_tests) == 2
    assert len(truth_test_issues) == 1
    assert truth_test_issues[0].field == "due_date"

    summary = summarize_validation_report(report, decide_validation_outcome(report))
    assert summary["truth_test_count"] == 2
    assert summary["passed_truth_tests"] == 1
    assert summary["failed_truth_tests"] == 1
    assert summary["truth_test_failures"] == ["Invoice date exists but due date is missing"]
