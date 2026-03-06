"""
ADIVA REST API

FastAPI application for document extraction services.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import sys
import os

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from api.routes import extraction, results, health, validation
from api.auth import routes as auth_routes
from logger import logger

# Create FastAPI app
app = FastAPI(
    title="ADIVA - Document Extraction API",
    version="1.0.0",
    description="""
    Intelligent document extraction API powered by AI.

    ## Authentication
    All extraction and results endpoints require a **JWT Bearer token**.
    1. Call `POST /api/auth/login` with your email + password.
    2. Copy the `access_token` from the response.
    3. Click **Authorize** (🔒) above and paste: `Bearer <token>`.

    ## Features
    - **Multi-format support**: PDF, DOCX, Images, Scanned documents
    - **Multi-language**: English, Hindi, Gujarati
    - **AI-powered**: Mistral-powered classification and structured extraction
    - **21 Document Types**: Invoices, Resumes, Contracts, Aadhaar, PAN, DL, Passport,
      Cheque, Form 16, Insurance Policy, GST Certificate,
      Birth/Death Certificate, Land Record, NREGA Card, and more
    - **Multiple outputs**: JSON, CSV, Excel, HTML
    - **Batch processing**: Up to 20 documents at once
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
_ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
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
app.include_router(health.router,       prefix="/api",  tags=["Health"])
app.include_router(auth_routes.router,  prefix="/api",  tags=["Authentication"])
app.include_router(extraction.router,   prefix="/api",  tags=["Extraction"])
app.include_router(results.router,      prefix="/api",  tags=["Results"])
app.include_router(validation.router,   prefix="/api",  tags=["Validation"])

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
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


# ──────────────────────────────────────────────────────────
# Custom OpenAPI schema — adds BearerAuth to Swagger UI
# ──────────────────────────────────────────────────────────
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Inject BearerAuth security scheme
    schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste your access_token from POST /api/auth/login here.",
    }

    # Apply BearerAuth to every protected path (skip /auth and /health)
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api/auth") or path.startswith("/api/health") or path == "/":
            continue
        for method in methods.values():
            method.setdefault("security", []).append({"BearerAuth": []})

    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi
