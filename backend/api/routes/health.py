"""Health, readiness, and runtime metrics routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.models.responses import HealthResponse
from logger import logger
from observability import get_readiness_snapshot, runtime_metrics
import config

router = APIRouter()


@router.get("/health/live")
async def liveness_check():
    """Simple process liveness endpoint."""
    return {
        "status": "alive",
        "version": "1.0.0",
    }


@router.get("/health/ready")
async def readiness_check():
    """Dependency-aware readiness check."""
    readiness = get_readiness_snapshot()
    status_code = 200 if readiness["status"] == "ready" else 503
    logger.info(f"Readiness check requested | status={readiness['status']}")
    return JSONResponse(status_code=status_code, content=readiness)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Backward-compatible summary health endpoint.
    """
    readiness = get_readiness_snapshot()
    dependencies = {
        "database": readiness["checks"]["database"]["status"],
        "queue": readiness["checks"]["queue"]["status"],
        "storage": readiness["checks"]["storage"]["status"],
        "ocr": readiness["checks"]["ocr"]["status"],
        "mistral_ai": readiness["checks"]["llm"]["status"],
    }
    overall = "healthy" if readiness["status"] == "ready" else "degraded"
    logger.info(f"Health check requested | status={overall}")
    return HealthResponse(
        status=overall,
        version="1.0.0",
        dependencies=dependencies,
    )


@router.get("/metrics")
async def metrics_snapshot():
    """Machine-readable runtime metrics snapshot."""
    return runtime_metrics.snapshot()


@router.get("/status")
async def api_status():
    """
    Detailed operational status view.
    """
    readiness = get_readiness_snapshot()
    metrics = runtime_metrics.snapshot()
    return {
        "api": "ADIVA Document Extraction",
        "version": "1.0.0",
        "status": "running",
        "readiness": readiness["status"],
        "features": {
            "pdf_extraction": True,
            "docx_extraction": True,
            "ocr_extraction": True,
            "ai_classification": bool(config.MISTRAL_API_KEY),
            "multi_language": True,
            "batch_processing": True,
            "async_jobs": True,
            "job_execution_backend": config.JOB_EXECUTION_BACKEND,
            "exports": ["json", "csv", "xlsx", "html"],
        },
        "dependencies": readiness["checks"],
        "runtime_metrics": metrics["jobs"],
        "supported_languages": ["English", "Hindi", "Gujarati"],
        "supported_document_types": ["invoice", "resume", "contract"],
    }
