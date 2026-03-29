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
UNRECOVERABLE_FIELD_PATHS = {"transactions", "line_items", DEFAULT_DOCUMENT_REVIEW_FIELD}

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

    for attempt_index in range(1, max(1, config.AI_RECOVERY_MAX_ATTEMPTS) + 1):
        attempt_fields = _select_recoverable_fields(
            build_review_field_items_from_validation(
                document_type=document_type,
                structured_data=current_result.get("structured_data") or {},
                confidence_data=current_result.get("comprehensive_confidence") or {},
                validation_summary=summarize_validation_report(current_report, current_decision),
                validation_errors=_serialize_validation_errors(current_report),
            )
        )
        if not attempt_fields:
            break

        attempt_fields = attempt_fields[: max(1, config.AI_RECOVERY_MAX_FIELDS_PER_ATTEMPT)]
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
            )
            verified_changes, rejected_changes = _verify_repair_changes(
                attempt_fields=attempt_fields,
                raw_text=raw_text,
                repair_result=repair_result,
            )

            if not verified_changes:
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
        if any(part.isdigit() for part in _normalise_field_path(field_path).split(".")):
            continue
        recoverable.append(item)
    return recoverable


def _verify_repair_changes(
    *,
    attempt_fields: list[dict[str, Any]],
    raw_text: str,
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
            raw_text=raw_text,
            evidence_text=evidence_text,
            proposed_value=proposed_value,
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


def _evidence_supported(*, raw_text: str, evidence_text: Any, proposed_value: Any) -> bool:
    normalized_text = _normalize_text(raw_text)
    evidence_candidates = []
    if evidence_text:
        evidence_candidates.append(str(evidence_text))
    if proposed_value not in (None, "", [], {}):
        evidence_candidates.append(str(proposed_value))

    for candidate in evidence_candidates:
        normalized_candidate = _normalize_text(candidate)
        if len(normalized_candidate) >= 4 and normalized_candidate in normalized_text:
            return True
    return False


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text)


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

    for pattern, weight in invoice_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["invoice"] += weight
    for pattern, weight in bank_statement_rules:
        if re.search(pattern, sample, flags=re.IGNORECASE):
            scores["bank_statement"] += weight

    best_type, best_score = max(scores.items(), key=lambda item: item[1])
    return best_type if best_score >= 2.5 else ""


def _refresh_confidence(candidate_result: dict[str, Any], *, document_type: str) -> None:
    structured_data = candidate_result.get("structured_data")
    if not isinstance(structured_data, dict):
        return

    agent = _get_ai_agent()
    if agent is not None:
        try:
            candidate_result["extraction_confidence"] = agent.calculate_extraction_confidence(
                structured_data,
                document_type,
            )
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

    accepted = False
    if not blockers and after_confidence >= config.AI_RECOVERY_MIN_ACCEPT_CONFIDENCE:
        if confidence_improvement >= config.AI_RECOVERY_MIN_IMPROVEMENT:
            accepted = True
        elif len(changes) == 1 and after_confidence > before_confidence:
            accepted = True

    return accepted, {
        "confidence_before": before_confidence,
        "confidence_after": after_confidence,
        "confidence_improvement": confidence_improvement,
        "blockers": blockers,
        "missing_required_fields": missing_required,
        "changed_fields": [change["field_path"] for change in changes],
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
        if isinstance(current, list):
            raise ValueError(f"Recovery does not support list-path updates for '{field_path}'")
        if is_last:
            current[part] = value
            return
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
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
