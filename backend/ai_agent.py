"""
ADIVA - AI Agent Module

This module handles interaction with Mistral AI for:
- Document classification
- Schema-based structured data extraction
- Response parsing and validation
"""

import json
import re
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from mistralai import Mistral

try:
    import config
    from logger import log_ai_response, log_error, logger
    from schemas import SCHEMA_REGISTRY, get_schema
except ModuleNotFoundError:
    from backend import config
    from backend.logger import log_ai_response, log_error, logger
    from backend.schemas import SCHEMA_REGISTRY, get_schema

VALID_DOCUMENT_TYPES = set(SCHEMA_REGISTRY) | {"form", "other"}

HEURISTIC_CLASSIFIERS = {
    "invoice": [
        (r"\btax invoice\b", 3.5, "tax invoice"),
        (r"\binvoice\b", 2.5, "invoice"),
        (r"\binvoice\s*(no|number)\b", 2.5, "invoice number"),
        (r"\bgstin\b", 2.0, "gstin"),
        (r"\bbill to\b", 1.5, "bill to"),
        (r"\btotal amount\b", 1.0, "total amount"),
    ],
    "purchase_order": [
        (r"\bpurchase order\b", 4.0, "purchase order"),
        (r"\bpo\s*(no|number)\b", 3.0, "po number"),
        (r"\bdelivery date\b", 1.5, "delivery date"),
        (r"\bvendor information\b", 1.5, "vendor information"),
        (r"\bnet\s*30\b", 1.0, "net 30"),
    ],
    "retail_receipt": [
        (r"\breceipt\b", 3.5, "receipt"),
        (r"\breceipt\s*(no|number)\b", 3.0, "receipt number"),
        (r"\bcashier\b", 1.5, "cashier"),
        (r"\bpayment method\b", 1.5, "payment method"),
        (r"\bwalk-?in\b", 1.2, "walk-in"),
    ],
    "bill_of_lading": [
        (r"\bbill of lading\b", 4.0, "bill of lading"),
        (r"\bb\/l\s*(no|number)\b", 3.0, "b/l number"),
        (r"\bshipper\b", 1.8, "shipper"),
        (r"\bconsignee\b", 1.8, "consignee"),
        (r"\bport of loading\b", 1.5, "port of loading"),
        (r"\bport of discharge\b", 1.5, "port of discharge"),
        (r"\bvessel\b", 1.2, "vessel"),
    ],
    "resume": [
        (r"\bresume\b", 3.0, "resume"),
        (r"\bcurriculum vitae\b", 3.5, "curriculum vitae"),
        (r"\bwork experience\b", 1.5, "work experience"),
        (r"\beducation\b", 1.0, "education"),
        (r"\bskills\b", 1.0, "skills"),
    ],
    "contract": [
        (r"\bagreement\b", 2.5, "agreement"),
        (r"\bcontract\b", 2.5, "contract"),
        (r"\bparty of the\b", 1.5, "party of the"),
        (r"\bterms and conditions\b", 1.5, "terms and conditions"),
        (r"\beffective date\b", 1.0, "effective date"),
    ],
    "prescription": [
        (r"\bprescription\b", 3.0, "prescription"),
        (r"\brx\b", 2.0, "rx"),
        (r"\bdoctor\b", 1.2, "doctor"),
        (r"\bdosage\b", 1.2, "dosage"),
        (r"\btablet\b", 1.0, "tablet"),
        (r"\bmg\b", 0.8, "mg"),
    ],
    "lab_report": [
        (r"\bpathology\b", 2.5, "pathology"),
        (r"\bdiagnostics?\b", 2.5, "diagnostics"),
        (r"\breference range\b", 2.0, "reference range"),
        (r"\bsample collected\b", 1.8, "sample collected"),
        (r"\bhemoglobin\b", 1.5, "hemoglobin"),
        (r"\bwbc count\b", 1.5, "wbc count"),
        (r"\bcbc\b", 2.5, "cbc"),
        (r"\blab report\b", 3.0, "lab report"),
    ],
    "certificate": [
        (r"\bcertificate\b", 2.0, "certificate"),
        (r"\bcertify that\b", 2.5, "certify that"),
        (r"\bregistration\s*(no|number)\b", 1.5, "registration number"),
        (r"\bissued on\b", 1.0, "issued on"),
    ],
    "bank_statement": [
        (r"\bbank statement\b", 3.0, "bank statement"),
        (r"\baccount statement\b", 3.0, "account statement"),
        (r"\bdebit\b", 1.2, "debit"),
        (r"\bcredit\b", 1.2, "credit"),
        (r"\bclosing balance\b", 1.5, "closing balance"),
        (r"\bwithdrawal\b", 0.8, "withdrawal"),
    ],
    "marksheet": [
        (r"\bmarksheet\b", 3.0, "marksheet"),
        (r"\bmark sheet\b", 3.0, "mark sheet"),
        (r"\broll number\b", 1.2, "roll number"),
        (r"\bgrade\b", 1.0, "grade"),
        (r"\btotal marks\b", 1.5, "total marks"),
        (r"\bresult\b", 0.8, "result"),
    ],
    "ration_card": [
        (r"\bration card\b", 4.0, "ration card"),
        (r"\bfair price shop\b", 1.5, "fair price shop"),
        (r"\bfamily members?\b", 1.2, "family members"),
    ],
    "utility_bill": [
        (r"\belectricity bill\b", 3.0, "electricity bill"),
        (r"\bwater bill\b", 3.0, "water bill"),
        (r"\bgas bill\b", 3.0, "gas bill"),
        (r"\bconsumer number\b", 1.5, "consumer number"),
        (r"\bmeter\b", 1.2, "meter"),
        (r"\bdue date\b", 1.0, "due date"),
    ],
    "aadhar_card": [
        (r"\baadhaar\b", 4.0, "aadhaar"),
        (r"\buidai\b", 3.0, "uidai"),
        (r"\bgovernment of india\b", 1.5, "government of india"),
        (r"\b\d{4}\s?\d{4}\s?\d{4}\b", 2.5, "12-digit uid"),
    ],
    "pan_card": [
        (r"\bpermanent account number\b", 3.5, "permanent account number"),
        (r"\bincome tax department\b", 3.0, "income tax department"),
        (r"\b[a-z]{5}\d{4}[a-z]\b", 2.5, "pan number"),
    ],
    "driving_licence": [
        (r"\bdriving licence\b", 4.0, "driving licence"),
        (r"\bdriving license\b", 4.0, "driving license"),
        (r"\bdl\s*(no|number)\b", 2.0, "dl number"),
        (r"\brto\b", 1.0, "rto"),
        (r"\bmcwg\b|\blmv\b|\bhmv\b", 1.2, "vehicle class"),
    ],
    "passport": [
        (r"\bpassport\b", 3.0, "passport"),
        (r"\brepublic of india\b", 3.0, "republic of india"),
        (r"\bnationality\b", 1.2, "nationality"),
        (r"\b[a-pr-wy][0-9]{7}\b", 2.0, "passport number"),
        (r"\bp<ind\b", 3.0, "mrz"),
    ],
    "cheque": [
        (r"\ba\/c payee\b", 2.0, "a/c payee"),
        (r"\bpay\b", 1.2, "pay"),
        (r"\bbearer\b", 1.2, "bearer"),
        (r"\bmicr\b", 2.5, "micr"),
        (r"\bifsc\b", 1.5, "ifsc"),
    ],
    "form_16": [
        (r"\bform\s*16\b", 4.0, "form 16"),
        (r"\btds\b", 2.0, "tds"),
        (r"\bassessment year\b", 1.5, "assessment year"),
        (r"\btan\b", 1.2, "tan"),
    ],
    "payslip": [
        (r"\bsalary slip\b", 4.0, "salary slip"),
        (r"\bpayslip\b", 4.0, "payslip"),
        (r"\bearnings\b", 1.5, "earnings"),
        (r"\bdeductions\b", 1.5, "deductions"),
        (r"\bnet pay\b", 2.0, "net pay"),
        (r"\bpay period\b", 1.2, "pay period"),
    ],
    "income_tax_acknowledgment": [
        (r"\bitr-?\d+\s+acknowledg", 4.0, "itr acknowledgment"),
        (r"\backnowledgment number\b", 3.0, "acknowledgment number"),
        (r"\bdate of filing\b", 2.0, "date of filing"),
        (r"\be-?filing\b", 1.5, "e-filing"),
        (r"\brefund\/demand\b", 1.5, "refund/demand"),
    ],
    "insurance_policy": [
        (r"\binsurance\b", 2.0, "insurance"),
        (r"\bpolicy number\b", 2.5, "policy number"),
        (r"\bsum assured\b", 1.5, "sum assured"),
        (r"\bpremium\b", 1.2, "premium"),
        (r"\bnominee\b", 1.2, "nominee"),
    ],
    "gst_certificate": [
        (r"\bgoods and services tax\b", 3.0, "goods and services tax"),
        (r"\bregistration certificate\b", 2.5, "registration certificate"),
        (r"\bgstin\b", 2.0, "gstin"),
        (r"\b\d{2}[a-z]{5}\d{4}[a-z][a-z0-9]z[a-z0-9]\b", 3.0, "gst number"),
    ],
    "birth_certificate": [
        (r"\bbirth certificate\b", 4.0, "birth certificate"),
        (r"\bdate of birth\b", 1.5, "date of birth"),
        (r"\bfather\b", 0.8, "father"),
        (r"\bmother\b", 0.8, "mother"),
        (r"\bplace of birth\b", 1.2, "place of birth"),
    ],
    "death_certificate": [
        (r"\bdeath certificate\b", 4.0, "death certificate"),
        (r"\bdate of death\b", 1.5, "date of death"),
        (r"\bdeceased\b", 1.2, "deceased"),
        (r"\bcause of death\b", 1.2, "cause of death"),
    ],
    "balance_sheet": [
        (r"\bbalance sheet\b", 4.0, "balance sheet"),
        (r"\bas at\b", 1.5, "as at"),
        (r"\bassets\b", 1.2, "assets"),
        (r"\bequity and liabilities\b", 2.5, "equity and liabilities"),
        (r"\bcurrent assets\b", 1.5, "current assets"),
        (r"\bnon-current assets\b", 1.5, "non-current assets"),
    ],
    "land_record": [
        (r"\b7\/12\b", 3.5, "7/12"),
        (r"\bkhata\b", 1.5, "khata"),
        (r"\bkhasra\b", 1.5, "khasra"),
        (r"\bjamabandi\b", 2.0, "jamabandi"),
        (r"\bgut number\b", 1.5, "gut number"),
        (r"\bsurvey number\b", 1.5, "survey number"),
    ],
    "nrega_card": [
        (r"\bmgnrega\b", 3.0, "mgnrega"),
        (r"\bnrega\b", 3.0, "nrega"),
        (r"\bjob card\b", 2.0, "job card"),
        (r"\bgram panchayat\b", 1.5, "gram panchayat"),
    ],
    "form": [
        (r"\bapplication form\b", 3.0, "application form"),
        (r"\bapplicant\b", 1.0, "applicant"),
        (r"\bsignature\b", 0.8, "signature"),
        (r"\bdeclaration\b", 0.8, "declaration"),
    ],
}


def _safe_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_numeric_or_none(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            cleaned = re.sub(r"[^\d.\-]", "", cleaned)
            if cleaned in {"", "-", ".", "-."}:
                return None
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return None


class AIAgent:
    """
    Manages interaction with Mistral AI for document intelligence.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.MISTRAL_API_KEY

        if not self.api_key:
            raise ValueError("Mistral API key not provided")

        self.model = config.MISTRAL_MODEL
        self.temperature = config.MISTRAL_TEMPERATURE
        self.max_tokens = config.MISTRAL_MAX_TOKENS
        self.timeout_ms = max(1000, config.MISTRAL_TIMEOUT_MS)
        self.max_retries = max(1, config.MISTRAL_MAX_RETRIES)
        self.retry_backoff_ms = max(0, config.MISTRAL_RETRY_BACKOFF_MS)
        self.client = Mistral(api_key=self.api_key, timeout_ms=self.timeout_ms)

        logger.info(
            f"AIAgent initialized with model={self.model}, timeout_ms={self.timeout_ms}, "
            f"retries={self.max_retries}"
        )

    def classify_document(self, text_sample: str, max_length: int = 2000) -> Dict[str, Any]:
        """
        Classify document type using Mistral AI with a deterministic heuristic fallback.
        """
        sample = (text_sample or "")[:max_length]
        heuristic_result = self._heuristic_classify_document(sample)

        if not sample.strip():
            return self._build_classification_result(
                document_type="other",
                confidence=0.0,
                reasoning="No readable text was available for classification.",
                alternative_type=None,
                classification_source="none",
                classification_status="unavailable",
                heuristic_result=heuristic_result,
            )

        prompt = f"""Analyze this document excerpt and classify it into exactly one type.
The excerpt may include English, Hindi, or Gujarati text.

Allowed document types:
{", ".join(sorted(VALID_DOCUMENT_TYPES))}

Rules:
- Pick the most specific type.
- Use "form" only for generic forms or applications that do not fit a better type.
- Use "other" only when no type fits.
- Return JSON only.

Document excerpt:
{sample}

Return exactly:
{{
  "document_type": "allowed_type",
  "confidence": 0.95,
  "reasoning": "short reason",
  "alternative_type": "allowed_type_or_null"
}}"""

        try:
            logger.info("Calling Mistral AI for document classification")
            response_text = self._request_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
                operation_name="document classification",
            )
            result = self._parse_json_response(response_text)
            if not result or "document_type" not in result:
                raise ValueError("Invalid classification response format")
            normalized = self._normalize_classification_result(result, heuristic_result, sample)
            logger.info(
                "Document classified as: {} (confidence={}, source={})",
                normalized["document_type"],
                normalized.get("confidence", 0.0),
                normalized["classification_source"],
            )
            return normalized
        except Exception as exc:
            log_error("DocumentClassification", str(exc))
            fallback = heuristic_result or self._build_classification_result(
                document_type="other",
                confidence=0.15,
                reasoning="The AI classifier was unavailable and no strong fallback match was found.",
                alternative_type=None,
                classification_source="heuristic",
                classification_status="fallback",
            )
            fallback["classification_status"] = "fallback"
            fallback["classification_source"] = "heuristic"
            fallback["fallback_used"] = True
            fallback["llm_error"] = str(exc)
            if fallback["document_type"] == "other":
                fallback["reasoning"] = (
                    "The AI classifier was unavailable, so the document type could not be "
                    "confirmed automatically."
                )
            return fallback

    def extract_structured_data(self, full_text: str, document_type: str) -> Dict[str, Any]:
        """
        Extract structured data based on document type schema.
        Long documents use chunked extraction for better coverage.
        """
        try:
            schema = get_schema(document_type)
            if not schema:
                logger.warning(f"No schema found for document type: {document_type}")
                return {}

            schema_dict = schema.get_schema()
            instructions = schema.get_prompt_instructions()

            chunk_size = 4000
            overlap = 500

            if len(full_text) > chunk_size * 2:
                logger.info(
                    f"Long document ({len(full_text)} chars) using chunked extraction "
                    f"(chunk_size={chunk_size}, overlap={overlap})"
                )
                return self._extract_chunked(
                    full_text,
                    document_type,
                    schema_dict,
                    instructions,
                    chunk_size=chunk_size,
                    overlap=overlap,
                )

            prompt = self._create_extraction_prompt(
                full_text, document_type, schema_dict, instructions
            )
            logger.info(f"Calling Mistral AI for {document_type} data extraction")
            response_text = self._request_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                operation_name=f"{document_type} structured extraction",
            )

            extracted_data = self._parse_json_response(response_text)
            if not extracted_data:
                raise ValueError("Failed to parse extraction response")

            extracted_data = self._post_process_extracted_data(
                extracted_data,
                document_type,
                full_text,
            )

            is_valid, issues = schema.validate_extracted_data(extracted_data)
            if not is_valid:
                logger.warning(f"Validation issues: {issues}")

            logger.info(f"Successfully extracted {len(extracted_data)} top-level fields")
            return extracted_data
        except Exception as exc:
            log_error("StructuredExtraction", str(exc), f"Document type: {document_type}")
            return {}

    def repair_weak_fields(
        self,
        *,
        full_text: str,
        document_type: str,
        structured_data: Dict[str, Any],
        weak_fields: list[dict[str, Any]],
        validation_summary: Optional[Dict[str, Any]] = None,
        max_text_chars: int = 7000,
    ) -> Dict[str, Any]:
        """
        Ask the LLM to repair only explicitly weak fields.
        Returns structured JSON with per-field actions.
        """
        schema = get_schema(document_type)
        if not schema:
            raise ValueError(f"No schema found for recovery document type: {document_type}")

        if not weak_fields:
            return {"changes": [], "summary": "No weak fields were supplied for recovery."}

        weak_field_payload = []
        for item in weak_fields:
            weak_field_payload.append(
                {
                    "field_path": item.get("field_path"),
                    "reason_code": item.get("reason_code"),
                    "current_value": item.get("original_value"),
                    "validation_message": item.get("validation_message"),
                    "is_critical": bool(item.get("is_critical")),
                }
            )

        prompt = f"""You are repairing weak extracted fields for a {document_type} document.

You must follow these rules strictly:
1. Repair only the listed weak fields.
2. Do not change fields that are not listed.
3. If evidence is insufficient, return action="no_change".
4. Use OCR/document text as the primary evidence source.
5. Return valid JSON only.

Document type:
{document_type}

Validation summary:
{json.dumps(validation_summary or {}, ensure_ascii=False, indent=2)}

Weak fields to review:
{json.dumps(weak_field_payload, ensure_ascii=False, indent=2)}

Current structured data:
{json.dumps(structured_data, ensure_ascii=False, indent=2)}

OCR/document text excerpt:
{(full_text or '')[:max_text_chars]}

Return exactly this JSON shape:
{{
  "changes": [
    {{
      "field_path": "dot.path",
      "action": "update_or_no_change",
      "proposed_value": "new value or null",
      "evidence_text": "short text copied from OCR/document evidence",
      "reason": "short explanation",
      "confidence": 0.0
    }}
  ],
  "summary": "short overall summary"
}}"""

        response_text = self._request_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=min(self.max_tokens, 1200),
            operation_name=f"{document_type} weak-field recovery",
        )
        result = self._parse_json_response(response_text)
        if not isinstance(result, dict):
            raise ValueError("Weak-field recovery returned invalid JSON")

        changes = result.get("changes")
        if not isinstance(changes, list):
            raise ValueError("Weak-field recovery response missing 'changes' list")

        normalized_changes = []
        allowed_paths = {str(item.get("field_path")) for item in weak_field_payload}
        for change in changes:
            if not isinstance(change, dict):
                continue
            field_path = str(change.get("field_path") or "").strip()
            if not field_path or field_path not in allowed_paths:
                continue
            action = str(change.get("action") or "no_change").strip().lower()
            if action not in {"update", "no_change"}:
                action = "no_change"
            try:
                confidence = float(change.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            normalized_changes.append(
                {
                    "field_path": field_path,
                    "action": action,
                    "proposed_value": change.get("proposed_value"),
                    "evidence_text": str(change.get("evidence_text") or "").strip() or None,
                    "reason": str(change.get("reason") or "").strip() or None,
                    "confidence": round(max(0.0, min(1.0, confidence)), 2),
                }
            )

        return {
            "changes": normalized_changes,
            "summary": str(result.get("summary") or "").strip(),
        }

    def triage_review_fields(
        self,
        *,
        full_text: str,
        document_type: str,
        structured_data: Dict[str, Any],
        candidate_fields: list[dict[str, Any]],
        validation_summary: Optional[Dict[str, Any]] = None,
        validation_errors: Optional[list[dict[str, Any]]] = None,
        max_text_chars: int = 7000,
    ) -> Dict[str, Any]:
        """
        Ask the LLM to convert raw validation noise into a compact, human-friendly
        set of review fields. This does not auto-apply any changes; it only
        decides what still needs human verification and what value should be
        suggested, if the document evidence clearly supports it.
        """
        if not candidate_fields:
            return {"review_fields": [], "summary": "No candidate review fields were supplied."}

        allowed_reason_codes = [
            "missing_critical_field",
            "unsupported_ai_change",
            "math_consistency_failed",
            "amount_mismatch",
            "date_parse_uncertain",
            "low_ocr_support",
            "classification_ambiguous",
            "validation_rule_failed",
            "conflicting_candidate_values",
            "schema_coverage_low",
        ]

        prompt = f"""You are reviewing extraction validation output for a {document_type} document.

Your job is to produce the FINAL minimal set of fields that still need human review.

Rules:
1. Start from the candidate review fields and validation issues below.
2. Remove duplicate or near-duplicate issues.
3. If many indexed child fields are really one repeated sequence problem, consolidate them into a parent field path such as "transactions".
4. Keep only issues that truly still need human verification.
5. If the document text clearly supports a better value for a field, include it as proposed_value.
6. If evidence is insufficient, proposed_value must be null.
7. Do not invent new problems that are not grounded in the candidate fields or validation errors.
8. Return valid JSON only.

Allowed reason codes:
{json.dumps(allowed_reason_codes, ensure_ascii=False)}

Validation summary:
{json.dumps(validation_summary or {}, ensure_ascii=False, indent=2)}

Validation issues:
{json.dumps(validation_errors or [], ensure_ascii=False, indent=2)}

Candidate review fields:
{json.dumps(candidate_fields, ensure_ascii=False, indent=2)}

Current structured data:
{json.dumps(structured_data, ensure_ascii=False, indent=2)}

OCR/document text excerpt:
{(full_text or '')[:max_text_chars]}

Return exactly this JSON shape:
{{
  "review_fields": [
    {{
      "field_path": "dot.path.or.parent.path",
      "reason_code": "one of the allowed reason codes",
      "validation_message": "short human-readable reason",
      "evidence_text": "short text copied from the document evidence",
      "proposed_value": "value or null",
      "confidence": 0.0
    }}
  ],
  "summary": "short overall summary"
}}"""

        response_text = self._request_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=min(self.max_tokens, 1400),
            operation_name=f"{document_type} review triage",
        )
        result = self._parse_json_response(response_text)
        if not isinstance(result, dict):
            raise ValueError("Review triage returned invalid JSON")

        review_fields = result.get("review_fields")
        if not isinstance(review_fields, list):
            raise ValueError("Review triage response missing 'review_fields' list")

        normalized_fields = []
        for item in review_fields:
            if not isinstance(item, dict):
                continue
            field_path = str(item.get("field_path") or "").strip()
            reason_code = str(item.get("reason_code") or "").strip()
            if not field_path or reason_code not in allowed_reason_codes:
                continue
            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            normalized_fields.append(
                {
                    "field_path": field_path,
                    "reason_code": reason_code,
                    "validation_message": str(item.get("validation_message") or "").strip() or None,
                    "evidence_text": str(item.get("evidence_text") or "").strip() or None,
                    "proposed_value": item.get("proposed_value"),
                    "confidence": round(max(0.0, min(1.0, confidence)), 2),
                }
            )

        return {
            "review_fields": normalized_fields,
            "summary": str(result.get("summary") or "").strip(),
        }

    def _extract_chunked(
        self,
        full_text: str,
        document_type: str,
        schema_dict: dict,
        instructions: str,
        chunk_size: int = 4000,
        overlap: int = 500,
    ) -> Dict[str, Any]:
        """
        Extract structured data from a long document by chunking and merging.
        """
        chunks = []
        start = 0
        while start < len(full_text):
            end = min(start + chunk_size, len(full_text))
            chunks.append(full_text[start:end])
            if end == len(full_text):
                break
            start = end - overlap

        logger.info(f"Chunked extraction: {len(chunks)} chunks for {document_type}")

        merged: Dict[str, Any] = {}
        for index, chunk in enumerate(chunks, start=1):
            logger.info(f"Extracting chunk {index}/{len(chunks)} ({len(chunk)} chars)")
            try:
                prompt = self._create_extraction_prompt(
                    chunk, document_type, schema_dict, instructions
                )
                response_text = self._request_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    operation_name=f"{document_type} chunk {index}",
                )
                chunk_data = self._parse_json_response(response_text)
                if chunk_data:
                    merged = self._merge_extraction_results(merged, chunk_data)
            except Exception as exc:
                logger.warning(f"Chunk {index} extraction failed: {exc}")
                continue

        merged["_chunked_extraction"] = True
        merged["_chunks_processed"] = len(chunks)
        return merged

    def _merge_extraction_results(self, base: dict, update: dict) -> dict:
        """
        Merge two extraction dicts.
        Later values fill empty earlier values. Lists accumulate unique values.
        """
        if not base:
            return dict(update)

        result = dict(base)
        for key, value in update.items():
            if key not in result or result[key] is None or result[key] == "":
                result[key] = value
            elif isinstance(result[key], list) and isinstance(value, list):
                existing = {str(item) for item in result[key]}
                for item in value:
                    if str(item) not in existing:
                        result[key].append(item)
            elif isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_extraction_results(result[key], value)
        return result

    def _create_extraction_prompt(
        self, text: str, doc_type: str, schema: dict, instructions: str
    ) -> str:
        schema_json = json.dumps(schema, indent=2)
        return f"""{instructions}

SCHEMA TO EXTRACT:
{schema_json}

DOCUMENT TYPE:
{doc_type}

DOCUMENT TEXT:
{text}

CRITICAL INSTRUCTIONS:
1. Respond only with valid JSON matching the schema structure.
2. Use null for any missing fields.
3. Keep dates in the requested format.
4. Extract all relevant information.
5. Do not add explanations outside the JSON.

Extract the data now:"""

    def _request_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        operation_name: str,
    ) -> str:
        """
        Call Mistral with bounded retries so transient outages fail fast.
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.chat.complete(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                response_text = response.choices[0].message.content
                log_ai_response(
                    len(messages[-1]["content"]),
                    len(response_text),
                    self.model,
                )
                return response_text
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                sleep_seconds = (self.retry_backoff_ms * attempt) / 1000.0
                logger.warning(
                    f"Mistral {operation_name} failed on attempt {attempt}/{self.max_retries}: {exc}. "
                    f"Retrying in {sleep_seconds:.2f}s."
                )
                time.sleep(sleep_seconds)

        raise RuntimeError(
            f"Mistral {operation_name} failed after {self.max_retries} attempt(s): {last_error}"
        )

    def _heuristic_classify_document(self, text_sample: str) -> Dict[str, Any]:
        """
        Rule-based fallback classifier for when the LLM is unavailable or uncertain.
        """
        normalized = re.sub(r"\s+", " ", (text_sample or "").lower())
        if not normalized.strip():
            return self._build_classification_result(
                document_type="other",
                confidence=0.0,
                reasoning="No readable text was available for heuristic classification.",
                alternative_type=None,
                classification_source="heuristic",
                classification_status="fallback",
            )

        scores: Dict[str, float] = {}
        matches: Dict[str, list[str]] = {}

        for document_type, rules in HEURISTIC_CLASSIFIERS.items():
            for pattern, weight, label in rules:
                if re.search(pattern, normalized, flags=re.IGNORECASE):
                    scores[document_type] = scores.get(document_type, 0.0) + weight
                    matches.setdefault(document_type, []).append(label)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if not ranked:
            return self._build_classification_result(
                document_type="other",
                confidence=0.15,
                reasoning="No strong document keywords were found in the text sample.",
                alternative_type=None,
                classification_source="heuristic",
                classification_status="fallback",
            )

        best_type, best_score = ranked[0]
        alternative_type = ranked[1][0] if len(ranked) > 1 and ranked[1][1] >= 2.0 else None
        confidence = min(0.35 + (best_score / 10.0), 0.82)
        matched = ", ".join(matches.get(best_type, [])[:4])
        reasoning = (
            f"Heuristic match based on keywords: {matched}."
            if matched
            else "Heuristic fallback selected the closest document type."
        )
        result = self._build_classification_result(
            document_type=best_type,
            confidence=round(confidence, 2),
            reasoning=reasoning,
            alternative_type=alternative_type,
            classification_source="heuristic",
            classification_status="fallback",
        )
        result["matched_keywords"] = matches.get(best_type, [])
        return result

    def _normalize_classification_result(
        self,
        result: Dict[str, Any],
        heuristic_result: Optional[Dict[str, Any]] = None,
        text_sample: str = "",
    ) -> Dict[str, Any]:
        """
        Validate and normalize the LLM classification payload.
        """
        document_type = str(result.get("document_type", "other")).strip().lower()
        if document_type not in VALID_DOCUMENT_TYPES:
            raise ValueError(f"Unsupported document type returned by LLM: {document_type}")

        alternative_type = result.get("alternative_type")
        if alternative_type is not None:
            alternative_type = str(alternative_type).strip().lower()
            if alternative_type not in VALID_DOCUMENT_TYPES:
                alternative_type = None

        try:
            confidence = float(result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = round(max(0.0, min(1.0, confidence)), 2)

        normalized = self._build_classification_result(
            document_type=document_type,
            confidence=confidence,
            reasoning=str(result.get("reasoning", "")).strip()
            or "Classification returned by the LLM.",
            alternative_type=alternative_type,
            classification_source="llm",
            classification_status="confirmed",
            heuristic_result=heuristic_result,
        )

        heuristic_type = (heuristic_result or {}).get("document_type")
        heuristic_confidence = (heuristic_result or {}).get("confidence", 0.0)
        if self._should_downgrade_low_signal_gst_classification(
            document_type=document_type,
            confidence=confidence,
            text_sample=text_sample,
            heuristic_type=heuristic_type,
            heuristic_confidence=heuristic_confidence,
        ):
            downgraded = self._build_classification_result(
                document_type="other",
                confidence=max(0.15, min(0.35, heuristic_confidence or 0.15)),
                reasoning=(
                    "The low-confidence GST-certificate classification was downgraded because "
                    "the OCR excerpt does not contain strong GST-certificate evidence."
                ),
                alternative_type=document_type,
                classification_source="heuristic",
                classification_status="fallback",
                heuristic_result=heuristic_result,
            )
            downgraded["llm_document_type"] = document_type
            downgraded["classification_warning"] = (
                "Low-confidence GST-certificate classification was downgraded to 'other' "
                "because the excerpt lacks clear GST markers."
            )
            return downgraded

        if (
            heuristic_type
            and heuristic_type != document_type
            and heuristic_confidence >= 0.65
            and confidence < 0.65
        ):
            normalized["classification_warning"] = (
                f"LLM result '{document_type}' disagrees with heuristic fallback "
                f"'{heuristic_type}'."
            )

        return normalized

    def _build_classification_result(
        self,
        *,
        document_type: str,
        confidence: float,
        reasoning: str,
        alternative_type: Optional[str],
        classification_source: str,
        classification_status: str,
        heuristic_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = {
            "document_type": document_type,
            "confidence": round(max(0.0, min(1.0, confidence)), 2),
            "reasoning": reasoning,
            "alternative_type": alternative_type,
            "classification_source": classification_source,
            "classification_status": classification_status,
            "fallback_used": classification_source != "llm",
        }
        if heuristic_result:
            result["heuristic_document_type"] = heuristic_result.get("document_type")
            result["heuristic_confidence"] = heuristic_result.get("confidence")
        return result

    def _post_process_extracted_data(
        self,
        extracted_data: Dict[str, Any],
        document_type: str,
        full_text: str,
    ) -> Dict[str, Any]:
        if not isinstance(extracted_data, dict):
            return extracted_data

        normalized_data = deepcopy(extracted_data)

        if document_type == "payslip":
            normalized_data = self._normalize_payslip_extraction(normalized_data)
        elif document_type == "bank_statement":
            normalized_data = self._normalize_bank_statement_extraction(normalized_data)
        elif document_type == "balance_sheet":
            normalized_data = self._normalize_balance_sheet_extraction(normalized_data)
        elif document_type == "marksheet":
            normalized_data = self._normalize_marksheet_extraction(normalized_data)
        elif document_type == "utility_bill":
            normalized_data = self._normalize_utility_bill_extraction(normalized_data)

        if document_type == "payslip" and self._payslip_amounts_look_inconsistent(normalized_data):
            repaired = self._repair_payslip_extraction(full_text, normalized_data)
            if repaired:
                return repaired

        if document_type == "bank_statement" and self._bank_statement_amounts_look_inconsistent(normalized_data):
            repaired = self._repair_bank_statement_extraction(full_text, normalized_data)
            if repaired:
                return repaired

        if document_type == "balance_sheet" and self._balance_sheet_amounts_look_inconsistent(normalized_data):
            repaired = self._repair_balance_sheet_extraction(full_text, normalized_data)
            if repaired:
                return repaired

        return normalized_data

    def _normalize_payslip_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("total_earnings", "total_deductions", "net_pay"):
            extracted_data[key] = self._coerce_numeric_value(extracted_data.get(key))

        extracted_data["earnings"] = self._clean_named_amount_rows(
            extracted_data.get("earnings"),
            label_keys=("component", "name", "label"),
        )
        extracted_data["deductions"] = self._clean_named_amount_rows(
            extracted_data.get("deductions"),
            label_keys=("component", "name", "label"),
        )

        pay_period = extracted_data.get("pay_period")
        if isinstance(pay_period, dict) and not extracted_data.get("payslip_month"):
            anchor_date = pay_period.get("to_date") or pay_period.get("from_date")
            extracted_data["payslip_month"] = self._derive_month_label(anchor_date)

        return extracted_data

    def _normalize_balance_sheet_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        assets = extracted_data.get("assets")
        if isinstance(assets, dict):
            for key in ("non_current_assets", "current_assets"):
                assets[key] = self._clean_named_amount_rows(assets.get(key), label_keys=("name", "label"))
            assets["total_assets"] = self._coerce_numeric_value(assets.get("total_assets"))

        liabilities = extracted_data.get("equity_and_liabilities")
        if isinstance(liabilities, dict):
            for key in ("equity", "non_current_liabilities", "current_liabilities"):
                liabilities[key] = self._clean_named_amount_rows(
                    liabilities.get(key),
                    label_keys=("name", "label"),
                )
            liabilities["total_equity_and_liabilities"] = self._coerce_numeric_value(
                liabilities.get("total_equity_and_liabilities")
            )

        return extracted_data

    def _normalize_bank_statement_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("opening_balance", "closing_balance", "total_debits", "total_credits"):
            if key in extracted_data:
                extracted_data[key] = self._coerce_numeric_value(extracted_data.get(key))

        statement_period = extracted_data.get("statement_period")
        if isinstance(statement_period, dict):
            for key in ("from_date", "to_date"):
                value = statement_period.get(key)
                if isinstance(value, str):
                    statement_period[key] = value.strip() or None

        extracted_data["transactions"] = self._clean_transaction_rows(extracted_data.get("transactions"))
        return extracted_data

    def _normalize_marksheet_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("total_marks", "obtained_marks", "percentage"):
            if key in extracted_data:
                extracted_data[key] = self._coerce_numeric_value(extracted_data.get(key))

        subjects = extracted_data.get("subjects")
        if not isinstance(subjects, list):
            extracted_data["subjects"] = []
            return extracted_data

        cleaned_subjects: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in subjects:
            if not isinstance(row, dict):
                continue

            normalized_row = dict(row)
            subject_name = str(
                normalized_row.get("subject_name")
                or normalized_row.get("subject")
                or normalized_row.get("name")
                or ""
            ).strip()
            if not subject_name:
                continue

            for key in ("marks_obtained", "obtained_marks", "max_marks", "total_marks", "grade_points"):
                if key in normalized_row:
                    normalized_row[key] = self._coerce_numeric_value(normalized_row.get(key))

            dedupe_key = (
                subject_name.lower(),
                str(normalized_row.get("marks_obtained") or normalized_row.get("obtained_marks") or ""),
                str(normalized_row.get("grade") or ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned_subjects.append(normalized_row)

        extracted_data["subjects"] = cleaned_subjects
        return extracted_data

    def _normalize_utility_bill_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("total_amount", "amount_due", "current_charges", "previous_balance"):
            if key in extracted_data:
                extracted_data[key] = self._coerce_numeric_value(extracted_data.get(key))

        for key in ("consumer_number", "account_number", "meter_number"):
            if key in extracted_data and isinstance(extracted_data.get(key), str):
                extracted_data[key] = extracted_data[key].strip()

        return extracted_data

    def _clean_named_amount_rows(
        self,
        rows: Any,
        *,
        label_keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []

        cleaned: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue

            normalized_row = dict(row)
            label_value = next(
                (str(normalized_row.get(key) or "").strip() for key in label_keys if str(normalized_row.get(key) or "").strip()),
                "",
            )
            amount_value = self._coerce_numeric_value(normalized_row.get("amount"))
            normalized_row["amount"] = amount_value

            if not label_value and amount_value in (None, 0, 0.0):
                continue

            dedupe_key = (label_value.lower(), str(amount_value))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            cleaned.append(normalized_row)
        return cleaned

    def _clean_transaction_rows(self, rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []

        cleaned: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue

            normalized_row = dict(row)
            description = str(
                normalized_row.get("description")
                or normalized_row.get("narration")
                or normalized_row.get("details")
                or ""
            ).strip()
            txn_date = str(normalized_row.get("date") or "").strip()

            for key in ("debit", "credit", "amount", "balance"):
                if key in normalized_row:
                    normalized_row[key] = self._coerce_numeric_value(normalized_row.get(key))

            if not description and not txn_date:
                continue

            dedupe_key = (
                txn_date,
                description.lower(),
                str(normalized_row.get("debit") or ""),
                str(normalized_row.get("credit") or normalized_row.get("amount") or ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned.append(normalized_row)

        return cleaned

    def _coerce_numeric_value(self, value: Any) -> Any:
        if value in (None, ""):
            return value
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            cleaned = re.sub(r"[^\d.\-]", "", cleaned)
            if cleaned in {"", "-", ".", "-."}:
                return value
            try:
                return float(cleaned)
            except ValueError:
                return value
        return value

    def _derive_month_label(self, iso_date: Any) -> Optional[str]:
        if not iso_date:
            return None
        try:
            parsed = datetime.fromisoformat(str(iso_date))
        except ValueError:
            return None
        return parsed.strftime("%B %Y")

    def _repair_payslip_extraction(
        self,
        full_text: str,
        extracted_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        schema = get_schema("payslip")
        if not schema:
            return None

        prompt = f"""You are correcting an extracted PAYSLIP JSON that has internal arithmetic inconsistencies.

You must return the FULL payslip JSON using the exact schema below.
Use the OCR text as the source of truth.

Critical rules:
1. Do not duplicate digits from neighboring OCR columns.
2. Do not invent extra zeros in salary components.
3. February 2024 is a leap-year month, so 2024-02-29 is valid.
4. The final JSON must satisfy:
   - sum(earnings[].amount) = total_earnings
   - sum(deductions[].amount) = total_deductions
   - total_earnings - total_deductions = net_pay
5. Keep identity fields unless the OCR text clearly shows a different value.
6. If totals are printed explicitly, prefer those totals and align the component rows to them.
7. Return valid JSON only.

Schema:
{json.dumps(schema.get_schema(), ensure_ascii=False, indent=2)}

Current extracted JSON:
{json.dumps(extracted_data, ensure_ascii=False, indent=2)}

OCR/document text:
{(full_text or '')[:7000]}
"""
        try:
            response_text = self._request_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=min(self.max_tokens, 1400),
                operation_name="payslip arithmetic repair",
            )
            repaired = self._parse_json_response(response_text)
            if isinstance(repaired, dict) and not self._payslip_amounts_look_inconsistent(repaired):
                return repaired
        except Exception as exc:
            logger.warning(f"Payslip post-processing repair failed: {exc}")
        return None

    def _repair_bank_statement_extraction(
        self,
        full_text: str,
        extracted_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        schema = get_schema("bank_statement")
        if not schema:
            return None

        prompt = f"""You are correcting an extracted BANK STATEMENT JSON that has arithmetic or column-alignment inconsistencies.

You must return the FULL bank-statement JSON using the exact schema below.
Use the OCR text as the source of truth.

Critical rules:
1. Do not shift numbers between debit, credit, and balance columns.
2. Do not prepend or append stray digits from neighboring OCR tokens.
3. Preserve all visible transactions and keep their order.
4. Preserve account identity fields unless the OCR text clearly shows a different value.
5. Reconcile arithmetic whenever the document supports it:
   - first running balance = opening_balance - debit + credit
   - each next running balance = previous_balance - debit + credit
   - closing_balance should match the last running balance when clearly shown
6. If a row clearly has only one money movement, populate only one of debit or credit.
7. Prefer explicitly printed opening/closing balances over guessed values.
8. Return valid JSON only.

Schema:
{json.dumps(schema.get_schema(), ensure_ascii=False, indent=2)}

Current extracted JSON:
{json.dumps(extracted_data, ensure_ascii=False, indent=2)}

OCR/document text:
{(full_text or '')[:7000]}
"""
        try:
            response_text = self._request_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=min(self.max_tokens, 1800),
                operation_name="bank statement repair",
            )
            repaired = self._parse_json_response(response_text)
            if not isinstance(repaired, dict):
                return None
            repaired = self._normalize_bank_statement_extraction(repaired)
            if not self._bank_statement_amounts_look_inconsistent(repaired):
                return repaired
        except Exception as exc:
            logger.warning(f"Bank-statement post-processing repair failed: {exc}")
        return None

    def _bank_statement_amounts_look_inconsistent(self, extracted_data: Dict[str, Any]) -> bool:
        transactions = extracted_data.get("transactions") or []
        if not isinstance(transactions, list) or not transactions:
            return False

        checks = 0
        issues = 0
        previous_balance = _safe_numeric_or_none(extracted_data.get("opening_balance"))

        total_debits = 0.0
        total_credits = 0.0
        for row in transactions:
            if not isinstance(row, dict):
                continue

            debit = _safe_numeric_or_none(row.get("debit"))
            credit = _safe_numeric_or_none(row.get("credit") if row.get("credit") not in (None, "") else row.get("amount"))
            balance = _safe_numeric_or_none(row.get("balance"))

            if debit is not None:
                total_debits += debit
            if credit is not None:
                total_credits += credit

            if debit is not None and credit is not None and debit > 0 and credit > 0:
                checks += 1
                issues += 1

            if (
                previous_balance is not None
                and balance is not None
                and (debit is not None or credit is not None)
            ):
                checks += 1
                expected_balance = round(previous_balance - (debit or 0.0) + (credit or 0.0), 2)
                if abs(expected_balance - balance) > 1.0:
                    issues += 1

            if balance is not None:
                previous_balance = balance
            elif previous_balance is not None and (debit is not None or credit is not None):
                previous_balance = round(previous_balance - (debit or 0.0) + (credit or 0.0), 2)

        stated_total_debits = _safe_numeric_or_none(extracted_data.get("total_debits"))
        stated_total_credits = _safe_numeric_or_none(extracted_data.get("total_credits"))
        closing_balance = _safe_numeric_or_none(extracted_data.get("closing_balance"))

        if stated_total_debits is not None:
            checks += 1
            if abs(stated_total_debits - round(total_debits, 2)) > 1.0:
                issues += 1
        if stated_total_credits is not None:
            checks += 1
            if abs(stated_total_credits - round(total_credits, 2)) > 1.0:
                issues += 1
        if previous_balance is not None and closing_balance is not None:
            checks += 1
            if abs(previous_balance - closing_balance) > 1.0:
                issues += 1

        return checks > 0 and issues > 0

    def _payslip_amounts_look_inconsistent(self, extracted_data: Dict[str, Any]) -> bool:
        def _sum_amounts(rows: Any) -> float:
            return round(
                sum(
                    _safe_float(item.get("amount"))
                    for item in (rows or [])
                    if isinstance(item, dict)
                ),
                2,
            )

        total_earnings = _safe_float(extracted_data.get("total_earnings"))
        total_deductions = _safe_float(extracted_data.get("total_deductions"))
        net_pay = _safe_float(extracted_data.get("net_pay"))
        earnings_sum = _sum_amounts(extracted_data.get("earnings"))
        deductions_sum = _sum_amounts(extracted_data.get("deductions"))

        if total_earnings and earnings_sum and abs(total_earnings - earnings_sum) > 1.0:
            return True
        if total_deductions and deductions_sum and abs(total_deductions - deductions_sum) > 1.0:
            return True
        if (
            total_earnings
            and total_deductions is not None
            and net_pay is not None
            and abs((total_earnings - total_deductions) - net_pay) > 1.0
        ):
            return True
        return False

    def _repair_balance_sheet_extraction(
        self,
        full_text: str,
        extracted_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        schema = get_schema("balance_sheet")
        if not schema:
            return None

        prompt = f"""You are correcting an extracted BALANCE SHEET JSON that has grouping or total inconsistencies.

You must return the FULL balance-sheet JSON using the exact schema below.
Use the OCR text as the source of truth.

Critical rules:
1. Keep each line item in the correct section: non_current_assets, current_assets, equity, non_current_liabilities, or current_liabilities.
2. Do not duplicate OCR rows across sections.
3. Preserve printed total_assets and total_equity_and_liabilities when they are clearly visible.
4. Reconcile the grouped line items so that:
   - sum(non_current_assets + current_assets) = total_assets
   - sum(equity + non_current_liabilities + current_liabilities) = total_equity_and_liabilities
5. Capital WIP may remain under non_current_assets if shown that way.
6. Return valid JSON only.

Schema:
{json.dumps(schema.get_schema(), ensure_ascii=False, indent=2)}

Current extracted JSON:
{json.dumps(extracted_data, ensure_ascii=False, indent=2)}

OCR/document text:
{(full_text or '')[:7000]}
"""
        try:
            response_text = self._request_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=min(self.max_tokens, 1600),
                operation_name="balance sheet repair",
            )
            repaired = self._parse_json_response(response_text)
            if isinstance(repaired, dict) and not self._balance_sheet_amounts_look_inconsistent(repaired):
                return repaired
        except Exception as exc:
            logger.warning(f"Balance-sheet post-processing repair failed: {exc}")
        return None

    def _balance_sheet_amounts_look_inconsistent(self, extracted_data: Dict[str, Any]) -> bool:
        assets = extracted_data.get("assets") or {}
        liabilities = extracted_data.get("equity_and_liabilities") or {}
        if not isinstance(assets, dict) or not isinstance(liabilities, dict):
            return False

        def _sum_amounts(rows: Any) -> float:
            return round(
                sum(
                    _safe_float(item.get("amount"))
                    for item in (rows or [])
                    if isinstance(item, dict)
                ),
                2,
            )

        total_assets = _safe_float(assets.get("total_assets"))
        total_equity_and_liabilities = _safe_float(liabilities.get("total_equity_and_liabilities"))
        computed_assets = round(
            _sum_amounts(assets.get("non_current_assets")) + _sum_amounts(assets.get("current_assets")),
            2,
        )
        computed_equity_and_liabilities = round(
            _sum_amounts(liabilities.get("equity"))
            + _sum_amounts(liabilities.get("non_current_liabilities"))
            + _sum_amounts(liabilities.get("current_liabilities")),
            2,
        )

        if total_assets and abs(total_assets - computed_assets) > 1.0:
            return True
        if total_equity_and_liabilities and abs(total_equity_and_liabilities - computed_equity_and_liabilities) > 1.0:
            return True
        if total_assets and total_equity_and_liabilities and abs(total_assets - total_equity_and_liabilities) > 1.0:
            return True
        return False

    def _should_downgrade_low_signal_gst_classification(
        self,
        *,
        document_type: str,
        confidence: float,
        text_sample: str,
        heuristic_type: Optional[str],
        heuristic_confidence: float,
    ) -> bool:
        if document_type != "gst_certificate" or confidence >= 0.85:
            return False
        if heuristic_type not in {None, "", "other"} and heuristic_confidence >= 0.4:
            return False

        normalized = re.sub(r"\s+", " ", (text_sample or "").lower())
        strong_gst_markers = (
            r"\bgoods and services tax\b",
            r"\bgstin\b",
            r"\bregistration certificate\b",
            r"\bcertificate of registration\b",
            r"\b\d{2}[a-z]{5}\d{4}[a-z][a-z0-9]z[a-z0-9]\b",
        )
        return not any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in strong_gst_markers)

    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from an LLM response, including fenced JSON payloads.
        """
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            fenced_match = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```",
                response_text,
                re.DOTALL,
            )
            if fenced_match:
                try:
                    return json.loads(fenced_match.group(1))
                except json.JSONDecodeError:
                    pass

            inline_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if inline_match:
                try:
                    return json.loads(inline_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.error("Failed to parse JSON from response")
            return None

    def calculate_extraction_confidence(self, extracted_data: dict, schema_type: str) -> float:
        """
        Calculate confidence score from required-field coverage.
        """
        schema = get_schema(schema_type)
        if not schema:
            return 0.0

        required_fields = schema.get_required_fields()
        if not required_fields:
            return 1.0

        present_count = 0
        for field in required_fields:
            if "." in field:
                current: Any = extracted_data
                found = True
                for part in field.split("."):
                    if isinstance(current, dict) and part in current and current[part] is not None:
                        current = current[part]
                    else:
                        found = False
                        break
                if found:
                    present_count += 1
            elif field in extracted_data and extracted_data[field] is not None:
                present_count += 1

        confidence = present_count / len(required_fields) if required_fields else 1.0
        return round(confidence, 2)
