import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from ai_agent import AIAgent
from confidence_scorer import ConfidenceScorer


def _consistent_bank_statement():
    return {
        "bank_name": "ABC Bank",
        "account_holder": "John Doe",
        "account_number": "XXXX1234",
        "opening_balance": 45230.0,
        "closing_balance": 74830.0,
        "transactions": [
            {
                "date": "2024-02-02",
                "description": "SALARY CREDIT - FEB 2024",
                "debit": None,
                "credit": 55000.0,
                "balance": 100230.0,
            },
            {
                "date": "2024-02-05",
                "description": "ATM CASH WD",
                "debit": 18000.0,
                "credit": None,
                "balance": 82230.0,
            },
            {
                "date": "2024-02-10",
                "description": "UPI GROCERY MART",
                "debit": 3450.0,
                "credit": None,
                "balance": 78780.0,
            },
            {
                "date": "2024-02-15",
                "description": "ELECTRICITY BILL",
                "debit": 2100.0,
                "credit": None,
                "balance": 76680.0,
            },
            {
                "date": "2024-02-22",
                "description": "UPI PHARMACY",
                "debit": 1850.0,
                "credit": None,
                "balance": 74830.0,
            },
        ],
    }


def _broken_bank_statement():
    return {
        "bank_name": "ABC Bank",
        "account_holder": "John Doe",
        "account_number": "XXXX1234",
        "opening_balance": 745230.0,
        "closing_balance": 74830.0,
        "transactions": [
            {
                "date": "2024-02-02",
                "description": "SALARY CREDIT - FEB 2024",
                "debit": None,
                "credit": 100230.0,
                "balance": 82230.0,
            },
            {
                "date": "2024-02-05",
                "description": "ATM CASH WD",
                "debit": 18000.0,
                "credit": None,
                "balance": 78780.0,
            },
            {
                "date": "2024-02-10",
                "description": "UPI GROCERY MART",
                "debit": 3450.0,
                "credit": None,
                "balance": 76680.0,
            },
            {
                "date": "2024-02-15",
                "description": "ELECTRICITY BILL",
                "debit": 2100.0,
                "credit": None,
                "balance": 74830.0,
            },
            {
                "date": "2024-02-22",
                "description": "UPI PHARMACY",
                "debit": 1850.0,
                "credit": None,
                "balance": 74830.0,
            },
        ],
    }


def test_bank_statement_consistency_rewards_reconciled_balances():
    scorer = ConfidenceScorer()

    result = scorer.calculate_comprehensive_confidence(
        _consistent_bank_statement(),
        "bank_statement",
    )

    assert result["metrics"]["consistency"] == 1.0
    assert result["overall_confidence"] >= 0.9


def test_bank_statement_consistency_penalizes_broken_running_balances():
    scorer = ConfidenceScorer()

    result = scorer.calculate_comprehensive_confidence(
        _broken_bank_statement(),
        "bank_statement",
    )

    assert result["metrics"]["consistency"] <= 0.2
    assert result["overall_confidence"] <= 0.55
    assert result["grade"] == "D"


def test_post_process_uses_bank_statement_repair_when_sequence_is_broken(monkeypatch):
    agent = AIAgent.__new__(AIAgent)
    repaired_data = _consistent_bank_statement()

    monkeypatch.setattr(
        agent,
        "_repair_bank_statement_extraction",
        lambda full_text, extracted_data: repaired_data,
    )

    result = agent._post_process_extracted_data(
        _broken_bank_statement(),
        "bank_statement",
        "Opening Balance: 45,230.00 ... Closing Balance: 74,830.00",
    )

    assert result == repaired_data
