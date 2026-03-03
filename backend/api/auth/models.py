"""
Auth Pydantic Models

Request and response schemas for authentication endpoints.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    """Body for POST /api/auth/login"""
    email: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "email": "ansh@adiva.ai",
                "password": "your_password"
            }
        }


class TokenResponse(BaseModel):
    """Successful login response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds
    user: "UserInfo"


class UserInfo(BaseModel):
    """Public user profile embedded in token response"""
    name: str
    email: str
    role: str


class RefreshRequest(BaseModel):
    """Body for POST /api/auth/refresh"""
    refresh_token: str


class MeResponse(BaseModel):
    """Response for GET /api/auth/me"""
    name: str
    email: str
    role: str
    username: Optional[str] = None


# Rebuild to allow forward ref
TokenResponse.model_rebuild()
