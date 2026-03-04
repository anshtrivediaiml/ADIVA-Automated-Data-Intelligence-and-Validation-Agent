"""
Validation Routes

POST /api/validate/{extraction_id}  — validate a previous extraction
POST /api/validate/file              — validate an uploaded JSON/CSV
GET  /api/validate/report/{id}       — retrieve a saved audit report
GET  /api/validate/reports            — list all audit reports
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from typing import Optional
import sys
import json
import time
import tempfile
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from agents.validator.logic import ValidationAgent
from agents.validator.schemas import AuditReport
from logger import logger
import config

router = APIRouter(prefix="/validate", tags=["Validation"])

# Singleton agent
_agent: Optional[ValidationAgent] = None


def _get_agent() -> ValidationAgent:
    global _agent
    if _agent is None:
        _agent = ValidationAgent()
    return _agent


# ──────────────────────────────────────────
# POST /api/validate/file
# ──────────────────────────────────────────
# NOTE: This MUST be defined BEFORE /{extraction_id}
# otherwise FastAPI treats "file" as an extraction_id.

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
):
    """
    Upload a **.json** or **.csv** file and receive a validation Audit Report.

    This is useful for validating data that wasn't produced by the ADIVA
    extraction pipeline (e.g. external CSVs or manually crafted JSON).
    """
    agent = _get_agent()
    ext = Path(file.filename).suffix.lower() if file.filename else ""

    if ext not in (".json", ".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload .json or .csv",
        )

    # Save to temp location
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


# ──────────────────────────────────────────
# POST /api/validate/{extraction_id}
# ──────────────────────────────────────────

@router.post(
    "/{extraction_id}",
    response_model=AuditReport,
    summary="Validate a previous extraction",
)
async def validate_extraction(
    extraction_id: str,
    document_type: Optional[str] = Query(
        None,
        description="Override document type (auto-detected from extraction if omitted)",
    ),
):
    """
    Run the four-pillar validation against an existing extraction.

    - **extraction_id**: Folder name from a previous `/api/extract` call
    - **document_type**: Optional override (auto-detected from extraction JSON if omitted)

    Returns a full **Audit Report** with errors, normalised data,
    truth-test results, and a confidence score.
    """
    agent = _get_agent()
    try:
        report = agent.validate_extraction(extraction_id, document_type=document_type)
        return report
    except Exception as exc:
        logger.error(f"Validation failed for {extraction_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────
# GET /api/validate/reports
# ──────────────────────────────────────────

@router.get("/reports", summary="List all audit reports")
async def list_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
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


# ──────────────────────────────────────────
# GET /api/validate/report/{filename}
# ──────────────────────────────────────────

@router.get(
    "/report/{filename}",
    response_model=AuditReport,
    summary="Get a specific audit report",
)
async def get_report(filename: str):
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
        raise HTTPException(status_code=500, detail=str(exc))
