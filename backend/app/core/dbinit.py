from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from ..models import models  # noqa: F401  (register all tables)
from ..models.base import Base
from .config import get_settings
from .db import owner_engine

RLS_SQL = Path(__file__).with_name("rls.sql")


def init_db(drop: bool = False) -> None:
    settings = get_settings()
    engine = owner_engine()
    with engine.begin() as conn:
        if drop:
            Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)

    sql = RLS_SQL.read_text(encoding="utf-8").format(
        app_user=settings.app_db_user, app_password=settings.app_db_password
    )
    # psycopg can execute a multi-statement script in one go.
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(sql)
        raw.commit()
    finally:
        raw.close()


def reset_db() -> None:
    """Drop and recreate all tables + RLS. Used by seed-reset and tests."""
    init_db(drop=True)


if __name__ == "__main__":
    init_db()
    print("DB initialised (tables + RLS).")
