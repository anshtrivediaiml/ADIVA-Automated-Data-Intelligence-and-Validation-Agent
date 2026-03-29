"""
Extraction Routes

Phase 2 converts extraction submission into asynchronous job creation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import hashlib
import re
import time
import uuid
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from api.errors import internal_server_error
from api.middleware.auth_middleware import get_current_user
from api.models.responses import BatchJobItem, BatchSubmissionResponse, JobSubmissionResponse
from db import models
from db.session import SessionLocal, get_db
from logger import logger
from observability import runtime_metrics
from orchestration.service import build_job_submission_response, enqueue_extraction_job
from workflow_contract import JobState
import config

router = APIRouter()

MAX_FILE_SIZE = config.MAX_FILE_SIZE
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS
UPLOAD_CHUNK_SIZE = config.UPLOAD_CHUNK_SIZE


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    return name or f"upload_{int(time.time())}"


def _validate_magic_bytes(file_path: Path, file_ext: str) -> None:
    with open(file_path, "rb") as f:
        header = f.read(16)

    if file_ext == ".pdf" and not header.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File content is not a valid PDF")

    if file_ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        expected_format = {
            ".png": "PNG",
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".tiff": "TIFF",
            ".bmp": "BMP",
        }[file_ext]
        try:
            with Image.open(file_path) as img:
                detected_format = (img.format or "").upper()
                img.verify()
        except (UnidentifiedImageError, OSError):
            logger.warning(
                f"Invalid image payload rejected: {file_path.name}, "
                f"extension={file_ext}, header={header.hex()}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"File content is not a valid {expected_format}",
            )

        if detected_format not in {"PNG", "JPEG", "TIFF", "BMP"}:
            raise HTTPException(status_code=400, detail="Unsupported image file content")

        if detected_format != expected_format:
            logger.warning(
                f"Image extension/content mismatch for {file_path.name}: "
                f"extension={file_ext}, detected={detected_format}"
            )

    if file_ext == ".docx":
        if not header.startswith(b"PK"):
            raise HTTPException(status_code=400, detail="File content is not a valid DOCX")
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                if "[Content_Types].xml" not in zf.namelist():
                    raise HTTPException(status_code=400, detail="File content is not a valid DOCX")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="File content is not a valid DOCX")


def validate_file(file: UploadFile) -> None:
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )


async def save_upload_file(upload_file: UploadFile) -> tuple[Path, str, int]:
    temp_path: Optional[Path] = None
    try:
        date_dir = config.UPLOADS_DIR / datetime.now().strftime("%Y%m%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _sanitize_filename(upload_file.filename or "upload")
        temp_path = date_dir / f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_name}"
        total = 0
        sha256 = hashlib.sha256()

        with open(temp_path, "wb") as f:
            while True:
                chunk = await upload_file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB",
                    )
                sha256.update(chunk)
                f.write(chunk)

        _validate_magic_bytes(temp_path, Path(upload_file.filename or "").suffix.lower())
        return temp_path, sha256.hexdigest(), total

    except HTTPException:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        logger.exception(f"Failed to save upload for filename={upload_file.filename}: {exc}")
        raise internal_server_error("Failed to save uploaded file")


def _find_existing_idempotent_job(
    *,
    idempotency_key: str,
    user_id,
):
    db = SessionLocal()
    try:
        existing = (
            db.query(models.Extraction, models.Document)
            .join(models.Document, models.Extraction.document_id == models.Document.id)
            .filter(models.Extraction.user_id == user_id)
            .filter(models.Extraction.idempotency_key == idempotency_key)
            .order_by(models.Extraction.created_at.desc())
            .first()
        )
        if not existing:
            return None

        extraction, document = existing
        return build_job_submission_response(extraction, document)
    finally:
        db.close()


@router.post(
    "/extract",
    response_model=JobSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def extract_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to extract"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: models.User = Depends(get_current_user),
):
    """
    Accept a document upload and return a queued job.
    """
    durable_path: Optional[Path] = None

    try:
        validate_file(file)

        if idempotency_key:
            existing = _find_existing_idempotent_job(
                idempotency_key=idempotency_key,
                user_id=current_user.id,
            )
            if existing:
                logger.info(
                    f"Reused existing extraction job for user_id={current_user.id}, "
                    f"idempotency_key={idempotency_key}"
                )
                return existing

        durable_path, checksum, size_bytes = await save_upload_file(file)

        db = SessionLocal()
        try:
            document = models.Document(
                user_id=current_user.id,
                filename=file.filename,
                mime_type=file.content_type,
                size_bytes=size_bytes,
                checksum=checksum,
                storage_uri=str(durable_path),
            )
            db.add(document)
            db.flush()

            extraction = models.Extraction(
                document_id=document.id,
                user_id=current_user.id,
                status=JobState.QUEUED.value,
                current_stage=None,
                retry_count=0,
                submitted_at=datetime.now(timezone.utc),
                started_at=None,
                finished_at=None,
                model_name=config.MISTRAL_MODEL,
                model_version=None,
                prompt_version=None,
                review_required=False,
                validation_decision=None,
                batch_id=None,
                idempotency_key=idempotency_key,
                error_message=None,
            )
            db.add(extraction)
            db.commit()
            db.refresh(document)
            db.refresh(extraction)

            extraction_id = extraction.id
            document_id = document.id

            response = build_job_submission_response(extraction, document)

            db.add(
                models.AuditLog(
                    user_id=current_user.id,
                    action="extract_submitted",
                    resource_type="extraction",
                    resource_id=str(extraction_id),
                    metadata_jsonb={
                        "filename": file.filename,
                        "document_id": str(document_id),
                        "idempotency_key": idempotency_key,
                    },
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        enqueue_extraction_job(background_tasks, extraction_id)
        logger.info(f"Queued extraction job {extraction_id} for file {file.filename}")
        return response

    except HTTPException:
        if durable_path and durable_path.exists():
            durable_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if durable_path and durable_path.exists():
            durable_path.unlink(missing_ok=True)
        logger.exception(f"Failed to queue extraction for filename={file.filename}: {exc}")
        raise internal_server_error()


@router.post(
    "/extract/batch",
    response_model=BatchSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def extract_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Multiple document files"),
    current_user: models.User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Accept multiple uploads and queue one job per file.
    """
    durable_paths: list[Path] = []

    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        if len(files) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 files per batch")

        batch_id = f"batch_{config.get_timestamp()}_{uuid.uuid4().hex[:8]}"
        jobs: list[BatchJobItem] = []
        extraction_ids = []

        for upload in files:
            validate_file(upload)
            durable_path, checksum, size_bytes = await save_upload_file(upload)
            durable_paths.append(durable_path)

            document = models.Document(
                user_id=current_user.id,
                filename=upload.filename,
                mime_type=upload.content_type,
                size_bytes=size_bytes,
                checksum=checksum,
                storage_uri=str(durable_path),
            )
            db.add(document)
            db.flush()

            extraction = models.Extraction(
                document_id=document.id,
                user_id=current_user.id,
                status=JobState.QUEUED.value,
                current_stage=None,
                retry_count=0,
                submitted_at=datetime.now(timezone.utc),
                started_at=None,
                finished_at=None,
                model_name=config.MISTRAL_MODEL,
                model_version=None,
                prompt_version=None,
                review_required=False,
                validation_decision=None,
                batch_id=batch_id,
                idempotency_key=None,
                error_message=None,
            )
            db.add(extraction)
            db.flush()

            extraction_ids.append(extraction.id)
            jobs.append(
                BatchJobItem(
                    job_id=str(extraction.id),
                    filename=upload.filename,
                    status=extraction.status,
                    status_url=f"/api/jobs/{extraction.id}",
                )
            )

            db.add(
                models.AuditLog(
                    user_id=current_user.id,
                    action="extract_batch_submitted",
                    resource_type="extraction",
                    resource_id=str(extraction.id),
                    metadata_jsonb={
                        "filename": upload.filename,
                        "batch_id": batch_id,
                        "document_id": str(document.id),
                    },
                )
            )

        db.commit()

        for extraction_id in extraction_ids:
            enqueue_extraction_job(background_tasks, extraction_id, batch=True)

        logger.info(f"Queued batch {batch_id} with {len(extraction_ids)} extraction jobs")
        return BatchSubmissionResponse(
            batch_id=batch_id,
            status=JobState.QUEUED.value,
            total_documents=len(files),
            submitted_at=datetime.now(timezone.utc),
            jobs=jobs,
        )

    except HTTPException:
        db.rollback()
        for durable_path in durable_paths:
            if durable_path.exists():
                durable_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        db.rollback()
        for durable_path in durable_paths:
            if durable_path.exists():
                durable_path.unlink(missing_ok=True)
        logger.exception(f"Failed to queue batch extraction: {exc}")
        raise internal_server_error()
