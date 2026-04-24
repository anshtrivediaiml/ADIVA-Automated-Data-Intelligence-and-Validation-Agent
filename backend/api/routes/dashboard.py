"""Dashboard summary routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time as dt_time, timezone
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.errors import internal_server_error
from api.middleware.auth_middleware import get_current_user
from api.models.responses import (
    DashboardRecentJobResponse,
    DashboardReviewSpotlightResponse,
    DashboardSummaryResponse,
)
from db import models
from db.session import get_db
from logger import logger
from observability import get_readiness_snapshot

import config

router = APIRouter()

_dashboard_cache_lock = Lock()
_dashboard_cache: dict[str, tuple[float, DashboardSummaryResponse]] = {}


def _dashboard_cache_key(user_id: Any) -> str:
    return str(user_id)


def _get_cached_dashboard_summary(user_id: Any) -> DashboardSummaryResponse | None:
    ttl = max(0.0, config.DASHBOARD_SUMMARY_CACHE_TTL_SECONDS)
    if ttl <= 0:
        return None

    key = _dashboard_cache_key(user_id)
    now = datetime.now(timezone.utc).timestamp()
    with _dashboard_cache_lock:
        cached = _dashboard_cache.get(key)
        if not cached:
            return None
        expires_at, payload = cached
        if now >= expires_at:
            _dashboard_cache.pop(key, None)
            return None
        return payload


def _store_dashboard_summary(user_id: Any, payload: DashboardSummaryResponse) -> None:
    ttl = max(0.0, config.DASHBOARD_SUMMARY_CACHE_TTL_SECONDS)
    if ttl <= 0:
        return

    key = _dashboard_cache_key(user_id)
    expires_at = datetime.now(timezone.utc).timestamp() + ttl
    with _dashboard_cache_lock:
        _dashboard_cache[key] = (expires_at, payload)


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        cached = _get_cached_dashboard_summary(current_user.id)
        if cached is not None:
            return cached

        payload = _build_dashboard_summary(db, current_user.id)
        _store_dashboard_summary(current_user.id, payload)
        return payload
    except Exception as exc:
        logger.exception(f"Failed to build dashboard summary for user_id={current_user.id}: {exc}")
        raise internal_server_error()


def _build_dashboard_summary(db: Session, user_id: Any) -> DashboardSummaryResponse:
    now = datetime.now(timezone.utc)
    start_of_day = datetime.combine(now.date(), dt_time.min, tzinfo=timezone.utc)

    status_rows = (
        db.query(models.Extraction.status, func.count(models.Extraction.id))
        .filter(models.Extraction.user_id == user_id)
        .group_by(models.Extraction.status)
        .all()
    )
    status_counts = defaultdict(int)
    for status, count in status_rows:
        status_counts[str(status)] = int(count)

    total_jobs = sum(status_counts.values())
    completed_count = status_counts["completed"]
    queued_count = status_counts["queued"]
    processing_count = status_counts["processing"]
    needs_review_count = status_counts["needs_review"]
    low_confidence_count = status_counts["low_confidence"]
    failed_count = status_counts["failed"]
    active_count = queued_count + processing_count

    jobs_today = int(
        db.query(func.count(models.Extraction.id))
        .filter(models.Extraction.user_id == user_id)
        .filter(models.Extraction.submitted_at >= start_of_day)
        .scalar()
        or 0
    )
    completed_today = int(
        db.query(func.count(models.Extraction.id))
        .filter(models.Extraction.user_id == user_id)
        .filter(models.Extraction.status == "completed")
        .filter(models.Extraction.finished_at >= start_of_day)
        .scalar()
        or 0
    )

    recent_job_rows = (
        db.query(models.Extraction, models.Document, models.ExtractionResult)
        .join(models.Document, models.Extraction.document_id == models.Document.id, isouter=True)
        .join(models.ExtractionResult, models.ExtractionResult.extraction_id == models.Extraction.id, isouter=True)
        .filter(models.Extraction.user_id == user_id)
        .order_by(models.Extraction.created_at.desc())
        .limit(5)
        .all()
    )
    recent_jobs = [
        DashboardRecentJobResponse(
            job_id=str(extraction.id),
            file_name=document.filename if document else None,
            document_type=extraction_result.document_type if extraction_result else None,
            doc_type=extraction_result.document_type if extraction_result else None,
            status=extraction.status,
            submitted_at=extraction.submitted_at or extraction.created_at,
        )
        for extraction, document, extraction_result in recent_job_rows
    ]

    open_reviews_query = (
        db.query(models.ReviewCase)
        .filter(models.ReviewCase.user_id == user_id)
        .filter(models.ReviewCase.status != "resolved")
    )
    open_review_cases = int(open_reviews_query.count() or 0)

    total_open_review_fields = int(
        db.query(func.count(models.ReviewFieldItem.id))
        .join(models.ReviewCase, models.ReviewFieldItem.review_case_id == models.ReviewCase.id)
        .filter(models.ReviewCase.user_id == user_id)
        .filter(models.ReviewCase.status != "resolved")
        .filter(models.ReviewFieldItem.status == "open")
        .scalar()
        or 0
    )

    common_doc_type_row = (
        db.query(models.ReviewCase.document_type, func.count(models.ReviewCase.id).label("case_count"))
        .filter(models.ReviewCase.user_id == user_id)
        .filter(models.ReviewCase.status != "resolved")
        .filter(models.ReviewCase.document_type.isnot(None))
        .group_by(models.ReviewCase.document_type)
        .order_by(func.count(models.ReviewCase.id).desc(), models.ReviewCase.document_type.asc())
        .first()
    )
    common_review_doc_type = str(common_doc_type_row[0]) if common_doc_type_row and common_doc_type_row[0] else None

    spotlight_rows = (
        db.query(models.ReviewCase, models.Document)
        .join(models.Document, models.ReviewCase.document_id == models.Document.id, isouter=True)
        .filter(models.ReviewCase.user_id == user_id)
        .filter(models.ReviewCase.status != "resolved")
        .order_by(models.ReviewCase.created_at.desc())
        .limit(3)
        .all()
    )
    spotlight_case_ids = [review_case.id for review_case, _ in spotlight_rows]
    spotlight_field_counts: dict[Any, int] = {}
    if spotlight_case_ids:
        field_rows = (
            db.query(models.ReviewFieldItem.review_case_id, func.count(models.ReviewFieldItem.id))
            .filter(models.ReviewFieldItem.review_case_id.in_(spotlight_case_ids))
            .filter(models.ReviewFieldItem.status == "open")
            .group_by(models.ReviewFieldItem.review_case_id)
            .all()
        )
        spotlight_field_counts = {
            review_case_id: int(count)
            for review_case_id, count in field_rows
        }

    review_spotlight = [
        DashboardReviewSpotlightResponse(
            review_id=str(review_case.id),
            id=str(review_case.id),
            job_id=str(review_case.extraction_id),
            file_name=document.filename if document else None,
            document_type=review_case.document_type,
            doc_type=review_case.document_type,
            status=review_case.status,
            open_field_count=spotlight_field_counts.get(review_case.id, 0),
            created_at=review_case.created_at,
        )
        for review_case, document in spotlight_rows
    ]

    readiness_status = get_readiness_snapshot()["status"]
    health_status = "healthy" if readiness_status == "ready" else "degraded"

    return DashboardSummaryResponse(
        generated_at=now,
        cache_ttl_seconds=max(0.0, config.DASHBOARD_SUMMARY_CACHE_TTL_SECONDS),
        health_status=health_status,
        total_jobs=total_jobs,
        jobs_today=jobs_today,
        completed_today=completed_today,
        completed_count=completed_count,
        queued_count=queued_count,
        processing_count=processing_count,
        needs_review_count=needs_review_count,
        low_confidence_count=low_confidence_count,
        failed_count=failed_count,
        active_count=active_count,
        success_rate=round((completed_count / total_jobs) * 100, 1) if total_jobs > 0 else None,
        open_review_cases=open_review_cases,
        total_open_review_fields=total_open_review_fields,
        common_review_doc_type=common_review_doc_type,
        recent_jobs=recent_jobs,
        review_spotlight=review_spotlight,
    )
