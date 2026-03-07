"""
Extraction Routes

Document extraction endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
import sys
from pathlib import Path
import os
import tempfile
import time
import zipfile
import re
import hashlib
from PIL import Image, UnidentifiedImageError

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.models.responses import ExtractionResponse, BatchResponse, ErrorResponse
from api.middleware.auth_middleware import get_current_user
from extractor import DocumentExtractor
from logger import logger
import config
from db.session import get_db, SessionLocal
from db import models

router = APIRouter()

# Initialize extractor (singleton)
extractor = DocumentExtractor()

# Configuration (centralized in config.py)
MAX_FILE_SIZE = config.MAX_FILE_SIZE
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS
UPLOAD_CHUNK_SIZE = config.UPLOAD_CHUNK_SIZE


def _sanitize_filename(filename: str) -> str:
    """Return a safe filename (strip paths, allow only safe chars)."""
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    return name or f"upload_{int(time.time())}"


def _validate_magic_bytes(file_path: Path, file_ext: str) -> None:
    """Validate file content using magic bytes / structure."""
    with open(file_path, "rb") as f:
        header = f.read(16)

    # PDF
    if file_ext == ".pdf" and not header.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File content is not a valid PDF")

    # Images (robust decode check).
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
                detail=f"File content is not a valid {expected_format}"
            )

        if detected_format not in {"PNG", "JPEG", "TIFF", "BMP"}:
            raise HTTPException(status_code=400, detail="Unsupported image file content")

        if detected_format != expected_format:
            logger.warning(
                f"Image extension/content mismatch for {file_path.name}: "
                f"extension={file_ext}, detected={detected_format}"
            )

    # DOCX (ZIP with [Content_Types].xml)
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
    """Validate uploaded file"""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )


async def save_upload_file(upload_file: UploadFile) -> tuple[Path, str, int]:
    """Save uploaded file to temporary location"""
    try:
        temp_dir = Path(tempfile.gettempdir()) / "adiva_uploads"
        temp_dir.mkdir(exist_ok=True)

        file_ext = Path(upload_file.filename).suffix.lower()
        safe_name = _sanitize_filename(upload_file.filename)
        temp_path = temp_dir / f"{int(time.time())}_{safe_name}"

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
                        detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
                    )
                sha256.update(chunk)
                f.write(chunk)

        _validate_magic_bytes(temp_path, file_ext)
        return temp_path, sha256.hexdigest(), total

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


@router.post("/extract", response_model=ExtractionResponse)
async def extract_document(
    file: UploadFile = File(..., description="Document file to extract"),
    current_user: dict = Depends(get_current_user),
):
    """
    Extract from uploaded document

    Upload a PDF, DOCX, or image file and extract structured data.

    - **file**: Document file (PDF, DOCX, PNG, JPG, etc.)

    Returns extraction results with links to generated files.
    """
    start_time = time.time()
    temp_path = None

    try:
        validate_file(file)
        logger.info(f"Received extraction request for: {file.filename}")

        temp_path, checksum, size_bytes = await save_upload_file(file)

        # Extraction is the long step (~55s). We deliberately do NOT hold a DB
        # connection open here — Supabase kills idle connections after ~30s.
        logger.info(f"Extracting from: {temp_path}")
        result = extractor.extract(str(temp_path))

        processing_time = time.time() - start_time

        response = ExtractionResponse(
            status="success",
            extraction_id="",
            document_type=result.get('classification', {}).get('document_type'),
            confidence=result.get('comprehensive_confidence', {}).get('overall_confidence'),
            detected_language=result.get('metadata', {}).get('detected_language'),
            extraction_folder=result['extraction_folder'],
            files={
                "json": "extraction.json",
                **result.get('exports', {})
            },
            extracted_data=result,
            processing_time=round(processing_time, 2)
        )

        # Open a FRESH DB session now — extraction is done, no idle-timeout risk.
        db = SessionLocal()
        try:
            document = models.Document(
                user_id=current_user.id,
                filename=file.filename,
                mime_type=file.content_type,
                size_bytes=size_bytes,
                checksum=checksum,
                storage_uri=str(temp_path),
            )
            db.add(document)
            db.flush()

            extraction = models.Extraction(
                document_id=document.id,
                user_id=current_user.id,
                status="completed" if result.get("status") == "success" else "failed",
                version=1,
                started_at=None,
                finished_at=None,
                model_name=config.MISTRAL_MODEL,
                model_version=None,
                prompt_version=None,
                error_message=result.get("error"),
            )
            db.add(extraction)
            db.flush()

            extraction_result = models.ExtractionResult(
                extraction_id=extraction.id,
                document_type=result.get("classification", {}).get("document_type"),
                structured_data_jsonb=result.get("structured_data"),
                confidence_jsonb=result.get("comprehensive_confidence"),
                detected_language=result.get("metadata", {}).get("detected_language"),
                metadata_jsonb=result.get("metadata"),
            )
            db.add(extraction_result)

            output_file = result.get("output_file")
            if output_file:
                db.add(models.ExtractionOutput(
                    extraction_id=extraction.id,
                    format="json",
                    storage_uri=output_file,
                    size_bytes=Path(output_file).stat().st_size if Path(output_file).exists() else None,
                ))
            for fmt, path in result.get("exports", {}).items():
                db.add(models.ExtractionOutput(
                    extraction_id=extraction.id,
                    format=fmt,
                    storage_uri=path,
                    size_bytes=Path(path).stat().st_size if Path(path).exists() else None,
                ))

            db.commit()
            response.extraction_id = str(extraction.id)

            # AuditLog — record the extract action
            try:
                db.add(models.AuditLog(
                    user_id=current_user.id,
                    action="extract",
                    resource_type="document",
                    resource_id=str(document.id),
                    metadata_jsonb={
                        "filename": file.filename,
                        "extraction_id": str(extraction.id),
                        "document_type": result.get("classification", {}).get("document_type"),
                        "processing_time_sec": round(processing_time, 2),
                    },
                ))
                db.commit()
            except Exception as al_exc:
                logger.warning(f"AuditLog save failed (non-fatal): {al_exc}")
                db.rollback()

            logger.info(f"Extraction saved to DB: {response.extraction_id} in {processing_time:.2f}s")


        except Exception as db_exc:
            db.rollback()
            logger.error(f"DB save failed (extraction on disk is fine): {db_exc}")
            # Don't raise — the extraction itself succeeded. extraction_id stays ""
        finally:
            db.close()

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_path and temp_path.exists():
            try:
                os.remove(temp_path)
            except:
                pass


@router.post("/extract/batch", response_model=BatchResponse)
async def extract_batch(
    files: List[UploadFile] = File(..., description="Multiple document files"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Batch extraction from multiple documents

    Upload multiple files for batch processing.

    - **files**: List of document files

    Returns batch results with individual extraction details.
    """
    start_time = time.time()
    temp_paths = []

    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 files per batch")

        logger.info(f"Received batch extraction request for {len(files)} files")

        for file in files:
            validate_file(file)
            temp_path, checksum, size_bytes = await save_upload_file(file)
            temp_paths.append((temp_path, checksum, size_bytes, file))

        batch_timestamp = time.strftime("%Y%m%d_%H%M%S")
        batch_id = f"batch_{batch_timestamp}"
        batch_folder = config.OUTPUTS_DIR / "extracted" / batch_id
        batch_folder.mkdir(parents=True, exist_ok=True)

        results = []
        failed = 0

        for idx, entry in enumerate(temp_paths):
            temp_path, checksum, size_bytes, upload_file = entry
            try:
                logger.info(f"Processing batch file {idx+1}/{len(temp_paths)}: {temp_path.name}")
                result = extractor.extract(str(temp_path))

                response = ExtractionResponse(
                    status="success",
                    extraction_id="",
                    document_type=result.get('classification', {}).get('document_type'),
                    confidence=result.get('comprehensive_confidence', {}).get('overall_confidence'),
                    detected_language=result.get('metadata', {}).get('detected_language'),
                    extraction_folder=result['extraction_folder'],
                    files={
                        "json": "extraction.json",
                        **result.get('exports', {})
                    },
                    extracted_data=result
                )

                # Fresh session per batch item
                batch_db = SessionLocal()
                try:
                    document = models.Document(
                        user_id=current_user.id,
                        filename=upload_file.filename,
                        mime_type=upload_file.content_type,
                        size_bytes=size_bytes,
                        checksum=checksum,
                        storage_uri=str(temp_path),
                    )
                    batch_db.add(document)
                    batch_db.flush()

                    extraction = models.Extraction(
                        document_id=document.id,
                        user_id=current_user.id,
                        status="completed" if result.get("status") == "success" else "failed",
                        version=1,
                        started_at=None,
                        finished_at=None,
                        model_name=config.MISTRAL_MODEL,
                        model_version=None,
                        prompt_version=None,
                        error_message=result.get("error"),
                    )
                    batch_db.add(extraction)
                    batch_db.flush()

                    extraction_result = models.ExtractionResult(
                        extraction_id=extraction.id,
                        document_type=result.get("classification", {}).get("document_type"),
                        structured_data_jsonb=result.get("structured_data"),
                        confidence_jsonb=result.get("comprehensive_confidence"),
                        detected_language=result.get("metadata", {}).get("detected_language"),
                        metadata_jsonb=result.get("metadata"),
                    )
                    batch_db.add(extraction_result)

                    output_file = result.get("output_file")
                    if output_file:
                        batch_db.add(models.ExtractionOutput(
                            extraction_id=extraction.id,
                            format="json",
                            storage_uri=output_file,
                            size_bytes=Path(output_file).stat().st_size if Path(output_file).exists() else None,
                        ))
                    for fmt, path in result.get("exports", {}).items():
                        batch_db.add(models.ExtractionOutput(
                            extraction_id=extraction.id,
                            format=fmt,
                            storage_uri=path,
                            size_bytes=Path(path).stat().st_size if Path(path).exists() else None,
                        ))

                    batch_db.commit()
                    response.extraction_id = str(extraction.id)

                except Exception as db_exc:
                    batch_db.rollback()
                    logger.error(f"DB save failed for batch item {idx}: {db_exc}")
                finally:
                    batch_db.close()

                results.append(response)

            except Exception as e:
                failed += 1
                logger.error(f"Failed to extract {temp_path.name}: {e}")
                results.append(ExtractionResponse(
                    status="error",
                    extraction_id=f"error_{idx}",
                    extraction_folder="",
                    files={}
                ))

        processing_time = time.time() - start_time

        response = BatchResponse(
            status="success" if failed == 0 else "partial",
            batch_id=batch_id,
            batch_folder=str(batch_folder),
            total_documents=len(files),
            processed=len(files) - failed,
            failed=failed,
            results=results,
            processing_time=round(processing_time, 2)
        )

        logger.info(f"Batch extraction completed: {len(files)} files, {failed} failed, {processing_time:.2f}s")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        for entry in temp_paths:
            temp_path = entry[0] if isinstance(entry, tuple) else entry
            if isinstance(temp_path, Path) and temp_path.exists():
                try:
                    os.remove(temp_path)
                except:
                    pass
