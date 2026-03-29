from backend.review.service import (
    DEFAULT_DOCUMENT_REVIEW_FIELD,
    _ensure_non_empty_review_field_items,
    _normalize_review_case_status_value,
    _triage_review_field_items_with_ai,
)


def test_existing_review_field_items_are_preserved():
    existing_items = [
        {
            "field_path": "invoice_number",
            "reason_code": "missing_critical_field",
            "is_critical": True,
            "field_confidence": 0.51,
            "original_value": None,
            "evidence_text": "Observed: missing",
            "validation_message": "Invoice number is missing.",
        }
    ]

    resolved = _ensure_non_empty_review_field_items(
        field_items=existing_items,
        validation_summary={},
        confidence_data={"overall_confidence": 0.51},
    )

    assert resolved == existing_items


def test_empty_review_field_items_get_document_level_fallback():
    resolved = _ensure_non_empty_review_field_items(
        field_items=[],
        validation_summary={
            "reason_codes": ["unsupported_document_type"],
            "review_reasons": ["Unsupported document type requires manual confirmation."],
        },
        confidence_data={"overall_confidence": 0.41},
    )

    assert len(resolved) == 1
    fallback = resolved[0]
    assert fallback["field_path"] == DEFAULT_DOCUMENT_REVIEW_FIELD
    assert fallback["reason_code"] == "classification_ambiguous"
    assert fallback["is_critical"] is True
    assert fallback["field_confidence"] == 0.41
    assert "manual confirmation" in fallback["validation_message"].lower()


def test_legacy_in_review_status_normalizes_for_frontend():
    assert _normalize_review_case_status_value("in_review") == "in_progress"
    assert _normalize_review_case_status_value("open") == "open"


def test_ai_triage_can_deduplicate_repeated_indexed_review_items(monkeypatch):
    class FakeAgent:
        def triage_review_fields(self, **kwargs):
            return {
                "review_fields": [
                    {
                        "field_path": "opening_balance",
                        "reason_code": "math_consistency_failed",
                        "validation_message": "Opening balance needs confirmation.",
                        "evidence_text": "Opening Balance: 45,230.00",
                        "proposed_value": 45230.0,
                        "confidence": 0.91,
                    },
                    {
                        "field_path": "transactions",
                        "reason_code": "math_consistency_failed",
                        "validation_message": "Transaction balance sequence should be reviewed together.",
                        "evidence_text": "Debit Credit Balance",
                        "proposed_value": None,
                        "confidence": 0.84,
                    },
                ],
                "summary": "Grouped repeated balance issues into one transaction-sequence review item.",
            }

    monkeypatch.setattr("backend.review.service._get_ai_triage_agent", lambda: FakeAgent())

    candidate_fields = [
        {
            "field_path": "opening_balance",
            "reason_code": "math_consistency_failed",
            "is_critical": True,
            "field_confidence": 0.93,
            "original_value": 745230.0,
            "evidence_text": "Observed: 745230.0",
            "validation_message": "Opening balance does not match the first running balance.",
        },
        {
            "field_path": "transactions.0.balance",
            "reason_code": "math_consistency_failed",
            "is_critical": True,
            "field_confidence": 0.93,
            "original_value": 82230.0,
            "evidence_text": "Observed: 82230.0",
            "validation_message": "Running balance mismatch.",
        },
        {
            "field_path": "transactions.1.balance",
            "reason_code": "math_consistency_failed",
            "is_critical": True,
            "field_confidence": 0.93,
            "original_value": 78780.0,
            "evidence_text": "Observed: 78780.0",
            "validation_message": "Running balance mismatch.",
        },
        {
            "field_path": "transactions.2.balance",
            "reason_code": "math_consistency_failed",
            "is_critical": True,
            "field_confidence": 0.93,
            "original_value": 76680.0,
            "evidence_text": "Observed: 76680.0",
            "validation_message": "Running balance mismatch.",
        },
    ]

    resolved, summary = _triage_review_field_items_with_ai(
        document_type="bank_statement",
        structured_data={
            "opening_balance": 745230.0,
            "transactions": [
                {"balance": 82230.0},
                {"balance": 78780.0},
                {"balance": 76680.0},
            ],
        },
        confidence_data={"overall_confidence": 0.93},
        validation_summary={"decision": "low_confidence"},
        validation_errors=[],
        candidate_field_items=candidate_fields,
        raw_text="Opening Balance: 45,230.00 Debit Credit Balance",
    )

    assert summary["applied"] is True
    assert [item["field_path"] for item in resolved] == ["opening_balance", "transactions"]
    assert resolved[0]["proposed_value"] == 45230.0
