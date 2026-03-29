"""
ADIVA - Configuration Module

This module manages all configuration settings for the ADIVA system:
- Environment variables
- API keys (Mistral AI)
- File paths and directories
- Application settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file at project root (parent of backend/)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)


def _get_bool_env(name: str, default: bool) -> bool:
    """Parse a boolean environment variable with a sane fallback."""
    return os.getenv(name, str(default)).strip().lower() == "true"


def _get_csv_env(name: str, default: str) -> list[str]:
    """Parse a comma-separated environment variable into a clean list."""
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]

# ========================
# Environment Variables
# ========================

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
PROJECT_NAME = os.getenv("PROJECT_NAME", "ADIVA")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DATABASE_URL = os.getenv("DATABASE_URL")
TESSERACT_CMD_PATH = os.getenv("TESSERACT_CMD_PATH")

# ========================
# JWT Authentication
# ========================

# Secret key used to sign tokens. Override via JWT_SECRET_KEY env var in production.
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "adiva-secret-key-change-in-production-29af8e3c1b7d"
)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ========================
# Admin Seed (optional)
# ========================
# Used by backend/db/seed_admin.py
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_ROLE = os.getenv("ADMIN_ROLE", "admin")
ADMIN_DELETE_EMAILS = os.getenv("ADMIN_DELETE_EMAILS")

# ========================
# Project Paths
# ========================

# Get the project root directory (parent of backend/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Output directories
OUTPUTS_DIR = BASE_DIR / "outputs"
EXTRACTED_DIR = OUTPUTS_DIR / "extracted"
VALIDATED_DIR = OUTPUTS_DIR / "validated"
LOGS_DIR = OUTPUTS_DIR / "logs"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
METRICS_DIR = OUTPUTS_DIR / "metrics"

# Data directories
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"

# Ensure all directories exist
for directory in [EXTRACTED_DIR, VALIDATED_DIR, LOGS_DIR, UPLOADS_DIR, METRICS_DIR, SAMPLES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ========================
# File Upload Settings
# ========================

# Max file size in bytes (default: 200 MB)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(200 * 1024 * 1024)))

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

# Streamed upload chunk size (bytes)
UPLOAD_CHUNK_SIZE = int(os.getenv("UPLOAD_CHUNK_SIZE", str(1024 * 1024)))

# OCR / PDF processing settings
OCR_PDF_RENDER_DPI = int(os.getenv("OCR_PDF_RENDER_DPI", "300"))
OCR_PDF_RENDER_THREADS = int(os.getenv("OCR_PDF_RENDER_THREADS", "2"))
OCR_PAGE_WORKERS = int(os.getenv("OCR_PAGE_WORKERS", "2"))
MAX_OCR_IMAGE_PIXELS = int(os.getenv("MAX_OCR_IMAGE_PIXELS", "3000000"))

# ========================
# API Settings
# ========================

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_WORKERS = int(os.getenv("API_WORKERS", "2"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"
API_SHOW_ERROR_DETAILS = _get_bool_env("API_SHOW_ERROR_DETAILS", DEBUG_MODE)
READINESS_CACHE_TTL_SECONDS = float(os.getenv("READINESS_CACHE_TTL_SECONDS", "3"))
METRICS_SNAPSHOT_MIN_INTERVAL_SECONDS = float(
    os.getenv("METRICS_SNAPSHOT_MIN_INTERVAL_SECONDS", "2")
)
CORS_ORIGINS = _get_csv_env(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000"
)
REQUEST_ID_HEADER = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")
ENABLE_SECURITY_HEADERS = _get_bool_env("ENABLE_SECURITY_HEADERS", True)
HSTS_MAX_AGE_SECONDS = int(os.getenv("HSTS_MAX_AGE_SECONDS", "0"))
JOB_EXECUTION_BACKEND = os.getenv("JOB_EXECUTION_BACKEND", "local").strip().lower()
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

# ========================
# Mistral AI Settings
# ========================

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
MISTRAL_TEMPERATURE = float(os.getenv("MISTRAL_TEMPERATURE", "0.7"))
MISTRAL_MAX_TOKENS = int(os.getenv("MISTRAL_MAX_TOKENS", "1000"))
MISTRAL_TIMEOUT_MS = int(os.getenv("MISTRAL_TIMEOUT_MS", "12000"))
MISTRAL_MAX_RETRIES = int(os.getenv("MISTRAL_MAX_RETRIES", "2"))
MISTRAL_RETRY_BACKOFF_MS = int(os.getenv("MISTRAL_RETRY_BACKOFF_MS", "800"))

# Extraction review gates
REVIEW_MIN_QUALITY_SCORE = float(os.getenv("REVIEW_MIN_QUALITY_SCORE", "0.65"))
REVIEW_MIN_OCR_CONFIDENCE = float(os.getenv("REVIEW_MIN_OCR_CONFIDENCE", "0.70"))
LOW_CONFIDENCE_MIN_OCR = float(os.getenv("LOW_CONFIDENCE_MIN_OCR", "0.50"))
REVIEW_MIN_CLASSIFICATION_CONFIDENCE = float(
    os.getenv("REVIEW_MIN_CLASSIFICATION_CONFIDENCE", "0.60")
)
REVIEW_MIN_EXTRACTION_CONFIDENCE = float(
    os.getenv("REVIEW_MIN_EXTRACTION_CONFIDENCE", "0.72")
)
LOW_CONFIDENCE_MIN_EXTRACTION = float(
    os.getenv("LOW_CONFIDENCE_MIN_EXTRACTION", "0.55")
)
VALIDATION_PASS_MIN_CONFIDENCE = float(
    os.getenv("VALIDATION_PASS_MIN_CONFIDENCE", "0.80")
)
VALIDATION_LOW_CONFIDENCE_SCORE = float(
    os.getenv("VALIDATION_LOW_CONFIDENCE_SCORE", "0.55")
)
VALIDATION_ENABLE_TRUTH_TESTS = _get_bool_env("VALIDATION_ENABLE_TRUTH_TESTS", False)
VALIDATION_TRUTH_TEST_WEIGHT = float(
    os.getenv("VALIDATION_TRUTH_TEST_WEIGHT", "0.20")
)
ENABLE_AI_RECOVERY = _get_bool_env("ENABLE_AI_RECOVERY", True)
AI_RECOVERY_SHADOW_MODE = _get_bool_env("AI_RECOVERY_SHADOW_MODE", False)
AI_RECOVERY_MAX_ATTEMPTS = int(os.getenv("AI_RECOVERY_MAX_ATTEMPTS", "2"))
AI_RECOVERY_MIN_IMPROVEMENT = float(os.getenv("AI_RECOVERY_MIN_IMPROVEMENT", "0.05"))
AI_RECOVERY_MIN_ACCEPT_CONFIDENCE = float(
    os.getenv("AI_RECOVERY_MIN_ACCEPT_CONFIDENCE", str(VALIDATION_PASS_MIN_CONFIDENCE))
)
AI_RECOVERY_MAX_FIELDS_PER_ATTEMPT = int(os.getenv("AI_RECOVERY_MAX_FIELDS_PER_ATTEMPT", "5"))
AI_RECOVERY_IN_SCOPE_TYPES = {
    item.strip().lower()
    for item in os.getenv("AI_RECOVERY_IN_SCOPE_TYPES", "invoice,bank_statement").split(",")
    if item.strip()
}

# ========================
# Logging Settings
# ========================

LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "30 days"
LOG_COLORIZE = _get_bool_env("LOG_COLORIZE", False)

# ========================
# Validation
# ========================

def validate_config():
    """
    Validate that all required configuration is present
    """
    errors = []
    
    if not MISTRAL_API_KEY:
        errors.append("MISTRAL_API_KEY is not set in environment variables")
    if not DATABASE_URL:
        errors.append("DATABASE_URL is not set in environment variables")
    
    if errors:
        raise ValueError(
            f"Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
        )
    
    return True


# ========================
# Utility Functions
# ========================

from datetime import datetime

def get_timestamp():
    """
    Get current timestamp in YYYYMMDD_HHMMSS format
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_log_filename():
    """
    Generate timestamped log filename
    Returns: Path to log file with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return LOGS_DIR / f"app_{timestamp}_{os.getpid()}.log"


def get_extraction_folder(source_filename: str = None) -> Path:
    """
    Create and return a unique folder for an extraction run
    
    Args:
        source_filename: Original filename being extracted (optional)
        
    Returns:
        Path to the extraction folder
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create a clean folder name
    if source_filename:
        # Remove extension and clean filename
        clean_name = Path(source_filename).stem
        # Remove spaces and special chars
        clean_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in clean_name)
        folder_name = f"{timestamp}_{clean_name}"
    else:
        folder_name = f"extraction_{timestamp}"
    
    # Create folder path
    extraction_folder = OUTPUTS_DIR / "extracted" / folder_name
    extraction_folder.mkdir(parents=True, exist_ok=True)
    
    return extraction_folder


def get_output_filename(prefix: str, extension: str, extraction_folder: Path = None) -> str:
    """
    Generate timestamped output filename
    
    Args:
        prefix: Filename prefix (e.g., 'extracted', 'report')
        extension: File extension including dot (e.g., '.json', '.csv')
        extraction_folder: Optional folder to save in (new structure)
        
    Returns:
        Full path to output file
    """
    if extraction_folder:
        # New structure: save in specific extraction folder
        filename = f"{prefix}{extension}"
        return str(extraction_folder / filename)
    else:
        # Legacy structure: timestamp in filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}{extension}"
        output_path = OUTPUTS_DIR / "extracted"
        output_path.mkdir(parents=True, exist_ok=True)
        return str(output_path / filename)

