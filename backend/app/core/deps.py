from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..models.models import User
from .db import app_engine, set_scope
from .security import decode_token

ALL_ROLES = {"OPERATOR", "APPROVER", "AICTE_REVIEWER", "AICTE_SUPERVISOR", "ADMIN", "AUDITOR"}
AICTE_ROLES = {"AICTE_REVIEWER", "AICTE_SUPERVISOR", "ADMIN", "AUDITOR"}


@dataclass
class Principal:
    id: uuid.UUID
    role: str
    scope_ids: list[str]


def _error(code: str, message: str, status: int):
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message, "details": {}}})


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _error("UNAUTHENTICATED", "Missing bearer token", 401)
    token = authorization.split(" ", 1)[1]
    claims = decode_token(token)
    if not claims:
        raise _error("UNAUTHENTICATED", "Invalid or expired token", 401)
    return Principal(
        id=uuid.UUID(claims["sub"]),
        role=claims["role"],
        scope_ids=[str(s) for s in claims.get("scope_ids", [])],
    )


def get_scoped_db(principal: Principal = Depends(current_principal)) -> Iterator[Session]:
    """App-role session with RLS scope set for this request (deny-by-default elsewhere)."""
    session = Session(bind=app_engine(), expire_on_commit=False, future=True)
    try:
        session.begin()
        set_scope(session, principal.role, principal.scope_ids)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def require_roles(*roles: str):
    allowed = set(roles)

    def _dep(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in allowed:
            raise _error("FORBIDDEN", f"Requires one of {sorted(allowed)}", 403)
        return principal

    return _dep


def load_user(session: Session, principal: Principal) -> User:
    user = session.get(User, principal.id)
    if user is None or user.disabled:
        raise _error("UNAUTHENTICATED", "User not found or disabled", 401)
    return user
