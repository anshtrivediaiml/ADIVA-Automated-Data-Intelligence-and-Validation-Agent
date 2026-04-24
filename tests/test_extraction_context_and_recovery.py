import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from ai_agent import AIAgent
from extractor import DocumentExtractor
from extractors.ocr_extractor import OCRExtractor
from recovery.service import (
    _build_recovery_context,
    _evidence_supported,
    _evaluate_candidate_recovery,
    _select_grouped_recovery_targets,
    _select_recoverable_fields,
    _set_nested_value,
)


def test_structured_extraction_prompt_includes_table_context():
    agent = AIAgent.__new__(AIAgent)

    prompt = agent._create_extraction_prompt(
        "Opening Balance: 45,230.00",
        "bank_statement",
        {"transactions": []},
        "Extract the bank statement.",
        extraction_context={
            "signals": {"table_count": 1, "numeric_dense_line_count": 5},
            "line_blocks": ["Opening Balance: 45,230.00", "Closing Balance: 74,830.00"],
            "numeric_dense_lines": ["02-Feb-2024 55,000.00 1,00,230.00"],
            "table_blocks": [
                {
                    "page": 1,
                    "source": "img2table",
                    "headers": ["Date", "Description", "Credit", "Balance"],
                    "rows": [["02-Feb-2024", "SALARY CREDIT - FEB 2024", "55,000.00", "1,00,230.00"]],
                }
            ],
        },
    )

    assert "DOCUMENT STRUCTURE CONTEXT" in prompt
    assert "Detected tables:" in prompt
    assert "SALARY CREDIT - FEB 2024" in prompt
    assert "Do not move values between debit, credit, and balance columns." in prompt


def test_document_extractor_builds_table_aware_context():
    extractor = DocumentExtractor.__new__(DocumentExtractor)

    context = extractor._build_structured_extraction_context(
        raw_text=(
            "[Language: English, OCR Confidence: 88.0%, Engine: paddleocr]\n"
            "Opening Balance: 45,230.00\n"
            "02-Feb-2024 SALARY CREDIT - FEB 2024 55,000.00 1,00,230.00\n"
        ),
        tables=[
            {
                "page": 1,
                "source": "img2table",
                "headers": ["Date", "Description", "Credit", "Balance"],
                "rows": [["02-Feb-2024", "SALARY CREDIT - FEB 2024", "55,000.00", "1,00,230.00"]],
            }
        ],
        metadata={"ocr_run_summary": {"average_page_confidence": 88.0}},
        document_type="bank_statement",
    )

    assert context["signals"]["table_count"] == 1
    assert context["signals"]["ocr_average_page_confidence"] == 88.0
    assert any("Opening Balance" in line for line in context["line_blocks"])
    assert any("55,000.00" in line for line in context["numeric_dense_lines"])


def test_recovery_supports_indexed_transaction_fields():
    fields = _select_recoverable_fields(
        [
            {"field_path": "__document__"},
            {"field_path": "transactions"},
            {"field_path": "transactions.0.balance"},
            {"field_path": "transactions.1.credit"},
            {"field_path": "line_items.0.total"},
        ]
    )

    assert [item["field_path"] for item in fields] == [
        "transactions",
        "transactions.0.balance",
        "transactions.1.credit",
        "line_items.0.total",
    ]

    payload = {"transactions": [{"balance": 82230.0}, {"credit": None}]}
    _set_nested_value(payload, "transactions.0.balance", 100230.0)
    _set_nested_value(payload, "transactions.1.credit", 55000.0)

    assert payload["transactions"][0]["balance"] == 100230.0
    assert payload["transactions"][1]["credit"] == 55000.0


def test_grouped_recovery_targets_detect_repeated_section_fields():
    targets = _select_grouped_recovery_targets(
        [
            {"field_path": "transactions.0.balance", "reason_code": "math_consistency_failed"},
            {"field_path": "transactions.1.balance", "reason_code": "math_consistency_failed"},
            {"field_path": "transactions.2.balance", "reason_code": "math_consistency_failed"},
            {"field_path": "opening_balance", "reason_code": "math_consistency_failed"},
        ]
    )

    assert len(targets) == 1
    assert targets[0]["section_path"] == "transactions"
    assert [item["field_path"] for item in targets[0]["fields"]] == [
        "transactions.0.balance",
        "transactions.1.balance",
        "transactions.2.balance",
    ]


def test_recovery_evidence_supports_formatted_numeric_matches_from_context():
    result = {
        "text": {"raw": "Opening Balance: 45,230.00\nClosing Balance: 74,830.00"},
        "tables": [
            {
                "page": 1,
                "source": "img2table",
                "headers": ["Label", "Amount"],
                "rows": [["Closing Balance", "74,830.00"]],
            }
        ],
        "metadata": {"ocr_run_summary": {"average_page_confidence": 90.0}},
    }
    context = _build_recovery_context(result, document_type="bank_statement")

    assert _evidence_supported(
        document_type="bank_statement",
        field_path="closing_balance",
        raw_text=result["text"]["raw"],
        extraction_context=context,
        evidence_text="Closing Balance: 74,830.00",
        current_value=74830.0,
        proposed_value=74830.0,
        current_structured_data={"closing_balance": 74830.0},
    ) is True


def test_bank_statement_recovery_requires_consistent_row_and_context():
    raw_text = (
        "Opening Balance: 45,230.00\n"
        "02-Feb-2024 SALARY CREDIT - FEB 2024 55,000.00 1,00,230.00\n"
        "05-Feb-2024 ATM CASH WD 18,000.00 82,230.00\n"
    )
    result = {
        "text": {"raw": raw_text},
        "tables": [
            {
                "page": 1,
                "source": "img2table",
                "headers": ["Date", "Description", "Credit", "Balance"],
                "rows": [["02-Feb-2024", "SALARY CREDIT - FEB 2024", "55,000.00", "1,00,230.00"]],
            }
        ],
        "metadata": {"ocr_run_summary": {"average_page_confidence": 88.0}},
    }
    context = _build_recovery_context(result, document_type="bank_statement")
    structured_data = {
        "opening_balance": 45230.0,
        "transactions": [
            {
                "date": "2024-02-02",
                "description": "SALARY CREDIT - FEB 2024",
                "credit": 55000.0,
                "balance": 82230.0,
            },
            {
                "date": "2024-02-05",
                "description": "ATM CASH WD",
                "debit": 18000.0,
                "balance": 82230.0,
            },
        ],
    }

    assert _evidence_supported(
        document_type="bank_statement",
        field_path="transactions.0.balance",
        raw_text=raw_text,
        extraction_context=context,
        evidence_text="02-Feb-2024 SALARY CREDIT - FEB 2024 55,000.00 1,00,230.00",
        current_value=82230.0,
        proposed_value=100230.0,
        current_structured_data=structured_data,
    ) is True


def test_recovery_acceptance_blocks_inconsistent_bank_statement_even_if_validator_improves():
    class FakeReport:
        def __init__(self, confidence_score, error_log):
            self.confidence_score = confidence_score
            self.error_log = error_log

    accepted, summary = _evaluate_candidate_recovery(
        before_report=FakeReport(0.4, []),
        after_report=FakeReport(0.9, []),
        document_type="bank_statement",
        candidate_data={
            "bank_name": "ABC Bank",
            "account_holder": "John Doe",
            "account_number": "XXXX1234",
            "opening_balance": 74523.0,
            "transactions": [
                {"date": "2024-02-02", "description": "SALARY", "credit": 100230.0, "balance": 82230.0},
                {"date": "2024-02-05", "description": "ATM", "debit": 18000.0, "balance": 78780.0},
            ],
            "closing_balance": 78780.0,
        },
        changes=[
            {
                "field_path": "opening_balance",
                "old_value": 745230.0,
                "proposed_value": 74523.0,
                "is_critical": True,
                "evidence_supported": True,
            }
        ],
    )

    assert accepted is False
    assert any(str(blocker).startswith("low_consistency_score:") for blocker in summary["blockers"])


def test_payslip_recovery_evidence_supports_arithmetic_totals():
    haystack = "Total Earnings 50,000.00 Total Deductions 5,000.00 Net Pay 45,000.00"
    assert _evidence_supported(
        document_type="payslip",
        field_path="net_pay",
        raw_text=haystack,
        extraction_context={"line_blocks": [haystack], "numeric_dense_lines": [haystack], "flattened_table_lines": []},
        evidence_text="Net Pay 45,000.00",
        current_value=44000.0,
        proposed_value=45000.0,
        current_structured_data={
            "total_earnings": 50000.0,
            "total_deductions": 5000.0,
            "net_pay": 44000.0,
        },
    ) is True


def test_ocr_extractor_normalizes_image_tables():
    extractor = OCRExtractor.__new__(OCRExtractor)
    normalized = extractor._normalize_image_table(
        {
            "headers": ["Date", "Description", "Credit", "Balance"],
            "rows": [["02-Feb-2024", "SALARY CREDIT - FEB 2024", "55,000.00", "1,00,230.00"]],
        },
        page_num=1,
        table_num=1,
        source="img2table_image",
    )

    assert normalized["page"] == 1
    assert normalized["source"] == "img2table_image"
    assert normalized["row_count"] == 1
    assert normalized["col_count"] == 4
    assert normalized["data"][0]["Balance"] == "1,00,230.00"
