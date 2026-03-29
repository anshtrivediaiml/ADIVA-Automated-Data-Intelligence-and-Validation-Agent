"""Review routes for Phase 5 review/correction foundation."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.errors import internal_server_error
from api.middleware.auth_middleware import get_current_user
from api.models.responses import (
    ReviewCaseDetailResponse,
    ReviewCaseListResponse,
    ReviewCaseResolveRequest,
    ReviewFieldDecisionRequest,
)
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


@router.get("/reviews", response_model=ReviewCaseListResponse)
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    document_type: str | None = Query(None),
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
