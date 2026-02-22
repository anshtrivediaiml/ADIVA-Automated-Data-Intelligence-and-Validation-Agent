"""
JWT Handler

Handles token creation, verification and user authentication.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from logger import logger

# ──────────────────────────────────────────
# Password hashing context
# ──────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


# ──────────────────────────────────────────
# Token creation / verification
# ──────────────────────────────────────────

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload dict (must include 'sub' = username/email)
        expires_delta: Optional custom TTL; defaults to config value
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta
        else timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    token = jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    logger.debug(f"Access token created for: {data.get('sub')} | expires: {expire}")
    return token


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a longer-lived refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Returns:
        Decoded payload dict

    Raises:
        JWTError on invalid/expired token
    """
    return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])


def get_token_user(token: str) -> Optional[str]:
    """Extract username/email from token. Returns None on failure."""
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except JWTError:
        return None
