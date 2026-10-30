from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.audit import append_event
from ..core.db import app_engine, set_scope
from ..core.deps import Principal, _error, current_principal
from ..core.security import create_access_token, login_limiter, verify_password
from ..models.models import User
from sqlalchemy.orm import Session as _S

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str


def _admin_session() -> Session:
    # Admin-scope session for login (read users table). AICTE/ADMIN role bypasses institution RLS.
    s = _S(bind=app_engine(), expire_on_commit=False, future=True)
    s.begin()
    set_scope(s, "ADMIN", [])
    return s


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request):
    key = f"{request.client.host if request.client else 'x'}:{body.email}"
    if not login_limiter.allow(key):
        raise _error("RATE_LIMITED", "Too many login attempts", 429)

    session = _admin_session()
    try:
        user = session.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
        if user is None or user.disabled or not verify_password(body.password, user.password_hash):
            raise _error("INVALID_CREDENTIALS", "Invalid email or password", 401)
        login_limiter.reset(key)
        token = create_access_token(str(user.id), user.role, [str(i) for i in user.institution_ids])
        append_event(session, actor_id=user.id, action="LOGIN", entity_type="user", entity_id=str(user.id))
        session.commit()
        return TokenOut(access_token=token, role=user.role, user_id=str(user.id))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class MeOut(BaseModel):
    user_id: str
    role: str
    scope_ids: list[str]


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(current_principal)):
    return MeOut(user_id=str(principal.id), role=principal.role, scope_ids=principal.scope_ids)
