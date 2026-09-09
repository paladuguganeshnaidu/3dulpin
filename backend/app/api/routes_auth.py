"""Auth routes: register, login, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.enums import Role
from ..core.security import create_access_token, hash_password, verify_password
from ..db.models import User
from ..db.session import get_db
from ..services.audit import audit
from .deps import get_current_user
from .schemas import LoginIn, RegisterIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_payload(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
    }


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.execute(
        select(User).where((User.email == payload.email) | (User.username == payload.username))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Email or username already registered.")
    user = User(
        email=payload.email.lower(),
        username=payload.username,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=Role.VIEWER.value,  # self-registration always starts as viewer
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    settings = get_settings()
    token = create_access_token(
        str(user.id),
        settings.jwt_secret_key,
        expires_minutes=settings.access_token_expire_minutes,
        extra={"role": user.role},
    )
    audit(db, "login", user_id=user.id, target_type="user", target_id=user.email)
    return TokenOut(access_token=token, user=_user_payload(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password.")
    if not user.is_active:
        raise HTTPException(403, "Account disabled.")
    settings = get_settings()
    token = create_access_token(
        str(user.id),
        settings.jwt_secret_key,
        expires_minutes=settings.access_token_expire_minutes,
        extra={"role": user.role},
    )
    audit(db, "login", user_id=user.id, target_type="user", target_id=user.email)
    return TokenOut(access_token=token, user=_user_payload(user))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": _user_payload(user), "roles_available": [r.value for r in Role]}
