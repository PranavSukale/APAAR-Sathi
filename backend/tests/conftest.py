from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core import crypto
from backend.app.core.db import app_engine, owner_engine, set_scope
from backend.app.core.dbinit import reset_db
from backend.app.core.security import hash_password
from backend.app.models.models import Institution, User


def _db_available() -> bool:
    try:
        with owner_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not running (make up)")


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if not _db_available():
        pytest.skip("Postgres not available")
    reset_db()
    yield


@pytest.fixture
def owner_db() -> Session:
    s = Session(bind=owner_engine(), expire_on_commit=False, future=True)
    yield s
    s.close()


def app_session(role: str, scope_ids: list[str]) -> Session:
    s = Session(bind=app_engine(), expire_on_commit=False, future=True)
    s.begin()
    set_scope(s, role, scope_ids)
    return s


# FK-safe truncation order covering every table the DB-mutating fixtures touch, so each test
# starts from the same clean state regardless of module execution order.
_TRUNCATE_ORDER = [
    "audit_events", "reveal_requests", "enrolment_episodes", "student_records",
    "programs", "institutions", "users",
]


def truncate_all(session: Session) -> None:
    for tbl in _TRUNCATE_ORDER:
        session.execute(text(f"DELETE FROM {tbl}"))
    session.commit()


@pytest.fixture
def two_institutions(owner_db: Session):
    """Create institution A and B with an operator each, and one student record in each."""
    truncate_all(owner_db)

    a = Institution(official_institution_code="INST-A", name="Inst A", normalized_name="inst a")
    b = Institution(official_institution_code="INST-B", name="Inst B", normalized_name="inst b")
    owner_db.add_all([a, b])
    owner_db.flush()

    op_a = User(
        email="op_a@example.org", full_name="Op A", password_hash=hash_password("pw"),
        role="OPERATOR", institution_ids=[str(a.id)],
    )
    op_b = User(
        email="op_b@example.org", full_name="Op B", password_hash=hash_password("pw"),
        role="OPERATOR", institution_ids=[str(b.id)],
    )
    reviewer = User(
        email="rev@aicte.gov", full_name="Reviewer", password_hash=hash_password("pw"),
        role="AICTE_REVIEWER", institution_ids=[],
    )
    owner_db.add_all([op_a, op_b, reviewer])
    owner_db.flush()

    # One student record per institution (encrypted + tokenised), created as owner.
    rec_a = _make_record(a.id, "Student Alpha", "100000000001")
    rec_b = _make_record(b.id, "Student Beta", "100000000002")
    owner_db.add_all([rec_a, rec_b])
    owner_db.commit()

    return {
        "a": a.id, "b": b.id,
        "op_a": op_a.id, "op_b": op_b.id, "reviewer": reviewer.id,
        "rec_a": rec_a.id, "rec_b": rec_b.id,
    }


def _make_record(institution_id: uuid.UUID, name: str, apaar: str):
    from backend.app.models.models import StudentRecord

    rid = uuid.uuid4()
    return StudentRecord(
        id=rid,
        institution_id=institution_id,
        name_enc=crypto.encrypt(name, aad=str(rid)),
        name_norm_key=crypto.keyed_blocking_key(name.lower()),
        apaar_enc=crypto.encrypt(apaar, aad=str(rid)),
        apaar_token=crypto.token(apaar),
        apaar_last4=crypto.last4(apaar),
        key_version=crypto.get_key_manager().active_version,
        verification_status="FORMAT_VALID",
    )
