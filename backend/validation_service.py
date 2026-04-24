"""
Shared validation runtime helpers.

This module centralizes validation execution, persistence, and workflow
decisioning so both the API routes and the async orchestration path use the
same logic.
"""

from __future__ import annotations

import re
from typing import Any, Optional
import uuid as _uuid

from agents.validator.logic import ValidationAgent
from agents.validator.schemas import AuditReport, Severity
from db import models
from db.session import SessionLocal
from logger import logger
from schemas import get_schema
from workflow_contract import JobState, ValidationDecision
import config

_agent: Optional[ValidationAgent] = None
_UNSUPPORTED_VALIDATION_TYPES = {"other", "form"}


def get_validation_agent() -> ValidationAgent:
    global _agent
    if _agent is None:
        _agent = ValidationAgent()
    return _agent


def validate_extraction_payload(
    data: Any,
    *,
    source_file: str,
    document_type: Optional[str] = None,
) -> AuditReport:
    agent = get_validation_agent()
    return agent.validate_data(
        data,
        source_file=source_file,
        document_type=document_type,
    )


def decide_validation_outcome(report: AuditReport) -> ValidationDecision:
    if report.document_type and not _is_schema_supported(report.document_type):
        return ValidationDecision.LOW_CONFIDENCE

    error_count = sum(1 for item in report.error_log if item.severity == Severity.ERROR)

    if report.confidence_score < config.VALIDATION_LOW_CONFIDENCE_SCORE:
        return ValidationDecision.LOW_CONFIDENCE
    if error_count > 0:
        return ValidationDecision.NEEDS_REVIEW
    if report.confidence_score < config.VALIDATION_PASS_MIN_CONFIDENCE:
        return ValidationDecision.NEEDS_REVIEW
    return ValidationDecision.PASS


def summarize_validation_report(report: AuditReport, decision: ValidationDecision) -> dict[str, Any]:
    error_count = sum(1 for item in report.error_log if item.severity == Severity.ERROR)
    warning_count = sum(1 for item in report.error_log if item.severity == Severity.WARNING)
    info_count = sum(1 for item in report.error_log if item.severity == Severity.INFO)
    failed_truth_tests = sum(1 for item in report.truth_tests if not item.passed)
    passed_truth_tests = sum(1 for item in report.truth_tests if item.passed)

    reason_codes = {
        f"{item.pillar.value}_{item.severity.value}"
        for item in report.error_log
    }
    if report.document_type and not _is_schema_supported(report.document_type):
        reason_codes.add("unsupported_document_type")
    review_reasons = _build_review_reasons(report)

    return {
        "decision": decision.value,
        "is_valid": report.is_valid,
        "confidence_score": report.confidence_score,
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "truth_test_count": len(report.truth_tests),
        "passed_truth_tests": passed_truth_tests,
        "failed_truth_tests": failed_truth_tests,
        "truth_test_failures": _summarize_truth_test_failures(report),
        "normalisation_change_count": len(report.normalisation_changes),
        "reason_codes": sorted(reason_codes),
        "review_reasons": review_reasons,
        "document_type": report.document_type,
        "schema_supported": _is_schema_supported(report.document_type),
        "source_file": report.source_file,
        "validation_time_seconds": report.validation_time_seconds,
    }


def _build_review_reasons(report: AuditReport) -> list[str]:
    repeated_indexed_signatures: dict[tuple[str, str, str], int] = {}
    for item in report.error_log:
        if item.severity not in {Severity.ERROR, Severity.WARNING}:
            continue
        signature = _indexed_reason_signature(item)
        if signature is None:
            continue
        repeated_indexed_signatures[signature] = repeated_indexed_signatures.get(signature, 0) + 1

    reasons: list[str] = []
    seen: set[str] = set()
    for item in report.error_log:
        if item.severity not in {Severity.ERROR, Severity.WARNING}:
            continue
        indexed_signature = _indexed_reason_signature(item)
        if indexed_signature and repeated_indexed_signatures.get(indexed_signature, 0) >= 3:
            compact = _build_indexed_reason_summary(indexed_signature)
        else:
            compact = _compact_review_reason(item.message)
        signature = _reason_signature(compact)
        if not compact or signature in seen:
            continue
        reasons.append(compact)
        seen.add(signature)
        if len(reasons) >= 8:
            break
    return reasons


def _summarize_truth_test_failures(report: AuditReport) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()
    for item in report.truth_tests:
        if item.passed:
            continue
        compact = _compact_review_reason(item.detail or item.assertion)
        signature = _reason_signature(compact)
        if not compact or signature in seen:
            continue
        failures.append(compact)
        seen.add(signature)
        if len(failures) >= 5:
            break
    return failures


def _indexed_reason_signature(item) -> tuple[str, str, str] | None:
    field = str(item.field or "").strip()
    normalized_field = re.sub(r"\[(\d+)\]", r".\1", field)
    match = re.fullmatch(r"([a-zA-Z0-9_]+)\.(\d+)\.(.+)", normalized_field)
    if not match:
        return None
    collection_path = match.group(1)
    leaf_path = match.group(3)
    message = str(item.message or "").lower()
    if "balance" in (normalized_field.lower() + " " + message):
        reason_family = "math_consistency_failed"
    elif "mismatch" in message or "inconsisten" in message:
        reason_family = "validation_rule_failed"
    else:
        reason_family = "validation_rule_failed"
    return collection_path, leaf_path, reason_family


def _build_indexed_reason_summary(signature: tuple[str, str, str]) -> str:
    collection_path, leaf_path, _ = signature
    return (
        f"Multiple '{leaf_path}' entries in '{collection_path}' show the same validation problem. "
        f"Review this repeated sequence as one issue."
    )


def _compact_review_reason(message: str) -> str:
    compact = " ".join(str(message or "").split()).strip()
    if not compact:
        return ""
    replacements = {
        "No arithmetic error detected, but the initial concern was misplaced. No issue here.": "Validation concern needs confirmation.",
        "While historical dates are acceptable, this may indicate a data entry error or stale extraction.": "Historical date detected; confirm if expected.",
    }
    for old, new in replacements.items():
        compact = compact.replace(old, new)
    if len(compact) > 180:
        compact = compact[:179].rstrip() + "…"
    return compact


def _reason_signature(message: str) -> str:
    compact = re.sub(r"^ai truth check failed:\s*", "", str(message or "").strip().lower())
    compact = re.sub(r"^truth test failed:\s*", "", compact)
    compact = re.sub(r"[^a-z0-9]+", " ", compact)
    tokens = [token for token in compact.split() if token not in {"the", "a", "an", "should", "be", "is", "are", "to", "of", "and"}]
    return " ".join(tokens[:12])


def persist_validation_report(
    report: AuditReport,
    *,
    current_user=None,
    user_id=None,
    extraction_id: Optional[str] = None,
    request=None,
    decision: Optional[ValidationDecision] = None,
) -> Optional[str]:
    """
    Save ValidationReport + AuditLog to DB.

    Returns the validation report row id when persistence succeeds.
    """
    db = SessionLocal()
    try:
        resolved_user_id = user_id or getattr(current_user, "id", None)

        extraction_uuid = None
        if extraction_id:
            try:
                extraction_uuid = _uuid.UUID(str(extraction_id))
            except (ValueError, AttributeError):
                extraction_uuid = None

        status = (decision.value if decision else ("passed" if report.is_valid else "failed"))
        quality_score = int((report.confidence_score or 0) * 100)
        summary = summarize_validation_report(
            report,
            decision or decide_validation_outcome(report),
        )

        issues = []
        for err in (report.error_log or []):
            issues.append({
                "pillar": err.pillar.value if hasattr(err.pillar, "value") else str(err.pillar),
                "severity": err.severity.value if hasattr(err.severity, "value") else str(err.severity),
                "field": err.field,
                "message": err.message,
                "expected": err.expected,
                "actual": err.actual,
            })

        vr = models.ValidationReport(
            extraction_id=extraction_uuid,
            status=status,
            issues_jsonb={
                "summary": summary,
                "errors": issues,
                "truth_tests": [item.model_dump(mode="json") for item in report.truth_tests],
                "normalisation_changes": [
                    item.model_dump(mode="json") for item in report.normalisation_changes
                ],
            },
            quality_score=quality_score,
        )
        db.add(vr)
        db.flush()

        meta = {
            "document_type": report.document_type,
            "confidence_score": report.confidence_score,
            "validation_time_sec": report.validation_time_seconds,
            "decision": summary["decision"],
            "error_count": summary["error_count"],
            "warning_count": summary["warning_count"],
            "failed_truth_tests": summary["failed_truth_tests"],
        }
        if request:
            meta["ip"] = request.client.host if request.client else None
            meta["user_agent"] = request.headers.get("user-agent")

        db.add(
            models.AuditLog(
                user_id=resolved_user_id,
                action="validate",
                resource_type="extraction" if extraction_uuid else "file",
                resource_id=str(extraction_uuid) if extraction_uuid else report.source_file,
                metadata_jsonb=meta,
            )
        )
        db.commit()
        logger.info(f"ValidationReport saved: id={vr.id}, status={status}, score={quality_score}")
        return str(vr.id)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to persist validation report to DB: {exc}")
        return None
    finally:
        db.close()


def promote_final_job_status(
    extraction_status: str,
    validation_decision: ValidationDecision,
) -> str:
    if validation_decision == ValidationDecision.PASS:
        if extraction_status == JobState.FAILED.value:
            return extraction_status
        return JobState.COMPLETED.value

    priority = {
        JobState.COMPLETED.value: 0,
        JobState.NEEDS_REVIEW.value: 1,
        JobState.LOW_CONFIDENCE.value: 2,
        JobState.FAILED.value: 3,
    }
    validation_status = {
        ValidationDecision.PASS: JobState.COMPLETED.value,
        ValidationDecision.NEEDS_REVIEW: JobState.NEEDS_REVIEW.value,
        ValidationDecision.LOW_CONFIDENCE: JobState.LOW_CONFIDENCE.value,
        ValidationDecision.FAIL: JobState.FAILED.value,
        ValidationDecision.RETRY: JobState.NEEDS_REVIEW.value,
    }[validation_decision]

    if priority.get(validation_status, 0) > priority.get(extraction_status, 0):
        return validation_status
    return extraction_status


def _is_schema_supported(document_type: Optional[str]) -> bool:
    if not document_type or document_type in _UNSUPPORTED_VALIDATION_TYPES:
        return False
    return get_schema(document_type) is not None
