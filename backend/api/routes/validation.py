"""
ADIVA — Validation Routes

POST /api/validate/file              — validate an uploaded JSON/CSV
POST /api/validate/{extraction_id}   — validate a previous extraction
GET  /api/validate/reports           — list all saved audit reports
GET  /api/validate/report/{filename} — retrieve a single audit report

All endpoints require a valid JWT Bearer token (same as extraction routes).
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from typing import Optional
import json
import time
import tempfile
from pathlib import Path

from agents.validator.logic import ValidationAgent
from agents.validator.schemas import AuditReport
from api.middleware.auth_middleware import get_current_user
from logger import logger
import config
from db.session import get_db
from db import models

router = APIRouter(prefix="/validate", tags=["Validation"])

# Singleton agent — initialised once per process
_agent: Optional[ValidationAgent] = None


def _get_agent() -> ValidationAgent:
    global _agent
    if _agent is None:
        _agent = ValidationAgent()
    return _agent


# ────────────────────────────────────────────────────────────────────────────
# POST /api/validate/file
# NOTE: MUST be defined BEFORE /{extraction_id} — otherwise FastAPI would
#       treat the literal string "file" as an extraction_id.
# ────────────────────────────────────────────────────────────────────────────

@router.post(
    "/file",
    response_model=AuditReport,
    summary="Validate an uploaded JSON or CSV file",
)
async def validate_file(
    file: UploadFile = File(..., description="JSON or CSV file to validate"),
    document_type: Optional[str] = Query(
        None,
        description="Document type hint (e.g. invoice, resume)",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a **.json** or **.csv** file and receive a full Audit Report.

    Useful for validating data that wasn't produced by the ADIVA extraction
    pipeline (e.g. external CSVs or manually crafted JSON).
    """
    agent = _get_agent()
    ext = Path(file.filename).suffix.lower() if file.filename else ""

    if ext not in (".json", ".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload .json or .csv",
        )

    # Save to temp location; clean up after validation
    tmp_dir = Path(tempfile.gettempdir()) / "adiva_validation"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{int(time.time())}_{file.filename}"

    try:
        content = await file.read()
        with open(tmp_path, "wb") as fh:
            fh.write(content)

        report = agent.validate_file(str(tmp_path))

        # Override document_type if caller specified one
        if document_type:
            report.document_type = document_type

        return report

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Validation of uploaded file failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


# ────────────────────────────────────────────────────────────────────────────
# POST /api/validate/{extraction_id}
# ────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{extraction_id}",
    response_model=AuditReport,
    summary="Validate a previous extraction",
)
async def validate_extraction(
    extraction_id: str,
    document_type: Optional[str] = Query(
        None,
        description="Override document type (auto-detected from extraction JSON if omitted)",
    ),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Run the four-pillar validation against an existing extraction.

    - **extraction_id**: DB UUID returned by `/api/extract` OR a folder name
      from `outputs/extracted/` (both are accepted).
    - **document_type**: Optional override (auto-detected from extraction JSON if omitted)

    Returns a full **Audit Report** with errors, normalised data,
    truth-test results, and a confidence score.
    """
    agent = _get_agent()

    # ── Resolve the actual extraction.json path ──────────────────────────────
    # Strategy 1: look up the DB record by UUID to find the stored file path.
    resolved_folder: Optional[str] = None
    try:
        import uuid as _uuid
        _uuid.UUID(extraction_id)          # raises ValueError if not a valid UUID
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
                # Pass the full absolute path — logic.py handles it
                resolved_folder = output_record.storage_uri
    except ValueError:
        # extraction_id is not a UUID — treat it as a folder name directly
        resolved_folder = extraction_id
    except Exception as db_exc:
        logger.warning(f"DB lookup for extraction {extraction_id} failed: {db_exc}")

    # Strategy 2: fall back to using extraction_id as folder name directly
    if resolved_folder is None:
        resolved_folder = extraction_id

    try:
        report = agent.validate_extraction(resolved_folder, document_type=document_type)
        return report
    except Exception as exc:
        logger.error(f"Validation failed for {extraction_id} (resolved: {resolved_folder}): {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ────────────────────────────────────────────────────────────────────────────
# GET /api/validate/reports
# ────────────────────────────────────────────────────────────────────────────

@router.get("/reports", summary="List all saved audit reports")
async def list_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
):
    """
    List saved audit reports from ``outputs/validated/``.
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
                    e for e in data.get("error_log", [])
                    if e.get("severity") == "error"
                ]),
                "warning_count": len([
                    e for e in data.get("error_log", [])
                    if e.get("severity") == "warning"
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


# ────────────────────────────────────────────────────────────────────────────
# GET /api/validate/report/{filename}
# ────────────────────────────────────────────────────────────────────────────

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
    Retrieve a previously saved audit report by filename
    (as returned by the ``reports`` list endpoint).
    """
    report_path = config.VALIDATED_DIR / filename
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    try:
        with open(report_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return AuditReport(**data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
