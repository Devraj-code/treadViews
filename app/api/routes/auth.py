"""Authentication routes: register, login, refresh, forgot/reset password, profile."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    REFRESH_TOKEN,
    RESET_TOKEN,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    encrypt_secret,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import TradingViewCredential, User
from app.schemas.auth import (
    ForgotPasswordRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    TradingViewCredentialIn,
    UserLogin,
    UserProfile,
    UserRegister,
    UserUpdate,
)
from app.services.audit import record_audit
from app.services.email import send_password_reset

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    record_audit(db, action="user.register", user_id=user.id, ip_address=_client_ip(request))
    return user


@router.post("/login", response_model=TokenPair)
def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """OAuth2-compatible login. `username` field carries the email."""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        record_audit(db, action="user.login_failed", detail=form_data.username, ip_address=_client_ip(request))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, action="user.login", user_id=user.id, ip_address=_client_ip(request))
    return _issue_tokens(user)


@router.post("/login/json", response_model=TokenPair)
def login_json(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    """JSON login for SPA clients."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, action="user.login", user_id=user.id, ip_address=_client_ip(request))
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token, expected_type=REFRESH_TOKEN)
    if not data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = db.get(User, data.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _issue_tokens(user)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return 200 to avoid user enumeration.
    if user:
        token = create_reset_token(user.id)
        send_password_reset(user.email, token)
        record_audit(db, action="user.forgot_password", user_id=user.id)
    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.token, expected_type=RESET_TOKEN)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")
    user = db.get(User, data.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid token")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    record_audit(db, action="user.reset_password", user_id=user.id)
    return {"message": "Password updated successfully"}


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserProfile)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.password:
        current_user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/me/tradingview-credentials", status_code=status.HTTP_204_NO_CONTENT)
def set_tv_credentials(
    payload: TradingViewCredentialIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store encrypted TradingView credentials for autonomous login."""
    cred = current_user.credential
    if cred is None:
        cred = TradingViewCredential(user_id=current_user.id)
        db.add(cred)
    cred.tv_username = payload.tv_username
    cred.tv_password_encrypted = encrypt_secret(payload.tv_password)
    db.commit()
    record_audit(db, action="user.set_tv_credentials", user_id=current_user.id)
