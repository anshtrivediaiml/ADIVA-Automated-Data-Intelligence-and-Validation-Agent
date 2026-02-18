"""
Pydantic Response Models

Define response schemas for API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class ExtractionResponse(BaseModel):
    """Response for single document extraction"""
    status: str = Field(..., description="Status of extraction (success/error)")
    extraction_id: str = Field(..., description="Unique extraction identifier")
    document_type: Optional[str] = Field(None, description="Detected document type")
    confidence: Optional[float] = Field(None, description="Overall extraction confidence")
    extraction_folder: str = Field(..., description="Path to extraction folder")
    files: Dict[str, str] = Field(default_factory=dict, description="Generated file paths")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Complete extracted JSON data")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "extraction_id": "20260204_180000_invoice",
                "document_type": "invoice",
                "confidence": 0.885,
                "extraction_folder": "outputs/extracted/20260204_180000_invoice",
                "files": {
                    "json": "extraction.json",
                    "csv": "extraction.csv",
                    "excel": "extraction.xlsx",
                    "html": "extraction.html"
                },
                "processing_time": 8.5
            }
        }


class BatchResponse(BaseModel):
    """Response for batch extraction"""
    status: str
    batch_id: str
    batch_folder: str
    total_documents: int
    processed: int
    failed: int
    results: List[ExtractionResponse]
    processing_time: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "batch_id": "batch_20260204_180000",
                "batch_folder": "outputs/extracted/batch_20260204_180000",
                "total_documents": 3,
                "processed": 3,
                "failed": 0,
                "results": [],
                "processing_time": 25.3
            }
        }


class ExtractionListItem(BaseModel):
    """Single extraction in list"""
    extraction_id: str
    document_type: Optional[str]
    filename: str
    processed_at: str
    confidence: Optional[float]
    status: str


class ExtractionListResponse(BaseModel):
    """Response for listing extractions"""
    total: int
    page: int
    page_size: int
    extractions: List[ExtractionListItem]


class ErrorResponse(BaseModel):
    """Error response"""
    status: str = "error"
    message: str
    detail: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "message": "File upload failed",
                "detail": "File size exceeds maximum allowed size"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    dependencies: Dict[str, str]
    uptime: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "dependencies": {
                    "tesseract": "available",
                    "mistral_ai": "available",
                    "ocr": "ready"
                }
            }
        }
