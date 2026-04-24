"""Review routes for Phase 5 review/correction foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.errors import internal_server_error
from api.middleware.auth_middleware import get_current_user
from api.models.responses import (
    ReviewCaseDetailResponse,
    ReviewCaseListResponse,
    ReviewCaseResolveRequest,
    ReviewFieldDecisionRequest,
    ReviewSummaryResponse,
)
import config
from db import models
from db.session import get_db
from logger import logger
from review.service import (
    apply_review_field_decision,
    get_review_case_detail,
    list_review_cases,
    resolve_review_case,
)

router = APIRouter()
_reviews_summary_cache_lock = Lock()
_reviews_summary_cache: dict[str, tuple[float, ReviewSummaryResponse]] = {}


def _reviews_summary_cache_key(user_id) -> str:
    return str(user_id)


def _get_cached_reviews_summary(user_id) -> ReviewSummaryResponse | None:
    ttl = max(0.0, config.LIST_SUMMARY_CACHE_TTL_SECONDS)
    if ttl <= 0:
        return None

    key = _reviews_summary_cache_key(user_id)
    now = datetime.now(timezone.utc).timestamp()
    with _reviews_summary_cache_lock:
        cached = _reviews_summary_cache.get(key)
        if not cached:
            return None
        expires_at, payload = cached
        if now >= expires_at:
            _reviews_summary_cache.pop(key, None)
            return None
        return payload


def _store_reviews_summary(user_id, payload: ReviewSummaryResponse) -> None:
    ttl = max(0.0, config.LIST_SUMMARY_CACHE_TTL_SECONDS)
    if ttl <= 0:
        return
    with _reviews_summary_cache_lock:
        _reviews_summary_cache[_reviews_summary_cache_key(user_id)] = (
            datetime.now(timezone.utc).timestamp() + ttl,
            payload,
        )


@router.get("/reviews/summary", response_model=ReviewSummaryResponse)
async def get_reviews_summary(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        cached = _get_cached_reviews_summary(current_user.id)
        if cached is not None:
            return cached

        status_rows = (
            db.query(models.ReviewCase.status, func.count(models.ReviewCase.id))
            .filter(models.ReviewCase.user_id == current_user.id)
            .group_by(models.ReviewCase.status)
            .all()
        )
        counts = {str(status): int(count) for status, count in status_rows}
        total_open_fields = int(
            db.query(func.count(models.ReviewFieldItem.id))
            .join(models.ReviewCase, models.ReviewFieldItem.review_case_id == models.ReviewCase.id)
            .filter(models.ReviewCase.user_id == current_user.id)
            .filter(models.ReviewFieldItem.status == "open")
            .scalar()
            or 0
        )
        payload = ReviewSummaryResponse(
            generated_at=datetime.now(timezone.utc),
            cache_ttl_seconds=max(0.0, config.LIST_SUMMARY_CACHE_TTL_SECONDS),
            total_reviews=sum(counts.values()),
            open_count=counts.get("open", 0),
            in_progress_count=counts.get("in_progress", 0) + counts.get("in_review", 0),
            resolved_count=counts.get("resolved", 0),
            total_open_fields=total_open_fields,
        )
        _store_reviews_summary(current_user.id, payload)
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to build review summary for user_id={current_user.id}: {exc}")
        raise internal_server_error()


@router.get("/reviews", response_model=ReviewCaseListResponse)
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    document_type: str | None = Query(None),
    search: str | None = Query(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        total, review_cases = list_review_cases(
            db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            status=status,
            document_type=document_type,
            search=search,
        )
        return ReviewCaseListResponse(
            total=total,
            page=page,
            page_size=page_size,
            review_cases=review_cases,
            reviews=review_cases,
        )
    except Exception as exc:
        logger.exception(f"Failed to list review cases for user_id={current_user.id}: {exc}")
        raise internal_server_error()


@router.get("/reviews/{review_id}", response_model=ReviewCaseDetailResponse)
async def get_review(
    review_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_review_case_detail(db, review_id=review_id, user_id=current_user.id)
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to load review case review_id={review_id}: {exc}")
        raise internal_server_error()


@router.get("/reviews/{review_id}/source")
async def get_review_source(
    review_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        try:
            review_uuid = uuid.UUID(review_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid review_id")

        review_case = (
            db.query(models.ReviewCase, models.Document)
            .join(models.Document, models.ReviewCase.document_id == models.Document.id, isouter=True)
            .filter(models.ReviewCase.id == review_uuid)
            .filter(models.ReviewCase.user_id == current_user.id)
            .first()
        )
        if not review_case:
            raise HTTPException(status_code=404, detail="Review case not found")

        _, document = review_case
        if not document or not document.storage_uri:
            raise HTTPException(status_code=404, detail="Source document not found")

        file_path = Path(document.storage_uri)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Source document file is unavailable")

        media_type = document.mime_type or "application/octet-stream"
        safe_name = document.filename or file_path.name

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=safe_name,
            headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to load review source review_id={review_id}: {exc}")
        raise internal_server_error()


@router.post("/reviews/{review_id}/fields/{field_item_id}/correct", response_model=ReviewCaseDetailResponse)
async def decide_review_field(
    review_id: str,
    field_item_id: str,
    payload: ReviewFieldDecisionRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return apply_review_field_decision(
            db,
            review_id=review_id,
            field_item_id=field_item_id,
            reviewer=current_user,
            action=payload.action,
            value=payload.value,
            correction_reason=payload.correction_reason,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            f"Failed to apply review field decision for review_id={review_id}, "
            f"field_item_id={field_item_id}: {exc}"
        )
        raise internal_server_error()


@router.post("/reviews/{review_id}/resolve", response_model=ReviewCaseDetailResponse)
async def resolve_review(
    review_id: str,
    payload: ReviewCaseResolveRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return resolve_review_case(
            db,
            review_id=review_id,
            reviewer=current_user,
            resolution_notes=payload.resolution_notes,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to resolve review case review_id={review_id}: {exc}")
        raise internal_server_error()
