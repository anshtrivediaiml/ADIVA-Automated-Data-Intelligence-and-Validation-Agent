"""
ADIVA REST API

FastAPI application for document extraction services.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import sys

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from api.routes import extraction, results, health
from logger import logger

# Create FastAPI app
app = FastAPI(
    title="ADIVA - Document Extraction API",
    version="1.0.0",
    description="""
    Intelligent document extraction API powered by AI.
    
    ## Features
    - **Multi-format support**: PDF, DOCX, Images, Scanned documents
    - **Multi-language**: English, Hindi, Gujarati
    - **AI-powered**: Classification and structured data extraction
    - **Multiple outputs**: JSON, CSV, Excel, HTML
    - **Batch processing**: Process multiple documents at once
    
    ## Supported Document Types
    - Invoices
    - Resumes/CVs
    - Contracts
    - Receipts (coming soon)
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler caught: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc)
        }
    )

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(extraction.router, prefix="/api", tags=["Extraction"])
app.include_router(results.router, prefix="/api", tags=["Results"])

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root endpoint"""
    return {
        "message": "ADIVA Document Extraction API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 70)
    logger.info("ADIVA API Starting")
    logger.info("=" * 70)
    logger.info("API Documentation: http://localhost:8000/docs")
    logger.info("Health Check: http://localhost:8000/api/health")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("ADIVA API Shutting Down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
