"""
Auth Middleware

FastAPI dependency that validates the JWT Bearer token on protected routes.
Use as: Depends(get_current_user)
"""

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.auth.jwt_handler import decode_token
import config
from logger import logger

# Tells FastAPI where the login endpoint is (used by Swagger UI "Authorize" button)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Validate incoming Bearer JWT token and return the user dict.

    Raises HTTP 401 if token is missing, expired, or invalid.

    Usage in route:
        @router.get("/protected")
        async def my_route(user: dict = Depends(get_current_user)):
            ...
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials — token is missing, expired, or invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception

    # Look up user in hardcoded store
    user = next(
        (u for u in config.HARDCODED_USERS if u["email"].lower() == email.lower()),
        None
    )
    if user is None:
        logger.warning(f"Token valid but user not found: {email}")
        raise credentials_exception

    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Additional dependency: requires the user to have role='admin'.
    Chain with get_current_user for admin-only routes.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
