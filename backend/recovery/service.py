from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from api.models.responses import RecoveryAttemptListResponse, RecoveryAttemptResponse
from db import models
from logger import logger
from review.service import (
    DEFAULT_DOCUMENT_REVIEW_FIELD,
    attach_recovery_proposals_to_review_case,
    build_review_field_items_from_validation,
)
from schemas import get_schema
from validation_service import (
    ValidationDecision,
    decide_validation_outcome,
    summarize_validation_report,
    validate_extraction_payload,
)
import config

RECOVERY_MODES = {"shadow", "active"}
RECOVERY_STATUSES = {
    "started",
    "completed",
    "accepted",
    "rejected",
    "failed",
    "skipped",
}
UNRECOVERABLE_FIELD_PATHS = {DEFAULT_DOCUMENT_REVIEW_FIELD}
RECOVERABLE_INDEXED_COLLECTIONS = {"transactions", "line_items", "subjects"}
GROUPED_RECOVERY_COLLECTIONS = {"transactions", "line_items", "subjects"}

REQUIRED_AUTO_ACCEPT_FIELDS_BY_DOCUMENT_TYPE = {
    "invoice": {
        "invoice_number",
        "invoice_date",
        "vendor.name",
        "total",
    },
    "bank_statement": {
        "bank_name",
        "account_holder",
        "account_number",
        "statement_period.from_date",
        "statement_period.to_date",
        "transactions",
    },
    "purchase_order": {
        "purchase_order_number",
        "order_date",
        "buyer.name",
        "vendor.name",
        "total",
    },
    "retail_receipt": {
        "receipt_number",
        "receipt_date",
        "merchant.name",
        "total",
    },
    "payslip": {
        "employer_name",
        "employee.name",
        "pay_period.from_date",
        "pay_period.to_date",
        "total_earnings",
        "total_deductions",
        "net_pay",
    },
    "balance_sheet": {
        "entity_name",
        "statement_date",
        "assets.total_assets",
        "equity_and_liabilities.total_equity_and_liabilities",
    },
    "marksheet": {
        "institution_name",
        "student_name",
        "exam_name",
        "subjects",
        "result",
    },
    "utility_bill": {
        "provider_name",
        "consumer_name",
        "consumer_number",
        "due_date",
        "total_amount",
    },
}

_agent = None
_confidence_scorer = None


def create_recovery_attempt(
    db,
    *,
    extraction_id,
    review_case_id=None,
    strategy: str,
    mode: str = "shadow",
    model_name: Optional[str] = None,
    weak_fields: Optional[list[str]] = None,
    reason_codes: Optional[list[str]] = None,
    input_summary: Optional[dict[str, Any]] = None,
) -> models.RecoveryAttempt:
    if mode not in RECOVERY_MODES:
        raise ValueError("Unsupported recovery mode")

    if not strategy:
        raise ValueError("Recovery strategy is required")

    attempt_number = get_next_recovery_attempt_number(db, extraction_id)
    attempt = models.RecoveryAttempt(
        extraction_id=extraction_id,
        review_case_id=review_case_id,
        attempt_number=attempt_number,
        mode=mode,
        strategy=strategy,
        status="started",
        model_name=model_name,
        weak_fields_jsonb=weak_fields or [],
        reason_codes_jsonb=reason_codes or [],
        input_summary_jsonb=input_summary or {},
        started_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.flush()
    return attempt


def finalize_recovery_attempt(
    attempt: models.RecoveryAttempt,
    *,
    status: str,
    output_summary: Optional[dict[str, Any]] = None,
    improvement_score: Optional[float] = None,
    accepted: Optional[bool] = None,
    failure_reason: Optional[str] = None,
) -> models.RecoveryAttempt:
    if status not in RECOVERY_STATUSES:
        raise ValueError("Unsupported recovery status")

    attempt.status = status
    attempt.output_summary_jsonb = output_summary or {}
    attempt.improvement_score = improvement_score
    attempt.accepted = accepted
    attempt.failure_reason = failure_reason
    attempt.finished_at = datetime.now(timezone.utc)
    return attempt


def get_next_recovery_attempt_number(db, extraction_id) -> int:
    latest = (
        db.query(models.RecoveryAttempt.attempt_number)
        .filter(models.RecoveryAttempt.extraction_id == extraction_id)
        .order_by(models.RecoveryAttempt.attempt_number.desc())
        .first()
    )
    if not latest:
        return 1
    return int(latest[0]) + 1


def count_recovery_attempts(db, extraction_id) -> int:
    return (
        db.query(models.RecoveryAttempt)
        .filter(models.RecoveryAttempt.extraction_id == extraction_id)
        .count()
    )


def list_recovery_attempts_for_user(
    db,
    *,
    extraction_id: str,
    user_id,
) -> RecoveryAttemptListResponse:
    try:
        extraction_uuid = uuid.UUID(extraction_id)
    except ValueError as exc:
        raise ValueError("Invalid job_id") from exc

    extraction = (
        db.query(models.Extraction)
        .filter(models.Extraction.id == extraction_uuid)
        .filter(models.Extraction.user_id == user_id)
        .first()
    )
    if extraction is None:
        raise ValueError("Job not found")

    attempts = (
        db.query(models.RecoveryAttempt)
        .filter(models.RecoveryAttempt.extraction_id == extraction_uuid)
        .order_by(models.RecoveryAttempt.attempt_number.asc(), models.RecoveryAttempt.created_at.asc())
        .all()
    )

    return RecoveryAttemptListResponse(
        job_id=str(extraction.id),
        total=len(attempts),
        attempts=[
            RecoveryAttemptResponse(
                attempt_id=str(attempt.id),
                job_id=str(attempt.extraction_id),
                review_case_id=str(attempt.review_case_id) if attempt.review_case_id else None,
                attempt_number=attempt.attempt_number,
                mode=attempt.mode,
                strategy=attempt.strategy,
                status=attempt.status,
                model_name=attempt.model_name,
                weak_fields=list(attempt.weak_fields_jsonb or []),
                reason_codes=list(attempt.reason_codes_jsonb or []),
                input_summary=attempt.input_summary_jsonb or {},
                output_summary=attempt.output_summary_jsonb or {},
                improvement_score=attempt.improvement_score,
                accepted=attempt.accepted,
                failure_reason=attempt.failure_reason,
                started_at=attempt.started_at,
                finished_at=attempt.finished_at,
            )
            for attempt in attempts
        ],
    )


def run_bounded_recovery(
    db,
    *,
    extraction: models.Extraction,
    result: dict[str, Any],
    validation_report,
    validation_decision: ValidationDecision,
    validation_summary: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute bounded recovery for already-weak jobs.
    Returns a summary dict and may return an accepted repaired result in active mode.
    """
    mode = "shadow" if config.AI_RECOVERY_SHADOW_MODE else "active"
    document_type = _resolve_recovery_document_type(result)
    structured_data = result.get("structured_data") or {}
    raw_text = str((result.get("text") or {}).get("raw") or "")
    review_case_id = (result.get("metadata") or {}).get("review_case", {}).get("id")
    validation_errors = _serialize_validation_errors(validation_report)
    review_fields = build_review_field_items_from_validation(
        document_type=document_type,
        structured_data=structured_data if isinstance(structured_data, dict) else {},
        confidence_data=result.get("comprehensive_confidence") or {},
        validation_summary=validation_summary or {},
        validation_errors=validation_errors,
        collapse_repeated_groups=False,
    )

    logger.info(
        f"Recovery start | job_id={extraction.id} mode={mode} "
        f"doc_type={document_type or 'unknown'} review_fields={len(review_fields)}"
    )

    recovery_summary: dict[str, Any] = {
        "enabled": True,
        "mode": mode,
        "document_type": document_type,
        "attempts": [],
        "accepted": False,
        "activated": False,
        "reason": None,
    }

    if document_type not in config.AI_RECOVERY_IN_SCOPE_TYPES:
        _log_skipped_recovery_attempt(
            db,
            extraction_id=extraction.id,
            review_case_id=review_case_id,
            reason="document_type_out_of_scope",
            document_type=document_type,
            review_fields=review_fields,
            mode=mode,
        )
        recovery_summary["reason"] = "document_type_out_of_scope"
        return recovery_summary

    if not structured_data or not isinstance(structured_data, dict):
        _log_skipped_recovery_attempt(
            db,
            extraction_id=extraction.id,
            review_case_id=review_case_id,
            reason="structured_data_missing",
            document_type=document_type,
            review_fields=review_fields,
            mode=mode,
        )
        recovery_summary["reason"] = "structured_data_missing"
        return recovery_summary

    if not raw_text.strip():
        _log_skipped_recovery_attempt(
            db,
            extraction_id=extraction.id,
            review_case_id=review_case_id,
            reason="raw_text_missing",
            document_type=document_type,
            review_fields=review_fields,
            mode=mode,
        )
        recovery_summary["reason"] = "raw_text_missing"
        return recovery_summary

    recoverable_fields = _select_recoverable_fields(review_fields)
    if not recoverable_fields:
        _log_skipped_recovery_attempt(
            db,
            extraction_id=extraction.id,
            review_case_id=review_case_id,
            reason="no_recoverable_fields",
            document_type=document_type,
            review_fields=review_fields,
            mode=mode,
        )
        recovery_summary["reason"] = "no_recoverable_fields"
        return recovery_summary

    agent = _get_ai_agent()
    if agent is None:
        _log_skipped_recovery_attempt(
            db,
            extraction_id=extraction.id,
            review_case_id=review_case_id,
            reason="llm_unavailable",
            document_type=document_type,
            review_fields=recoverable_fields,
            mode=mode,
        )
        recovery_summary["reason"] = "llm_unavailable"
        return recovery_summary

    current_result = copy.deepcopy(result)
    current_report = validation_report
    current_decision = validation_decision
    proposals_for_review: list[dict[str, Any]] = []
    recovery_context = _build_recovery_context(result, document_type=document_type)

    for attempt_index in range(1, max(1, config.AI_RECOVERY_MAX_ATTEMPTS) + 1):
        attempt_fields = _build_recovery_attempt_fields(
            document_type=document_type,
            current_result=current_result,
            current_report=current_report,
            current_decision=current_decision,
        )
        if not attempt_fields:
            logger.info(
                f"Recovery stop | job_id={extraction.id} attempt={attempt_index} "
                f"reason=no_more_recoverable_fields"
            )
            break

        attempt_fields = attempt_fields[: max(1, config.AI_RECOVERY_MAX_FIELDS_PER_ATTEMPT)]
        logger.info(
            f"Recovery attempt | job_id={extraction.id} attempt={attempt_index} "
            f"strategy={'field_repair' if attempt_index == 1 else 'field_repair_followup'} "
            f"fields={[item['field_path'] for item in attempt_fields]}"
        )
        attempt = create_recovery_attempt(
            db,
            extraction_id=extraction.id,
            review_case_id=review_case_id,
            strategy="field_repair" if attempt_index == 1 else "field_repair_followup",
            mode=mode,
            model_name=getattr(agent, "model", None),
            weak_fields=[item["field_path"] for item in attempt_fields],
            reason_codes=[item["reason_code"] for item in attempt_fields],
            input_summary={
                "document_type": document_type,
                "validation_confidence_before": current_report.confidence_score,
                "weak_fields": [item["field_path"] for item in attempt_fields],
                "validation_reason_codes": validation_summary.get("reason_codes", []),
            },
        )

        try:
            repair_result = agent.repair_weak_fields(
                full_text=raw_text,
                document_type=document_type,
                structured_data=current_result.get("structured_data") or {},
                weak_fields=attempt_fields,
                validation_summary=summarize_validation_report(current_report, current_decision),
                extraction_context=recovery_context,
            )
            verified_changes, rejected_changes = _verify_repair_changes(
                document_type=document_type,
                attempt_fields=attempt_fields,
                raw_text=raw_text,
                extraction_context=recovery_context,
                current_structured_data=current_result.get("structured_data") or {},
                repair_result=repair_result,
            )

            if not verified_changes:
                fallback_summary = _attempt_grouped_section_recovery(
                    db,
                    extraction=extraction,
                    review_case_id=review_case_id,
                    mode=mode,
                    document_type=document_type,
                    agent=agent,
                    attempt_fields=attempt_fields,
                    raw_text=raw_text,
                    recovery_context=recovery_context,
                    current_result=current_result,
                    current_report=current_report,
                    current_decision=current_decision,
                )
                if fallback_summary is not None:
                    logger.info(
                        f"Recovery fallback | job_id={extraction.id} attempt={attempt_index} "
                        f"strategy=section_rebuild "
                        f"verified_changes={len(fallback_summary['verified_changes'])}"
                    )
                    recovery_summary["attempts"].extend(fallback_summary["attempts"])
                    if fallback_summary["verified_changes"]:
                        verified_changes = fallback_summary["verified_changes"]
                        rejected_changes = rejected_changes + fallback_summary["rejected_changes"]
                        repair_result = {
                            "summary": fallback_summary["summary"],
                            "changes": fallback_summary["raw_changes"],
                        }
                    else:
                        finalize_recovery_attempt(
                            attempt,
                            status="rejected",
                            output_summary={
                                "summary": repair_result.get("summary"),
                                "rejected_changes": rejected_changes,
                            },
                            improvement_score=0.0,
                            accepted=False,
                            failure_reason="no_verified_changes",
                        )
                        recovery_summary["attempts"].append(_attempt_to_dict(attempt))
                        db.flush()
                        break
                else:
                    finalize_recovery_attempt(
                        attempt,
                        status="rejected",
                        output_summary={
                            "summary": repair_result.get("summary"),
                            "rejected_changes": rejected_changes,
                        },
                        improvement_score=0.0,
                        accepted=False,
                        failure_reason="no_verified_changes",
                    )
                    recovery_summary["attempts"].append(_attempt_to_dict(attempt))
                    db.flush()
                    break

            candidate_result = copy.deepcopy(current_result)
            for change in verified_changes:
                _set_nested_value(
                    candidate_result.setdefault("structured_data", {}),
                    change["field_path"],
                    change["proposed_value"],
                )
            _refresh_confidence(candidate_result, document_type=document_type)

            candidate_report = validate_extraction_payload(
                candidate_result,
                source_file=candidate_result.get("output_file") or "",
                document_type=document_type,
            )
            candidate_decision = decide_validation_outcome(candidate_report)
            candidate_summary = summarize_validation_report(candidate_report, candidate_decision)

            accepted, acceptance_summary = _evaluate_candidate_recovery(
                before_report=current_report,
                after_report=candidate_report,
                document_type=document_type,
                candidate_data=candidate_result.get("structured_data") or {},
                changes=verified_changes,
            )
            improvement_score = acceptance_summary["confidence_improvement"]

            finalize_recovery_attempt(
                attempt,
                status="accepted" if accepted and mode == "active" else "completed",
                output_summary={
                    "summary": repair_result.get("summary"),
                    "candidate_validation_summary": candidate_summary,
                    "accepted_in_active_mode": accepted and mode == "active",
                    "accepted_in_shadow_mode": accepted and mode == "shadow",
                    "acceptance_summary": acceptance_summary,
                    "verified_changes": verified_changes,
                    "rejected_changes": rejected_changes,
                },
                improvement_score=improvement_score,
                accepted=accepted,
                failure_reason=None,
            )
            recovery_summary["attempts"].append(_attempt_to_dict(attempt))
            db.flush()
            logger.info(
                f"Recovery attempt result | job_id={extraction.id} "
                f"attempt={attempt.attempt_number} accepted={accepted} "
                f"improvement={improvement_score:.3f} "
                f"changed_fields={acceptance_summary.get('changed_fields', [])} "
                f"blockers={acceptance_summary.get('blockers', [])}"
            )

            for change in verified_changes:
                proposals_for_review.append(
                    {
                        **change,
                        "attempt_number": attempt.attempt_number,
                    }
                )

            if accepted:
                candidate_result["status"] = "success"
                candidate_result["review"] = {
                    "status": "success",
                    "needs_human_review": False,
                    "reasons": [],
                    "signals": {
                        "recovered_from_weak_result": True,
                    },
                }
                candidate_result.setdefault("metadata", {})["recovery_accepted"] = True
                recovery_summary["accepted"] = True
                recovery_summary["activated"] = mode == "active"
                recovery_summary["reason"] = "accepted_in_shadow_mode" if mode == "shadow" else "accepted"
                recovery_summary["accepted_result"] = candidate_result if mode == "active" else None
                recovery_summary["accepted_validation_report"] = candidate_report if mode == "active" else None
                recovery_summary["accepted_validation_decision"] = candidate_decision if mode == "active" else None
                recovery_summary["proposals"] = proposals_for_review
                _log_recovery_summary(extraction_id=extraction.id, summary=recovery_summary)
                return recovery_summary

            if improvement_score <= 0:
                break

            current_result = candidate_result
            current_report = candidate_report
            current_decision = candidate_decision
        except Exception as exc:
            logger.warning(f"Bounded recovery attempt failed for job_id={extraction.id}: {exc}")
            finalize_recovery_attempt(
                attempt,
                status="failed",
                output_summary={},
                improvement_score=None,
                accepted=False,
                failure_reason=str(exc),
            )
            recovery_summary["attempts"].append(_attempt_to_dict(attempt))
            db.flush()
            break

    recovery_summary["proposals"] = proposals_for_review
    recovery_summary["reason"] = recovery_summary["reason"] or "recovery_not_sufficient"
    _log_recovery_summary(extraction_id=extraction.id, summary=recovery_summary)
    return recovery_summary


def attach_recovery_proposals_if_present(
    db,
    *,
    review_case: Optional[models.ReviewCase],
    recovery_summary: Optional[dict[str, Any]],
) -> None:
    if not review_case or not recovery_summary:
        return
    proposals = recovery_summary.get("proposals") or []
    if not proposals:
        return
    latest_attempt_number = max(
        (proposal.get("attempt_number") for proposal in proposals if proposal.get("attempt_number") is not None),
        default=None,
    )
    attach_recovery_proposals_to_review_case(
        db,
        review_case=review_case,
        proposals=proposals,
        recovery_attempt_number=latest_attempt_number,
    )


def _log_skipped_recovery_attempt(
    db,
    *,
    extraction_id,
    review_case_id,
    reason: str,
    document_type: str,
    review_fields: list[dict[str, Any]],
    mode: str,
) -> None:
    attempt = create_recovery_attempt(
        db,
        extraction_id=extraction_id,
        review_case_id=review_case_id,
        strategy="eligibility_gate",
        mode=mode,
        model_name=None,
        weak_fields=[item["field_path"] for item in review_fields],
        reason_codes=[item["reason_code"] for item in review_fields],
        input_summary={
            "document_type": document_type,
            "reason": reason,
        },
    )
    finalize_recovery_attempt(
        attempt,
        status="skipped",
        output_summary={"reason": reason},
        improvement_score=0.0,
        accepted=False,
        failure_reason=reason,
    )
    db.flush()


def _get_ai_agent():
    global _agent
    if _agent is not None:
        return _agent
    try:
        from ai_agent import AIAgent

        if not config.MISTRAL_API_KEY:
            return None
        _agent = AIAgent()
        return _agent
    except Exception as exc:
        logger.warning(f"AI recovery agent unavailable: {exc}")
        return None


def _get_confidence_scorer():
    global _confidence_scorer
    if _confidence_scorer is not None:
        return _confidence_scorer
    try:
        from confidence_scorer import ConfidenceScorer

        _confidence_scorer = ConfidenceScorer()
        return _confidence_scorer
    except Exception as exc:
        logger.warning(f"Confidence scorer unavailable for recovery: {exc}")
        return None


def _serialize_validation_errors(report) -> list[dict[str, Any]]:
    return [
        {
            "pillar": item.pillar.value if hasattr(item.pillar, "value") else str(item.pillar),
            "severity": item.severity.value if hasattr(item.severity, "value") else str(item.severity),
            "field": item.field,
            "message": item.message,
            "expected": item.expected,
            "actual": item.actual,
        }
        for item in report.error_log
    ]


def _select_recoverable_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recoverable = []
    for item in fields:
        field_path = str(item.get("field_path") or "")
        if not field_path or field_path in UNRECOVERABLE_FIELD_PATHS:
            continue
        normalized_path = _normalise_field_path(field_path)
        path_parts = normalized_path.split(".")
        if any(part.isdigit() for part in path_parts):
            if not _is_recoverable_indexed_path(path_parts):
                continue
        recoverable.append(item)
    return recoverable


def _build_recovery_attempt_fields(
    *,
    document_type: str,
    current_result: dict[str, Any],
    current_report,
    current_decision: ValidationDecision,
) -> list[dict[str, Any]]:
    return _select_recoverable_fields(
        build_review_field_items_from_validation(
            document_type=document_type,
            structured_data=current_result.get("structured_data") or {},
            confidence_data=current_result.get("comprehensive_confidence") or {},
            validation_summary=summarize_validation_report(current_report, current_decision),
            validation_errors=_serialize_validation_errors(current_report),
            collapse_repeated_groups=False,
        )
    )


def _select_grouped_recovery_targets(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in fields:
        normalized_path = _normalise_field_path(str(item.get("field_path") or ""))
        if not normalized_path:
            continue
        parts = normalized_path.split(".")
        if not parts or parts[0] not in GROUPED_RECOVERY_COLLECTIONS:
            continue
        if len(parts) >= 3 and parts[1].isdigit():
            grouped.setdefault(parts[0], []).append(item)

    targets: list[dict[str, Any]] = []
    for section_path, grouped_fields in grouped.items():
        deduped_fields = sorted(
            grouped_fields,
            key=lambda item: _normalise_field_path(str(item.get("field_path") or "")),
        )
        deduped_fields = _unique_field_items(deduped_fields)
        if len(deduped_fields) < 2:
            continue
        targets.append(
            {
                "section_path": section_path,
                "fields": deduped_fields,
            }
        )
    return targets


def _unique_field_items(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in fields:
        field_path = _normalise_field_path(str(item.get("field_path") or ""))
        if not field_path or field_path in seen:
            continue
        unique.append(item)
        seen.add(field_path)
    return unique


def _attempt_grouped_section_recovery(
    db,
    *,
    extraction: models.Extraction,
    review_case_id,
    mode: str,
    document_type: str,
    agent,
    attempt_fields: list[dict[str, Any]],
    raw_text: str,
    recovery_context: dict[str, Any],
    current_result: dict[str, Any],
    current_report,
    current_decision: ValidationDecision,
) -> Optional[dict[str, Any]]:
    targets = _select_grouped_recovery_targets(attempt_fields)
    if not targets:
        return None

    target = targets[0]
    section_path = target["section_path"]
    section_fields = target["fields"][: max(2, config.AI_RECOVERY_MAX_FIELDS_PER_ATTEMPT)]

    attempt = create_recovery_attempt(
        db,
        extraction_id=extraction.id,
        review_case_id=review_case_id,
        strategy="section_rebuild",
        mode=mode,
        model_name=getattr(agent, "model", None),
        weak_fields=[item["field_path"] for item in section_fields],
        reason_codes=[item["reason_code"] for item in section_fields],
        input_summary={
            "document_type": document_type,
            "section_path": section_path,
            "validation_confidence_before": current_report.confidence_score,
            "weak_fields": [item["field_path"] for item in section_fields],
        },
    )

    try:
        repair_result = agent.repair_grouped_section(
            full_text=raw_text,
            document_type=document_type,
            section_path=section_path,
            structured_data=current_result.get("structured_data") or {},
            current_section=_get_nested_value(current_result.get("structured_data") or {}, section_path),
            candidate_fields=section_fields,
            validation_summary=summarize_validation_report(current_report, current_decision),
            extraction_context=recovery_context,
        )
        verified_changes, rejected_changes = _verify_repair_changes(
            document_type=document_type,
            attempt_fields=section_fields,
            raw_text=raw_text,
            extraction_context=recovery_context,
            current_structured_data=current_result.get("structured_data") or {},
            repair_result=repair_result,
        )
        if not verified_changes:
            finalize_recovery_attempt(
                attempt,
                status="rejected",
                output_summary={
                    "summary": repair_result.get("summary"),
                    "section_path": section_path,
                    "rejected_changes": rejected_changes,
                },
                improvement_score=0.0,
                accepted=False,
                failure_reason="no_verified_grouped_changes",
            )
        else:
            finalize_recovery_attempt(
                attempt,
                status="completed",
                output_summary={
                    "summary": repair_result.get("summary"),
                    "section_path": section_path,
                    "verified_changes": verified_changes,
                    "rejected_changes": rejected_changes,
                },
                improvement_score=0.0,
                accepted=False,
                failure_reason=None,
            )
        db.flush()
        return {
            "attempts": [_attempt_to_dict(attempt)],
            "verified_changes": verified_changes,
            "rejected_changes": rejected_changes,
            "summary": repair_result.get("summary"),
            "raw_changes": repair_result.get("changes", []),
        }
    except Exception as exc:
        logger.warning(
            f"Grouped recovery fallback failed for job_id={extraction.id}, section={section_path}: {exc}"
        )
        finalize_recovery_attempt(
            attempt,
            status="failed",
            output_summary={"section_path": section_path},
            improvement_score=None,
            accepted=False,
            failure_reason=str(exc),
        )
        db.flush()
        return {
            "attempts": [_attempt_to_dict(attempt)],
            "verified_changes": [],
            "rejected_changes": [],
            "summary": "",
            "raw_changes": [],
        }


def _log_recovery_summary(*, extraction_id, summary: dict[str, Any]) -> None:
    logger.info(
        f"Recovery summary | job_id={extraction_id} accepted={bool(summary.get('accepted'))} "
        f"activated={bool(summary.get('activated'))} "
        f"attempts={len(summary.get('attempts') or [])} "
        f"reason={summary.get('reason')} "
        f"proposals={len(summary.get('proposals') or [])}"
    )


def _is_recoverable_indexed_path(path_parts: list[str]) -> bool:
    if len(path_parts) < 3:
        return False
    if path_parts[0] not in RECOVERABLE_INDEXED_COLLECTIONS:
        return False
    if not path_parts[1].isdigit():
        return False
    return bool(path_parts[-1].strip())


def _verify_repair_changes(
    *,
    document_type: str,
    attempt_fields: list[dict[str, Any]],
    raw_text: str,
    extraction_context: dict[str, Any],
    current_structured_data: dict[str, Any],
    repair_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attempt_field_map = {item["field_path"]: item for item in attempt_fields}
    verified_changes = []
    rejected_changes = []

    for change in repair_result.get("changes", []):
        field_path = str(change.get("field_path") or "").strip()
        action = str(change.get("action") or "no_change").strip().lower()
        if field_path not in attempt_field_map or action != "update":
            continue

        attempt_field = attempt_field_map[field_path]
        proposed_value = change.get("proposed_value")
        evidence_text = change.get("evidence_text")
        evidence_supported = _evidence_supported(
            document_type=document_type,
            field_path=field_path,
            raw_text=raw_text,
            extraction_context=extraction_context,
            evidence_text=evidence_text,
            current_value=attempt_field.get("original_value"),
            proposed_value=proposed_value,
            current_structured_data=current_structured_data,
        )
        if attempt_field.get("is_critical") and not evidence_supported:
            rejected_changes.append(
                {
                    "field_path": field_path,
                    "reason": "unsupported_ai_change",
                    "evidence_text": evidence_text,
                }
            )
            continue

        verified_changes.append(
            {
                "field_path": field_path,
                "reason_code": attempt_field.get("reason_code"),
                "is_critical": bool(attempt_field.get("is_critical")),
                "old_value": attempt_field.get("original_value"),
                "proposed_value": proposed_value,
                "evidence_text": evidence_text,
                "reason": change.get("reason"),
                "confidence": change.get("confidence"),
                "evidence_supported": evidence_supported,
            }
        )

    return verified_changes, rejected_changes


def _evidence_supported(
    *,
    document_type: str,
    field_path: str,
    raw_text: str,
    extraction_context: dict[str, Any],
    evidence_text: Any,
    current_value: Any,
    proposed_value: Any,
    current_structured_data: dict[str, Any],
) -> bool:
    haystack_text = _flatten_recovery_search_text(raw_text=raw_text, extraction_context=extraction_context)
    haystack_norm = _normalize_text(haystack_text)

    for candidate in (evidence_text, proposed_value):
        for normalized_candidate in _candidate_search_terms(candidate):
            if len(normalized_candidate) >= 4 and normalized_candidate in haystack_norm:
                return True

    return _document_specific_evidence_supported(
        document_type=document_type,
        field_path=field_path,
        evidence_text=evidence_text,
        current_value=current_value,
        proposed_value=proposed_value,
        current_structured_data=current_structured_data,
        haystack_text=haystack_text,
    )


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text)


def _build_recovery_context(result: dict[str, Any], *, document_type: str) -> dict[str, Any]:
    raw_text = str((result.get("text") or {}).get("raw") or "")
    tables = result.get("tables") or []
    metadata = result.get("metadata") or {}

    cleaned_lines = []
    numeric_dense_lines = []
    for raw_line in raw_text.splitlines():
        line = " ".join(str(raw_line or "").split())
        if not line:
            continue
        if line.startswith("--- Page ") or line.startswith("[Language:"):
            continue
        cleaned_lines.append(line)
        if len(re.findall(r"\d", line)) >= 3:
            numeric_dense_lines.append(line)

    flattened_tables = []
    table_blocks = []
    for table in tables[:4]:
        if not isinstance(table, dict):
            continue
        headers = [str(header) for header in (table.get("headers") or [])[:8]]
        rows = [
            [str(cell) for cell in row[:8]]
            for row in (table.get("rows") or [])[:10]
            if isinstance(row, list)
        ]
        table_blocks.append(
            {
                "page": table.get("page"),
                "source": table.get("source"),
                "headers": headers,
                "rows": rows,
            }
        )
        if headers:
            flattened_tables.append(" | ".join(headers))
        flattened_tables.extend(" | ".join(row) for row in rows)

    return {
        "signals": {
            "document_type": document_type,
            "table_count": len(table_blocks),
            "line_count": len(cleaned_lines),
            "numeric_dense_line_count": len(numeric_dense_lines),
            "ocr_average_page_confidence": ((metadata.get("ocr_run_summary") or {}).get("average_page_confidence")),
        },
        "line_blocks": cleaned_lines[:80],
        "numeric_dense_lines": numeric_dense_lines[:40],
        "table_blocks": table_blocks,
        "flattened_table_lines": flattened_tables[:60],
    }


def _flatten_recovery_search_text(*, raw_text: str, extraction_context: dict[str, Any]) -> str:
    parts = [str(raw_text or "")]
    for key in ("line_blocks", "numeric_dense_lines", "flattened_table_lines"):
        value = extraction_context.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if str(item).strip())
    return "\n".join(parts)


def _candidate_search_terms(value: Any) -> set[str]:
    terms: set[str] = set()
    if value in (None, "", [], {}):
        return terms

    raw_value = str(value).strip()
    normalized_text = _normalize_text(raw_value)
    if normalized_text:
        terms.add(normalized_text)

    numeric_value = _coerce_numeric(value)
    if numeric_value is not None:
        terms.add(_normalize_text(f"{numeric_value:.2f}"))
        terms.add(_normalize_text(str(int(numeric_value))) if float(numeric_value).is_integer() else _normalize_text(str(numeric_value)))
        terms.add(_normalize_text(_format_indian_number(numeric_value)))

    parsed_date = _normalize_date_value(value)
    if parsed_date:
        terms.add(_normalize_text(parsed_date))
        terms.add(_normalize_text(parsed_date.replace("-", "/")))

    return {term for term in terms if term}


def _coerce_numeric(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _format_indian_number(value: float) -> str:
    sign = "-" if value < 0 else ""
    abs_value = abs(round(float(value), 2))
    integer_part, _, decimal_part = f"{abs_value:.2f}".partition(".")
    if len(integer_part) <= 3:
        grouped = integer_part
    else:
        head = integer_part[-3:]
        tail = integer_part[:-3]
        parts = []
        while len(tail) > 2:
            parts.insert(0, tail[-2:])
            tail = tail[:-2]
        if tail:
            parts.insert(0, tail)
        grouped = ",".join(parts + [head])
    return f"{sign}{grouped}.{decimal_part}"


def _normalize_date_value(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d-%B-%Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(text.replace("/", "-"), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _document_specific_evidence_supported(
    *,
    document_type: str,
    field_path: str,
    evidence_text: Any,
    current_value: Any,
    proposed_value: Any,
    current_structured_data: dict[str, Any],
    haystack_text: str,
) -> bool:
    proposed_numeric = _coerce_numeric(proposed_value)
    if document_type == "bank_statement":
        return _bank_statement_recovery_evidence_supported(
            field_path=field_path,
            evidence_text=evidence_text,
            current_value=current_value,
            proposed_value=proposed_value,
            proposed_numeric=proposed_numeric,
            current_structured_data=current_structured_data,
            haystack_text=haystack_text,
        )
    if document_type in {"invoice", "purchase_order", "retail_receipt"}:
        return _invoice_style_recovery_evidence_supported(
            field_path=field_path,
            evidence_text=evidence_text,
            proposed_value=proposed_value,
            proposed_numeric=proposed_numeric,
            current_structured_data=current_structured_data,
            haystack_text=haystack_text,
        )
    if document_type == "payslip":
        return _payslip_recovery_evidence_supported(
            field_path=field_path,
            proposed_numeric=proposed_numeric,
            current_structured_data=current_structured_data,
            haystack_text=haystack_text,
        )
    if document_type == "balance_sheet":
        return _balance_sheet_recovery_evidence_supported(
            field_path=field_path,
            proposed_numeric=proposed_numeric,
            current_structured_data=current_structured_data,
            haystack_text=haystack_text,
        )
    if document_type == "marksheet":
        return _marksheet_recovery_evidence_supported(
            field_path=field_path,
            proposed_numeric=proposed_numeric,
            current_structured_data=current_structured_data,
            haystack_text=haystack_text,
        )
    if document_type == "utility_bill":
        return _utility_bill_recovery_evidence_supported(
            field_path=field_path,
            proposed_numeric=proposed_numeric,
            current_structured_data=current_structured_data,
            haystack_text=haystack_text,
        )
    return False


def _bank_statement_recovery_evidence_supported(
    *,
    field_path: str,
    evidence_text: Any,
    current_value: Any,
    proposed_value: Any,
    proposed_numeric: Optional[float],
    current_structured_data: dict[str, Any],
    haystack_text: str,
) -> bool:
    if proposed_numeric is None:
        return False

    if any(term in _normalize_text(haystack_text) for term in _candidate_search_terms(proposed_value)):
        return True

    normalized_path = _normalise_field_path(field_path)
    match = re.fullmatch(r"transactions\.(\d+)\.(debit|credit|balance)", normalized_path)
    if not match:
        return False

    row_index = int(match.group(1))
    row_field = match.group(2)
    transactions = current_structured_data.get("transactions") or []
    if row_index >= len(transactions) or row_index < 0:
        return False

    transactions = copy.deepcopy(transactions)
    row = transactions[row_index]
    if not isinstance(row, dict):
        return False
    row[row_field] = proposed_numeric

    opening_balance = _coerce_numeric(current_structured_data.get("opening_balance"))
    previous_balance = opening_balance
    consistency_checks = 0
    consistency_failures = 0
    for index, txn in enumerate(transactions):
        if not isinstance(txn, dict):
            continue
        debit = _coerce_numeric(txn.get("debit")) or 0.0
        credit = _coerce_numeric(txn.get("credit") if txn.get("credit") not in (None, "") else txn.get("amount")) or 0.0
        balance = _coerce_numeric(txn.get("balance"))
        if previous_balance is not None and balance is not None:
            consistency_checks += 1
            expected_balance = round(previous_balance - debit + credit, 2)
            if abs(expected_balance - balance) > 1.0:
                consistency_failures += 1
        if balance is not None:
            previous_balance = balance
        elif previous_balance is not None:
            previous_balance = round(previous_balance - debit + credit, 2)

    if consistency_checks == 0 or consistency_failures > 0:
        return False

    evidence_norm = _normalize_text(evidence_text)
    row_tokens = []
    for token_key in ("date", "description"):
        token_value = row.get(token_key)
        token_norm = _normalize_text(token_value)
        if len(token_norm) >= 4:
            row_tokens.append(token_norm)
    return any(token in evidence_norm or token in _normalize_text(haystack_text) for token in row_tokens)


def _invoice_style_recovery_evidence_supported(
    *,
    field_path: str,
    evidence_text: Any,
    proposed_value: Any,
    proposed_numeric: Optional[float],
    current_structured_data: dict[str, Any],
    haystack_text: str,
) -> bool:
    if proposed_numeric is None:
        return False
    normalized_path = _normalise_field_path(field_path)
    if normalized_path not in {"subtotal", "tax", "total"}:
        return False

    subtotal = proposed_numeric if normalized_path == "subtotal" else _coerce_numeric(current_structured_data.get("subtotal"))
    tax = proposed_numeric if normalized_path == "tax" else _coerce_numeric(current_structured_data.get("tax"))
    total = proposed_numeric if normalized_path == "total" else _coerce_numeric(current_structured_data.get("total"))
    if subtotal is None or tax is None or total is None:
        return False
    if abs((subtotal + tax) - total) > 1.0:
        return False

    evidence_norm = _normalize_text(evidence_text)
    field_label = normalized_path.replace("_", " ")
    return field_label in evidence_norm or field_label in _normalize_text(haystack_text)


def _payslip_recovery_evidence_supported(
    *,
    field_path: str,
    proposed_numeric: Optional[float],
    current_structured_data: dict[str, Any],
    haystack_text: str,
) -> bool:
    normalized_path = _normalise_field_path(field_path)
    if proposed_numeric is None or normalized_path not in {"total_earnings", "total_deductions", "net_pay"}:
        return False
    total_earnings = proposed_numeric if normalized_path == "total_earnings" else _coerce_numeric(current_structured_data.get("total_earnings"))
    total_deductions = proposed_numeric if normalized_path == "total_deductions" else _coerce_numeric(current_structured_data.get("total_deductions"))
    net_pay = proposed_numeric if normalized_path == "net_pay" else _coerce_numeric(current_structured_data.get("net_pay"))
    if total_earnings is None or total_deductions is None or net_pay is None:
        return False
    if abs((total_earnings - total_deductions) - net_pay) > 1.0:
        return False
    return any(term in _normalize_text(haystack_text) for term in _candidate_search_terms(proposed_numeric))


def _balance_sheet_recovery_evidence_supported(
    *,
    field_path: str,
    proposed_numeric: Optional[float],
    current_structured_data: dict[str, Any],
    haystack_text: str,
) -> bool:
    normalized_path = _normalise_field_path(field_path)
    if proposed_numeric is None or normalized_path not in {"assets.total_assets", "equity_and_liabilities.total_equity_and_liabilities"}:
        return False
    total_assets = proposed_numeric if normalized_path == "assets.total_assets" else _coerce_numeric(((current_structured_data.get("assets") or {}).get("total_assets")))
    total_equity = proposed_numeric if normalized_path == "equity_and_liabilities.total_equity_and_liabilities" else _coerce_numeric(((current_structured_data.get("equity_and_liabilities") or {}).get("total_equity_and_liabilities")))
    if total_assets is None or total_equity is None:
        return False
    if abs(total_assets - total_equity) > 1.0:
        return False
    return any(term in _normalize_text(haystack_text) for term in _candidate_search_terms(proposed_numeric))


def _marksheet_recovery_evidence_supported(
    *,
    field_path: str,
    proposed_numeric: Optional[float],
    current_structured_data: dict[str, Any],
    haystack_text: str,
) -> bool:
    normalized_path = _normalise_field_path(field_path)
    if proposed_numeric is None or normalized_path not in {"total_marks", "max_total_marks", "percentage"}:
        return False
    total_marks = proposed_numeric if normalized_path == "total_marks" else _coerce_numeric(current_structured_data.get("total_marks"))
    max_total_marks = proposed_numeric if normalized_path == "max_total_marks" else _coerce_numeric(current_structured_data.get("max_total_marks"))
    percentage = proposed_numeric if normalized_path == "percentage" else _coerce_numeric(current_structured_data.get("percentage"))
    if total_marks is None or max_total_marks is None or percentage is None or max_total_marks == 0:
        return False
    expected_percentage = round((total_marks / max_total_marks) * 100, 2)
    if abs(expected_percentage - percentage) > 1.0:
        return False
    return any(term in _normalize_text(haystack_text) for term in _candidate_search_terms(proposed_numeric))


def _utility_bill_recovery_evidence_supported(
    *,
    field_path: str,
    proposed_numeric: Optional[float],
    current_structured_data: dict[str, Any],
    haystack_text: str,
) -> bool:
    normalized_path = _normalise_field_path(field_path)
    if proposed_numeric is None or normalized_path not in {"units_consumed", "total_amount"}:
        return False
    if normalized_path == "units_consumed":
        previous_reading = _coerce_numeric(current_structured_data.get("previous_reading"))
        current_reading = _coerce_numeric(current_structured_data.get("current_reading"))
        if previous_reading is None or current_reading is None:
            return False
        if abs((current_reading - previous_reading) - proposed_numeric) > 1.0:
            return False
    return any(term in _normalize_text(haystack_text) for term in _candidate_search_terms(proposed_numeric))


def _resolve_recovery_document_type(result: dict[str, Any]) -> str:
    classified_type = str(result.get("classification", {}).get("document_type") or "").strip().lower()
    if classified_type in config.AI_RECOVERY_IN_SCOPE_TYPES:
        return classified_type

    metadata = result.get("metadata") or {}
    filename = str(metadata.get("filename") or "")
    raw_text = str((result.get("text") or {}).get("raw") or "")
    inferred_type = _infer_in_scope_document_type(filename=filename, raw_text=raw_text)
    return inferred_type or classified_type


def _infer_in_scope_document_type(*, filename: str, raw_text: str) -> str:
    sample = _normalize_text(f"{filename} {raw_text}")
    if not sample:
        return ""

    scores = {
        "invoice": 0.0,
        "bank_statement": 0.0,
        "purchase_order": 0.0,
        "retail_receipt": 0.0,
        "payslip": 0.0,
        "balance_sheet": 0.0,
        "marksheet": 0.0,
        "utility_bill": 0.0,
    }
    invoice_rules = [
        (r"\binvoice\b", 2.5),
        (r"\btax invoice\b", 3.0),
        (r"\binvoice number\b", 2.0),
        (r"\bgstin\b", 1.0),
        (r"\bsubtotal\b", 1.0),
        (r"\btotal\b", 1.0),
        (r"\bbill to\b", 1.0),
    ]
    bank_statement_rules = [
        (r"\bbank statement\b", 3.0),
        (r"\baccount statement\b", 3.0),
        (r"\bclosing balance\b", 2.0),
        (r"\bopening balance\b", 2.0),
        (r"\baccount number\b", 1.5),
        (r"\bdebit\b", 1.0),
        (r"\bcredit\b", 1.0),
        (r"\bwithdrawal\b", 0.8),
    ]
    purchase_order_rules = [
        (r"\bpurchase order\b", 3.0),
        (r"\bpo\s*(no|number)\b", 2.0),
        (r"\bdelivery date\b", 1.5),
        (r"\bbuyer\b", 1.0),
        (r"\bvendor\b", 1.0),
    ]
    retail_receipt_rules = [
        (r"\breceipt\b", 2.5),
        (r"\breceipt\s*(no|number)\b", 2.0),
        (r"\bpayment method\b", 1.2),
        (r"\bcashier\b", 1.0),
        (r"\bsubtotal\b", 1.0),
    ]
    payslip_rules = [
        (r"\bpayslip\b", 3.0),
        (r"\bsalary slip\b", 3.0),
        (r"\bnet pay\b", 2.0),
        (r"\bearnings\b", 1.5),
        (r"\bdeductions\b", 1.5),
    ]
    balance_sheet_rules = [
        (r"\bbalance sheet\b", 3.5),
        (r"\bassets\b", 1.5),
        (r"\bequity and liabilities\b", 2.0),
        (r"\btotal assets\b", 1.5),
    ]
    marksheet_rules = [
        (r"\bmarksheet\b", 3.0),
        (r"\bmark sheet\b", 3.0),
        (r"\bsubject\b", 1.2),
        (r"\btotal marks\b", 1.2),
        (r"\bresult\b", 1.0),
    ]
    utility_bill_rules = [
        (r"\belectricity bill\b", 3.0),
        (r"\bwater bill\b", 3.0),
        (r"\bgas bill\b", 3.0),
        (r"\bconsumer number\b", 1.5),
        (r"\bdue date\b", 1.2),
        (r"\bmeter\b", 1.0),
    ]

    for pattern, weight in invoice_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["invoice"] += weight
    for pattern, weight in bank_statement_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["bank_statement"] += weight
    for pattern, weight in purchase_order_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["purchase_order"] += weight
    for pattern, weight in retail_receipt_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["retail_receipt"] += weight
    for pattern, weight in payslip_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["payslip"] += weight
    for pattern, weight in balance_sheet_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["balance_sheet"] += weight
    for pattern, weight in marksheet_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["marksheet"] += weight
    for pattern, weight in utility_bill_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["utility_bill"] += weight

    best_type, best_score = max(scores.items(), key=lambda item: item[1])
    return best_type if best_score >= 2.5 else ""


def _refresh_confidence(candidate_result: dict[str, Any], *, document_type: str) -> None:
    structured_data = candidate_result.get("structured_data")
    if not isinstance(structured_data, dict):
        return

    schema_coverage_confidence = None
    agent = _get_ai_agent()
    if agent is not None:
        try:
            schema_coverage_confidence = agent.calculate_extraction_confidence(
                structured_data,
                document_type,
            )
            candidate_result["schema_coverage_confidence"] = schema_coverage_confidence
            candidate_result["extraction_confidence"] = schema_coverage_confidence
        except Exception as exc:
            logger.debug(f"Failed to refresh extraction confidence during recovery: {exc}")

    scorer = _get_confidence_scorer()
    if scorer is not None:
        try:
            metadata = candidate_result.get("metadata") or {}
            review = candidate_result.get("review") or {}
            signals = review.get("signals") if isinstance(review, dict) else {}
            ocr_confidence = None
            if isinstance(signals, dict):
                ocr_confidence = signals.get("ocr_confidence")
            extraction_metadata = {}
            if ocr_confidence is not None:
                extraction_metadata["ocr_confidence"] = ocr_confidence
            candidate_result["comprehensive_confidence"] = scorer.calculate_comprehensive_confidence(
                structured_data,
                document_type,
                extraction_metadata=extraction_metadata,
            )
            candidate_result["extraction_confidence"] = candidate_result["comprehensive_confidence"]["overall_confidence"]
        except Exception as exc:
            logger.debug(f"Failed to refresh comprehensive confidence during recovery: {exc}")


def _evaluate_candidate_recovery(
    *,
    before_report,
    after_report,
    document_type: str,
    candidate_data: dict[str, Any],
    changes: list[dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    before_confidence = float(before_report.confidence_score or 0.0)
    after_confidence = float(after_report.confidence_score or 0.0)
    confidence_improvement = round(after_confidence - before_confidence, 3)
    blockers = []
    actual_value_changes = [
        change
        for change in changes
        if not _values_equivalent(change.get("old_value"), change.get("proposed_value"))
    ]

    required_fields = REQUIRED_AUTO_ACCEPT_FIELDS_BY_DOCUMENT_TYPE.get(document_type, set())
    missing_required = [
        field_path
        for field_path in required_fields
        if _is_blank(_get_nested_value(candidate_data, field_path))
    ]
    if missing_required:
        blockers.append(f"missing_required_fields:{','.join(sorted(missing_required))}")

    severe_validation_errors = _find_severe_validation_blockers(
        document_type=document_type,
        report=after_report,
    )
    blockers.extend(severe_validation_errors)

    unsupported_critical = [
        change["field_path"]
        for change in changes
        if change.get("is_critical") and not change.get("evidence_supported")
    ]
    if unsupported_critical:
        blockers.append("unsupported_critical_changes:" + ",".join(sorted(unsupported_critical)))

    scorer = _get_confidence_scorer()
    consistency_score = None
    post_repair_overall_confidence = None
    if scorer is not None:
        try:
            post_repair_confidence = scorer.calculate_comprehensive_confidence(
                candidate_data,
                document_type,
            )
            consistency_score = float(post_repair_confidence["metrics"].get("consistency", 1.0))
            post_repair_overall_confidence = float(post_repair_confidence.get("overall_confidence", 0.0))
        except Exception as exc:
            logger.debug(f"Failed to compute post-repair confidence guardrail: {exc}")

    if consistency_score is not None and consistency_score < 0.8:
        blockers.append(f"low_consistency_score:{consistency_score:.3f}")

    if post_repair_overall_confidence is not None and post_repair_overall_confidence < config.AI_RECOVERY_MIN_ACCEPT_CONFIDENCE:
        blockers.append(f"low_overall_confidence:{post_repair_overall_confidence:.3f}")

    if not actual_value_changes:
        blockers.append("no_material_changes")

    accepted = False
    if not blockers and after_confidence >= config.AI_RECOVERY_MIN_ACCEPT_CONFIDENCE:
        if confidence_improvement >= config.AI_RECOVERY_MIN_IMPROVEMENT:
            accepted = True
        elif len(actual_value_changes) == 1 and after_confidence > before_confidence:
            accepted = True

    return accepted, {
        "confidence_before": before_confidence,
        "confidence_after": after_confidence,
        "confidence_improvement": confidence_improvement,
        "blockers": blockers,
        "missing_required_fields": missing_required,
        "changed_fields": [change["field_path"] for change in actual_value_changes],
        "consistency_score": consistency_score,
        "post_repair_overall_confidence": post_repair_overall_confidence,
    }


def _find_severe_validation_blockers(*, document_type: str, report) -> list[str]:
    blockers = []
    for item in report.error_log:
        field = str(item.field or "").lower()
        message = str(item.message or "").lower()
        if "required" in message or "missing" in message:
            blockers.append(f"missing:{field or 'document'}")
            continue
        if "date" in field and ("invalid" in message or "parse" in message):
            blockers.append(f"invalid_date:{field}")
            continue
        if document_type == "invoice" and any(token in (field + " " + message) for token in ("subtotal", "tax", "total", "amount")):
            if "mismatch" in message or "inconsisten" in message:
                blockers.append("invoice_amount_mismatch")
                continue
        if document_type == "bank_statement" and "balance" in (field + " " + message):
            blockers.append("bank_balance_inconsistency")
            continue
    return sorted(set(blockers))


def _set_nested_value(payload: dict[str, Any], field_path: str, value: Any) -> None:
    current: Any = payload
    parts = _normalise_field_path(field_path).split(".")

    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        next_part = parts[index + 1] if not is_last else None

        if isinstance(current, list):
            if not part.isdigit():
                raise ValueError(f"Invalid list path segment '{part}' in '{field_path}'")
            target_index = int(part)
            while len(current) <= target_index:
                current.append([] if next_part and next_part.isdigit() else {})
            if is_last:
                current[target_index] = value
                return
            if not isinstance(current[target_index], (dict, list)):
                current[target_index] = [] if next_part and next_part.isdigit() else {}
            current = current[target_index]
            continue

        if is_last:
            current[part] = value
            return
        if part not in current or not isinstance(current[part], (dict, list)):
            current[part] = [] if next_part and next_part.isdigit() else {}
        current = current[part]


def _get_nested_value(payload: Any, field_path: str) -> Any:
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


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and not value:
        return True
    return False


def _values_equivalent(left: Any, right: Any) -> bool:
    left_num = _coerce_numeric(left)
    right_num = _coerce_numeric(right)
    if left_num is not None and right_num is not None:
        return abs(left_num - right_num) <= 0.01

    left_date = _normalize_date_value(left)
    right_date = _normalize_date_value(right)
    if left_date and right_date:
        return left_date == right_date

    return _normalize_text(left) == _normalize_text(right)


def _attempt_to_dict(attempt: models.RecoveryAttempt) -> dict[str, Any]:
    return {
        "attempt_id": str(attempt.id),
        "attempt_number": attempt.attempt_number,
        "mode": attempt.mode,
        "strategy": attempt.strategy,
        "status": attempt.status,
        "accepted": attempt.accepted,
        "improvement_score": attempt.improvement_score,
        "failure_reason": attempt.failure_reason,
    }


def _normalise_field_path(field_path: str) -> str:
    return re.sub(r"\[(\d+)\]", r".\1", field_path or "")
