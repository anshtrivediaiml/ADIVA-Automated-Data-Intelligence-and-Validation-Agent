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

# Load environment variables from .env file
load_dotenv()

# ========================
# Environment Variables
# ========================

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
PROJECT_NAME = os.getenv("PROJECT_NAME", "ADIVA")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

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
# Hardcoded Users
# ========================
# Passwords are bcrypt-hashed. Default plaintext: adiva@2026
# To generate a new hash: from passlib.context import CryptContext; CryptContext(['bcrypt']).hash('yourpassword')

HARDCODED_USERS = [
    {
        "username": "anshtrivedi",
        "name": "Ansh Trivedi",
        "email": "ansh@adiva.ai",
        "role": "admin",
        # bcrypt hash of: adiva@2026
        "hashed_password": "$2b$12$QomktBtHiAp1njTofHaCoeDNHYxyAKpUZEA7RrGaUl5qFGKtTgTIe",
    },
]

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

# Data directories
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"

# Ensure all directories exist
for directory in [EXTRACTED_DIR, VALIDATED_DIR, LOGS_DIR, SAMPLES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ========================
# File Upload Settings
# ========================

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}

# ========================
# API Settings
# ========================

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# ========================
# Mistral AI Settings
# ========================

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
MISTRAL_TEMPERATURE = float(os.getenv("MISTRAL_TEMPERATURE", "0.7"))
MISTRAL_MAX_TOKENS = int(os.getenv("MISTRAL_MAX_TOKENS", "1000"))

# ========================
# Logging Settings
# ========================

LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "30 days"

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOGS_DIR / f"app_{timestamp}.log"


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


# Validate configuration on import
validate_config()
