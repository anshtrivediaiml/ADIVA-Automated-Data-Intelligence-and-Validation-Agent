"""
ADIVA - Autonomous Data Intelligence & Verification Agent
Main Application Entry Point

This module serves as the main FastAPI application entry point.
It orchestrates the document processing pipeline:
- Document upload endpoints
- Coordination between extractor, AI agent, and validator
- Response handling and logging
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import config
from logger import logger, log_api_call

# Initialize FastAPI application
app = FastAPI(
    title=config.PROJECT_NAME,
    description="AI-powered backend system for document processing and validation",
    version="1.0.0",
    debug=config.DEBUG_MODE
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    Runs when the application starts
    """
    logger.info("=" * 60)
    logger.info(f"Starting {config.PROJECT_NAME}")
    logger.info(f"API Host: {config.API_HOST}:{config.API_PORT}")
    logger.info(f"Debug Mode: {config.DEBUG_MODE}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs when the application shuts down
    """
    logger.info("=" * 60)
    logger.info(f"Shutting down {config.PROJECT_NAME}")
    logger.info("=" * 60)


@app.get("/")
async def root():
    """
    Root endpoint - API health check
    """
    log_api_call("/", "GET")
    return {
        "message": f"Welcome to {config.PROJECT_NAME}",
        "status": "online",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    log_api_call("/health", "GET")
    return {
        "status": "healthy",
        "project": config.PROJECT_NAME,
        "log_level": config.LOG_LEVEL
    }


# TODO: Include routers from routes.py when implemented
# from routes import router
# app.include_router(router)


def main():
    """
    Main function to start the FastAPI application
    """
    logger.info("Starting uvicorn server...")
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.DEBUG_MODE,
        log_level=config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()

