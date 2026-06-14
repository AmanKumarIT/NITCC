"""
NITCC Authentication & Authorization
JWT + MFA (TOTP) + RBAC with 5 roles (PRD Section 8.4)
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .schemas.models import UserRole
from .config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# ─────────────────────────────────────────────────────────────────────────────
# RBAC Role Hierarchy
# Roles are ordered: ReadOnly < Operator < Supervisor < Emergency < Admin
# Each role implicitly includes permissions of lower roles.
# ─────────────────────────────────────────────────────────────────────────────

ROLE_HIERARCHY = {
    UserRole.READ_ONLY:  0,
    UserRole.OPERATOR:   1,
    UserRole.SUPERVISOR: 2,
    UserRole.EMERGENCY:  3,
    UserRole.ADMIN:      4,
}


def role_level(role: UserRole) -> int:
    return ROLE_HIERARCHY.get(role, -1)


# ─────────────────────────────────────────────────────────────────────────────
# Password Utilities
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─────────────────────────────────────────────────────────────────────────────
# MFA (TOTP — RFC 6238)  — FR-08.4
# ─────────────────────────────────────────────────────────────────────────────

def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def get_mfa_provisioning_uri(email: str, secret: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.mfa_issuer)


def verify_totp(secret: str, token: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)  # ±30s window


# ─────────────────────────────────────────────────────────────────────────────
# JWT Token Management
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    email: str,
    roles: List[UserRole],
    jurisdiction_zones: List[str],
) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "email": email,
        "roles": [r.value for r in roles],
        "zones": jurisdiction_zones,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.app_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Dependencies
# ─────────────────────────────────────────────────────────────────────────────

class CurrentUser:
    """Parsed JWT claims for the authenticated request."""

    def __init__(self, payload: dict):
        self.user_id: str = payload["sub"]
        self.email: str = payload.get("email", "")
        self.roles: List[UserRole] = [UserRole(r) for r in payload.get("roles", [])]
        self.jurisdiction_zones: List[str] = payload.get("zones", [])

    @property
    def max_role_level(self) -> int:
        return max((role_level(r) for r in self.roles), default=-1)

    def has_role(self, required: UserRole) -> bool:
        return self.max_role_level >= role_level(required)

    def can_access_zone(self, zone: str) -> bool:
        """Operators are restricted to their jurisdiction zones."""
        if self.has_role(UserRole.SUPERVISOR):
            return True  # Supervisor+ sees all zones
        return zone in self.jurisdiction_zones


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return CurrentUser(payload)


def require_role(minimum_role: UserRole):
    """FastAPI dependency factory for RBAC (FR-03.4)."""

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_role(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role.value}' or higher required",
            )
        return user

    return _check


# Convenience role dependencies
require_operator   = require_role(UserRole.OPERATOR)
require_supervisor = require_role(UserRole.SUPERVISOR)
require_emergency  = require_role(UserRole.EMERGENCY)
require_admin      = require_role(UserRole.ADMIN)
