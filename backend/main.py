"""
ADIVA - Legacy Entry Point

This file delegates to the unified API app in backend/api/main.py.
Keep this as a thin launcher to avoid confusion about which app is used.
"""

import uvicorn

import config
from logger import logger


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
        log_level=config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()
