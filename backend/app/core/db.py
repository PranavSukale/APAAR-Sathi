from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_owner_engine: Engine | None = None
_app_engine: Engine | None = None


def _engine_kwargs() -> dict:
    import os

    from sqlalchemy.pool import NullPool

    # Serverless: no persistent pool; pre-ping to survive Neon idle drops.
    if os.environ.get("VERCEL") or os.environ.get("SERVERLESS"):
        return {"future": True, "poolclass": NullPool, "pool_pre_ping": True}
    return {"future": True, "pool_pre_ping": True}


def owner_engine() -> Engine:
    global _owner_engine
    if _owner_engine is None:
        _owner_engine = create_engine(get_settings().database_owner_url, **_engine_kwargs())
    return _owner_engine


def app_engine() -> Engine:
    global _app_engine
    if _app_engine is None:
        _app_engine = create_engine(get_settings().database_app_url, **_engine_kwargs())
    return _app_engine


OwnerSession = sessionmaker(bind=None, class_=Session, expire_on_commit=False, future=True)
AppSession = sessionmaker(bind=None, class_=Session, expire_on_commit=False, future=True)


def owner_session() -> Session:
    return Session(bind=owner_engine(), expire_on_commit=False, future=True)


def set_scope(session: Session, role: str, scope_ids: list[str]) -> None:
    """Per-request RLS scope. Uses SET LOCAL so it is bound to the transaction."""
    ids = ",".join(scope_ids)
    session.execute(text("SELECT set_config('app.role', :r, true)"), {"r": role})
    session.execute(text("SELECT set_config('app.scope_ids', :s, true)"), {"s": ids})


def get_db() -> Iterator[Session]:
    """FastAPI dependency: app-role session (RLS enforced)."""
    session = Session(bind=app_engine(), expire_on_commit=False, future=True)
    try:
        yield session
    finally:
        session.close()
