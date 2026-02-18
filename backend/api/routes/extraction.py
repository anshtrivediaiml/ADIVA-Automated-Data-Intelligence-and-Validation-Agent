"""
Extraction Routes

Document extraction endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
import sys
from pathlib import Path
import os
import tempfile
import time

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.models.responses import ExtractionResponse, BatchResponse, ErrorResponse
from extractor import DocumentExtractor
from logger import logger
import config

router = APIRouter()

# Initialize extractor (singleton)
extractor = DocumentExtractor()

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}


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


async def save_upload_file(upload_file: UploadFile) -> Path:
    """Save uploaded file to temporary location"""
    try:
        # Create temp directory if it doesn't exist
        temp_dir = Path(tempfile.gettempdir()) / "adiva_uploads"
        temp_dir.mkdir(exist_ok=True)
        
        # Generate temp file path
        file_ext = Path(upload_file.filename).suffix
        temp_path = temp_dir / f"{int(time.time())}_{upload_file.filename}"
        
        # Save file
        with open(temp_path, "wb") as f:
            content = await upload_file.read()
            
            # Validate size
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
                )
            
            f.write(content)
        
        return temp_path
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


@router.post("/extract", response_model=ExtractionResponse)
async def extract_document(file: UploadFile = File(..., description="Document file to extract")):
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
        temp_path = await save_upload_file(file)
        
        # Extract
        logger.info(f"Extracting from: {temp_path}")
        result = extractor.extract(str(temp_path))
        
        # Prepare response
        processing_time = time.time() - start_time
        extraction_id = Path(result['extraction_folder']).name
        
        response = ExtractionResponse(
            status="success",
            extraction_id=extraction_id,
            document_type=result.get('classification', {}).get('document_type'),
            confidence=result.get('comprehensive_confidence', {}).get('overall_confidence'),
            extraction_folder=result['extraction_folder'],
            files={
                "json": "extraction.json",
                **result.get('exports', {})
            },
            extracted_data=result,  # Include the complete extraction result
            processing_time=round(processing_time, 2)
        )
        
        logger.info(f"Extraction completed: {extraction_id} in {processing_time:.2f}s")
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
async def extract_batch(files: List[UploadFile] = File(..., description="Multiple document files")):
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
            temp_path = await save_upload_file(file)
            temp_paths.append(temp_path)
        
        # Create batch folder
        batch_timestamp = time.strftime("%Y%m%d_%H%M%S")
        batch_id = f"batch_{batch_timestamp}"
        batch_folder = config.OUTPUTS_DIR / "extracted" / batch_id
        batch_folder.mkdir(parents=True, exist_ok=True)
        
        # Extract all files
        results = []
        failed = 0
        
        for idx, temp_path in enumerate(temp_paths):
            try:
                logger.info(f"Processing batch file {idx+1}/{len(temp_paths)}: {temp_path.name}")
                result = extractor.extract(str(temp_path))
                
                extraction_id = Path(result['extraction_folder']).name
                
                results.append(ExtractionResponse(
                    status="success",
                    extraction_id=extraction_id,
                    document_type=result.get('classification', {}).get('document_type'),
                    confidence=result.get('comprehensive_confidence', {}).get('overall_confidence'),
                    extraction_folder=result['extraction_folder'],
                    files={
                        "json": "extraction.json",
                        **result.get('exports', {})
                    },
                    extracted_data=result  # Include the complete extraction result
                ))
            
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
