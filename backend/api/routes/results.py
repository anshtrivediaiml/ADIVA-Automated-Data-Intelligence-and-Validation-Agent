"""
Results Routes

Endpoints for retrieving and managing extraction results.
"""

from fastapi import APIRouter, HTTPException, Query, Path as PathParam
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
import sys
from pathlib import Path
import json
import shutil

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from api.models.responses import ExtractionListResponse, ExtractionListItem
from logger import logger
import config

router = APIRouter()


@router.get("/results/{extraction_id}")
async def get_results(extraction_id: str):
    """
    Get extraction results by ID
    
    Retrieve complete extraction results as JSON.
    
    - **extraction_id**: Extraction folder name (e.g., 20260204_180000_invoice)
    
    Returns full extraction data including text, structured data, confidence scores, etc.
    """
    try:
        # Find extraction folder
        extraction_folder = config.OUTPUTS_DIR / "extracted" / extraction_id
        json_file = extraction_folder / "extraction.json"
        
        if not json_file.exists():
            raise HTTPException(status_code=404, detail=f"Extraction '{extraction_id}' not found")
        
        # Load and return results
        with open(json_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        logger.info(f"Retrieved results for: {extraction_id}")
        return results
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{extraction_id}/{format}")
async def download_file(
    extraction_id: str,
    format: str = PathParam(..., pattern="^(json|csv|xlsx|html)$", description="File format")
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
        
        # Find file
        extraction_folder = config.OUTPUTS_DIR / "extracted" / extraction_id
        file_path = extraction_folder / f"extraction.{ext}"
        
        if not file_path.exists():
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
    document_type: Optional[str] = Query(None, description="Filter by document type")
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
        extracted_dir = config.OUTPUTS_DIR / "extracted"
        
        if not extracted_dir.exists():
            return ExtractionListResponse(
                total=0,
                page=page,
                page_size=page_size,
                extractions=[]
            )
        
        # Get all extraction folders
        folders = [f for f in extracted_dir.iterdir() if f.is_dir() and not f.name.startswith('batch_')]
        
        # Sort by modification time (newest first)
        folders.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Load metadata and filter
        extractions = []
        for folder in folders:
            json_file = folder / "extraction.json"
            if not json_file.exists():
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Filter by document type if specified
                doc_type = data.get('classification', {}).get('document_type')
                if document_type and doc_type != document_type:
                    continue
                
                extractions.append(ExtractionListItem(
                    extraction_id=folder.name,
                    document_type=doc_type,
                    filename=data.get('metadata', {}).get('filename', 'unknown'),
                    processed_at=data.get('metadata', {}).get('processed_at', ''),
                    confidence=data.get('comprehensive_confidence', {}).get('overall_confidence'),
                    status=data.get('status', 'unknown')
                ))
            except:
                continue
        
        # Pagination
        total = len(extractions)
        start = (page - 1) * page_size
        end = start + page_size
        page_extractions = extractions[start:end]
        
        logger.info(f"Listed {len(page_extractions)} extractions (page {page}, total {total})")
        
        return ExtractionListResponse(
            total=total,
            page=page,
            page_size=page_size,
            extractions=page_extractions
        )
    
    except Exception as e:
        logger.error(f"Failed to list extractions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/extractions/{extraction_id}")
async def delete_extraction(extraction_id: str):
    """
    Delete extraction and all associated files
    
    Permanently delete an extraction folder and all its files.
    
    - **extraction_id**: Extraction folder name
    
    Returns confirmation of deletion.
    """
    try:
        extraction_folder = config.OUTPUTS_DIR / "extracted" / extraction_id
        
        if not extraction_folder.exists():
            raise HTTPException(status_code=404, detail=f"Extraction '{extraction_id}' not found")
        
        # Delete folder and all contents
        shutil.rmtree(extraction_folder)
        
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
