"""
Job Routes

Async job status endpoints for Phase 2 orchestration.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Load, Session

from api.errors import internal_server_error
from api.middleware.auth_middleware import get_current_user
from api.models.responses import JobStatusResponse, RecoveryAttemptListResponse
from db import models
from db.session import get_db
from logger import logger
from recovery.service import count_recovery_attempts, list_recovery_attempts_for_user
from review.service import get_open_review_case_snapshot
from workflow_contract import requires_review

router = APIRouter()


def _build_job_status_response(
    db: Session,
    extraction,
    extraction_result,
    document=None,
    *,
    review_snapshot: dict | None = None,
    recovery_attempt_count: int | None = None,
    metadata: dict | None = None,
) -> JobStatusResponse:
    runtime_metadata = metadata if isinstance(metadata, dict) else {}
    timings = runtime_metadata.get("stage_timings_seconds", {}) if isinstance(runtime_metadata, dict) else {}
    validation_summary = runtime_metadata.get("validation_summary") if isinstance(runtime_metadata, dict) else None
    confidence_data = (extraction_result.confidence_jsonb or {}) if extraction_result else {}

    if isinstance(confidence_data, dict):
        ocr_confidence = confidence_data.get("ocr_confidence") or confidence_data.get("ocr")
        overall_confidence = (
            confidence_data.get("overall_confidence")
            or confidence_data.get("overall_conf")
            or confidence_data.get("score")
        )
    else:
        ocr_confidence = None
        overall_confidence = None

    if review_snapshot is None:
        review_snapshot = get_open_review_case_snapshot(db, extraction.id)

    return JobStatusResponse(
        job_id=str(extraction.id),
        document_id=str(extraction.document_id) if extraction.document_id else "",
        file_name=document.filename if document else None,
        document_type=extraction_result.document_type if extraction_result else None,
        ocr_confidence=ocr_confidence if isinstance(ocr_confidence, (int, float)) else None,
        overall_confidence=overall_confidence if isinstance(overall_confidence, (int, float)) else None,
        status=extraction.status,
        current_stage=extraction.current_stage,
        submitted_at=extraction.submitted_at or extraction.created_at,
        started_at=extraction.started_at,
        finished_at=extraction.finished_at,
        retry_count=extraction.retry_count or 0,
        review_required=bool(extraction.review_required or requires_review(extraction.status)),
        failure_reason=extraction.error_message,
        validation_decision=extraction.validation_decision,
        validation_summary=validation_summary if isinstance(validation_summary, dict) else None,
        review_case_id=review_snapshot["review_case_id"] if review_snapshot else None,
        review_status=review_snapshot["status"] if review_snapshot else None,
        review_priority=review_snapshot["priority"] if review_snapshot else None,
        review_open_field_count=review_snapshot["open_field_count"] if review_snapshot else 0,
        critical_review_open_field_count=(
            review_snapshot["critical_open_field_count"] if review_snapshot else 0
        ),
        recovery_attempt_count=(
            recovery_attempt_count
            if recovery_attempt_count is not None
            else count_recovery_attempts(db, extraction.id)
        ),
        timings=timings if isinstance(timings, dict) else {},
    )


@router.get("/jobs", response_model=list[JobStatusResponse])
async def list_jobs(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        query = (
            db.query(models.Extraction, models.Document, models.ExtractionResult)
            .options(
                Load(models.Extraction).load_only(
                    models.Extraction.id,
                    models.Extraction.document_id,
                    models.Extraction.user_id,
                    models.Extraction.status,
                    models.Extraction.current_stage,
                    models.Extraction.submitted_at,
                    models.Extraction.created_at,
                    models.Extraction.started_at,
                    models.Extraction.finished_at,
                    models.Extraction.retry_count,
                    models.Extraction.review_required,
                    models.Extraction.validation_decision,
                    models.Extraction.error_message,
                ),
                Load(models.Document).load_only(
                    models.Document.id,
                    models.Document.filename,
                ),
                Load(models.ExtractionResult).load_only(
                    models.ExtractionResult.extraction_id,
                    models.ExtractionResult.document_type,
                    models.ExtractionResult.confidence_jsonb,
                ),
            )
            .join(models.Document, models.Extraction.document_id == models.Document.id, isouter=True)
            .join(models.ExtractionResult, models.ExtractionResult.extraction_id == models.Extraction.id, isouter=True)
            .filter(models.Extraction.user_id == current_user.id)
        )
        if status:
            query = query.filter(models.Extraction.status == status)

        rows = (
            query.order_by(models.Extraction.created_at.desc())
            .limit(limit)
            .all()
        )

        extraction_ids = [extraction.id for extraction, _, _ in rows]
        review_snapshots: dict[uuid.UUID, dict] = {}
        recovery_attempt_counts: dict[uuid.UUID, int] = {}

        if extraction_ids:
            review_rows = (
                db.query(
                    models.ReviewCase.extraction_id,
                    models.ReviewCase.id,
                    models.ReviewCase.status,
                    models.ReviewCase.priority,
                    models.ReviewCase.created_at,
                )
                .filter(models.ReviewCase.extraction_id.in_(extraction_ids))
                .filter(models.ReviewCase.status != "resolved")
                .all()
            )
            case_ids = [review_id for _, review_id, _, _, _ in review_rows]
            field_counts: dict[uuid.UUID, int] = {}
            critical_field_counts: dict[uuid.UUID, int] = {}
            if case_ids:
                field_rows = (
                    db.query(
                        models.ReviewFieldItem.review_case_id,
                        func.count(models.ReviewFieldItem.id),
                    )
                    .filter(models.ReviewFieldItem.review_case_id.in_(case_ids))
                    .filter(models.ReviewFieldItem.status == "open")
                    .group_by(models.ReviewFieldItem.review_case_id)
                    .all()
                )
                field_counts = {
                    review_case_id: int(count)
                    for review_case_id, count in field_rows
                }
                critical_field_rows = (
                    db.query(
                        models.ReviewFieldItem.review_case_id,
                        func.count(models.ReviewFieldItem.id),
                    )
                    .filter(models.ReviewFieldItem.review_case_id.in_(case_ids))
                    .filter(models.ReviewFieldItem.status == "open")
                    .filter(models.ReviewFieldItem.is_critical.is_(True))
                    .group_by(models.ReviewFieldItem.review_case_id)
                    .all()
                )
                critical_field_counts = {
                    review_case_id: int(count)
                    for review_case_id, count in critical_field_rows
                }

            review_snapshots = {
                extraction_id: {
                    "review_case_id": str(review_id),
                    "status": review_status,
                    "priority": priority,
                    "open_field_count": field_counts.get(review_id, 0),
                    "critical_open_field_count": critical_field_counts.get(review_id, 0),
                }
                for extraction_id, review_id, review_status, priority, _ in review_rows
            }

            recovery_rows = (
                db.query(
                    models.RecoveryAttempt.extraction_id,
                    func.count(models.RecoveryAttempt.id),
                )
                .filter(models.RecoveryAttempt.extraction_id.in_(extraction_ids))
                .group_by(models.RecoveryAttempt.extraction_id)
                .all()
            )
            recovery_attempt_counts = {
                extraction_id: int(count)
                for extraction_id, count in recovery_rows
            }

        return [
            _build_job_status_response(
                db,
                extraction,
                extraction_result,
                document,
                review_snapshot=review_snapshots.get(extraction.id),
                recovery_attempt_count=recovery_attempt_counts.get(extraction.id, 0),
                metadata=None,
            )
            for extraction, document, extraction_result in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to list jobs for user_id={current_user.id}: {exc}")
        raise internal_server_error()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        try:
            extraction_uuid = uuid.UUID(job_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job_id")

        row = (
            db.query(models.Extraction, models.Document, models.ExtractionResult)
            .join(models.Document, models.Extraction.document_id == models.Document.id, isouter=True)
            .join(models.ExtractionResult, models.ExtractionResult.extraction_id == models.Extraction.id, isouter=True)
            .filter(models.Extraction.id == extraction_uuid)
            .filter(models.Extraction.user_id == current_user.id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        extraction, document, extraction_result = row
        metadata = (
            extraction_result.metadata_jsonb
            if extraction_result and isinstance(extraction_result.metadata_jsonb, dict)
            else {}
        )
        return _build_job_status_response(
            db,
            extraction,
            extraction_result,
            document,
            metadata=metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get job status for job_id={job_id}: {exc}")
        raise internal_server_error()


@router.get("/jobs/{job_id}/recovery-attempts", response_model=RecoveryAttemptListResponse)
async def list_job_recovery_attempts(
    job_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return list_recovery_attempts_for_user(
            db,
            extraction_id=job_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to list recovery attempts for job_id={job_id}: {exc}")
        raise internal_server_error()
