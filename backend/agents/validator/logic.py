"""
ADIVA — Validation Agent (core logic)

Quality-control layer for the extraction pipeline.
Implements four validation pillars:

1. Logical Consistency   — deterministic math / numeric checks
2. Contextual Sanity     — LLM doc-type-aware sanity checks (with expected/actual)
3. Schema & Format       — date / phone / currency normalisation
4. Autonomous Truth Tests — LLM generates exhaustive, doc-type-specific math tests

Production-grade features:
- Exponential backoff retry on all LLM calls
- Document-type context hints fed to LLM for smarter validation
- Proportional, non-collapsing confidence scoring
- Full expected/actual values in all error and truth-test output
"""

from __future__ import annotations

import copy
import csv
import json
import math
import os
import re
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mistralai import Mistral

import config
from logger import logger, log_error
from schemas import get_schema

from agents.validator.schemas import (
    AuditReport,
    NormalisationChange,
    Severity,
    TruthTestResult,
    ValidationError,
    ValidationPillar,
)

# ──────────────────────────────────────────────────────────────────────────────
# Regex helpers used across pillars
# ──────────────────────────────────────────────────────────────────────────────

# Date patterns (non-ISO) — DD/MM/YYYY, MM-DD-YYYY, DD.MM.YYYY, DD Mon YYYY …
_DATE_PATTERNS: list[tuple[str, str]] = [
    # DD/MM/YYYY  or  DD-MM-YYYY  or  DD.MM.YYYY
    (r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", "%d/%m/%Y"),
    # Month DD, YYYY
    (r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}", None),
    # DD Month YYYY
    (r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}", None),
]

_PHONE_DIGITS_RE = re.compile(r"[^\d+]")
_CURRENCY_CHARS_RE = re.compile(r"[₹$€£¥,\s]")

# ──────────────────────────────────────────────────────────────────────────────
# Document-type context hints for LLM prompts
#
# Why: Without context, the LLM has to guess document structure from raw JSON.
# Providing a brief field-vocabulary hint per doc-type dramatically improves
# the quality and specificity of both Pillar 2 sanity issues and Pillar 4
# truth tests — the LLM knows what to look for rather than exploring blindly.
# ──────────────────────────────────────────────────────────────────────────────

_DOC_TYPE_HINTS: dict[str, str] = {
    "invoice": (
        "Key fields: vendor_name, buyer_name, invoice_date, due_date, "
        "line_items[{name, quantity, unit_price, total}], subtotal, tax/tax_amount, "
        "grand_total/total. Math rules: qty×unit_price=line_total; "
        "sum(line_totals)=subtotal; subtotal+tax=grand_total."
    ),
    "marksheet": (
        "Key fields: student_name, roll_number, class_grade, academic_year, "
        "subjects[{name, max_marks, marks_obtained, grade}], total_marks, "
        "max_total_marks, percentage, result. Math rules: "
        "sum(marks_obtained)=total_marks; sum(max_marks)=max_total_marks; "
        "(total_marks/max_total_marks)×100=percentage."
    ),
    "resume": (
        "Key fields: full_name, email, phone, skills[], "
        "experience[{company, role, start_date, end_date, description}], "
        "education[{institution, degree, graduation_date}]. "
        "Rules: end_date > start_date for each job; graduation years 1950-present+5."
    ),
    "bank_statement": (
        "Key fields: account_number, account_holder, bank_name, statement_period, "
        "opening_balance, transactions[{date, description, debit, credit, balance}], "
        "closing_balance. Math rules: opening_balance + sum(credits) - sum(debits) = closing_balance; "
        "running balance should be consistent across transactions."
    ),
    "contract": (
        "Key fields: party_a, party_b, contract_date, start_date, end_date, "
        "contract_value/amount, jurisdiction, terms. "
        "Rules: end_date > start_date; contract_value > 0; parties cannot be empty."
    ),
    "prescription": (
        "Key fields: patient_name, doctor_name, date, medications["
        "{name, dosage, frequency, duration}], diagnosis. "
        "Rules: prescription date not in future; dosage values must be positive numbers."
    ),
    "utility_bill": (
        "Key fields: consumer_name, account_number, billing_period, meter_reading_start, "
        "meter_reading_end, units_consumed, rate_per_unit, bill_amount, due_date. "
        "Math rules: meter_reading_end - meter_reading_start = units_consumed; "
        "units_consumed × rate_per_unit ≈ bill_amount."
    ),
    "aadhar_card": (
        "Key fields: name, aadhaar_number (exactly 12 digits), date_of_birth, gender, address. "
        "Rules: aadhaar_number must be exactly 12 digits; DOB must be in past; "
        "name and address must not be empty."
    ),
    "pan_card": (
        "Key fields: name, pan_number (format: 5 letters + 4 digits + 1 letter = AAAAA9999A), "
        "date_of_birth, father_name. Rules: PAN format must be valid; DOB in past."
    ),
    "passport": (
        "Key fields: surname, given_names, passport_number, nationality, date_of_birth, "
        "date_of_issue, date_of_expiry, place_of_birth. "
        "Rules: expiry > issue date; DOB in past and realistic; passport_number not empty."
    ),
    "land_record": (
        "Key fields: owner_name, survey_number, area (numeric + unit), location/address, "
        "registration_date, document_number. Rules: area must be positive; owner_name not empty."
    ),
    "ration_card": (
        "Key fields: card_number, head_of_family, address, members[], card_type, issue_date. "
        "Rules: member_count should match len(members); card_number not empty."
    ),
    "certificate": (
        "Key fields: recipient_name, certificate_type, issued_by, issue_date, "
        "valid_until (if applicable). Rules: issue_date not in future; recipient_name not empty."
    ),
    "gst_certificate": (
        "Key fields: gstin (15-char alphanumeric), legal_name, trade_name, "
        "registration_date, business_type. Rules: GSTIN must be 15 characters; first 2 chars are state code."
    ),
    "cheque": (
        "Key fields: payee_name, amount_in_figures, amount_in_words, date, "
        "bank_name, account_number, ifsc_code, cheque_number. "
        "Rules: amount_in_figures must match amount_in_words numerically; date not too old."
    ),
}

_NON_REVIEWABLE_FIELD_PREFIXES: tuple[str, ...] = (
    "metadata.",
    "ocr_run_summary.",
    "review_summary.",
    "text.raw",
)

_UNSUPPORTED_DOCUMENT_TYPES = {"other", "form"}

_DOC_TYPE_VALIDATION_RULES: dict[str, str] = {
    "invoice": "Prefer arithmetic checks on line items, subtotal, tax, total, and invoice/due date consistency.",
    "bank_statement": "Focus on running balances, opening/closing balance consistency, and transaction date ranges.",
    "marksheet": "Focus on subject totals, percentage correctness, and pass/fail consistency.",
    "prescription": (
        "Treat dosage as a free-form string like '500mg' or '10ml'. "
        "Frequency shorthand such as '1-0-1', '0-0-1', and 'SOS' is acceptable. "
        "Follow-up text like 'after 2 weeks' is acceptable. "
        "Historical prescription dates are allowed. "
        "Short clinic addresses and explicit patient gender values are acceptable if they match the document."
    ),
    "aadhar_card": "Use `uid_number` as the canonical Aadhaar field name. Do not require alternate names such as `aadhaar_number`.",
    "cheque": "Use `amount_figures` and `amount_words` exactly as named in the schema.",
    "form_16": (
        "Use the nested employer/employee/tax structure exactly as defined; do not invent flat aliases. "
        "Historical assessment years are valid for archived tax documents. "
        "Do not flag a past assessment year as suspicious just because it is older than the current date. "
        "Only flag period_of_employment dates if one side exists and conflicts with the other, not when both are missing."
    ),
    "purchase_order": (
        "Use purchase_order_number and order_date exactly as named; buyer and vendor are distinct parties. "
        "Historical purchase-order dates are valid for archived business documents. "
        "If quantity × unit_price, subtotal, tax, and total are mathematically consistent, do not re-flag them."
    ),
    "retail_receipt": (
        "Use receipt_number and merchant fields exactly as named; customer_name may be null or 'Walk-in'. "
        "Historical receipt dates are valid. Preserve payment_method exactly as printed. "
        "Minor tax rounding differences within normal receipt rounding should not be treated as errors."
    ),
    "bill_of_lading": "Use bill_number, shipper, consignee, vessel, and freight fields exactly as named; do not force invoice assumptions.",
    "lab_report": "This is a diagnostic report, not a prescription; focus on report_name and test_results.",
    "payslip": (
        "Use earnings/deductions totals and net_pay arithmetic; do not require Form 16/TAN-only fields. "
        "Historical pay periods are valid for archived payslips. Leap-year dates such as 2024-02-29 are valid."
    ),
    "balance_sheet": (
        "Use assets.total_assets and equity_and_liabilities.total_equity_and_liabilities as the key balancing fields. "
        "Capital WIP is acceptable under non-current assets when shown that way. "
        "Do not flag line items purely because an amount seems large if totals and grouping are internally consistent."
    ),
    "income_tax_acknowledgment": (
        "This is an ITR acknowledgment, not Form 16; use acknowledgment_number, filing data, and summary tax fields. "
        "tax_paid may exceed total_tax_payable because of advance tax/TDS and can lead to refund positions."
    ),
}

_DOC_TYPE_CONTEXTUAL_FIELD_ALLOWLIST_PREFIXES: dict[str, tuple[str, ...]] = {
    "invoice": (
        "invoice_number",
        "invoice_date",
        "due_date",
        "vendor.name",
        "customer.name",
        "line_items",
        "subtotal",
        "tax",
        "tax_rate",
        "total",
    ),
    "bank_statement": (
        "account_number",
        "ifsc_code",
        "statement_period",
        "opening_balance",
        "closing_balance",
        "transactions",
    ),
    "marksheet": (
        "institution_name",
        "exam_name",
        "student_name",
        "roll_number",
        "class_grade",
        "subjects",
        "total_marks",
        "max_total_marks",
        "percentage",
        "result",
    ),
    "prescription": (
        "doctor_name",
        "patient_name",
        "date",
        "medicines",
        "diagnosis",
    ),
    "aadhar_card": (
        "uid_number",
        "name",
        "dob",
        "gender",
        "address",
    ),
    "cheque": (
        "cheque_number",
        "payee_name",
        "amount_figures",
        "amount_words",
        "date",
        "account_number",
        "ifsc_code",
        "micr_code",
    ),
    "form_16": (
        "assessment_year",
        "employer.name",
        "employer.tan",
        "employee.name",
        "employee.pan",
        "income",
        "tax",
    ),
    "contract": (
        "contract_date",
        "effective_date",
        "expiration_date",
        "term_duration",
        "contract_value",
        "parties",
    ),
    "utility_bill": (
        "provider_name",
        "consumer_name",
        "consumer_number",
        "due_date",
        "previous_reading",
        "current_reading",
        "units_consumed",
        "total_amount",
    ),
    "birth_certificate": (
        "child_name",
        "dob",
        "gender",
        "registration_date",
        "place_of_birth",
    ),
    "ration_card": (
        "card_number",
        "card_type",
        "head_of_family.name",
        "head_of_family.address",
        "family_members",
    ),
    "purchase_order": (
        "purchase_order_number",
        "order_date",
        "delivery_date",
        "buyer.name",
        "vendor.name",
        "line_items",
        "subtotal",
        "tax",
        "tax_rate",
        "total",
    ),
    "retail_receipt": (
        "receipt_number",
        "receipt_date",
        "merchant.name",
        "customer_name",
        "line_items",
        "subtotal",
        "tax",
        "tax_rate",
        "total",
        "payment_method",
        "card_last4",
    ),
    "bill_of_lading": (
        "bill_number",
        "issue_date",
        "shipper.name",
        "consignee.name",
        "vessel_name",
        "voyage_number",
        "port_of_loading",
        "port_of_discharge",
        "goods_description",
        "freight_amount",
    ),
    "lab_report": (
        "lab_name",
        "patient_name",
        "sample_collected_date",
        "report_name",
        "test_results",
    ),
    "payslip": (
        "employer_name",
        "employee.name",
        "employee.employee_id",
        "employee.pan",
        "pay_period.from_date",
        "pay_period.to_date",
        "earnings",
        "deductions",
        "total_earnings",
        "total_deductions",
        "net_pay",
    ),
    "balance_sheet": (
        "entity_name",
        "statement_date",
        "assets.non_current_assets",
        "assets.current_assets",
        "assets.total_assets",
        "equity_and_liabilities.equity",
        "equity_and_liabilities.non_current_liabilities",
        "equity_and_liabilities.current_liabilities",
        "equity_and_liabilities.total_equity_and_liabilities",
    ),
    "income_tax_acknowledgment": (
        "assessment_year",
        "pan",
        "taxpayer_name",
        "acknowledgment_number",
        "date_of_filing",
        "gross_total_income",
        "total_tax_payable",
        "tax_paid",
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# Utility — safe numeric coercion
# ──────────────────────────────────────────────────────────────────────────────

def _to_float(val: Any) -> Optional[float]:
    """Attempt to coerce *val* to a float. Returns ``None`` on failure."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = _CURRENCY_CHARS_RE.sub("", val).strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _try_parse_date(raw: str) -> Optional[str]:
    """
    Try several date formats and return ISO-8601 (YYYY-MM-DD) on success.
    Returns ``None`` if parsing fails.
    """
    raw = raw.strip()
    # Already ISO?
    iso_match = re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw)
    if iso_match:
        return raw

    for fmt in (
        "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%d.%m.%Y", "%Y/%m/%d",
        "%B %d, %Y", "%b %d, %Y",
        "%d %B %Y", "%d %b %Y",
        "%d %B, %Y", "%d %b, %Y",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _normalise_phone(raw: str) -> str:
    """Normalise a phone number string to digits-only (optionally with leading +)."""
    digits = _PHONE_DIGITS_RE.sub("", raw)
    if not digits:
        return raw
    # Indian 10-digit mobile → prefix with +91
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"
    if digits.startswith("+"):
        return digits
    return digits


# ══════════════════════════════════════════════════════════════════════════════
#  VALIDATION AGENT
# ══════════════════════════════════════════════════════════════════════════════

class ValidationAgent:
    """
    Quality-control agent for the ADIVA extraction pipeline.

    Reads extracted data (``.json`` or ``.csv``) from ``EXTRACTED_DIR``
    and produces a strict :class:`AuditReport` covering four pillars.
    """

    def __init__(self):
        self.data_dir: Path = config.EXTRACTED_DIR   # extracted output dir
        self.validated_dir: Path = config.VALIDATED_DIR

        # LLM client (Mistral — same as AIAgent)
        self._llm: Optional[Mistral] = None
        if config.MISTRAL_API_KEY:
            try:
                self._llm = Mistral(api_key=config.MISTRAL_API_KEY)
                logger.info("ValidationAgent: Mistral LLM ready")
            except Exception as exc:
                logger.warning(f"ValidationAgent: LLM init failed — {exc}")

        self.model = config.MISTRAL_MODEL
        self._llm_max_retries: int = 3  # retries per LLM call
        logger.info("ValidationAgent initialised")

    # ──────────────────────────────────────────────────────────────────────────
    #  PRODUCTION HELPER — LLM Call with Exponential Backoff
    # ──────────────────────────────────────────────────────────────────────────

    def _llm_call_with_retry(
        self,
        prompt: str,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> str:
        """
        Call the Mistral LLM with automatic exponential-backoff retry.

        Why retry? LLM APIs can return transient errors (rate limits, timeouts,
        server overload). A single failure should not silently kill a validation
        pillar. Retry with back-off gives the API time to recover while still
        failing fast after repeated failures.

        Back-off: 1s → 2s → 4s (for max_retries=3).
        """
        last_exc: Exception = RuntimeError("LLM not initialised")
        for attempt in range(self._llm_max_retries):
            try:
                resp = self._llm.chat.complete(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content.strip()
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt   # 1 s, 2 s, 4 s
                if attempt < self._llm_max_retries - 1:
                    logger.warning(
                        f"LLM call attempt {attempt + 1}/{self._llm_max_retries} "
                        f"failed: {exc}. Retrying in {wait}s…"
                    )
                    time.sleep(wait)
        raise last_exc

    # ──────────────────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    def validate_extraction(
        self,
        extraction_id: str,
        *,
        document_type: Optional[str] = None,
    ) -> AuditReport:
        """
        Validate an extraction by its folder-name ID.

        Looks for ``extraction.json`` inside
        ``outputs/extracted/<extraction_id>/``.
        """
        start = time.time()

        # ── Resolve json_path from 3 possible input formats ──────────────────
        candidate = Path(extraction_id)
        if candidate.is_absolute():
            # Case 1: absolute path to extraction.json (from DB storage_uri)
            if candidate.suffix == ".json":
                json_path = candidate
            else:
                # Case 2: absolute path to the extraction folder
                json_path = candidate / "extraction.json"
        else:
            # Case 3: short folder name — original behaviour
            json_path = self.data_dir / extraction_id / "extraction.json"

        if not json_path.exists():
            return AuditReport(
                is_valid=False,
                confidence_score=0.0,
                error_log=[
                    ValidationError(
                        pillar=ValidationPillar.SCHEMA_FORMAT,
                        severity=Severity.ERROR,
                        message=f"Extraction not found: {extraction_id}",
                    )
                ],
                source_file=str(json_path),
                validation_time_seconds=round(time.time() - start, 2),
            )

        with open(json_path, "r", encoding="utf-8") as fh:
            extraction_result = json.load(fh)

        return self._run_validation(
            data=extraction_result,
            source_file=str(json_path),
            document_type=document_type,
            start_time=start,
        )

    def validate_file(self, file_path: str) -> AuditReport:
        """
        Validate an arbitrary ``.json`` or ``.csv`` file.
        """
        start = time.time()
        path = Path(file_path)

        if not path.exists():
            return AuditReport(
                is_valid=False,
                confidence_score=0.0,
                error_log=[
                    ValidationError(
                        pillar=ValidationPillar.SCHEMA_FORMAT,
                        severity=Severity.ERROR,
                        message=f"File not found: {file_path}",
                    )
                ],
                source_file=file_path,
                validation_time_seconds=round(time.time() - start, 2),
            )

        if path.suffix.lower() == ".csv":
            data = self._load_csv(path)
        elif path.suffix.lower() == ".json":
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            return AuditReport(
                is_valid=False,
                confidence_score=0.0,
                error_log=[
                    ValidationError(
                        pillar=ValidationPillar.SCHEMA_FORMAT,
                        severity=Severity.ERROR,
                        message=f"Unsupported format: {path.suffix}. Use .json or .csv",
                    )
                ],
                source_file=file_path,
                validation_time_seconds=round(time.time() - start, 2),
            )

        return self._run_validation(
            data=data,
            source_file=file_path,
            start_time=start,
        )

    def validate_data(
        self,
        data: Any,
        *,
        source_file: str,
        document_type: Optional[str] = None,
    ) -> AuditReport:
        """
        Validate an in-memory extraction payload and persist the resulting report.
        """
        return self._run_validation(
            data=data,
            source_file=source_file,
            document_type=document_type,
            start_time=time.time(),
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  ORCHESTRATOR
    # ──────────────────────────────────────────────────────────────────────────

    def _run_validation(
        self,
        data: Any,
        source_file: str,
        document_type: Optional[str] = None,
        start_time: Optional[float] = None,
    ) -> AuditReport:
        """Run all four validation pillars and assemble the report."""
        start_time = start_time or time.time()
        errors: List[ValidationError] = []
        norm_changes: List[NormalisationChange] = []
        truth_tests: List[TruthTestResult] = []

        # Resolve document type from extraction envelope
        if document_type is None and isinstance(data, dict):
            document_type = (
                data.get("classification", {}).get("document_type")
                or data.get("document_type")
            )

        # Get the structured_data from the extraction envelope
        structured = data
        if isinstance(data, dict) and "structured_data" in data:
            structured = data["structured_data"]

        if document_type and not _has_supported_schema(document_type):
            errors.append(
                ValidationError(
                    pillar=ValidationPillar.CONTEXTUAL_SANITY,
                    severity=Severity.WARNING,
                    message=(
                        f"Document type '{document_type}' does not have dedicated schema-backed "
                        "validation support yet. Results should be treated cautiously."
                    ),
                )
            )

        # Deep copy for normalisation so originals stay untouched
        normalised = copy.deepcopy(structured) if structured else {}

        # ── Pillar 1: Logical consistency ──────────────────────────────────
        logger.info("Validation Pillar 1: Logical Consistency")
        errors.extend(self._check_logical_consistency(structured, document_type))

        # ── Pillar 2: Contextual sanity (LLM) ─────────────────────────────
        logger.info("Validation Pillar 2: Contextual Sanity")
        errors.extend(self._check_contextual_sanity(structured, document_type))

        # ── Pillar 3: Schema & format normalisation ────────────────────────
        logger.info("Validation Pillar 3: Schema & Format Enforcement")
        normalised, norm_changes = self._normalise_data(normalised)

        # ── Pillar 4: Autonomous truth tests ──────────────────────────────
        if config.VALIDATION_ENABLE_TRUTH_TESTS:
            logger.info("Validation Pillar 4: Autonomous Truth Tests")
            truth_tests = self._generate_truth_tests(structured, document_type)
        else:
            logger.info("Validation Pillar 4 skipped - disabled by configuration")
            truth_tests = []

        # Failed truth tests → errors
        for tt in truth_tests:
            if tt.test_name == "llm_generation_failed":
                continue
            if not tt.passed:
                errors.append(
                    ValidationError(
                        pillar=ValidationPillar.TRUTH_TEST,
                        severity=Severity.WARNING,
                        message=f"Truth test failed: {tt.assertion}",
                        expected="pass",
                        actual="fail",
                    )
                )

        # ── Calculate confidence ───────────────────────────────────────────
        confidence = self._compute_confidence(errors, truth_tests, norm_changes)

        is_valid = not any(e.severity == Severity.ERROR for e in errors)

        elapsed = round(time.time() - start_time, 2)

        report = AuditReport(
            is_valid=is_valid,
            confidence_score=round(confidence, 3),
            error_log=errors,
            normalized_data=normalised,
            normalisation_changes=norm_changes,
            truth_tests=truth_tests,
            source_file=source_file,
            document_type=document_type,
            validation_time_seconds=elapsed,
        )

        # Persist report
        self._save_report(report, source_file)

        logger.info(
            f"Validation complete — valid={is_valid}, "
            f"confidence={confidence:.3f}, "
            f"errors={sum(1 for e in errors if e.severity == Severity.ERROR)}, "
            f"warnings={sum(1 for e in errors if e.severity == Severity.WARNING)}, "
            f"time={elapsed}s"
        )

        return report

    # ══════════════════════════════════════════════════════════════════════════
    #  PILLAR 1 — LOGICAL CONSISTENCY  (Math Check)
    # ══════════════════════════════════════════════════════════════════════════

    def _check_logical_consistency(
        self, data: Any, doc_type: Optional[str]
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []
        if not isinstance(data, dict):
            return errors

        # --- Line-item math: qty × unit_price == total ---
        line_items = data.get("line_items") or data.get("items") or []
        for idx, item in enumerate(line_items):
            if not isinstance(item, dict):
                continue
            qty = _to_float(item.get("quantity"))
            price = _to_float(item.get("unit_price") or item.get("rate") or item.get("price"))
            total = _to_float(item.get("total") or item.get("amount"))

            if qty is not None and price is not None and total is not None:
                expected_total = round(qty * price, 2)
                if not math.isclose(expected_total, total, rel_tol=0.02):
                    errors.append(
                        ValidationError(
                            pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                            severity=Severity.ERROR,
                            field=f"line_items.{idx}.total",
                            message="Quantity × Unit Price ≠ Total",
                            expected=str(expected_total),
                            actual=str(total),
                        )
                    )

        # --- Subtotal / tax / total alignment ---
        subtotal = _to_float(data.get("subtotal"))
        tax = _to_float(data.get("tax") or data.get("tax_amount"))
        total = _to_float(data.get("total") or data.get("grand_total"))

        if subtotal is not None and tax is not None and total is not None:
            expected_total = round(subtotal + tax, 2)
            if not math.isclose(expected_total, total, rel_tol=0.02):
                errors.append(
                    ValidationError(
                        pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                        severity=Severity.ERROR,
                        field="total",
                        message="Subtotal + Tax ≠ Total",
                        expected=str(expected_total),
                        actual=str(total),
                    )
                )

        # --- Subtotal == sum of line_items totals ---
        if subtotal is not None and line_items:
            line_sum = sum(
                _to_float(it.get("total") or it.get("amount")) or 0
                for it in line_items
                if isinstance(it, dict)
            )
            if line_sum > 0 and not math.isclose(subtotal, line_sum, rel_tol=0.02):
                errors.append(
                    ValidationError(
                        pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                        severity=Severity.WARNING,
                        field="subtotal",
                        message="Subtotal ≠ sum of line-item totals",
                        expected=str(round(line_sum, 2)),
                        actual=str(subtotal),
                    )
                )

        # --- Payslip arithmetic ---
        if doc_type == "payslip":
            earnings = data.get("earnings") or []
            deductions = data.get("deductions") or []
            total_earnings = _to_float(data.get("total_earnings"))
            total_deductions = _to_float(data.get("total_deductions"))
            net_pay = _to_float(data.get("net_pay"))

            earnings_sum = sum(
                _to_float(item.get("amount")) or 0
                for item in earnings
                if isinstance(item, dict)
            )
            deductions_sum = sum(
                _to_float(item.get("amount")) or 0
                for item in deductions
                if isinstance(item, dict)
            )

            if total_earnings is not None and earnings:
                if not math.isclose(total_earnings, round(earnings_sum, 2), rel_tol=0.02, abs_tol=1.0):
                    errors.append(
                        ValidationError(
                            pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                            severity=Severity.ERROR,
                            field="total_earnings",
                            message="Total earnings do not match the sum of earnings components",
                            expected=str(round(earnings_sum, 2)),
                            actual=str(total_earnings),
                        )
                    )

            if total_deductions is not None and deductions:
                if not math.isclose(total_deductions, round(deductions_sum, 2), rel_tol=0.02, abs_tol=1.0):
                    errors.append(
                        ValidationError(
                            pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                            severity=Severity.ERROR,
                            field="total_deductions",
                            message="Total deductions do not match the sum of deduction components",
                            expected=str(round(deductions_sum, 2)),
                            actual=str(total_deductions),
                        )
                    )

            if total_earnings is not None and total_deductions is not None and net_pay is not None:
                expected_net_pay = round(total_earnings - total_deductions, 2)
                if not math.isclose(expected_net_pay, net_pay, rel_tol=0.02, abs_tol=1.0):
                    errors.append(
                        ValidationError(
                            pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                            severity=Severity.ERROR,
                            field="net_pay",
                            message="Net pay does not match total earnings minus total deductions",
                            expected=str(expected_net_pay),
                            actual=str(net_pay),
                        )
                    )

        # --- Balance sheet balancing ---
        if doc_type == "balance_sheet":
            assets = data.get("assets") or {}
            liabilities = data.get("equity_and_liabilities") or {}
            total_assets = _to_float(assets.get("total_assets")) if isinstance(assets, dict) else None
            total_equity_and_liabilities = (
                _to_float(liabilities.get("total_equity_and_liabilities"))
                if isinstance(liabilities, dict)
                else None
            )
            if total_assets is not None and total_equity_and_liabilities is not None:
                if not math.isclose(
                    total_assets,
                    total_equity_and_liabilities,
                    rel_tol=0.02,
                    abs_tol=1.0,
                ):
                    errors.append(
                        ValidationError(
                            pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                            severity=Severity.ERROR,
                            field="equity_and_liabilities.total_equity_and_liabilities",
                            message="Balance sheet does not balance: total assets do not equal total equity and liabilities",
                            expected=str(total_assets),
                            actual=str(total_equity_and_liabilities),
                        )
                    )

        # --- Education year ranges (for resumes) ---
        if doc_type == "resume":
            for idx, edu in enumerate(data.get("education") or []):
                if not isinstance(edu, dict):
                    continue
                grad = edu.get("graduation_date") or edu.get("end_date")
                if grad:
                    year_match = re.search(r"(\d{4})", str(grad))
                    if year_match:
                        year = int(year_match.group(1))
                        if year > datetime.now().year + 10 or year < 1950:
                            errors.append(
                                ValidationError(
                                    pillar=ValidationPillar.LOGICAL_CONSISTENCY,
                                    severity=Severity.WARNING,
                                    field=f"education.{idx}.graduation_date",
                                    message="Graduation year looks unrealistic",
                                    actual=str(year),
                                )
                            )

        return errors

    # ══════════════════════════════════════════════════════════════════════════
    #  PILLAR 2 — CONTEXTUAL SANITY  (LLM — Doc-Type-Aware)
    #
    #  Why this matters: A generic "flag impossible values" prompt works but
    #  misses document-specific required fields and domain rules. By injecting
    #  the doc-type context hint we tell the LLM exactly what a marksheet,
    #  invoice, or passport should look like — so it can flag missing required
    #  fields, wrong formats, and value-range violations specific to that type.
    #
    #  Why expected/actual: The original prompt only returned a message string.
    #  Adding expected_value and actual_value makes every error self-contained
    #  and actionable — no manual inspection of the data is required.
    # ══════════════════════════════════════════════════════════════════════════

    def _check_contextual_sanity(
        self, data: Any, doc_type: Optional[str]
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []

        if not self._llm or not isinstance(data, dict):
            logger.warning("Pillar 2 skipped — LLM not available or data is not a dict")
            return errors

        if not _has_supported_schema(doc_type):
            logger.info(f"Pillar 2 skipped - unsupported or generic document type: {doc_type}")
            return errors

        # Smart truncation: keep a meaningful JSON budget instead of a hard char cut
        compact = json.dumps(data, indent=None, ensure_ascii=False, default=str)
        if len(compact) > 6000:
            compact = compact[:6000] + " … [truncated — first 6000 chars shown]"

        type_context_block = _build_schema_validation_context(doc_type)
        current_date = datetime.now().date().isoformat()

        prompt = f"""You are a strict data quality auditor for a document extraction system.

You are reviewing extracted data from a **{doc_type or 'unknown'}** document.
Current system date: {current_date}
{type_context_block}
Extracted data:
```json
{compact}
```

Your task: identify at most 8 high-value semantic issues.

Rules:
1. Use the schema field names exactly as provided. Do not suggest renaming fields that already match the schema.
2. Only mark a field as missing if it is in the required field list or is clearly mandatory from another non-null sibling field.
3. Do not report metadata, OCR runtime details, file paths, or processing timestamps.
4. Use the current system date above for all future/past checks. Do not invent another current date.
5. Do not flag dosage strings like "500mg" or "10ml" as invalid just because they are not pure numbers unless the schema requires a numeric field.
6. Prefer concrete field issues over generic document-level statements.
7. Use severity="warning" unless the extracted value is definitely wrong, impossible, or contradictory based on the provided data.
8. Do not treat archived or historical documents as suspicious just because dates are older than the current date.
9. Accept domain-standard shorthand values if they are common for that document type.

For EACH issue, return a JSON object with:
- "field"          : dot-path to the problematic field (e.g. "subjects.0.marks_obtained")
- "severity"       : "error" (data is definitely wrong) or "warning" (data looks suspicious)
- "message"        : clear, specific explanation of what is wrong
- "expected_value" : what the value should be, or what was computed/expected (string or null)
- "actual_value"   : what was actually found in the data (string or null)

Respond ONLY with a valid JSON array. Do not use markdown fences. If there are no issues, respond with: []
"""

        try:
            raw = self._llm_call_with_retry(prompt, max_tokens=1000, temperature=0.1)

            issues = self._parse_json_array(raw)
            logger.info(f"Pillar 2 received {len(issues)} issues from LLM")
            for iss in issues:
                if not isinstance(iss, dict):
                    continue
                # Safely coerce severity — fall back to warning for unknown values
                raw_sev = iss.get("severity", "warning").lower()
                try:
                    sev = Severity(raw_sev)
                except ValueError:
                    sev = Severity.WARNING

                errors.append(
                    ValidationError(
                        pillar=ValidationPillar.CONTEXTUAL_SANITY,
                        severity=sev,
                        field=iss.get("field"),
                        message=iss.get("message", "Contextual sanity issue"),
                        expected=str(iss["expected_value"]) if iss.get("expected_value") is not None else None,
                        actual=str(iss["actual_value"]) if iss.get("actual_value") is not None else None,
                    )
                )
        except Exception as exc:
            logger.warning(f"Pillar 2 failed after retries: {exc}")
            errors.append(
                ValidationError(
                    pillar=ValidationPillar.CONTEXTUAL_SANITY,
                    severity=Severity.INFO,
                    message=f"LLM contextual sanity check could not complete: {exc}",
                )
            )

        return self._filter_contextual_sanity_issues(errors, doc_type, data)

    # ══════════════════════════════════════════════════════════════════════════
    #  PILLAR 3 — SCHEMA & FORMAT  (Normalisation Layer)
    # ══════════════════════════════════════════════════════════════════════════

    def _normalise_data(
        self, data: Any, _prefix: str = ""
    ) -> Tuple[Any, List[NormalisationChange]]:
        """
        Walk *data* recursively and normalise:
        - dates → ISO 8601 (YYYY-MM-DD)
        - phone numbers → digits with country code
        - currency strings → plain floats
        Returns (normalised_data, list_of_changes).
        """
        changes: List[NormalisationChange] = []

        if isinstance(data, dict):
            out = {}
            for key, val in data.items():
                path = f"{_prefix}.{key}" if _prefix else key
                new_val, sub_changes = self._normalise_data(val, path)
                changes.extend(sub_changes)

                # Apply field-specific normalisation
                lower_key = key.lower()

                # Date fields
                if any(tok in lower_key for tok in ("date", "dob", "birth", "expiry", "issued", "due")):
                    if isinstance(new_val, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", new_val):
                        parsed = _try_parse_date(new_val)
                        if parsed and parsed != new_val:
                            changes.append(
                                NormalisationChange(
                                    field=path,
                                    original_value=new_val,
                                    normalised_value=parsed,
                                    rule_applied="ISO 8601 date conversion",
                                )
                            )
                            new_val = parsed

                # Phone fields
                if any(tok in lower_key for tok in ("phone", "mobile", "contact", "tel")):
                    if isinstance(new_val, str) and new_val.strip():
                        normed = _normalise_phone(new_val)
                        if normed != new_val:
                            changes.append(
                                NormalisationChange(
                                    field=path,
                                    original_value=new_val,
                                    normalised_value=normed,
                                    rule_applied="Phone number normalisation",
                                )
                            )
                            new_val = normed

                # Currency string → float
                if any(tok in lower_key for tok in ("amount", "total", "subtotal", "tax", "price", "cost", "fee", "premium")):
                    if isinstance(new_val, str) and _CURRENCY_CHARS_RE.search(new_val):
                        num = _to_float(new_val)
                        if num is not None:
                            changes.append(
                                NormalisationChange(
                                    field=path,
                                    original_value=new_val,
                                    normalised_value=str(num),
                                    rule_applied="Currency string to float",
                                )
                            )
                            new_val = num

                out[key] = new_val
            return out, changes

        if isinstance(data, list):
            out_list = []
            for idx, item in enumerate(data):
                path = f"{_prefix}.{idx}" if _prefix else str(idx)
                new_item, sub_changes = self._normalise_data(item, path)
                out_list.append(new_item)
                changes.extend(sub_changes)
            return out_list, changes

        return data, changes

    # ══════════════════════════════════════════════════════════════════════════
    #  PILLAR 4 — AUTONOMOUS TRUTH TESTS  (Exhaustive + Expected/Actual)
    #
    #  Why unlimited tests: The original design capped at 3. For a marksheet
    #  with 6 subjects there are 6+ arithmetic relationships to verify. Capping
    #  at 3 means most go unchecked. We now ask for ALL meaningful tests and
    #  let the LLM decide how many are appropriate for the document.
    #
    #  Why expected/actual per test: Pass/fail alone is not actionable.
    #  Knowing "expected: 513, actual: 253" immediately tells a human where
    #  and what the problem is without re-reading the raw data.
    # ══════════════════════════════════════════════════════════════════════════

    def _generate_truth_tests(
        self, data: Any, doc_type: Optional[str]
    ) -> List[TruthTestResult]:
        """
        Ask the LLM to generate a comprehensive set of math/logic truth tests
        tailored to this specific document and evaluate each one with concrete
        expected and actual values.
        """
        results: List[TruthTestResult] = []

        if not self._llm or not isinstance(data, dict):
            logger.warning("Pillar 4 skipped — LLM not available or data is not a dict")
            return results
        if not _has_supported_schema(doc_type):
            logger.info(f"Pillar 4 skipped - unsupported or generic document type: {doc_type}")
            return results

        compact = json.dumps(data, indent=None, ensure_ascii=False, default=str)
        if len(compact) > 5000:
            compact = compact[:5000] + " … [truncated — see full data in extraction.json]"

        type_context_block = _build_schema_validation_context(doc_type)
        current_date = datetime.now().date().isoformat()

        prompt = f"""You are a mathematical consistency auditor for a document extraction system.

You are reviewing extracted data from a **{doc_type or 'unknown'}** document.
Current system date: {current_date}
{type_context_block}
Extracted data:
```json
{compact}
```

Generate up to 8 high-value truth tests to verify the mathematical and logical integrity
of this specific document. Use only schema field names that actually exist.

For EACH testable claim:
1. Look at the actual data values
2. Compute what the value SHOULD be based on document rules
3. Compare expected vs actual and determine pass/fail

Focus on:
- All arithmetic relationships (sums, products, ratios, percentages)
- Required fields that should not be null for this document type
- Date logic (end > start, no future dates for issue dates) using the current system date above
- Cross-field consistency (if field A is present, field B should also be present)
- Format validity (12-digit ID numbers, percentage within 0-100, etc.)

Rules:
- Do not use alternative field names not present in the schema.
- Do not wrap the response in markdown fences.
- If there is no meaningful truth test for a field, omit it.

For each test, return a JSON object with:
- "test_name"       : short snake_case identifier
- "assertion"       : natural-language statement of what should be true
- "passed"          : true if the assertion holds, false otherwise
- "detail"          : explanation of why it failed, null if passed
- "expected_value"  : the expected value as a string (computed or inferred)
- "actual_value"    : the actual value found in the data as a string

Respond ONLY with a valid JSON array. Example:
[
  {{"test_name": "marks_sum", "assertion": "Sum of marks_obtained equals total_marks",
    "passed": false, "detail": "Sum is 253 but total_marks is 513",
    "expected_value": "253", "actual_value": "513"}}
]
"""

        try:
            raw = self._llm_call_with_retry(prompt, max_tokens=1200, temperature=0.1)
            logger.debug(f"Pillar 4 raw LLM response (first 500 chars): {raw[:500]}")
            tests = self._parse_json_array(raw)
            logger.info(f"Pillar 4 parsed {len(tests)} truth tests from LLM")

            for t in tests:
                if not isinstance(t, dict):
                    continue
                results.append(
                    TruthTestResult(
                        test_name=t.get("test_name", "unnamed_test"),
                        assertion=t.get("assertion", ""),
                        passed=bool(t.get("passed", False)),
                        detail=t.get("detail"),
                        expected_value=str(t["expected_value"]) if t.get("expected_value") is not None else None,
                        actual_value=str(t["actual_value"]) if t.get("actual_value") is not None else None,
                    )
                )
        except Exception as exc:
            logger.warning(f"Pillar 4 failed after retries: {exc}")
            return []

        return results

    # ──────────────────────────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _compute_confidence(
        self,
        errors: List[ValidationError],
        truth_tests: List[TruthTestResult],
        changes: List[NormalisationChange],
    ) -> float:
        """
        Proportional confidence score in [0, 1].

        Why proportional instead of flat deductions:
        The original flat formula (−0.15 per error) collapsed to 0.0 on
        documents with 5+ errors — even when some fields were perfectly valid.
        A score of 0.0 is indistinguishable from "file not found" errors,
        making it useless for ranking or triaging document quality.

        New formula (two-component blend):
        ┌─────────────────────────────────────────────────────────────────┐
        │  error_penalty = 1 − 1/(1 + error_count × 0.4)   (asymptotic) │
        │  warning_penalty = warning_count × 0.04           (linear)     │
        │  raw_score = max(0, 1 − error_penalty − warning_penalty)        │
        │  truth_pass_rate = passed_tests / total_tests                   │
        │  final = raw_score × 0.55 + truth_pass_rate × 0.45             │
        └─────────────────────────────────────────────────────────────────┘

        Properties:
        - 0 errors, 0 warnings, all tests pass  → ~1.0
        - 5 errors, 6 warnings, 2/3 tests fail  → ~0.25  (meaningful signal)
        - Score never collapses to 0.0 unless ALL truth tests fail AND
          errors are extreme — preserving ranking granularity.
        """
        error_count   = sum(1 for e in errors if e.severity == Severity.ERROR)
        warning_count = sum(1 for e in errors if e.severity == Severity.WARNING)

        # Asymptotic error penalty: first error hurts most; diminishing returns
        error_penalty   = 1.0 - (1.0 / (1.0 + error_count * 0.4))
        warning_penalty = warning_count * 0.04
        raw_score = max(0.0, 1.0 - error_penalty - warning_penalty)

        usable_truth_tests = [
            test for test in truth_tests
            if test.test_name != "llm_generation_failed"
        ]

        # Truth-test pass rate (treat no usable tests as fully passing)
        if usable_truth_tests:
            truth_pass_rate = (
                sum(1 for t in usable_truth_tests if t.passed) / len(usable_truth_tests)
            )
        else:
            truth_pass_rate = 1.0

        truth_weight = max(0.0, min(0.45, config.VALIDATION_TRUTH_TEST_WEIGHT))
        raw_weight = 1.0 - truth_weight
        final = raw_score * raw_weight + truth_pass_rate * truth_weight

        return round(max(0.0, min(1.0, final)), 4)

    @staticmethod
    def _load_csv(path: Path) -> dict:
        """Load a CSV into a dict with a ``rows`` key."""
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        return {"rows": rows, "_source_format": "csv"}

    @staticmethod
    def _parse_json_array(raw: str) -> list:
        """Parse a JSON array from LLM output, tolerating markdown fences."""
        raw = raw.strip()

        # Strategy 1: strip markdown code fences (```json ... ```)
        cleaned = raw
        if cleaned.startswith("```"):
            # Remove opening fence: ```json or ```
            cleaned = re.sub(r"^```[a-zA-Z]*\s*\n?", "", cleaned)
            # Remove closing fence
            cleaned = re.sub(r"\n?\s*```\s*$", "", cleaned)
            cleaned = cleaned.strip()

        # Strategy 2: direct parse
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

        # Strategy 2b: repair common trailing-comma mistakes before parsing
        repaired = re.sub(r",(\s*[}\]])", r"\1", cleaned)
        if repaired != cleaned:
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except json.JSONDecodeError:
                pass

        # Strategy 3: find the outermost [...] block
        bracket_depth = 0
        start_idx = None
        for i, ch in enumerate(cleaned):
            if ch == "[":
                if bracket_depth == 0:
                    start_idx = i
                bracket_depth += 1
            elif ch == "]":
                bracket_depth -= 1
                if bracket_depth == 0 and start_idx is not None:
                    candidate = cleaned[start_idx : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        pass
                    break

        # Strategy 4: regex fallback on original input
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"_parse_json_array: could not parse LLM output (len={len(raw)}): {raw[:200]}")
        return []

    def _filter_contextual_sanity_issues(
        self,
        issues: List[ValidationError],
        doc_type: Optional[str],
        data: Any,
    ) -> List[ValidationError]:
        filtered: List[ValidationError] = []
        required_fields = set(_get_required_field_paths(doc_type))

        for issue in issues:
            field = (issue.field or "").strip()
            message = (issue.message or "").lower()
            actual_value = _get_nested_value(data, field) if field else None

            if field and not _is_reviewable_field(field):
                continue

            normalized_field = _normalise_field_path(field) if field else ""
            if normalized_field and not _is_contextual_field_allowed(doc_type, normalized_field):
                continue

            # Drop schema-renaming noise such as "description should be name".
            if "should be" in message and (
                "key fields context" in message
                or "schema" in message
                or "canonical" in message
            ):
                continue

            # Skip unverifiable complaints that simply restate missing context.
            if "cannot be verified due to missing" in message or "cannot be validated due to missing" in message:
                continue

            if _is_subjective_contextual_issue(doc_type, normalized_field, message):
                continue

            # Prescription dosage is intentionally free-form in the schema.
            if (
                doc_type == "prescription"
                and normalized_field.endswith(".dosage")
                and any(
                    token in message
                    for token in (
                        "positive number",
                        "non-numeric",
                        "not numeric",
                        "standardized format",
                    )
                )
            ):
                continue

            if doc_type == "prescription" and normalized_field.endswith(".frequency"):
                if any(
                    token in message
                    for token in (
                        "ambiguous",
                        "clear instructions",
                        "once daily",
                        "twice daily",
                        "morning and night",
                    )
                ):
                    continue

            if doc_type == "prescription" and normalized_field.endswith(".instructions"):
                if "vague" in message or "standard prescription practices" in message:
                    continue

            if doc_type == "prescription" and normalized_field in {"follow_up", "patient_gender", "clinic_address"}:
                if any(
                    token in message
                    for token in (
                        "vague",
                        "incomplete",
                        "allows for",
                        "default value",
                    )
                ):
                    continue

            if doc_type == "prescription" and normalized_field == "date":
                if "in the past" in message or "historical" in message:
                    continue

            if doc_type in {"invoice", "purchase_order", "retail_receipt"}:
                if normalized_field == "invoice_date" and any(
                    token in message for token in ("in the past", "historical", "current system date", "stale extraction")
                ):
                    continue
                if normalized_field == "due_date" and "matches the payment terms" in message:
                    continue
                if normalized_field == "invoice_number" and "purchase order" in message:
                    continue
                if normalized_field == "notes" and any(
                    token in message
                    for token in ("security risk", "sensitive payment information", "should be redacted")
                ):
                    continue
                if any(
                    token in message
                    for token in (
                        "minor rounding discrepancy",
                        "the calculation is correct",
                        "precision issue",
                        "typical invoice practices",
                        "tax-exempt",
                    )
                ):
                    continue
                if _invoice_math_is_consistent(data, normalized_field):
                    continue

            if doc_type == "purchase_order":
                if normalized_field == "order_date" and any(
                    token in message for token in ("in the past", "previous year", "historical")
                ):
                    continue

            if doc_type == "retail_receipt":
                if normalized_field == "receipt_date" and any(
                    token in message for token in ("in the past", "historical", "current system date")
                ):
                    continue
                if normalized_field == "payment_method" and "not standardized" in message:
                    continue

            if doc_type == "form_16" and normalized_field == "assessment_year":
                if "assessment year" in message and any(
                    token in message
                    for token in ("current system date", "should typically", "or later")
                ):
                    continue

            if doc_type == "form_16" and normalized_field.startswith("employee.period_of_employment."):
                if "both are null" in message or "if the form is complete" in message:
                    continue

            if doc_type == "bank_statement" and normalized_field == "account_number":
                if "masked characters" in message or _looks_like_masked_identifier(actual_value):
                    continue

            if doc_type == "bank_statement":
                if normalized_field == "statement_period.to_date" and any(
                    token in message for token in ("over 2 years old", "stale or outdated data", "current system date")
                ):
                    continue
                if normalized_field == "transactions" and "missing transactions between" in message:
                    continue
                if normalized_field.endswith(".date") and "outside the statement period" in message:
                    if _statement_period_contains_date(data, actual_value):
                        continue

            if doc_type == "cheque":
                if normalized_field == "date" and "in the past relative to the current system date" in message:
                    continue
                if normalized_field == "cheque_number" and any(
                    token in message
                    for token in ("placeholder", "sequential", "verify if this is the correct")
                ):
                    continue
                if normalized_field == "account_number" and "unusually long" in message:
                    continue
                if normalized_field == "ifsc_code" and _looks_like_ifsc(actual_value):
                    continue
                if normalized_field == "micr_code" and _looks_like_micr(actual_value):
                    continue
                if normalized_field == "amount_figures" and _amount_words_match_numeric(
                    _get_nested_value(data, "amount_words"),
                    actual_value,
                ):
                    continue

            if doc_type == "aadhar_card" and normalized_field == "uid_number":
                if _has_digit_count(actual_value, 12) or _looks_like_masked_uid(actual_value):
                    continue

            if doc_type == "payslip":
                if normalized_field.startswith("pay_period.") and any(
                    token in message for token in ("in the past", "archived document", "current system date")
                ):
                    continue
                if normalized_field == "pay_period.to_date" and "not a leap year" in message:
                    if _date_value_is_valid(actual_value):
                        continue
                if normalized_field in {"total_earnings", "total_deductions"} and _payslip_math_is_consistent(
                    data, normalized_field
                ):
                    continue

            if doc_type == "balance_sheet":
                if normalized_field in {
                    "assets.total_assets",
                    "equity_and_liabilities.total_equity_and_liabilities",
                } and _balance_sheet_math_is_consistent(data, normalized_field):
                    continue
                if normalized_field.endswith(".name") and "capital wip" in message:
                    continue
                if "seems high relative to other liabilities" in message:
                    continue

            if doc_type == "income_tax_acknowledgment" and normalized_field == "tax_paid":
                if any(
                    token in message
                    for token in ("tax paid cannot be greater than tax payable", "which is impossible")
                ):
                    continue

            if doc_type == "marksheet":
                if normalized_field == "result" and "many grading systems" in message:
                    continue
                if normalized_field == "academic_year" and "current system date" in message:
                    continue
                if normalized_field == "percentage" and "cannot be calculated or validated without" in message:
                    continue

            if doc_type == "contract":
                if normalized_field in {"obligations.party_1", "obligations.party_2"} and (
                    "role-specific key" in message or "schema-defined key" in message
                ):
                    continue
                if normalized_field == "expiration_date" and _term_duration_matches_expiration(
                    _get_nested_value(data, "effective_date"),
                    actual_value,
                    _get_nested_value(data, "term_duration"),
                ):
                    continue

            # Guard against the model inventing the current date.
            if normalized_field and "future" in message and "date" in normalized_field:
                parsed_actual_date = _try_parse_date(str(actual_value)) if actual_value else None
                if parsed_actual_date and parsed_actual_date <= datetime.now().date().isoformat():
                    continue

            # Only required schema fields should trigger "missing" review pressure.
            if ("missing" in message or "required" in message) and normalized_field:
                if normalized_field not in required_fields:
                    continue

            # Do not penalize blank optional contact fields.
            if normalized_field and _is_blank_value(actual_value):
                if normalized_field not in required_fields and any(
                    token in normalized_field.lower()
                    for token in ("phone", "mobile", "email", "address", "payment_terms")
                ):
                    continue

            filtered.append(_coerce_contextual_issue_severity(issue, message, normalized_field, required_fields))

        return filtered

    def _save_report(self, report: AuditReport, source_file: str) -> None:
        """Persist the audit report to ``outputs/validated/``."""
        try:
            self.validated_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = Path(source_file).stem if source_file else "report"
            out_path = self.validated_dir / f"audit_{stem}_{timestamp}.json"

            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(report.model_dump_json(indent=2))

            logger.info(f"Audit report saved -> {out_path.name}")
        except Exception as exc:
            logger.error(f"Failed to persist audit report: {exc}")


def _get_required_field_paths(doc_type: Optional[str]) -> list[str]:
    if not doc_type:
        return []

    schema = get_schema(doc_type)
    if not schema:
        return []
    return [str(field).strip() for field in schema.get_required_fields() if str(field).strip()]


def _has_supported_schema(doc_type: Optional[str]) -> bool:
    if not doc_type or doc_type in _UNSUPPORTED_DOCUMENT_TYPES:
        return False
    return get_schema(doc_type) is not None


def _build_schema_validation_context(doc_type: Optional[str]) -> str:
    schema = get_schema(doc_type) if doc_type else None
    if not schema:
        return ""

    schema_fields = _flatten_schema_field_descriptions(schema.get_schema())
    required_fields = schema.get_required_fields()
    prompt_summary = _summarize_schema_prompt(schema.get_prompt_instructions())
    extra_rules = _DOC_TYPE_VALIDATION_RULES.get(doc_type or "")

    lines = [
        "Authoritative schema context:",
        "- Use only these field paths and meanings. Do not invent aliases.",
    ]
    if required_fields:
        lines.append(f"- Required fields: {', '.join(required_fields)}")
    if schema_fields:
        lines.append("- Schema fields:")
        for field_line in schema_fields[:40]:
            lines.append(f"  - {field_line}")
    if prompt_summary:
        lines.append(f"- Extraction guidance summary: {prompt_summary}")
    if extra_rules:
        lines.append(f"- Validation-specific rules: {extra_rules}")
    return "\n".join(lines) + "\n"


def _flatten_schema_field_descriptions(schema_fragment: Any, prefix: str = "") -> list[str]:
    lines: list[str] = []

    if isinstance(schema_fragment, dict):
        for key, value in schema_fragment.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                lines.extend(_flatten_schema_field_descriptions(value, path))
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    lines.extend(_flatten_schema_field_descriptions(value[0], f"{path}[]"))
                else:
                    descriptor = value[0] if value else "list"
                    lines.append(f"{path}: list[{descriptor}]")
            else:
                lines.append(f"{path}: {value}")
    return lines


def _summarize_schema_prompt(prompt: str, max_chars: int = 480) -> str:
    cleaned = " ".join((prompt or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _get_nested_value(payload: Any, field_path: str) -> Any:
    if not field_path:
        return None

    current = payload
    for part in _normalise_field_path(field_path).split("."):
        if isinstance(current, list):
            if not part.isdigit():
                return None
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
            continue

        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _is_reviewable_field(field_path: str) -> bool:
    lower_field = _normalise_field_path(field_path).lower()
    if lower_field == "__document__":
        return False
    return not any(lower_field.startswith(prefix) for prefix in _NON_REVIEWABLE_FIELD_PREFIXES)


def _is_blank_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return all(_is_blank_value(item) for item in value)
    if isinstance(value, dict):
        return all(_is_blank_value(item) for item in value.values())
    return False


def _normalise_field_path(field_path: str) -> str:
    return re.sub(r"\[(\d+)\]", r".\1", field_path or "")


def _has_digit_count(value: Any, expected_digits: int) -> bool:
    digits = re.sub(r"\D", "", str(value or ""))
    return len(digits) == expected_digits


def _looks_like_ifsc(value: Any) -> bool:
    return bool(re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", str(value or "").strip().upper()))


def _looks_like_micr(value: Any) -> bool:
    return bool(re.fullmatch(r"\d{9}", re.sub(r"\D", "", str(value or "").strip())))


def _looks_like_masked_identifier(value: Any) -> bool:
    text = str(value or "").strip().upper()
    if not text:
        return False
    compact = re.sub(r"[\s-]", "", text)
    if not re.fullmatch(r"[A-Z0-9X*]+", compact):
        return False
    return any(ch in compact for ch in {"X", "*"}) and any(ch.isdigit() for ch in compact)


def _looks_like_masked_uid(value: Any) -> bool:
    text = str(value or "").strip().upper().replace("-", " ")
    if not text:
        return False
    if re.fullmatch(r"(?:[0-9X*]{4}\s+){3}[0-9X*]{4}", text):
        compact = text.replace(" ", "")
        return any(ch.isdigit() for ch in compact) and any(ch in {"X", "*"} for ch in compact)
    return False


def _safe_parse_date_obj(value: Any) -> Optional[datetime]:
    parsed = _try_parse_date(str(value or ""))
    if not parsed:
        return None
    try:
        return datetime.strptime(parsed, "%Y-%m-%d")
    except ValueError:
        return None


def _term_duration_matches_expiration(
    effective_date: Any,
    expiration_date: Any,
    term_duration: Any,
) -> bool:
    start = _safe_parse_date_obj(effective_date)
    end = _safe_parse_date_obj(expiration_date)
    if not start or not end or not term_duration:
        return False

    match = re.search(r"(\d+)\s*month", str(term_duration).lower())
    if not match:
        return False

    months = int(match.group(1))
    actual_months = (end.year - start.year) * 12 + (end.month - start.month)
    day_delta = abs(end.day - start.day)
    return actual_months in {months, months - 1} and day_delta <= 3


_NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_NUMBER_SCALES: dict[str, int] = {
    "hundred": 100,
    "thousand": 1000,
    "lakh": 100000,
    "lac": 100000,
    "million": 1000000,
    "crore": 10000000,
}


def _words_to_number(raw: Any) -> Optional[float]:
    text = str(raw or "").lower()
    if not text:
        return None
    text = text.replace("-", " ")
    text = re.sub(r"\bonly\b|\brupees?\b|\binr\b|\band\b", " ", text)
    tokens = [token for token in re.split(r"\s+", text) if token]
    if not tokens:
        return None

    total = 0
    current = 0
    matched_any = False
    for token in tokens:
        if token in _NUMBER_WORDS:
            current += _NUMBER_WORDS[token]
            matched_any = True
            continue
        if token == "hundred":
            current = max(current, 1) * 100
            matched_any = True
            continue
        scale = _NUMBER_SCALES.get(token)
        if scale:
            total += max(current, 1) * scale
            current = 0
            matched_any = True
            continue
        if token == "point":
            break
    if not matched_any:
        return None
    return float(total + current)


def _amount_words_match_numeric(amount_words: Any, numeric_value: Any) -> bool:
    numeric = _to_float(numeric_value)
    words_numeric = _words_to_number(amount_words)
    if numeric is None or words_numeric is None:
        return False
    return math.isclose(numeric, words_numeric, rel_tol=0.001, abs_tol=0.5)


def _statement_period_contains_date(data: Any, date_value: Any) -> bool:
    if not isinstance(data, dict):
        return False
    target = _safe_parse_date_obj(date_value)
    if not target:
        return False
    period = data.get("statement_period") or {}
    if not isinstance(period, dict):
        return False
    from_date = _safe_parse_date_obj(period.get("from_date"))
    to_date = _safe_parse_date_obj(period.get("to_date"))
    if not from_date or not to_date:
        return False
    return from_date <= target <= to_date


def _invoice_math_is_consistent(data: Any, field_path: str) -> bool:
    if not isinstance(data, dict):
        return False

    line_items = data.get("line_items") or []
    subtotal = _to_float(data.get("subtotal"))
    tax = _to_float(data.get("tax") or data.get("tax_amount"))
    tax_rate = _to_float(data.get("tax_rate"))
    total = _to_float(data.get("total") or data.get("grand_total"))

    if field_path.startswith("line_items.") and field_path.endswith(".total"):
        parts = field_path.split(".")
        if len(parts) < 3 or not parts[1].isdigit():
            return False
        idx = int(parts[1])
        if idx >= len(line_items) or not isinstance(line_items[idx], dict):
            return False
        item = line_items[idx]
        qty = _to_float(item.get("quantity"))
        price = _to_float(item.get("unit_price") or item.get("rate") or item.get("price"))
        item_total = _to_float(item.get("total") or item.get("amount"))
        if qty is None or price is None or item_total is None:
            return False
        expected_total = round(qty * price, 2)
        return math.isclose(expected_total, item_total, rel_tol=0.02, abs_tol=1.0)

    if field_path == "subtotal" and subtotal is not None and line_items:
        line_sum = sum(
            _to_float(it.get("total") or it.get("amount")) or 0
            for it in line_items
            if isinstance(it, dict)
        )
        return math.isclose(subtotal, round(line_sum, 2), rel_tol=0.02, abs_tol=1.0)

    if field_path in {"tax", "tax_rate"} and subtotal is not None and tax is not None and tax_rate is not None:
        expected_tax = round(subtotal * tax_rate / 100.0, 2)
        return math.isclose(expected_tax, tax, rel_tol=0.02, abs_tol=1.0)

    if field_path == "total" and subtotal is not None and total is not None:
        inferred_tax = tax if tax is not None else 0.0
        expected_total = round(subtotal + inferred_tax, 2)
        return math.isclose(expected_total, total, rel_tol=0.02, abs_tol=1.0)

    return False


def _payslip_math_is_consistent(data: Any, field_path: str) -> bool:
    if not isinstance(data, dict):
        return False

    if field_path == "total_earnings":
        earnings = data.get("earnings") or []
        total_earnings = _to_float(data.get("total_earnings"))
        if total_earnings is None or not earnings:
            return False
        earnings_sum = sum(
            _to_float(item.get("amount")) or 0
            for item in earnings
            if isinstance(item, dict)
        )
        return math.isclose(total_earnings, round(earnings_sum, 2), rel_tol=0.02, abs_tol=1.0)

    if field_path == "total_deductions":
        deductions = data.get("deductions") or []
        total_deductions = _to_float(data.get("total_deductions"))
        if total_deductions is None or not deductions:
            return False
        deductions_sum = sum(
            _to_float(item.get("amount")) or 0
            for item in deductions
            if isinstance(item, dict)
        )
        return math.isclose(total_deductions, round(deductions_sum, 2), rel_tol=0.02, abs_tol=1.0)

    return False


def _balance_sheet_math_is_consistent(data: Any, field_path: str) -> bool:
    if not isinstance(data, dict):
        return False

    assets = data.get("assets") or {}
    liabilities = data.get("equity_and_liabilities") or {}
    if not isinstance(assets, dict) or not isinstance(liabilities, dict):
        return False

    def _sum_rows(rows: Any) -> float:
        return round(
            sum(
                _to_float(item.get("amount")) or 0
                for item in (rows or [])
                if isinstance(item, dict)
            ),
            2,
        )

    if field_path == "assets.total_assets":
        total_assets = _to_float(assets.get("total_assets"))
        if total_assets is None:
            return False
        computed_assets = round(
            _sum_rows(assets.get("non_current_assets")) + _sum_rows(assets.get("current_assets")),
            2,
        )
        return math.isclose(total_assets, computed_assets, rel_tol=0.02, abs_tol=1.0)

    if field_path == "equity_and_liabilities.total_equity_and_liabilities":
        total_equity_and_liabilities = _to_float(liabilities.get("total_equity_and_liabilities"))
        if total_equity_and_liabilities is None:
            return False
        computed_total = round(
            _sum_rows(liabilities.get("equity"))
            + _sum_rows(liabilities.get("non_current_liabilities"))
            + _sum_rows(liabilities.get("current_liabilities")),
            2,
        )
        return math.isclose(total_equity_and_liabilities, computed_total, rel_tol=0.02, abs_tol=1.0)

    return False


def _date_value_is_valid(value: Any) -> bool:
    return _safe_parse_date_obj(value) is not None


def _is_contextual_field_allowed(doc_type: Optional[str], field_path: str) -> bool:
    prefixes = _DOC_TYPE_CONTEXTUAL_FIELD_ALLOWLIST_PREFIXES.get(doc_type or "")
    if not prefixes:
        return True
    return any(
        field_path == prefix
        or field_path.startswith(prefix + ".")
        or prefix.startswith(field_path + ".")
        for prefix in prefixes
    )


def _is_subjective_contextual_issue(
    doc_type: Optional[str],
    field_path: str,
    message: str,
) -> bool:
    generic_tokens = (
        "often included",
        "standard field",
        "typically included",
        "common component",
        "may have been missed",
        "may indicate incomplete extraction",
        "should be fully spelled out",
        "full name is expected",
        "too vague",
        "is vague",
        "appears to be an abbreviation",
        "likely an abbreviation",
        "unusually low",
        "unusually high",
        "is highly unusual",
        "overdue",
    )
    if any(token in message for token in generic_tokens):
        return True

    if doc_type == "prescription" and field_path in {"patient_gender", "registration_number", "clinic_address"}:
        return True

    if doc_type == "marksheet" and (
        field_path.startswith("subjects.") and field_path.endswith(".name")
        or field_path in {"class_teacher", "class_grade", "result"}
    ):
        return True

    if doc_type == "contract" and (
        field_path.endswith(".address")
        or field_path.endswith(".role")
        or field_path.startswith("signatures.")
        or field_path.startswith("obligations.")
        or field_path == "deliverables"
    ):
        return True

    if doc_type == "utility_bill" and field_path in {
        "charges.fixed_charge",
        "charges.taxes",
        "due_date",
    }:
        return True

    if doc_type == "birth_certificate" and field_path == "place_of_birth.district":
        return True

    if doc_type == "invoice" and field_path in {"invoice_number", "notes", "tax", "tax_rate", "due_date"}:
        if any(
            token in message
            for token in (
                "purchase order",
                "security risk",
                "sensitive payment information",
                "minor rounding discrepancy",
                "the calculation is correct",
                "precision issue",
                "typical invoice practices",
                "tax-exempt",
            )
        ):
            return True

    if doc_type == "cheque" and field_path in {"date", "cheque_number", "account_number"}:
        return True

    return False


def _coerce_contextual_issue_severity(
    issue: ValidationError,
    message: str,
    field_path: str,
    required_fields: set[str],
) -> ValidationError:
    hard_tokens = (
        "mismatch",
        "does not match",
        "invalid",
        "conflict",
        "contradict",
        "cannot be null",
        "required",
        "missing",
        "impossible",
        "must be",
        "incorrect",
    )
    keep_error = (
        issue.severity == Severity.ERROR
        and (
            any(token in message for token in hard_tokens)
            or field_path in required_fields
        )
    )
    if keep_error or issue.severity != Severity.ERROR:
        return issue

    return ValidationError(
        pillar=issue.pillar,
        severity=Severity.WARNING,
        field=issue.field,
        message=issue.message,
        expected=issue.expected,
        actual=issue.actual,
    )
