"""
ADIVA - Centralized Logging Module

This module sets up centralized logging using loguru.
Import this module in other modules to use the logger:
    from logger import logger
"""

import sys
from loguru import logger
from pathlib import Path
import config

# Remove default handler
logger.remove()

# Add console handler with color
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=config.LOG_LEVEL,
    colorize=True
)

# Add file handler with timestamped filename
log_file = config.get_log_filename()
logger.add(
    log_file,
    format="[{time:YYYY-MM-DD HH:mm:ss}] [{name}] [{level}] {message}",
    level=config.LOG_LEVEL,
    rotation=config.LOG_ROTATION,
    retention=config.LOG_RETENTION,
    compression="zip",
    backtrace=True,
    diagnose=True
)

# Log startup
logger.info(f"Logging system initialized - Log file: {log_file}")
logger.info(f"Log level: {config.LOG_LEVEL}")



# Utility functions for consistent logging
def log_api_call(endpoint: str, method: str, details: str = ""):
    """Log API endpoint calls"""
    logger.info(f"API Call - {method} {endpoint} {details}")


def log_error(error_type: str, error_message: str, details: str = ""):
    """Log errors with context"""
    logger.error(f"{error_type}: {error_message} | {details}")


def log_ai_response(prompt_length: int, response_length: int, model: str):
    """Log AI/LLM interactions"""
    logger.info(f"AI Response - Model: {model}, Prompt: {prompt_length} chars, Response: {response_length} chars")


def log_file_upload(filename: str, file_size: int, file_type: str):
    """Log file upload events"""
    logger.info(f"File Upload - Name: {filename}, Size: {file_size} bytes, Type: {file_type}")


def log_validation(status: str, data_type: str, details: str = ""):
    """Log validation results"""
    logger.info(f"Validation - Status: {status}, Type: {data_type} | {details}")


def log_extraction(filename: str, text_length: int, extraction_time: float):
    """Log text extraction events"""
    logger.info(f"Text Extraction - File: {filename}, Length: {text_length} chars, Time: {extraction_time:.2f}s")


# Export logger and utility functions
__all__ = [
    "logger",
    "log_api_call",
    "log_error",
    "log_ai_response",
    "log_file_upload",
    "log_validation",
    "log_extraction"
]
