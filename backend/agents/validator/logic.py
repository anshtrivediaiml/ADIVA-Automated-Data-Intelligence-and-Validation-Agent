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
    "aadhaar": (
        "Key fields: name, aadhaar_number (exactly 12 digits), date_of_birth, gender, address. "
        "Rules: aadhaar_number must be exactly 12 digits; DOB must be in past; "
        "name and address must not be empty."
    ),
    "pan": (
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
    "gstin": (
        "Key fields: gstin (15-char alphanumeric), legal_name, trade_name, "
        "registration_date, business_type. Rules: GSTIN must be 15 characters; first 2 chars are state code."
    ),
    "cheque": (
        "Key fields: payee_name, amount_in_figures, amount_in_words, date, "
        "bank_name, account_number, ifsc_code, cheque_number. "
        "Rules: amount_in_figures must match amount_in_words numerically; date not too old."
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
        logger.info("Validation Pillar 4: Autonomous Truth Tests")
        truth_tests = self._generate_truth_tests(structured, document_type)

        # Failed truth tests → errors
        for tt in truth_tests:
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

        # Smart truncation: keep a meaningful JSON budget instead of a hard char cut
        compact = json.dumps(data, indent=None, ensure_ascii=False, default=str)
        if len(compact) > 6000:
            compact = compact[:6000] + " … [truncated — first 6000 chars shown]"

        # Look up doc-type-specific field vocabulary to guide the LLM
        type_hint = _DOC_TYPE_HINTS.get(doc_type or "", "")
        type_context_block = (
            f"\nDocument type context:\n{type_hint}\n"
            if type_hint
            else ""
        )

        prompt = f"""You are a strict data quality auditor for a document extraction system.

You are reviewing extracted data from a **{doc_type or 'unknown'}** document.
{type_context_block}
Extracted data:
```json
{compact}
```

Your task — identify ALL of the following categories of issues:
1. **Missing required fields**: Fields that are null/empty but are expected for this document type.
2. **Mathematical inconsistencies**: Numbers that do not add up (totals, sums, percentages).
3. **Format violations**: Incorrect date formats, invalid phone/ID numbers, wrong string patterns.
4. **Logical contradictions**: Values that contradict each other (e.g. grade present but marks_obtained is null).
5. **Out-of-range values**: Dates in the future where they shouldn't be, negative quantities, percentages > 100.

For EACH issue, return a JSON object with:
- "field"          : dot-path to the problematic field (e.g. "subjects.0.marks_obtained")
- "severity"       : "error" (data is definitely wrong) or "warning" (data looks suspicious)
- "message"        : clear, specific explanation of what is wrong
- "expected_value" : what the value should be, or what was computed/expected (string or null)
- "actual_value"   : what was actually found in the data (string or null)

Respond ONLY with a valid JSON array. If there are no issues, respond with: []
"""

        try:
            raw = self._llm_call_with_retry(prompt, max_tokens=1200, temperature=0.1)

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

        return errors

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

        compact = json.dumps(data, indent=None, ensure_ascii=False, default=str)
        if len(compact) > 5000:
            compact = compact[:5000] + " … [truncated — see full data in extraction.json]"

        # Look up doc-type hint to focus the LLM on the right math relationships
        type_hint = _DOC_TYPE_HINTS.get(doc_type or "", "")
        type_context_block = f"\nDocument type context:\n{type_hint}\n" if type_hint else ""

        prompt = f"""You are a mathematical consistency auditor for a document extraction system.

You are reviewing extracted data from a **{doc_type or 'unknown'}** document.
{type_context_block}
Extracted data:
```json
{compact}
```

Generate a **comprehensive** list of truth tests to verify the mathematical and logical integrity
of this specific document. Do NOT limit yourself to 3 — generate as many as are meaningful.

For EACH testable claim:
1. Look at the actual data values
2. Compute what the value SHOULD be based on document rules
3. Compare expected vs actual and determine pass/fail

Focus on:
- All arithmetic relationships (sums, products, ratios, percentages)
- Required fields that should not be null for this document type
- Date logic (end > start, no future dates for issue dates)
- Cross-field consistency (if field A is present, field B should also be present)
- Format validity (12-digit ID numbers, percentage within 0-100, etc.)

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
            raw = self._llm_call_with_retry(prompt, max_tokens=2000, temperature=0.1)
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
            results.append(
                TruthTestResult(
                    test_name="llm_generation_failed",
                    assertion="LLM should generate comprehensive truth tests",
                    passed=False,
                    detail=str(exc),
                )
            )

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

        # Truth-test pass rate (treat no tests as fully passing)
        if truth_tests:
            truth_pass_rate = sum(1 for t in truth_tests if t.passed) / len(truth_tests)
        else:
            truth_pass_rate = 1.0

        # Blend: error/warning component (55%) + truth test pass rate (45%)
        final = raw_score * 0.55 + truth_pass_rate * 0.45

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

    def _save_report(self, report: AuditReport, source_file: str) -> None:
        """Persist the audit report to ``outputs/validated/``."""
        try:
            self.validated_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = Path(source_file).stem if source_file else "report"
            out_path = self.validated_dir / f"audit_{stem}_{timestamp}.json"

            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(report.model_dump_json(indent=2))

            logger.info(f"Audit report saved → {out_path.name}")
        except Exception as exc:
            logger.error(f"Failed to persist audit report: {exc}")
