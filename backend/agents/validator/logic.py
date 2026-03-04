"""
ADIVA — Validation Agent  (core logic)

Quality-control layer for the extraction pipeline.
Implements four validation pillars:

1. Logical Consistency   — math / numeric checks
2. Contextual Sanity     — LLM-powered common-sense checks
3. Schema & Format       — date / phone / currency normalisation
4. Autonomous Truth Tests — LLM generates 3 assertions per document
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

# ──────────────────────────────────────────────────────────
# Regex helpers used across pillars
# ──────────────────────────────────────────────────────────

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

# ──────────────────────────────────────────────────────────
# Utility — safe numeric coercion
# ──────────────────────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════
#  VALIDATION AGENT
# ══════════════════════════════════════════════════════════

class ValidationAgent:
    """
    Quality-control agent for the ADIVA extraction pipeline.

    Reads extracted data (``.json`` or ``.csv``) from ``EXTRACTED_DIR``
    and produces a strict :class:`AuditReport` covering four pillars.
    """

    def __init__(self):
        self.data_dir: Path = config.EXTRACTED_DIR  # extracted output dir
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
        logger.info("ValidationAgent initialised")

    # ──────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────

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
        folder = self.data_dir / extraction_id
        json_path = folder / "extraction.json"

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

    # ──────────────────────────────────────────────────────
    #  ORCHESTRATOR
    # ──────────────────────────────────────────────────────

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

        # ── Pillar 1: Logical consistency ─────────────────
        logger.info("Validation Pillar 1: Logical Consistency")
        errors.extend(self._check_logical_consistency(structured, document_type))

        # ── Pillar 2: Contextual sanity (LLM) ────────────
        logger.info("Validation Pillar 2: Contextual Sanity")
        errors.extend(self._check_contextual_sanity(structured, document_type))

        # ── Pillar 3: Schema & format normalisation ───────
        logger.info("Validation Pillar 3: Schema & Format Enforcement")
        normalised, norm_changes = self._normalise_data(normalised)

        # ── Pillar 4: Autonomous truth tests ──────────────
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

        # ── Calculate confidence ──────────────────────────
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

    # ══════════════════════════════════════════════════════
    #  PILLAR 1 — LOGICAL CONSISTENCY  (Math Check)
    # ══════════════════════════════════════════════════════

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

    # ══════════════════════════════════════════════════════
    #  PILLAR 2 — CONTEXTUAL SANITY  (LLM Common-Sense)
    # ══════════════════════════════════════════════════════

    def _check_contextual_sanity(
        self, data: Any, doc_type: Optional[str]
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []

        if not self._llm or not isinstance(data, dict):
            logger.warning("Pillar 2 skipped — LLM not available or data is not a dict")
            return errors

        # Build a compact JSON to send to the LLM
        compact = json.dumps(data, indent=None, ensure_ascii=False, default=str)
        # Truncate to keep prompt under token limits
        if len(compact) > 6000:
            compact = compact[:6000] + " … [truncated]"

        prompt = f"""You are a data quality auditor. Analyse the following extracted document data and flag any values that are **physically impossible**, **logically contradictory**, or **commonly-sense invalid**.

Document type: {doc_type or "unknown"}

Data:
```json
{compact}
```

Rules:
- Dates must be logical (no future dates for birth certificates, invoice dates shouldn't be decades ago, etc.)
- Monetary values must be within reasonable ranges for the document type.
- Physical quantities (age, weight, height, percentages) must be realistic.
- Phone numbers should be plausible digit counts.
- Percentages should be 0-100 (unless explicitly a multiplier).

Respond ONLY with a JSON array of issues. Each issue is an object:
{{"field": "dot.path", "severity": "error" or "warning", "message": "explanation"}}

If there are NO issues, respond with an empty array: []
"""

        try:
            resp = self._llm.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800,
            )
            raw = resp.choices[0].message.content.strip()

            # Parse the JSON array
            issues = self._parse_json_array(raw)
            for iss in issues:
                if not isinstance(iss, dict):
                    continue
                errors.append(
                    ValidationError(
                        pillar=ValidationPillar.CONTEXTUAL_SANITY,
                        severity=Severity(iss.get("severity", "warning")),
                        field=iss.get("field"),
                        message=iss.get("message", "Contextual sanity issue"),
                    )
                )
        except Exception as exc:
            logger.warning(f"Pillar 2 LLM call failed: {exc}")
            errors.append(
                ValidationError(
                    pillar=ValidationPillar.CONTEXTUAL_SANITY,
                    severity=Severity.INFO,
                    message=f"LLM contextual sanity check could not complete: {exc}",
                )
            )

        return errors

    # ══════════════════════════════════════════════════════
    #  PILLAR 3 — SCHEMA & FORMAT  (Normalisation Layer)
    # ══════════════════════════════════════════════════════

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

    # ══════════════════════════════════════════════════════
    #  PILLAR 4 — AUTONOMOUS TRUTH TESTS
    # ══════════════════════════════════════════════════════

    def _generate_truth_tests(
        self, data: Any, doc_type: Optional[str]
    ) -> List[TruthTestResult]:
        """
        Ask the LLM to generate 3 logical truth-test assertions
        tailored to the document, then evaluate each.
        """
        results: List[TruthTestResult] = []

        if not self._llm or not isinstance(data, dict):
            logger.warning("Pillar 4 skipped — LLM not available or data is not a dict")
            return results

        compact = json.dumps(data, indent=None, ensure_ascii=False, default=str)
        if len(compact) > 5000:
            compact = compact[:5000] + " … [truncated]"

        prompt = f"""You are a document-data auditor. Given the following extracted data from a **{doc_type or 'unknown'}** document, generate exactly 3 truth-test assertions that can verify data integrity.

Data:
```json
{compact}
```

For each test, provide:
- test_name: snake_case short name
- assertion: the natural-language logical assertion
- passed: true/false — evaluate the assertion against the data above
- detail: explanation if the test failed, null if passed

Respond ONLY with a JSON array of 3 objects:
[
  {{"test_name": "...", "assertion": "...", "passed": true, "detail": null}},
  ...
]
"""

        try:
            resp = self._llm.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1200,
            )
            raw = resp.choices[0].message.content.strip()
            logger.debug(f"Pillar 4 raw LLM response: {raw[:500]}")
            tests = self._parse_json_array(raw)
            logger.info(f"Pillar 4 parsed {len(tests)} truth tests from LLM")

            for t in tests[:3]:
                if not isinstance(t, dict):
                    continue
                results.append(
                    TruthTestResult(
                        test_name=t.get("test_name", "unnamed_test"),
                        assertion=t.get("assertion", ""),
                        passed=bool(t.get("passed", False)),
                        detail=t.get("detail"),
                    )
                )
        except Exception as exc:
            logger.warning(f"Pillar 4 LLM call failed: {exc}")
            results.append(
                TruthTestResult(
                    test_name="llm_generation_failed",
                    assertion="LLM should generate truth tests",
                    passed=False,
                    detail=str(exc),
                )
            )

        return results

    # ──────────────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────────────

    def _compute_confidence(
        self,
        errors: List[ValidationError],
        truth_tests: List[TruthTestResult],
        changes: List[NormalisationChange],
    ) -> float:
        """
        Heuristic confidence score 0-1.

        - Start at 1.0
        - Each ERROR deducts  0.15
        - Each WARNING deducts 0.05
        - Each failed truth test deducts 0.08
        - Normalisation changes are neutral (data was fixable)
        """
        score = 1.0
        for e in errors:
            if e.severity == Severity.ERROR:
                score -= 0.15
            elif e.severity == Severity.WARNING:
                score -= 0.05

        for tt in truth_tests:
            if not tt.passed:
                score -= 0.08

        return max(0.0, min(1.0, score))

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
