from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.models.user import User
from app.core.config import settings
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import structlog

logger = structlog.get_logger()


router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, email=user.email, full_name=user.full_name)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


async def _send_reset_email(email: str, token: str) -> None:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    if not settings.RESEND_API_KEY:
        logger.info("password_reset_link", email=email, url=reset_url)
        return
    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": "Passwort zurücksetzen — MA Analytics",
            "html": f"""
                <p>Hallo,</p>
                <p>du hast ein Passwort-Reset für dein MA Analytics-Konto angefordert.</p>
                <p><a href="{reset_url}" style="background:#4f46e5;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;display:inline-block;">Passwort zurücksetzen</a></p>
                <p>Dieser Link ist 1 Stunde gültig. Falls du kein Reset angefordert hast, kannst du diese E-Mail ignorieren.</p>
            """,
        })
    except Exception as e:
        logger.error("reset_email_failed", email=email, error=str(e))


@router.post("/forgot-password", status_code=200)
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # Always return 200 — never reveal if email exists (prevents enumeration)
    if not user:
        return {"message": "If this email exists, a reset link has been sent."}

    plain_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    user.reset_token_hash = token_hash
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.commit()

    await _send_reset_email(user.email, plain_token)
    return {"message": "If this email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    result = await db.execute(select(User).where(User.reset_token_hash == token_hash))
    user = result.scalar_one_or_none()

    if not user or not user.reset_token_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if user.reset_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(body.new_password)
    user.reset_token_hash = None
    user.reset_token_expires = None
    await db.commit()

    return {"message": "Password updated successfully"}
