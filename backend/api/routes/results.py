"""
Results Routes

Endpoints for retrieving and managing extraction results.
"""

from fastapi import APIRouter, HTTPException, Query, Path as PathParam, Depends
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
import sys
from pathlib import Path
import json
import shutil
import uuid

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.models.responses import ExtractionListResponse, ExtractionListItem
from api.middleware.auth_middleware import get_current_user
from logger import logger
import config
from db.session import get_db
from db import models
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/results/{extraction_id}")
async def get_results(
    extraction_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get extraction results by ID
    
    Retrieve complete extraction results as JSON.
    
    - **extraction_id**: Extraction folder name (e.g., 20260204_180000_invoice)
    
    Returns full extraction data including text, structured data, confidence scores, etc.
    """
    try:
        try:
            extraction_uuid = uuid.UUID(extraction_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid extraction_id")

        target = (
            db.query(models.Extraction)
            .filter(models.Extraction.id == extraction_uuid)
            .filter(models.Extraction.user_id == current_user.id)
            .first()
        )

        if not target:
            raise HTTPException(status_code=404, detail=f"Extraction '{extraction_id}' not found")

        # Return structured data + metadata
        extraction_result = (
            db.query(models.ExtractionResult)
            .filter(models.ExtractionResult.extraction_id == target.id)
            .first()
        )

        if not extraction_result:
            raise HTTPException(status_code=404, detail="Extraction result not found")

        logger.info(f"Retrieved results for: {extraction_id}")
        return {
            "extraction_id": extraction_id,
            "document_type": extraction_result.document_type,
            "structured_data": extraction_result.structured_data_jsonb,
            "confidence": extraction_result.confidence_jsonb,
            "detected_language": extraction_result.detected_language,
            "metadata": extraction_result.metadata_jsonb,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{extraction_id}/{format}")
async def download_file(
    extraction_id: str,
    format: str = PathParam(..., pattern="^(json|csv|xlsx|html)$", description="File format"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download extraction file in specific format
    
    Download CSV, Excel, HTML, or JSON file.
    
    - **extraction_id**: Extraction folder name
    - **format**: File format (json, csv, xlsx, html)
    
    Returns the file for download.
    """
    try:
        # Determine file extension
        ext_map = {
            "json": "json",
            "csv": "csv",
            "xlsx": "xlsx",
            "html": "html"
        }
        
        ext = ext_map.get(format)
        if not ext:
            raise HTTPException(status_code=400, detail=f"Invalid format: {format}")
        
        # Locate output via DB
        try:
            extraction_uuid = uuid.UUID(extraction_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid extraction_id")

        out = (
            db.query(models.ExtractionOutput)
            .join(models.Extraction, models.ExtractionOutput.extraction_id == models.Extraction.id)
            .filter(models.Extraction.user_id == current_user.id)
            .filter(models.ExtractionOutput.extraction_id == extraction_uuid)
            .filter(models.ExtractionOutput.format == format)
            .first()
        )

        file_path = Path(out.storage_uri) if out and out.storage_uri else None

        if not file_path or not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: extraction.{ext} in {extraction_id}"
            )
        
        # Determine media type
        media_types = {
            "json": "application/json",
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "html": "text/html"
        }
        
        logger.info(f"Downloading {format} for: {extraction_id}")
        
        return FileResponse(
            path=file_path,
            media_type=media_types[format],
            filename=f"{extraction_id}.{ext}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/extractions", response_model=ExtractionListResponse)
async def list_extractions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all extractions
    
    Get paginated list of all extractions with filtering options.
    
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page
    - **document_type**: Filter by type (invoice, resume, contract)
    
    Returns list of extractions with metadata.
    """
    try:
        query = (
            db.query(models.Extraction, models.Document, models.ExtractionResult)
            .join(models.Document, models.Extraction.document_id == models.Document.id, isouter=True)
            .join(models.ExtractionResult, models.ExtractionResult.extraction_id == models.Extraction.id, isouter=True)
            .filter(models.Extraction.user_id == current_user.id)
        )

        if document_type:
            query = query.filter(models.ExtractionResult.document_type == document_type)

        total = query.count()
        rows = (
            query.order_by(models.Extraction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        extractions = []
        for extraction, document, result in rows:
            extractions.append(ExtractionListItem(
                extraction_id=str(extraction.id),
                document_type=result.document_type if result else None,
                filename=document.filename if document else "unknown",
                processed_at=extraction.created_at.isoformat() if extraction.created_at else "",
                confidence=(result.confidence_jsonb or {}).get("overall_confidence") if result else None,
                status=extraction.status
            ))
        
        # Pagination
        logger.info(f"Listed {len(extractions)} extractions (page {page}, total {total})")
        
        return ExtractionListResponse(
            total=total,
            page=page,
            page_size=page_size,
            extractions=extractions
        )
    
    except Exception as e:
        logger.error(f"Failed to list extractions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/extractions/{extraction_id}")
async def delete_extraction(
    extraction_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete extraction and all associated files
    
    Permanently delete an extraction folder and all its files.
    
    - **extraction_id**: Extraction folder name
    
    Returns confirmation of deletion.
    """
    try:
        try:
            extraction_uuid = uuid.UUID(extraction_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid extraction_id")

        target = (
            db.query(models.Extraction)
            .filter(models.Extraction.id == extraction_uuid)
            .filter(models.Extraction.user_id == current_user.id)
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail=f"Extraction '{extraction_id}' not found")

        output = (
            db.query(models.ExtractionOutput)
            .filter(models.ExtractionOutput.extraction_id == extraction_uuid)
            .first()
        )
        target_folder = Path(output.storage_uri).parent if output and output.storage_uri else None

        # Delete DB records
        db.query(models.ExtractionOutput).filter(models.ExtractionOutput.extraction_id == extraction_uuid).delete()
        db.query(models.ExtractionResult).filter(models.ExtractionResult.extraction_id == extraction_uuid).delete()
        db.query(models.ValidationReport).filter(models.ValidationReport.extraction_id == extraction_uuid).delete()
        db.query(models.Extraction).filter(models.Extraction.id == extraction_uuid).delete()
        db.commit()

        # Delete files (if present)
        if target_folder and target_folder.exists():
            shutil.rmtree(target_folder, ignore_errors=True)

        logger.info(f"Deleted extraction: {extraction_id}")

        return {
            "status": "success",
            "message": f"Extraction '{extraction_id}' deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))
