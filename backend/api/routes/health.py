"""
Health Check Routes

API health and status endpoints.
"""

from fastapi import APIRouter
from api.models.responses import HealthResponse
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from logger import logger
import config

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check API health and dependencies status
    
    Returns health status and availability of key dependencies.
    """
    dependencies = {}
    
    # Check Tesseract
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        dependencies["tesseract"] = "available"
    except:
        dependencies["tesseract"] = "not available"
    
    # Check Mistral AI
    try:
        if config.MISTRAL_API_KEY:
            dependencies["mistral_ai"] = "configured"
        else:
            dependencies["mistral_ai"] = "not configured"
    except:
        dependencies["mistral_ai"] = "error"
    
    # Check OCR
    try:
        from extractors.ocr_extractor import HAS_OCR
        dependencies["ocr"] = "ready" if HAS_OCR else "not available"
    except:
        dependencies["ocr"] = "error"
    
    logger.info("Health check requested")
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        dependencies=dependencies
    )


@router.get("/status")
async def api_status():
    """
    Get detailed API status
    
    Returns more detailed status information including configuration.
    """
    return {
        "api": "ADIVA Document Extraction",
        "version": "1.0.0",
        "status": "running",
        "features": {
            "pdf_extraction": True,
            "docx_extraction": True,
            "ocr_extraction": True,
            "ai_classification": bool(config.MISTRAL_API_KEY),
            "multi_language": True,
            "batch_processing": True,
            "exports": ["json", "csv", "excel", "html"]
        },
        "supported_languages": ["English", "Hindi", "Gujarati"],
        "supported_document_types": ["invoice", "resume", "contract"]
    }
