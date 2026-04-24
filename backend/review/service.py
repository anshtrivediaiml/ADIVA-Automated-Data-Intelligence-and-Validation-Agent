from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import Text, cast, func, or_

from api.models.responses import (
    FieldCorrectionResponse,
    ResultFlaggedFieldResponse,
    ReviewCaseDetailResponse,
    ReviewCaseListItem,
    ReviewFieldItemResponse,
)
from db import models
from logger import logger
from schemas import get_schema
from workflow_contract import JobState, requires_review
import config

IN_SCOPE_DOCUMENT_TYPES = {"invoice", "bank_statement"}

CRITICAL_FIELDS_BY_DOCUMENT_TYPE = {
    "invoice": {
        "invoice_number",
        "invoice_date",
        "vendor.name",
        "total",
        "subtotal",
        "tax",
    },
    "bank_statement": {
        "bank_name",
        "account_holder",
        "account_number",
        "statement_period.from_date",
        "statement_period.to_date",
        "opening_balance",
        "closing_balance",
        "transactions",
    },
}

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

DEFAULT_DOCUMENT_REVIEW_FIELD = "__document__"
FIELD_DECISION_ACTIONS = {"corrected", "accept_original", "accept_ai_proposal"}
NON_REVIEWABLE_FIELD_PREFIXES = (
    "metadata.",
    "ocr_run_summary.",
    "review_summary.",
    "text.raw",
)

FIELD_REASON_RANK = {
    "missing_critical_field": 0,
    "unsupported_ai_change": 1,
    "math_consistency_failed": 2,
    "amount_mismatch": 3,
    "date_parse_uncertain": 4,
    "low_ocr_support": 5,
    "classification_ambiguous": 6,
    "validation_rule_failed": 7,
    "conflicting_candidate_values": 8,
    "schema_coverage_low": 9,
}

FIELD_REASON_SUMMARIES = {
    "missing_critical_field": "Critical field is missing and needs confirmation.",
    "unsupported_ai_change": "AI suggestion could not be applied safely.",
    "math_consistency_failed": "Values do not reconcile mathematically.",
    "amount_mismatch": "An amount or total does not match related values.",
    "date_parse_uncertain": "Date looks plausible but needs human confirmation.",
    "low_ocr_support": "OCR evidence is too weak to trust this field fully.",
    "classification_ambiguous": "Document classification needs confirmation.",
    "validation_rule_failed": "Validation rule failed and needs review.",
    "conflicting_candidate_values": "Multiple conflicting values were detected.",
    "schema_coverage_low": "Required schema coverage is too low.",
}


def create_or_update_review_case(
    db,
    *,
    extraction: models.Extraction,
    document: Optional[models.Document],
    document_type: Optional[str],
    structured_data: Optional[dict[str, Any]],
    confidence_data: Optional[dict[str, Any]],
    validation_summary: Optional[dict[str, Any]],
    validation_errors: Optional[list[dict[str, Any]]],
    raw_text: Optional[str] = None,
) -> Optional[models.ReviewCase]:
    if not requires_review(extraction.status):
        return None

    review_case = (
        db.query(models.ReviewCase)
        .filter(models.ReviewCase.extraction_id == extraction.id)
        .first()
    )
    if review_case and review_case.status == "resolved":
        return review_case

    field_items = build_review_field_items_from_validation(
        document_type=document_type,
        structured_data=structured_data or {},
        confidence_data=confidence_data or {},
        validation_summary=validation_summary or {},
        validation_errors=validation_errors or [],
    )
    field_items, ai_triage_summary = _triage_review_field_items_with_ai(
        document_type=document_type,
        structured_data=structured_data or {},
        confidence_data=confidence_data or {},
        validation_summary=validation_summary or {},
        validation_errors=validation_errors or [],
        candidate_field_items=field_items,
        raw_text=raw_text,
    )
    field_items = _ensure_non_empty_review_field_items(
        field_items=field_items,
        validation_summary=validation_summary or {},
        confidence_data=confidence_data or {},
    )
    reason_codes = list((validation_summary or {}).get("reason_codes") or [])
    if not reason_codes:
        reason_codes = sorted({item["reason_code"] for item in field_items}) or ["review_required"]
    priority = _determine_priority(extraction.status, field_items)
    critical_open_field_count = sum(1 for item in field_items if item["is_critical"])
    next_recommended_field = field_items[0]["field_path"] if field_items else None
    review_summary = {
        "locked_scope_applied": document_type in IN_SCOPE_DOCUMENT_TYPES,
        "validation_summary": validation_summary or {},
        "open_field_count": len(field_items),
        "critical_open_field_count": critical_open_field_count,
        "next_recommended_field": next_recommended_field,
        "reason_codes": reason_codes,
        "ai_triage_applied": ai_triage_summary.get("applied", False),
        "ai_triage_summary": ai_triage_summary.get("summary"),
    }

    if review_case is None:
        review_case = models.ReviewCase(
            extraction_id=extraction.id,
            document_id=extraction.document_id,
            user_id=extraction.user_id,
            document_type=document_type,
            status="open",
            priority=priority,
            source_job_status=extraction.status,
            validation_decision=extraction.validation_decision,
            review_reason_codes_jsonb=reason_codes,
            review_summary_jsonb=review_summary,
        )
        db.add(review_case)
        db.flush()
    else:
        db.query(models.FieldCorrection).filter(
            models.FieldCorrection.review_case_id == review_case.id
        ).delete()
        db.query(models.ReviewFieldItem).filter(
            models.ReviewFieldItem.review_case_id == review_case.id
        ).delete()
        review_case.document_id = extraction.document_id
        review_case.user_id = extraction.user_id
        review_case.document_type = document_type
        review_case.status = "open"
        review_case.priority = priority
        review_case.source_job_status = extraction.status
        review_case.validation_decision = extraction.validation_decision
        review_case.review_reason_codes_jsonb = reason_codes
        review_case.review_summary_jsonb = review_summary
        review_case.resolution_notes = None
        review_case.resolved_at = None

    for item in field_items:
        db.add(
            models.ReviewFieldItem(
                review_case_id=review_case.id,
                field_path=item["field_path"],
                status="open",
                reason_code=item["reason_code"],
                is_critical=item["is_critical"],
                field_confidence=item["field_confidence"],
                original_value_jsonb=item["original_value"],
                proposed_value_jsonb=item.get("proposed_value"),
                final_value_jsonb=None,
                evidence_text=item["evidence_text"],
                validation_message=item["validation_message"],
                recovery_attempt_number=None,
            )
        )

    db.add(
        models.AuditLog(
            user_id=extraction.user_id,
            action="review_case_created",
            resource_type="review_case",
            resource_id=str(review_case.id),
            metadata_jsonb={
                "job_id": str(extraction.id),
                "document_id": str(document.id) if document else None,
                "document_type": document_type,
                "source_job_status": extraction.status,
                "reason_codes": reason_codes,
                "open_field_count": len(field_items),
            },
        )
    )

    return review_case


def build_review_field_items_from_validation(
    *,
    document_type: Optional[str],
    structured_data: dict[str, Any],
    confidence_data: dict[str, Any],
    validation_summary: dict[str, Any],
    validation_errors: list[dict[str, Any]],
    collapse_repeated_groups: bool = True,
) -> list[dict[str, Any]]:
    return _build_review_field_items(
        document_type=document_type,
        structured_data=structured_data,
        confidence_data=confidence_data,
        validation_summary=validation_summary,
        validation_errors=validation_errors,
        collapse_repeated_groups=collapse_repeated_groups,
    )


def get_open_review_case_id(db, extraction_id: uuid.UUID | str) -> Optional[str]:
    snapshot = get_open_review_case_snapshot(db, extraction_id)
    return snapshot["review_case_id"] if snapshot else None


def get_open_review_case_snapshot(
    db,
    extraction_id: uuid.UUID | str,
) -> Optional[dict[str, Any]]:
    try:
        extraction_uuid = uuid.UUID(str(extraction_id))
    except (ValueError, TypeError):
        return None

    review_case = (
        db.query(models.ReviewCase)
        .filter(models.ReviewCase.extraction_id == extraction_uuid)
        .filter(models.ReviewCase.status != "resolved")
        .first()
    )
    if not review_case:
        return None

    _ensure_review_case_status(review_case)
    _ensure_review_case_has_field_items(db, review_case)

    open_items = (
        db.query(models.ReviewFieldItem)
        .filter(models.ReviewFieldItem.review_case_id == review_case.id)
        .filter(models.ReviewFieldItem.status == "open")
        .all()
    )
    ordered_open_items = sorted(open_items, key=_review_field_sort_key)
    flagged_fields = [_build_flagged_field_payload(item) for item in ordered_open_items]
    critical_open_field_count = sum(1 for item in ordered_open_items if item.is_critical)
    age_bucket = _age_bucket(review_case.created_at)
    reason_codes = list(review_case.review_reason_codes_jsonb or [])
    review_summary = _build_review_summary(
        open_field_count=len(ordered_open_items),
        resolved_field_count=0,
        critical_open_field_count=critical_open_field_count,
        next_recommended_field=ordered_open_items[0].field_path if ordered_open_items else None,
        age_bucket=age_bucket,
        reason_codes=reason_codes,
    )

    return {
        "review_case_id": str(review_case.id),
        "status": review_case.status,
        "priority": review_case.priority,
        "priority_score": _review_case_priority_score(
            priority=review_case.priority,
            open_field_count=len(ordered_open_items),
            critical_open_field_count=critical_open_field_count,
            age_bucket=age_bucket,
        ),
        "open_field_count": len(ordered_open_items),
        "critical_open_field_count": critical_open_field_count,
        "next_recommended_field": ordered_open_items[0].field_path if ordered_open_items else None,
        "unresolved_review_fields": flagged_fields,
        "reason_codes": reason_codes,
        "age_bucket": age_bucket,
        "review_summary": review_summary,
    }


def attach_recovery_proposals_to_review_case(
    db,
    *,
    review_case: models.ReviewCase,
    proposals: list[dict[str, Any]],
    recovery_attempt_number: Optional[int],
) -> None:
    if not proposals:
        return

    existing_items = {
        item.field_path: item
        for item in db.query(models.ReviewFieldItem)
        .filter(models.ReviewFieldItem.review_case_id == review_case.id)
        .all()
    }

    for proposal in proposals:
        field_path = str(proposal.get("field_path") or "").strip()
        if not field_path:
            continue

        item = _resolve_review_item_for_proposal(existing_items, field_path)
        if item is None:
            continue

        if item.field_path == field_path:
            item.proposed_value_jsonb = proposal.get("proposed_value")
        else:
            item.proposed_value_jsonb = _merge_grouped_proposal_value(
                item.proposed_value_jsonb,
                proposal,
            )
        item.recovery_attempt_number = recovery_attempt_number
        if proposal.get("evidence_text"):
            item.evidence_text = proposal["evidence_text"]
        if proposal.get("reason"):
            existing_message = item.validation_message or ""
            item.validation_message = (
                f"{existing_message} | AI suggestion: {proposal['reason']}".strip(" |")
            )


def _resolve_review_item_for_proposal(
    existing_items: dict[str, models.ReviewFieldItem],
    field_path: str,
):
    exact = existing_items.get(field_path)
    if exact is not None:
        return exact

    normalized_field_path = _normalise_field_path(field_path)
    parent_candidates = []
    for item_path, item in existing_items.items():
        normalized_item_path = _normalise_field_path(item_path)
        if normalized_field_path.startswith(normalized_item_path + "."):
            parent_candidates.append((normalized_item_path.count("."), item))

    if not parent_candidates:
        return None

    parent_candidates.sort(key=lambda entry: entry[0], reverse=True)
    return parent_candidates[0][1]


def _merge_grouped_proposal_value(existing_value: Any, proposal: dict[str, Any]) -> dict[str, Any]:
    bundle = existing_value if isinstance(existing_value, dict) else {}
    changes = list(bundle.get("changes") or [])

    field_path = str(proposal.get("field_path") or "").strip()
    if field_path and not any(str(change.get("field_path") or "").strip() == field_path for change in changes):
        changes.append(
            {
                "field_path": field_path,
                "proposed_value": proposal.get("proposed_value"),
                "evidence_text": proposal.get("evidence_text"),
                "reason": proposal.get("reason"),
                "confidence": proposal.get("confidence"),
            }
        )

    summary = bundle.get("summary")
    if not summary:
        summary = "AI suggested updates for fields within this grouped section."

    return {
        "summary": summary,
        "changes": changes,
    }


def list_review_cases(
    db,
    *,
    user_id,
    page: int,
    page_size: int,
    status: Optional[str] = None,
    document_type: Optional[str] = None,
    search: Optional[str] = None,
):
    count_query = db.query(func.count(models.ReviewCase.id)).filter(models.ReviewCase.user_id == user_id)
    rows_query = (
        db.query(models.ReviewCase, models.Document)
        .join(models.Document, models.ReviewCase.document_id == models.Document.id, isouter=True)
        .filter(models.ReviewCase.user_id == user_id)
    )

    if status:
        normalized_status = _normalize_review_case_status_value(status)
        if normalized_status == "in_progress":
            count_query = count_query.filter(models.ReviewCase.status.in_(["in_progress", "in_review"]))
            rows_query = rows_query.filter(models.ReviewCase.status.in_(["in_progress", "in_review"]))
        else:
            count_query = count_query.filter(models.ReviewCase.status == normalized_status)
            rows_query = rows_query.filter(models.ReviewCase.status == normalized_status)
    if document_type:
        count_query = count_query.filter(models.ReviewCase.document_type == document_type)
        rows_query = rows_query.filter(models.ReviewCase.document_type == document_type)
    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        search_filter = or_(
            models.Document.filename.ilike(pattern),
            models.ReviewCase.document_type.ilike(pattern),
            cast(models.ReviewCase.id, Text).ilike(pattern),
            cast(models.ReviewCase.extraction_id, Text).ilike(pattern),
        )
        count_query = (
            count_query
            .join(models.Document, models.ReviewCase.document_id == models.Document.id, isouter=True)
            .filter(search_filter)
        )
        rows_query = rows_query.filter(search_filter)

    total = int(count_query.scalar() or 0)
    rows = (
        rows_query.order_by(models.ReviewCase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    repaired_cases = False
    for review_case, _ in rows:
        _ensure_review_case_status(review_case)
        repaired_cases = _ensure_review_case_has_field_items(db, review_case) or repaired_cases
    if repaired_cases:
        db.flush()

    case_ids = [review_case.id for review_case, _ in rows]
    field_stats = _get_review_case_field_stats(db, case_ids)

    review_cases = [
        ReviewCaseListItem(
            review_id=str(review_case.id),
            id=str(review_case.id),
            job_id=str(review_case.extraction_id),
            document_id=str(review_case.document_id) if review_case.document_id else None,
            filename=document.filename if document else None,
            file_name=document.filename if document else None,
            document_type=review_case.document_type,
            doc_type=review_case.document_type,
            source_job_status=review_case.source_job_status,
            review_status=review_case.status,
            status=review_case.status,
            priority=review_case.priority,
            priority_score=_review_case_priority_score(
                priority=review_case.priority,
                open_field_count=field_stats.get(review_case.id, {}).get("open", 0),
                critical_open_field_count=field_stats.get(review_case.id, {}).get("critical_open", 0),
                age_bucket=_age_bucket(review_case.created_at),
            ),
            created_at=review_case.created_at,
            updated_at=review_case.updated_at,
            resolved_at=review_case.resolved_at,
            reason_codes=list(review_case.review_reason_codes_jsonb or []),
            open_field_count=field_stats.get(review_case.id, {}).get("open", 0),
            critical_open_field_count=field_stats.get(review_case.id, {}).get("critical_open", 0),
            next_recommended_field=(review_case.review_summary_jsonb or {}).get("next_recommended_field"),
            review_summary=_build_review_summary(
                open_field_count=field_stats.get(review_case.id, {}).get("open", 0),
                resolved_field_count=field_stats.get(review_case.id, {}).get("resolved", 0),
                critical_open_field_count=field_stats.get(review_case.id, {}).get("critical_open", 0),
                next_recommended_field=(review_case.review_summary_jsonb or {}).get("next_recommended_field"),
                age_bucket=_age_bucket(review_case.created_at),
                reason_codes=list(review_case.review_reason_codes_jsonb or []),
            ),
            age_bucket=_age_bucket(review_case.created_at),
        )
        for review_case, document in rows
    ]
    return total, review_cases


def get_review_case_detail(db, *, review_id: str, user_id) -> ReviewCaseDetailResponse:
    review_case = _load_review_case_for_user(db, review_id=review_id, user_id=user_id)
    _ensure_review_case_status(review_case)
    _ensure_review_case_has_field_items(db, review_case)
    return _build_review_case_detail_response(db, review_case)


def apply_review_field_decision(
    db,
    *,
    review_id: str,
    field_item_id: str,
    reviewer: models.User,
    action: str,
    value: Any = None,
    correction_reason: Optional[str] = None,
) -> ReviewCaseDetailResponse:
    if action not in FIELD_DECISION_ACTIONS:
        raise ValueError("Unsupported field decision action")

    review_case = _load_review_case_for_user(db, review_id=review_id, user_id=reviewer.id)
    if review_case.status == "resolved":
        raise ValueError("Review case is already resolved")

    try:
        field_uuid = uuid.UUID(field_item_id)
    except ValueError as exc:
        raise ValueError("Invalid field_item_id") from exc

    field_item = (
        db.query(models.ReviewFieldItem)
        .filter(models.ReviewFieldItem.id == field_uuid)
        .filter(models.ReviewFieldItem.review_case_id == review_case.id)
        .first()
    )
    if not field_item:
        raise ValueError("Review field item not found")

    extraction_result = (
        db.query(models.ExtractionResult)
        .filter(models.ExtractionResult.extraction_id == review_case.extraction_id)
        .first()
    )
    if extraction_result is None:
        raise ValueError("Extraction result not found for review case")

    next_value = _resolve_field_decision_value(field_item, action, value)
    next_status = {
        "corrected": "corrected",
        "accept_original": "accepted_original",
        "accept_ai_proposal": "accepted_ai_proposal",
    }[action]

    if action != "accept_original":
        updated_payload = copy.deepcopy(extraction_result.structured_data_jsonb or {})
        if field_item.field_path != DEFAULT_DOCUMENT_REVIEW_FIELD:
            _set_nested_value(updated_payload, field_item.field_path, next_value)
        extraction_result.structured_data_jsonb = updated_payload

    old_value = field_item.original_value_jsonb
    field_item.final_value_jsonb = next_value
    field_item.status = next_status
    field_item.resolved_at = datetime.now(timezone.utc)

    if action != "accept_original":
        db.add(
            models.FieldCorrection(
                review_case_id=review_case.id,
                review_field_item_id=field_item.id,
                extraction_id=review_case.extraction_id,
                corrected_by_user_id=reviewer.id,
                field_path=field_item.field_path,
                correction_source=action,
                old_value_jsonb=old_value,
                new_value_jsonb=next_value,
                correction_reason=correction_reason,
            )
        )

    review_case.status = "in_progress"
    _update_review_metadata(extraction_result, review_case)
    db.add(
        models.AuditLog(
            user_id=reviewer.id,
            action="review_field_decision",
            resource_type="review_case",
            resource_id=str(review_case.id),
            metadata_jsonb={
                "field_item_id": str(field_item.id),
                "field_path": field_item.field_path,
                "action": action,
                "correction_reason": correction_reason,
            },
        )
    )
    db.commit()
    db.refresh(review_case)
    return _build_review_case_detail_response(db, review_case)


def resolve_review_case(
    db,
    *,
    review_id: str,
    reviewer: models.User,
    resolution_notes: Optional[str] = None,
) -> ReviewCaseDetailResponse:
    review_case = _load_review_case_for_user(db, review_id=review_id, user_id=reviewer.id)
    if review_case.status == "resolved":
        return _build_review_case_detail_response(db, review_case)

    open_items = (
        db.query(models.ReviewFieldItem)
        .filter(models.ReviewFieldItem.review_case_id == review_case.id)
        .filter(models.ReviewFieldItem.status == "open")
        .count()
    )
    if open_items > 0:
        raise ValueError("All review field items must be addressed before resolving the case")

    extraction = (
        db.query(models.Extraction)
        .filter(models.Extraction.id == review_case.extraction_id)
        .first()
    )
    extraction_result = (
        db.query(models.ExtractionResult)
        .filter(models.ExtractionResult.extraction_id == review_case.extraction_id)
        .first()
    )
    if not extraction or not extraction_result:
        raise ValueError("Review case is missing its extraction result")

    review_case.status = "resolved"
    review_case.resolution_notes = resolution_notes
    review_case.resolved_at = datetime.now(timezone.utc)

    extraction.status = JobState.COMPLETED.value
    extraction.review_required = False
    extraction.current_stage = None
    extraction.finished_at = extraction.finished_at or datetime.now(timezone.utc)

    _update_review_metadata(extraction_result, review_case)
    db.add(
        models.AuditLog(
            user_id=reviewer.id,
            action="review_case_resolved",
            resource_type="review_case",
            resource_id=str(review_case.id),
            metadata_jsonb={
                "job_id": str(review_case.extraction_id),
                "resolution_notes": resolution_notes,
            },
        )
    )
    db.commit()
    db.refresh(review_case)
    return _build_review_case_detail_response(db, review_case)


def _load_review_case_for_user(db, *, review_id: str, user_id) -> models.ReviewCase:
    try:
        review_uuid = uuid.UUID(review_id)
    except ValueError as exc:
        raise ValueError("Invalid review_id") from exc

    review_case = (
        db.query(models.ReviewCase)
        .filter(models.ReviewCase.id == review_uuid)
        .filter(models.ReviewCase.user_id == user_id)
        .first()
    )
    if not review_case:
        raise ValueError("Review case not found")
    return review_case


def _build_review_case_detail_response(db, review_case: models.ReviewCase) -> ReviewCaseDetailResponse:
    document = (
        db.query(models.Document)
        .filter(models.Document.id == review_case.document_id)
        .first()
    )
    extraction_result = (
        db.query(models.ExtractionResult)
        .filter(models.ExtractionResult.extraction_id == review_case.extraction_id)
        .first()
    )
    outputs = (
        db.query(models.ExtractionOutput)
        .filter(models.ExtractionOutput.extraction_id == review_case.extraction_id)
        .all()
    )
    field_items = (
        db.query(models.ReviewFieldItem)
        .filter(models.ReviewFieldItem.review_case_id == review_case.id)
        .all()
    )
    corrections = (
        db.query(models.FieldCorrection)
        .filter(models.FieldCorrection.review_case_id == review_case.id)
        .order_by(models.FieldCorrection.created_at.asc())
        .all()
    )

    metadata = (extraction_result.metadata_jsonb or {}) if extraction_result else {}
    validation_summary = metadata.get("validation_summary") if isinstance(metadata, dict) else None
    artifacts = {
        output.format: output.storage_uri
        for output in outputs
        if output.storage_uri
    }
    field_items = sorted(field_items, key=_review_field_sort_key)
    open_field_count = sum(1 for item in field_items if item.status == "open")
    resolved_field_count = sum(1 for item in field_items if item.status != "open")
    critical_open_field_count = sum(
        1 for item in field_items if item.status == "open" and item.is_critical
    )
    next_recommended_field = next(
        (item.field_path for item in field_items if item.status == "open"),
        None,
    )
    priority_score = _review_case_priority_score(
        priority=review_case.priority,
        open_field_count=open_field_count,
        critical_open_field_count=critical_open_field_count,
        age_bucket=_age_bucket(review_case.created_at),
    )
    review_summary = dict(review_case.review_summary_jsonb or {})
    review_summary.update(
        _build_review_summary(
            open_field_count=open_field_count,
            resolved_field_count=resolved_field_count,
            critical_open_field_count=critical_open_field_count,
            next_recommended_field=next_recommended_field,
            age_bucket=_age_bucket(review_case.created_at),
            reason_codes=list(review_case.review_reason_codes_jsonb or []),
        )
    )

    field_payload = [
        _build_review_field_response(item)
        for item in field_items
    ]

    return ReviewCaseDetailResponse(
        review_id=str(review_case.id),
        id=str(review_case.id),
        job_id=str(review_case.extraction_id),
        document_id=str(review_case.document_id) if review_case.document_id else None,
        filename=document.filename if document else None,
        file_name=document.filename if document else None,
        document_type=review_case.document_type,
        doc_type=review_case.document_type,
        source_job_status=review_case.source_job_status,
        review_status=review_case.status,
        status=review_case.status,
        priority=review_case.priority,
        priority_score=priority_score,
        validation_decision=review_case.validation_decision,
        reason_codes=list(review_case.review_reason_codes_jsonb or []),
        review_summary=review_summary,
        validation_summary=validation_summary if isinstance(validation_summary, dict) else None,
        created_at=review_case.created_at,
        updated_at=review_case.updated_at,
        resolved_at=review_case.resolved_at,
        open_field_count=open_field_count,
        resolved_field_count=resolved_field_count,
        critical_open_field_count=critical_open_field_count,
        next_recommended_field=next_recommended_field,
        artifacts=artifacts,
        fields=field_payload,
        review_fields=field_payload,
        corrections=[
            FieldCorrectionResponse(
                correction_id=str(correction.id),
                field_item_id=str(correction.review_field_item_id),
                field_path=correction.field_path,
                correction_source=correction.correction_source,
                old_value=correction.old_value_jsonb,
                new_value=correction.new_value_jsonb,
                correction_reason=correction.correction_reason,
                corrected_by_user_id=str(correction.corrected_by_user_id) if correction.corrected_by_user_id else None,
                created_at=correction.created_at,
            )
            for correction in corrections
        ],
    )


def _build_review_field_items(
    *,
    document_type: Optional[str],
    structured_data: dict[str, Any],
    confidence_data: dict[str, Any],
    validation_summary: dict[str, Any],
    validation_errors: list[dict[str, Any]],
    collapse_repeated_groups: bool,
) -> list[dict[str, Any]]:
    overall_confidence = _safe_float(confidence_data.get("overall_confidence"))
    grouped: dict[str, dict[str, Any]] = {}
    required_fields = set(_get_required_field_paths(document_type))

    for error in validation_errors:
        field_path = str(error.get("field") or "").strip()
        if not _is_reviewable_field_path(field_path):
            continue

        reason_code = _map_error_to_reason_code(error)
        if reason_code == "missing_critical_field" and not _should_escalate_missing_field(
            document_type,
            field_path,
            required_fields,
        ):
            continue

        grouped.setdefault(
            field_path,
            {
                "field_path": field_path,
                "messages": [],
                "reason_codes": [],
                "expected": [],
                "actual": [],
            },
        )
        grouped[field_path]["messages"].append(str(error.get("message") or "Validation issue"))
        grouped[field_path]["reason_codes"].append(reason_code)
        if error.get("expected") is not None:
            grouped[field_path]["expected"].append(str(error["expected"]))
        if error.get("actual") is not None:
            grouped[field_path]["actual"].append(str(error["actual"]))

    if collapse_repeated_groups:
        grouped = _collapse_repeated_indexed_issue_groups(grouped)

    for field_path in _get_required_review_fields(document_type):
        if _is_blank(_get_nested_value(structured_data, field_path)) and field_path not in grouped:
            grouped[field_path] = {
                "field_path": field_path,
                "messages": ["Required critical field is missing from the extracted payload"],
                "reason_codes": ["missing_critical_field"],
                "expected": [],
                "actual": [],
            }

    items: list[dict[str, Any]] = []
    for field_path, payload in grouped.items():
        reason_code = _select_reason_code(payload["reason_codes"])
        is_critical = _is_critical_field(document_type, field_path)
        original_value = (
            None
            if field_path == DEFAULT_DOCUMENT_REVIEW_FIELD
            else _get_nested_value(structured_data, field_path)
        )
        compact_validation_message = _compact_validation_messages(payload["messages"])
        compact_evidence_text = _compact_evidence_text(
            payload["actual"],
            payload["expected"],
        )
        if (
            reason_code in {"validation_rule_failed", "amount_mismatch", "math_consistency_failed"}
            and compact_validation_message is None
        ):
            continue

        items.append(
            {
                "field_path": field_path,
                "reason_code": reason_code,
                "is_critical": is_critical,
                "field_confidence": overall_confidence,
                "original_value": original_value,
                "evidence_text": compact_evidence_text,
                "validation_message": compact_validation_message,
            }
        )

    items.sort(
        key=lambda item: (
            not item["is_critical"],
            _reason_rank(item["reason_code"]),
            item["field_path"],
        )
    )
    return items


def _triage_review_field_items_with_ai(
    *,
    document_type: Optional[str],
    structured_data: dict[str, Any],
    confidence_data: dict[str, Any],
    validation_summary: dict[str, Any],
    validation_errors: list[dict[str, Any]],
    candidate_field_items: list[dict[str, Any]],
    raw_text: Optional[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not raw_text or not raw_text.strip() or not candidate_field_items:
        return candidate_field_items, {"applied": False, "summary": "raw_text_unavailable"}

    ai_agent = _get_ai_triage_agent()
    if ai_agent is None:
        return candidate_field_items, {"applied": False, "summary": "ai_unavailable"}

    allowed_paths = _allowed_ai_triage_field_paths(candidate_field_items)
    candidate_payload = [
        {
            "field_path": item["field_path"],
            "reason_code": item["reason_code"],
            "is_critical": item["is_critical"],
            "original_value": item["original_value"],
            "validation_message": item["validation_message"],
            "evidence_text": item["evidence_text"],
        }
        for item in candidate_field_items
    ]

    try:
        triage_result = ai_agent.triage_review_fields(
            full_text=raw_text,
            document_type=document_type or "unknown",
            structured_data=structured_data,
            candidate_fields=candidate_payload,
            validation_summary=validation_summary,
            validation_errors=validation_errors,
        )
    except Exception as exc:
        logger.warning(f"AI review triage failed for document_type={document_type}: {exc}")
        return candidate_field_items, {"applied": False, "summary": f"ai_error:{exc}"}

    triaged_items = _normalize_ai_triaged_review_fields(
        document_type=document_type,
        structured_data=structured_data,
        confidence_data=confidence_data,
        ai_fields=triage_result.get("review_fields") or [],
        allowed_paths=allowed_paths,
    )
    if not triaged_items:
        return candidate_field_items, {"applied": False, "summary": "ai_no_valid_fields"}

    return triaged_items, {
        "applied": True,
        "summary": triage_result.get("summary") or "ai_triage_applied",
    }


def _allowed_ai_triage_field_paths(candidate_field_items: list[dict[str, Any]]) -> set[str]:
    allowed_paths = {str(item["field_path"]).strip() for item in candidate_field_items if str(item.get("field_path") or "").strip()}
    for field_path in list(allowed_paths):
        normalized = _normalise_field_path(field_path)
        match = re.fullmatch(r"([a-zA-Z0-9_]+)\.\d+\..+", normalized)
        if match:
            allowed_paths.add(match.group(1))
    return allowed_paths


def _normalize_ai_triaged_review_fields(
    *,
    document_type: Optional[str],
    structured_data: dict[str, Any],
    confidence_data: dict[str, Any],
    ai_fields: list[dict[str, Any]],
    allowed_paths: set[str],
) -> list[dict[str, Any]]:
    overall_confidence = _safe_float(confidence_data.get("overall_confidence"))
    normalized_items: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for item in ai_fields:
        field_path = str(item.get("field_path") or "").strip()
        reason_code = str(item.get("reason_code") or "").strip()
        if not field_path or field_path in seen_paths or field_path not in allowed_paths:
            continue
        if reason_code not in FIELD_REASON_RANK:
            continue

        normalized_items.append(
            {
                "field_path": field_path,
                "reason_code": reason_code,
                "is_critical": _is_critical_field(document_type, field_path),
                "field_confidence": overall_confidence,
                "original_value": None if field_path == DEFAULT_DOCUMENT_REVIEW_FIELD else _get_nested_value(structured_data, field_path),
                "proposed_value": item.get("proposed_value"),
                "evidence_text": _compact_single_message(item.get("evidence_text"), max_length=220),
                "validation_message": _compact_single_message(item.get("validation_message"), max_length=220),
            }
        )
        seen_paths.add(field_path)

    normalized_items.sort(
        key=lambda item: (
            not item["is_critical"],
            _reason_rank(item["reason_code"]),
            item["field_path"],
        )
    )
    return normalized_items


def _collapse_repeated_indexed_issue_groups(
    grouped: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed_groups: dict[tuple[str, str, str], list[str]] = {}

    for field_path, payload in grouped.items():
        normalized = _normalise_field_path(field_path)
        match = re.fullmatch(r"([a-zA-Z0-9_]+)\.(\d+)\.(.+)", normalized)
        if not match:
            continue

        collection_path = match.group(1)
        leaf_path = match.group(3)
        reason_code = _select_reason_code(payload.get("reason_codes", []))
        indexed_groups.setdefault((collection_path, leaf_path, reason_code), []).append(field_path)

    for (collection_path, leaf_path, reason_code), field_paths in indexed_groups.items():
        if len(field_paths) < 3:
            continue

        collapsed_expected: list[str] = []
        collapsed_actual: list[str] = []
        for field_path in sorted(field_paths, key=_normalise_field_path):
            payload = grouped.pop(field_path)
            collapsed_expected.extend(payload.get("expected", []))
            collapsed_actual.extend(payload.get("actual", []))

        existing = grouped.get(collection_path)
        existing_messages = list(existing.get("messages", [])) if existing else []
        grouped[collection_path] = {
            "field_path": collection_path,
            "messages": existing_messages + [
                f"Multiple '{leaf_path}' entries in '{collection_path}' show the same validation problem. Review this repeated sequence as one issue."
            ],
            "reason_codes": list(existing.get("reason_codes", [])) + [reason_code] if existing else [reason_code],
            "expected": list(existing.get("expected", [])) + collapsed_expected if existing else collapsed_expected,
            "actual": list(existing.get("actual", [])) + collapsed_actual if existing else collapsed_actual,
        }

    return grouped


def _ensure_non_empty_review_field_items(
    *,
    field_items: list[dict[str, Any]],
    validation_summary: dict[str, Any],
    confidence_data: dict[str, Any],
) -> list[dict[str, Any]]:
    if field_items:
        return field_items
    return [
        _build_document_level_review_item(
            validation_summary=validation_summary,
            reason_codes=list(validation_summary.get("reason_codes") or []),
            field_confidence=_safe_float(confidence_data.get("overall_confidence")),
        )
    ]


def _ensure_review_case_has_field_items(db, review_case: models.ReviewCase) -> bool:
    if not review_case or review_case.status == "resolved":
        return False

    existing_count = (
        db.query(models.ReviewFieldItem)
        .filter(models.ReviewFieldItem.review_case_id == review_case.id)
        .count()
    )
    if existing_count > 0:
        return False

    review_summary = review_case.review_summary_jsonb if isinstance(review_case.review_summary_jsonb, dict) else {}
    validation_summary = review_summary.get("validation_summary") if isinstance(review_summary, dict) else {}
    fallback_item = _build_document_level_review_item(
        validation_summary=validation_summary if isinstance(validation_summary, dict) else {},
        reason_codes=list(review_case.review_reason_codes_jsonb or []),
        field_confidence=None,
    )

    db.add(
        models.ReviewFieldItem(
            review_case_id=review_case.id,
            field_path=fallback_item["field_path"],
            status="open",
            reason_code=fallback_item["reason_code"],
            is_critical=fallback_item["is_critical"],
            field_confidence=fallback_item["field_confidence"],
            original_value_jsonb=fallback_item["original_value"],
            proposed_value_jsonb=None,
            final_value_jsonb=None,
            evidence_text=fallback_item["evidence_text"],
            validation_message=fallback_item["validation_message"],
            recovery_attempt_number=None,
        )
    )

    updated_summary = dict(review_summary)
    updated_summary["open_field_count"] = 1
    updated_summary["critical_open_field_count"] = 1
    updated_summary["next_recommended_field"] = DEFAULT_DOCUMENT_REVIEW_FIELD
    review_case.review_summary_jsonb = updated_summary
    return True


def _normalize_review_case_status_value(status: Optional[str]) -> Optional[str]:
    if status == "in_review":
        return "in_progress"
    return status


_ai_triage_agent = None


def _get_ai_triage_agent():
    global _ai_triage_agent
    if _ai_triage_agent is not None:
        return _ai_triage_agent
    try:
        if not config.MISTRAL_API_KEY:
            return None
        from ai_agent import AIAgent

        _ai_triage_agent = AIAgent()
        return _ai_triage_agent
    except Exception as exc:
        logger.warning(f"AI review triage agent unavailable: {exc}")
        return None


def _ensure_review_case_status(review_case: models.ReviewCase) -> bool:
    normalized_status = _normalize_review_case_status_value(review_case.status)
    if normalized_status == review_case.status:
        return False
    review_case.status = normalized_status
    return True


def _build_document_level_review_item(
    *,
    validation_summary: dict[str, Any],
    reason_codes: list[str],
    field_confidence: Optional[float],
) -> dict[str, Any]:
    return {
        "field_path": DEFAULT_DOCUMENT_REVIEW_FIELD,
        "reason_code": _default_review_field_reason_code(reason_codes),
        "is_critical": True,
        "field_confidence": field_confidence,
        "original_value": None,
        "evidence_text": _document_level_review_evidence(validation_summary),
        "validation_message": _document_level_review_message(validation_summary, reason_codes),
    }
 

def _default_review_field_reason_code(reason_codes: list[str]) -> str:
    normalized = [str(reason).strip().lower() for reason in reason_codes if str(reason).strip()]
    if any("schema" in reason for reason in normalized):
        return "schema_coverage_low"
    if any(
        token in reason
        for reason in normalized
        for token in ("classification", "document_type", "unsupported_document_type")
    ):
        return "classification_ambiguous"
    if any("ocr" in reason for reason in normalized):
        return "low_ocr_support"
    return "validation_rule_failed"


def _document_level_review_message(
    validation_summary: dict[str, Any],
    reason_codes: list[str],
) -> str:
    review_reasons = validation_summary.get("review_reasons") if isinstance(validation_summary, dict) else []
    if isinstance(review_reasons, list):
        joined = " ".join(str(reason).strip() for reason in review_reasons if str(reason).strip())
        compact = _compact_single_message(joined)
        if compact:
            return compact

    if reason_codes:
        pretty_codes = ", ".join(str(code).replace("_", " ") for code in reason_codes[:3])
        return f"Document requires manual review due to: {pretty_codes}."

    return "Document requires manual review before it can be finalized."


def _document_level_review_evidence(validation_summary: dict[str, Any]) -> Optional[str]:
    if not isinstance(validation_summary, dict):
        return None

    details = []
    decision = validation_summary.get("decision")
    if decision:
        details.append(f"Decision: {decision}")
    confidence_score = validation_summary.get("confidence_score")
    if isinstance(confidence_score, (int, float)):
        details.append(f"Confidence: {confidence_score:.2f}")
    return " | ".join(details) if details else None


def _determine_priority(extraction_status: str, field_items: Iterable[dict[str, Any]]) -> str:
    if extraction_status == JobState.LOW_CONFIDENCE.value:
        return "high"
    if any(item["is_critical"] for item in field_items):
        return "high"
    return "normal"


def _get_open_field_counts(db, case_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not case_ids:
        return {}

    rows = (
        db.query(models.ReviewFieldItem.review_case_id, models.ReviewFieldItem.id)
        .filter(models.ReviewFieldItem.review_case_id.in_(case_ids))
        .filter(models.ReviewFieldItem.status == "open")
        .all()
    )
    counts: dict[uuid.UUID, int] = {}
    for review_case_id, _ in rows:
        counts[review_case_id] = counts.get(review_case_id, 0) + 1
    return counts


def _get_review_case_field_stats(
    db,
    case_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, int]]:
    if not case_ids:
        return {}

    rows = (
        db.query(
            models.ReviewFieldItem.review_case_id,
            models.ReviewFieldItem.status,
            models.ReviewFieldItem.is_critical,
        )
        .filter(models.ReviewFieldItem.review_case_id.in_(case_ids))
        .all()
    )
    stats: dict[uuid.UUID, dict[str, int]] = {}
    for review_case_id, status, is_critical in rows:
        case_stats = stats.setdefault(
            review_case_id,
            {"open": 0, "resolved": 0, "critical_open": 0},
        )
        if status == "open":
            case_stats["open"] += 1
            if is_critical:
                case_stats["critical_open"] += 1
        else:
            case_stats["resolved"] += 1
    return stats


def _update_review_metadata(extraction_result: models.ExtractionResult, review_case: models.ReviewCase) -> None:
    metadata = dict(extraction_result.metadata_jsonb or {})
    metadata["review_case"] = {
        "id": str(review_case.id),
        "status": review_case.status,
        "resolved_at": review_case.resolved_at.isoformat() if review_case.resolved_at else None,
    }
    extraction_result.metadata_jsonb = metadata


def _build_review_field_response(item: models.ReviewFieldItem) -> ReviewFieldItemResponse:
    display_label = _field_display_label(item.field_path)
    compact_validation_message = _compact_single_message(item.validation_message)
    evidence_snippet = _compact_single_message(item.evidence_text, max_length=180)
    ui_message = _build_ui_message(item.reason_code, compact_validation_message, display_label)
    return ReviewFieldItemResponse(
        field_item_id=str(item.id),
        id=str(item.id),
        field_path=item.field_path,
        status=item.status,
        reason_code=item.reason_code,
        display_label=display_label,
        label=display_label,
        is_critical=bool(item.is_critical),
        field_confidence=item.field_confidence,
        original_value=item.original_value_jsonb,
        proposed_value=item.proposed_value_jsonb,
        final_value=item.final_value_jsonb,
        evidence_text=evidence_snippet,
        evidence_snippet=evidence_snippet,
        validation_message=compact_validation_message,
        ui_message=ui_message,
        message=ui_message,
        priority_score=_field_priority_score(item),
        recovery_attempt_number=item.recovery_attempt_number,
    )


def _build_flagged_field_payload(item: models.ReviewFieldItem) -> ResultFlaggedFieldResponse:
    display_label = _field_display_label(item.field_path)
    compact_validation_message = _compact_single_message(item.validation_message)
    message = compact_validation_message or FIELD_REASON_SUMMARIES.get(
        item.reason_code,
        "Field needs review.",
    )
    return ResultFlaggedFieldResponse(
        field_item_id=str(item.id),
        id=str(item.id),
        field_path=item.field_path,
        display_label=display_label,
        label=display_label,
        reason_code=item.reason_code,
        validation_message=message,
        message=message,
        original_value=item.original_value_jsonb,
        proposed_value=item.proposed_value_jsonb,
        evidence_text=_compact_single_message(item.evidence_text, max_length=180),
        is_critical=bool(item.is_critical),
        priority_score=_field_priority_score(item),
    )


def _resolve_field_decision_value(field_item: models.ReviewFieldItem, action: str, value: Any) -> Any:
    if action == "accept_original":
        return field_item.original_value_jsonb
    if action == "accept_ai_proposal":
        if field_item.proposed_value_jsonb is None:
            raise ValueError("No AI proposal is available for this field")
        return field_item.proposed_value_jsonb
    if value is None:
        raise ValueError("A corrected value is required for action='corrected'")
    return value


def _map_error_to_reason_code(error: dict[str, Any]) -> str:
    field = str(error.get("field") or "").lower()
    message = str(error.get("message") or "").lower()
    pillar = str(error.get("pillar") or "").lower()

    if "missing" in message or "required" in message:
        return "missing_critical_field"
    if "amount" in field or "tax" in field or "subtotal" in field or "total" in field:
        if "mismatch" in message or "inconsisten" in message:
            return "amount_mismatch"
    if "balance" in field or "balance" in message:
        return "math_consistency_failed"
    if "date" in field or "date" in message:
        return "date_parse_uncertain"
    if "classification" in field or "classif" in message:
        return "classification_ambiguous"
    if "ocr" in message:
        return "low_ocr_support"
    if pillar == "schema_format":
        return "validation_rule_failed"
    if "conflict" in message or "multiple" in message:
        return "conflicting_candidate_values"
    return "validation_rule_failed"


def _select_reason_code(reason_codes: list[str]) -> str:
    priority = [
        "missing_critical_field",
        "unsupported_ai_change",
        "math_consistency_failed",
        "amount_mismatch",
        "date_parse_uncertain",
        "low_ocr_support",
        "classification_ambiguous",
        "validation_rule_failed",
        "schema_coverage_low",
    ]
    for candidate in priority:
        if candidate in reason_codes:
            return candidate
    return reason_codes[0] if reason_codes else "validation_rule_failed"


def _reason_rank(reason_code: str) -> int:
    return FIELD_REASON_RANK.get(reason_code or "", 99)


def _review_field_sort_key(item: models.ReviewFieldItem) -> tuple[Any, ...]:
    return (
        item.status != "open",
        not bool(item.is_critical),
        _reason_rank(item.reason_code),
        item.field_path or "",
    )


def _field_priority_score(item: models.ReviewFieldItem) -> int:
    base = 100 - min(_reason_rank(item.reason_code) * 8, 72)
    if item.is_critical:
        base += 20
    if item.status == "open":
        base += 10
    if item.recovery_attempt_number:
        base += min(item.recovery_attempt_number, 5)
    return max(base, 0)


def _review_case_priority_score(
    *,
    priority: str,
    open_field_count: int,
    critical_open_field_count: int,
    age_bucket: str,
) -> int:
    score = {"low": 20, "normal": 50, "high": 80}.get((priority or "").lower(), 50)
    score += min(open_field_count * 2, 12)
    score += critical_open_field_count * 5
    score += {"fresh": 0, "aging": 4, "stale": 8}.get(age_bucket, 0)
    return score


def _age_bucket(created_at: Optional[datetime]) -> str:
    if created_at is None:
        return "fresh"
    age_hours = max(
        (datetime.now(timezone.utc) - created_at).total_seconds() / 3600.0,
        0.0,
    )
    if age_hours >= 72:
        return "stale"
    if age_hours >= 24:
        return "aging"
    return "fresh"


def _field_display_label(field_path: str) -> str:
    if field_path == DEFAULT_DOCUMENT_REVIEW_FIELD:
        return "Document-level review"
    normalized = _normalise_field_path(field_path)
    label = normalized.replace(".", " / ")
    label = re.sub(r"\b(\d+)\b", r"#\1", label)
    label = label.replace("_", " ")
    label = re.sub(r"\s+", " ", label).strip()
    return label.title()


def _compact_validation_messages(messages: list[str]) -> Optional[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for message in messages:
        compact = _compact_single_message(message)
        if compact and compact not in seen:
            cleaned.append(compact)
            seen.add(compact)
        if len(cleaned) >= 2:
            break
    return " ".join(cleaned) if cleaned else None


def _compact_evidence_text(actual_values: list[str], expected_values: list[str]) -> Optional[str]:
    parts: list[str] = []
    if actual_values:
        actual = ", ".join(str(value).strip() for value in actual_values[:2] if str(value).strip())
        if actual:
            parts.append(f"Observed: {actual}")
    if expected_values:
        expected = ", ".join(str(value).strip() for value in expected_values[:2] if str(value).strip())
        if expected:
            parts.append(f"Expected: {expected}")
    return " | ".join(parts)[:220] or None


def _compact_single_message(message: Optional[str], *, max_length: int = 220) -> Optional[str]:
    if not message:
        return None
    compact = re.sub(r"\s+", " ", str(message)).strip()
    compact = compact.replace(" | ", "; ")
    lowered = compact.lower()
    if any(
        phrase in lowered
        for phrase in (
            "no issue here",
            "initial concern was misplaced",
            "this is correct in the data",
            "which is correct",
            "no arithmetic error detected",
            "appears internally consistent",
        )
    ):
        return None
    if len(compact) > max_length:
        compact = compact[: max_length - 3].rstrip() + "..."
    return compact or None


def _build_ui_message(reason_code: str, validation_message: Optional[str], display_label: str) -> str:
    summary = FIELD_REASON_SUMMARIES.get(reason_code, "Field needs review.")
    if validation_message:
        return f"{display_label}: {validation_message}"
    return f"{display_label}: {summary}"


def _build_review_summary(
    *,
    open_field_count: int,
    resolved_field_count: int,
    critical_open_field_count: int,
    next_recommended_field: Optional[str],
    age_bucket: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "open_field_count": open_field_count,
        "resolved_field_count": resolved_field_count,
        "critical_open_field_count": critical_open_field_count,
        "next_recommended_field": next_recommended_field,
        "age_bucket": age_bucket,
        "reason_codes": reason_codes,
    }


def _is_critical_field(document_type: Optional[str], field_path: str) -> bool:
    if field_path == DEFAULT_DOCUMENT_REVIEW_FIELD:
        return True

    critical_fields = set(CRITICAL_FIELDS_BY_DOCUMENT_TYPE.get(document_type or "", set()))
    critical_fields.update(_get_required_field_paths(document_type))
    for critical_field in critical_fields:
        if field_path == critical_field:
            return True
        if field_path.startswith(critical_field + "."):
            return True
        if critical_field.startswith(field_path + "."):
            return True
    return False


def _get_required_field_paths(document_type: Optional[str]) -> set[str]:
    if not document_type:
        return set()

    schema = get_schema(document_type)
    if not schema:
        return set()
    return {str(field).strip() for field in schema.get_required_fields() if str(field).strip()}


def _get_required_review_fields(document_type: Optional[str]) -> set[str]:
    required_fields = set(REQUIRED_AUTO_ACCEPT_FIELDS_BY_DOCUMENT_TYPE.get(document_type or "", set()))
    required_fields.update(_get_required_field_paths(document_type))
    return required_fields


def _should_escalate_missing_field(
    document_type: Optional[str],
    field_path: str,
    required_fields: set[str],
) -> bool:
    if field_path in required_fields:
        return True
    return _is_critical_field(document_type, field_path)


def _is_reviewable_field_path(field_path: str) -> bool:
    if not field_path:
        return False
    lower_field = field_path.lower()
    if lower_field == DEFAULT_DOCUMENT_REVIEW_FIELD:
        return False
    return not any(lower_field.startswith(prefix) for prefix in NON_REVIEWABLE_FIELD_PREFIXES)


def _get_nested_value(payload: Any, field_path: str) -> Any:
    if field_path == DEFAULT_DOCUMENT_REVIEW_FIELD:
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


def _set_nested_value(payload: dict[str, Any], field_path: str, value: Any) -> None:
    current: Any = payload
    parts = _normalise_field_path(field_path).split(".")

    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        if isinstance(current, list):
            if not part.isdigit():
                raise ValueError(f"Invalid field path segment '{part}' for list payload")
            item_index = int(part)
            while item_index >= len(current):
                current.append({})
            if is_last:
                current[item_index] = value
                return
            if not isinstance(current[item_index], (dict, list)):
                current[item_index] = {}
            current = current[item_index]
            continue

        if is_last:
            current[part] = value
            return

        next_part = parts[index + 1]
        if part not in current or not isinstance(current[part], (dict, list)):
            current[part] = [] if next_part.isdigit() else {}
        current = current[part]


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        logger.debug(f"Unable to convert value to float for review confidence: {value}")
        return None


def _normalise_field_path(field_path: str) -> str:
    return re.sub(r"\[(\d+)\]", r".\1", field_path or "")
