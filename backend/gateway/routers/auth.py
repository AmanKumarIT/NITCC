"""
Auth Router — Login, MFA, Token Refresh
PRD Screen S1: Login / MFA
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb import users_col
from shared.auth import (
    verify_password, hash_password, create_access_token, create_refresh_token,
    decode_token, verify_totp, generate_mfa_secret, get_mfa_provisioning_uri,
    get_current_user, CurrentUser
)
from shared.schemas.models import UserModel, UserRole, APIResponse

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class MFAVerifyRequest(BaseModel):
    temp_token: str    # Token issued after password check, before MFA
    totp_code: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    requires_mfa: bool = False
    temp_token: Optional[str] = None

class MFASetupResponse(BaseModel):
    secret: str
    qr_uri: str


# ─────────────────────────────────────────────────────────────────────────────
# Helper for Demo Users
# ─────────────────────────────────────────────────────────────────────────────
from shared.config import settings

def get_demo_user(email: str) -> Optional[dict]:
    for user in settings.demo_users:
        if user.get("email", "").lower() == email.lower():
            return user
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, summary="Login (Step 1 of 2 for MFA)")
async def login(body: LoginRequest):
    """
    Step 1: Validate email + password against demo users in .env.
    MFA is bypassed for demo users to ensure easy access.
    """
    demo_user = get_demo_user(body.email)
    if not demo_user or body.password != demo_user.get("password"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Bypass MFA entirely for demo users
    user_id = demo_user["email"]
    email = demo_user["email"]
    roles = [UserRole(demo_user["role"])]
    jurisdiction_zones = []

    access_token = create_access_token(user_id, email, roles, jurisdiction_zones)
    refresh_token = create_refresh_token(user_id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/mfa/verify", response_model=TokenResponse, summary="Login MFA Verification (Step 2)")
async def verify_mfa(body: MFAVerifyRequest):
    # MFA bypassed, this endpoint is not needed for demo users
    raise HTTPException(status_code=400, detail="MFA not required for demo users")


@router.post("/refresh", response_model=TokenResponse, summary="Refresh Access Token")
async def refresh_token(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type")

    demo_user = get_demo_user(payload["sub"])
    if not demo_user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = demo_user["email"]
    email = demo_user["email"]
    roles = [UserRole(demo_user["role"])]
    jurisdiction_zones = []

    access_token = create_access_token(user_id, email, roles, jurisdiction_zones)
    new_refresh = create_refresh_token(user_id)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.get("/me", summary="Get current user profile")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    demo_user = get_demo_user(user.user_id)
    if not demo_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return APIResponse(data={
        "userId": demo_user["email"],
        "email": demo_user["email"],
        "roles": [demo_user["role"]],
        "jurisdictionZones": [],
        "mfaEnabled": False,
        "isActive": True
    })


@router.post("/mfa/setup", summary="Initialize MFA for user", response_model=MFASetupResponse)
async def setup_mfa(user: CurrentUser = Depends(get_current_user)):
    secret = generate_mfa_secret()
    qr_uri = get_mfa_provisioning_uri(user.email, secret)
    # Store secret (activated after first successful verification)
    await users_col().update_one(
        {"userId": user.user_id},
        {"$set": {"mfaSecret": secret, "mfaEnabled": False}}  # Enabled after verify
    )
    return MFASetupResponse(secret=secret, qr_uri=qr_uri)
