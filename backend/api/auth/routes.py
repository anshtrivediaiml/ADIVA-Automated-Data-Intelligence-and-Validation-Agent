"""
Auth Routes

POST /api/auth/login   — get tokens
POST /api/auth/refresh — refresh access token
GET  /api/auth/me      — get current user profile
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.auth.models import LoginRequest, TokenResponse, UserInfo, RefreshRequest, MeResponse
from api.auth.jwt_handler import (
    verify_password, create_access_token, create_refresh_token, decode_token
)
from api.middleware.auth_middleware import get_current_user
import config
from db.session import get_db
from db import models
from sqlalchemy.orm import Session
from logger import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ──────────────────────────────────────────
# Helper: look up user from hardcoded store
# ──────────────────────────────────────────

def _get_user(db: Session, email: str) -> models.User | None:
    """Find user by email in the database."""
    return db.query(models.User).filter(models.User.email == email).first()


# ──────────────────────────────────────────
# POST /api/auth/login
# ──────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Login and get JWT tokens")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with **email + password**.

    Returns a short-lived **access_token** (Bearer) and a **refresh_token**.
    Pass the access token as `Authorization: Bearer <token>` on all protected routes.
    """
    user = _get_user(db, body.email)

    if not user or not verify_password(body.password, user.hashed_password):
        logger.warning(f"Failed login attempt for: {body.email}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = {"sub": user.email, "name": user.name, "role": user.role}
    access_token  = create_access_token(token_payload)
    refresh_token = create_refresh_token({"sub": user.email})

    logger.info(f"Successful login: {user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserInfo(name=user.name, email=user.email, role=user.role)
    )


# ──────────────────────────────────────────
# POST /api/auth/refresh
# ──────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid **refresh_token** for a new access token without re-logging in.
    """
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        email = payload.get("sub")
        user  = _get_user(db, email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        token_payload = {"sub": user.email, "name": user.name, "role": user.role}
        new_access    = create_access_token(token_payload)
        new_refresh   = create_refresh_token({"sub": user.email})

        logger.info(f"Token refreshed for: {email}")

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserInfo(name=user.name, email=user.email, role=user.role)
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


# ──────────────────────────────────────────
# GET /api/auth/me
# ──────────────────────────────────────────

@router.get("/me", response_model=MeResponse, summary="Get current user profile")
async def get_me(current_user: models.User = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.
    Requires a valid Bearer token.
    """
    return MeResponse(
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        username=current_user.username
    )
