"""
ADIVA — Validation Agent Pydantic Schemas

Strict output schemas for the Audit Report produced by the ValidationAgent.
Every validation run yields an ``AuditReport`` that captures errors,
normalised data, dynamic truth-test results and an overall confidence score.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────

class Severity(str, Enum):
    """How severe a validation error is."""
    ERROR   = "error"
    WARNING = "warning"
    INFO    = "info"


class ValidationPillar(str, Enum):
    """Which of the four validation pillars raised the issue."""
    LOGICAL_CONSISTENCY  = "logical_consistency"
    CONTEXTUAL_SANITY    = "contextual_sanity"
    SCHEMA_FORMAT        = "schema_format"
    TRUTH_TEST           = "truth_test"


# ──────────────────────────────────────────────────────────
# Error / warning entry
# ──────────────────────────────────────────────────────────

class ValidationError(BaseModel):
    """A single validation error / warning produced during a check."""
    pillar: ValidationPillar = Field(
        ..., description="Validation pillar that raised this issue"
    )
    severity: Severity = Field(
        ..., description="Severity level"
    )
    field: Optional[str] = Field(
        None, description="Dot-separated path to the offending field, e.g. 'line_items.0.total'"
    )
    message: str = Field(
        ..., description="Human-readable explanation of the issue"
    )
    expected: Optional[str] = Field(
        None, description="What the correct / expected value should be"
    )
    actual: Optional[str] = Field(
        None, description="The value that was found"
    )


# ──────────────────────────────────────────────────────────
# Truth-test result
# ──────────────────────────────────────────────────────────

class TruthTestResult(BaseModel):
    """Result of a single dynamically-generated truth test."""
    test_name: str = Field(
        ..., description="Short name of the truth test"
    )
    assertion: str = Field(
        ..., description="Natural-language assertion tested"
    )
    passed: bool = Field(
        ..., description="Whether the assertion held"
    )
    detail: Optional[str] = Field(
        None, description="Explanatory detail when the assertion failed"
    )


# ──────────────────────────────────────────────────────────
# Normalisation change log (one entry per field touched)
# ──────────────────────────────────────────────────────────

class NormalisationChange(BaseModel):
    """Records a single field that was normalised."""
    field: str
    original_value: Optional[str] = None
    normalised_value: Optional[str] = None
    rule_applied: str = Field(
        ..., description="Short description of the normalisation rule"
    )


# ──────────────────────────────────────────────────────────
# Top-level Audit Report
# ──────────────────────────────────────────────────────────

class AuditReport(BaseModel):
    """
    The complete audit report returned by the Validation Agent.

    This is the canonical output schema — every validation run
    MUST produce exactly one AuditReport.
    """
    # --- core verdicts ------------------------------------------------
    is_valid: bool = Field(
        ..., description="True if no ERROR-level issues were found"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Overall confidence in the data quality (0-1)"
    )

    # --- detailed logs ------------------------------------------------
    error_log: List[ValidationError] = Field(
        default_factory=list,
        description="All errors, warnings and info messages"
    )

    # --- normalised payload -------------------------------------------
    normalized_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="The data after normalisation (dates → ISO 8601, phones → E.164, etc.)"
    )
    normalisation_changes: List[NormalisationChange] = Field(
        default_factory=list,
        description="Log of every normalisation change applied"
    )

    # --- truth tests --------------------------------------------------
    truth_tests: List[TruthTestResult] = Field(
        default_factory=list,
        description="Dynamically-generated truth test results"
    )

    # --- metadata -----------------------------------------------------
    source_file: Optional[str] = Field(
        None, description="Path to the input file that was validated"
    )
    document_type: Optional[str] = Field(
        None, description="Detected / provided document type"
    )
    validation_time_seconds: Optional[float] = Field(
        None, description="Wall-clock time taken by the entire validation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "is_valid": False,
                "confidence_score": 0.72,
                "error_log": [
                    {
                        "pillar": "logical_consistency",
                        "severity": "error",
                        "field": "line_items.0.total",
                        "message": "Quantity × Unit Price ≠ Total",
                        "expected": "500.00",
                        "actual": "450.00",
                    }
                ],
                "normalized_data": {"invoice_date": "2026-03-04"},
                "normalisation_changes": [
                    {
                        "field": "invoice_date",
                        "original_value": "04/03/2026",
                        "normalised_value": "2026-03-04",
                        "rule_applied": "ISO 8601 date conversion",
                    }
                ],
                "truth_tests": [
                    {
                        "test_name": "total_matches_subtotal_plus_tax",
                        "assertion": "subtotal + tax == total",
                        "passed": True,
                        "detail": None,
                    }
                ],
                "source_file": "outputs/extracted/20260304_invoice/extraction.json",
                "document_type": "invoice",
                "validation_time_seconds": 3.42,
            }
        }
