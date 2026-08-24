"""
Auth endpoints — JWT-based, simple RBAC for hackathon MVP.
Roles: MERCHANT_ADMIN, OPERATOR, AUDITOR, SYSTEM
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, create_access_token, hash_password, verify_password
from app.models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "OPERATOR"
    full_name: str | None = None


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    token = create_access_token(subject=user.username, role=Role(user.role))
    return TokenResponse(access_token=token, role=user.role)


@router.post("/register", status_code=201, response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Register a new user. In production this would require MERCHANT_ADMIN role."""
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    user = User(
        username=request.username,
        hashed_password=hash_password(request.password),
        role=role.value,
        full_name=request.full_name,
    )
    db.add(user)
    await db.flush()

    token = create_access_token(subject=user.username, role=role)
    return TokenResponse(access_token=token, role=role.value)
