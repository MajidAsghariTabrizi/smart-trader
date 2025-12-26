# -*- coding: utf-8 -*-
"""
SmartTrader Auth Module
- JWT token generation/validation
- Password hashing/verification
- FastAPI dependencies for auth
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database_setup import get_db_connection, USERS_TABLE

# =====================================================================
# Configuration
# =====================================================================

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "smarttrader-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# =====================================================================
# Password Hashing
# =====================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# =====================================================================
# JWT Token Management
# =====================================================================


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# =====================================================================
# User Lookup
# =====================================================================


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email from database."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        row = conn.execute(
            f"SELECT id, email, password_hash, role, is_active, created_at FROM {USERS_TABLE} WHERE email = ?",
            (email,),
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID from database."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        row = conn.execute(
            f"SELECT id, email, password_hash, role, is_active, created_at FROM {USERS_TABLE} WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


# =====================================================================
# FastAPI Dependencies
# =====================================================================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user.
    Raises 401 if token is invalid or user not found.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_auth():
    """Helper to mark endpoints as requiring authentication."""
    return Depends(get_current_user)


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require admin role."""
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user

