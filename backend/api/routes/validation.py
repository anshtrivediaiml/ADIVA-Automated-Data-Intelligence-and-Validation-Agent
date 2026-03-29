"""
Validation routes.

Manual validation remains available, but persistence and decision logic are
shared with the orchestration workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import json
import tempfile
import time
import uuid as _uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from agents.validator.schemas import AuditReport
from api.errors import internal_server_error
from api.middleware.auth_middleware import get_current_user
from db import models
from db.session import get_db
from logger import logger
from validation_service import (
    decide_validation_outcome,
    get_validation_agent,
    persist_validation_report,
)
import config

router = APIRouter(prefix="/validate", tags=["Validation"])


def _persist_validation(
    report: AuditReport,
    current_user,
    extraction_id: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    persist_validation_report(
        report,
        current_user=current_user,
        extraction_id=extraction_id,
        request=request,
        decision=decide_validation_outcome(report),
    )


@router.post(
    "/file",
    response_model=AuditReport,
    summary="Validate an uploaded JSON or CSV file",
)
async def validate_file(
    request: Request,
    file: UploadFile = File(..., description="JSON or CSV file to validate"),
    document_type: Optional[str] = Query(
        None,
        description="Document type hint (e.g. invoice, resume)",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a `.json` or `.csv` file and receive a full audit report.
    """
    agent = get_validation_agent()
    ext = Path(file.filename).suffix.lower() if file.filename else ""

    if ext not in (".json", ".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload .json or .csv",
        )

    tmp_dir = Path(tempfile.gettempdir()) / "adiva_validation"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{int(time.time())}_{file.filename}"

    try:
        content = await file.read()
        with open(tmp_path, "wb") as fh:
            fh.write(content)

        report = agent.validate_file(str(tmp_path))
        if document_type:
            report.document_type = document_type

        _persist_validation(report, current_user, request=request)
        return report

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Validation of uploaded file failed for {file.filename}: {exc}")
        raise internal_server_error()
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


@router.post(
    "/{extraction_id}",
    response_model=AuditReport,
    summary="Validate a previous extraction",
)
async def validate_extraction(
    request: Request,
    extraction_id: str,
    document_type: Optional[str] = Query(
        None,
        description="Override document type (auto-detected from extraction JSON if omitted)",
    ),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Run the validation agent against an existing extraction result.
    """
    agent = get_validation_agent()

    resolved_folder: Optional[str] = None
    try:
        _uuid.UUID(extraction_id)
        output_record = (
            db.query(models.ExtractionOutput)
            .join(models.Extraction, models.ExtractionOutput.extraction_id == models.Extraction.id)
            .filter(
                models.Extraction.id == extraction_id,
                models.ExtractionOutput.format == "json",
            )
            .first()
        )
        if output_record and output_record.storage_uri:
            resolved_folder = output_record.storage_uri
    except ValueError:
        resolved_folder = extraction_id
    except Exception as db_exc:
        logger.warning(f"DB lookup for extraction {extraction_id} failed: {db_exc}")

    if resolved_folder is None:
        resolved_folder = extraction_id

    try:
        report = agent.validate_extraction(resolved_folder, document_type=document_type)
        _persist_validation(report, current_user, extraction_id=extraction_id, request=request)
        return report
    except Exception as exc:
        logger.exception(
            f"Validation failed for extraction_id={extraction_id} "
            f"(resolved={resolved_folder}): {exc}"
        )
        raise internal_server_error()


@router.get("/reports", summary="List all saved audit reports")
async def list_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
):
    """
    List saved audit reports from `outputs/validated/`.
    """
    validated_dir = config.VALIDATED_DIR
    if not validated_dir.exists():
        return {"total": 0, "page": page, "page_size": page_size, "reports": []}

    files = sorted(
        [f for f in validated_dir.glob("audit_*.json")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    total = len(files)
    start = (page - 1) * page_size
    page_files = files[start : start + page_size]

    reports = []
    for fp in page_files:
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            reports.append({
                "filename": fp.name,
                "is_valid": data.get("is_valid"),
                "confidence_score": data.get("confidence_score"),
                "document_type": data.get("document_type"),
                "source_file": data.get("source_file"),
                "validation_time_seconds": data.get("validation_time_seconds"),
                "error_count": len([
                    item for item in data.get("error_log", [])
                    if item.get("severity") == "error"
                ]),
                "warning_count": len([
                    item for item in data.get("error_log", [])
                    if item.get("severity") == "warning"
                ]),
            })
        except Exception:
            continue

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "reports": reports,
    }


@router.get(
    "/report/{filename}",
    response_model=AuditReport,
    summary="Get a specific audit report by filename",
)
async def get_report(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve a previously saved audit report by filename.
    """
    report_path = config.VALIDATED_DIR / filename
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    try:
        with open(report_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return AuditReport(**data)
    except Exception as exc:
        logger.exception(f"Failed to load validation report {filename}: {exc}")
        raise internal_server_error()
