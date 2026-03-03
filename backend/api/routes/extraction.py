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

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.models.responses import ExtractionResponse, BatchResponse, ErrorResponse
from api.middleware.auth_middleware import get_current_user
from extractor import DocumentExtractor
from logger import logger
import config
from db.session import get_db
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

    # PNG
    if file_ext == ".png" and header[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(status_code=400, detail="File content is not a valid PNG")

    # JPEG
    if file_ext in {".jpg", ".jpeg"} and not (header[:2] == b"\xff\xd8"):
        raise HTTPException(status_code=400, detail="File content is not a valid JPEG")

    # TIFF
    if file_ext == ".tiff" and header[:4] not in {b"II*\x00", b"MM\x00*"}:
        raise HTTPException(status_code=400, detail="File content is not a valid TIFF")

    # BMP
    if file_ext == ".bmp" and header[:2] != b"BM":
        raise HTTPException(status_code=400, detail="File content is not a valid BMP")

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
    # Check extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Note: Size validation would happen here if needed
    # FastAPI doesn't provide file size before reading


async def save_upload_file(upload_file: UploadFile) -> tuple[Path, str, int]:
    """Save uploaded file to temporary location"""
    try:
        # Create temp directory if it doesn't exist
        temp_dir = Path(tempfile.gettempdir()) / "adiva_uploads"
        temp_dir.mkdir(exist_ok=True)
        
        # Generate temp file path
        file_ext = Path(upload_file.filename).suffix.lower()
        safe_name = _sanitize_filename(upload_file.filename)
        temp_path = temp_dir / f"{int(time.time())}_{safe_name}"
        
        # Save file
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

        # Validate file content
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
    db=Depends(get_db),
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
        # Validate file
        validate_file(file)
        logger.info(f"Received extraction request for: {file.filename}")
        
        # Save uploaded file
        temp_path, checksum, size_bytes = await save_upload_file(file)
        
        # Extract
        logger.info(f"Extracting from: {temp_path}")
        result = extractor.extract(str(temp_path))
        
        # Prepare response (extraction_id will be DB UUID)
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
            extracted_data=result,  # Include the complete extraction result
            processing_time=round(processing_time, 2)
        )

        # Persist to DB
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

        # Outputs
        outputs = []
        output_file = result.get("output_file")
        if output_file:
            outputs.append(
                models.ExtractionOutput(
                    extraction_id=extraction.id,
                    format="json",
                    storage_uri=output_file,
                    size_bytes=Path(output_file).stat().st_size if Path(output_file).exists() else None,
                )
            )
        for fmt, path in result.get("exports", {}).items():
            outputs.append(
                models.ExtractionOutput(
                    extraction_id=extraction.id,
                    format=fmt,
                    storage_uri=path,
                    size_bytes=Path(path).stat().st_size if Path(path).exists() else None,
                )
            )
        for out in outputs:
            db.add(out)

        db.commit()

        # Now that DB commit succeeded, set response extraction_id to DB UUID
        response.extraction_id = str(extraction.id)
        
        logger.info(f"Extraction completed: {response.extraction_id} in {processing_time:.2f}s")
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup temp file
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
        
        # Save all uploaded files
        for file in files:
            validate_file(file)
            temp_path, checksum, size_bytes = await save_upload_file(file)
            temp_paths.append((temp_path, checksum, size_bytes, file))
        
        # Create batch folder
        batch_timestamp = time.strftime("%Y%m%d_%H%M%S")
        batch_id = f"batch_{batch_timestamp}"
        batch_folder = config.OUTPUTS_DIR / "extracted" / batch_id
        batch_folder.mkdir(parents=True, exist_ok=True)
        
        # Extract all files
        results = []
        failed = 0
        
        for idx, entry in enumerate(temp_paths):
            temp_path, checksum, size_bytes, upload_file = entry
            try:
                logger.info(f"Processing batch file {idx+1}/{len(temp_paths)}: {temp_path.name}")
                result = extractor.extract(str(temp_path))
                
                extraction_id = Path(result['extraction_folder']).name
                
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
                    extracted_data=result  # Include the complete extraction result
                )

                # Persist to DB
                document = models.Document(
                    user_id=current_user.id,
                    filename=upload_file.filename,
                    mime_type=upload_file.content_type,
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

                outputs = []
                output_file = result.get("output_file")
                if output_file:
                    outputs.append(
                        models.ExtractionOutput(
                            extraction_id=extraction.id,
                            format="json",
                            storage_uri=output_file,
                            size_bytes=Path(output_file).stat().st_size if Path(output_file).exists() else None,
                        )
                    )
                for fmt, path in result.get("exports", {}).items():
                    outputs.append(
                        models.ExtractionOutput(
                            extraction_id=extraction.id,
                            format=fmt,
                            storage_uri=path,
                            size_bytes=Path(path).stat().st_size if Path(path).exists() else None,
                        )
                    )
                for out in outputs:
                    db.add(out)

                db.commit()

                response.extraction_id = str(extraction.id)
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
        
        # Prepare batch response
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
        # Cleanup temp files
        for temp_path in temp_paths:
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except:
                    pass
