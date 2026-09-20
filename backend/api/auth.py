from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from backend.database.database import (
    fetch_one,
    execute,
)
from backend.services.usage_service import ensure_customer


# =========================================================
# CONFIGURATION
# =========================================================

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

security_scheme = HTTPBearer()

JWT_ALGORITHM = "HS256"

JWT_SECRET_KEY = os.getenv(
    "SAIRLAB_JWT_SECRET",
    "sair-lab-development-secret-change-this-in-production",
)

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


# =========================================================
# PASSWORD HASHING
# =========================================================

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """
    Securely hash a password.
    """

    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a password against its stored hash.
    """

    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# =========================================================
# REQUEST MODELS
# =========================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# =========================================================
# JWT
# =========================================================

def create_access_token(
    customer_id: str,
    email: str,
) -> str:
    """
    Create a JWT access token.
    """

    now = datetime.now(timezone.utc)

    expires = now + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": customer_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


# =========================================================
# CURRENT USER
# =========================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security_scheme
    ),
) -> dict:
    """
    Validate JWT and return authenticated user.
    """

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    customer_id = payload.get("sub")
    email = payload.get("email")

    if not customer_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    user = fetch_one(
        """
        SELECT
            id,
            customer_id,
            email,
            plan,
            created_at
        FROM users
        WHERE customer_id = ?
        """,
        (customer_id,),
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    return user


# =========================================================
# REGISTER
# =========================================================

@router.post("/register")
def register(
    request: RegisterRequest,
):
    """
    Create a new Sair Lab customer account.
    """

    email = str(request.email).strip().lower()
    password = request.password

    # -----------------------------------------------------
    # PASSWORD VALIDATION
    # -----------------------------------------------------

    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least 8 characters.",
        )

    # -----------------------------------------------------
    # CHECK EXISTING EMAIL
    # -----------------------------------------------------

    existing_user = fetch_one(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (email,),
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # -----------------------------------------------------
    # CREATE CUSTOMER ID
    # -----------------------------------------------------

    customer_id = (
        f"cus_{uuid.uuid4().hex}"
    )

    password_hash = hash_password(
        password
    )

    # -----------------------------------------------------
    # CREATE USER
    # -----------------------------------------------------

    execute(
        """
        INSERT INTO users (
            customer_id,
            email,
            password_hash,
            plan
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            customer_id,
            email,
            password_hash,
            "free",
        ),
    )

    # -----------------------------------------------------
    # INITIALIZE USAGE
    # -----------------------------------------------------

    ensure_customer(
        customer_id
    )

    return {
        "message": "Account created successfully.",
        "customer_id": customer_id,
        "email": email,
        "plan": "free",
    }


# =========================================================
# LOGIN
# =========================================================

@router.post("/login")
def login(
    request: LoginRequest,
):
    """
    Authenticate an existing customer.
    """

    email = str(request.email).strip().lower()

    user = fetch_one(
        """
        SELECT
            id,
            customer_id,
            email,
            password_hash,
            plan,
            created_at
        FROM users
        WHERE email = ?
        """,
        (email,),
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    password_valid = verify_password(
        request.password,
        user["password_hash"],
    )

    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    token = create_access_token(
        customer_id=user["customer_id"],
        email=user["email"],
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "customer_id": user["customer_id"],
        "email": user["email"],
        "plan": user["plan"],
    }


# =========================================================
# CURRENT USER
# =========================================================

@router.get("/me")
def get_me(
    current_user: dict = Depends(
        get_current_user
    ),
):
    """
    Return the authenticated customer's account.
    """

    return {
        "customer_id": current_user["customer_id"],
        "email": current_user["email"],
        "plan": current_user["plan"],
        "created_at": current_user["created_at"],
    }
