"""
ADIVA - Legacy Entry Point

This file delegates to the unified API app in backend/api/main.py.
Keep this as a thin launcher to avoid confusion about which app is used.
"""

import os
import uvicorn

import config
from logger import logger


def _resolve_worker_count() -> int:
    """
    Keep local Windows development single-process.

    Uvicorn multi-worker startup is a poor default for this project on Windows
    and is unnecessary for the normal local workflow. Non-Windows production
    launches can still opt into more workers via API_WORKERS.
    """
    if config.DEBUG_MODE or os.name == "nt":
        return 1
    return max(1, config.API_WORKERS)


def main():
    """
    Main function to start the unified FastAPI application
    """
    logger.info("Starting uvicorn server (delegating to api.main:app)...")
    uvicorn.run(
        "api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.DEBUG_MODE,
        workers=_resolve_worker_count(),
        log_level=config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()
