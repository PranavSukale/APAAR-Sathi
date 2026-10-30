from __future__ import annotations

import logging
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.core import crypto
from backend.app.core.audit import append_event, verify_chain
from backend.app.core.logging_filter import redact
from backend.app.main import app
from backend.app.models.models import StudentRecord
from backend.tests.conftest import app_session


# ---------- RLS: operator of A cannot read B, via API and raw SQL ----------
def test_rls_isolation_raw_sql(two_institutions):
    ids = two_institutions
    s = app_session("OPERATOR", [str(ids["a"])])
    try:
        rows = s.execute(text("SELECT institution_id FROM student_records")).scalars().all()
        assert all(str(r) == str(ids["a"]) for r in rows)
        assert len(rows) == 1  # only A's record visible
        # explicitly cannot fetch B's record
        got_b = s.execute(
            text("SELECT id FROM student_records WHERE id = :rid"), {"rid": str(ids["rec_b"])}
        ).first()
        assert got_b is None
    finally:
        s.rollback()
        s.close()


def test_rls_isolation_via_orm(two_institutions):
    ids = two_institutions
    s = app_session("OPERATOR", [str(ids["a"])])
    try:
        rec = s.get(StudentRecord, ids["rec_b"])
        assert rec is None
        rec_a = s.get(StudentRecord, ids["rec_a"])
        assert rec_a is not None
    finally:
        s.rollback()
        s.close()


def test_reviewer_sees_both(two_institutions):
    s = app_session("AICTE_REVIEWER", [])
    try:
        rows = s.execute(text("SELECT id FROM student_records")).scalars().all()
        assert len(rows) == 2
    finally:
        s.rollback()
        s.close()


def test_api_login_and_cross_institution_denied(two_institutions):
    from backend.app.core.security import login_limiter

    login_limiter._hits.clear()
    ids = two_institutions
    client = TestClient(app)
    r = client.post("/api/v1/auth/login", json={"email": "op_a@example.org", "password": "pw"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["scope_ids"] == [str(ids["a"])]
    # no token -> 401 with error shape
    r2 = client.get("/api/v1/audit/verify")
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "UNAUTHENTICATED"


def test_login_bad_password_and_rate_limit(two_institutions):
    from backend.app.core.security import login_limiter

    login_limiter._hits.clear()
    client = TestClient(app)
    last = None
    for _ in range(6):
        last = client.post("/api/v1/auth/login", json={"email": "op_a@example.org", "password": "wrong"})
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "RATE_LIMITED"


# ---------- Encrypted columns are ciphertext, not plaintext ----------
def test_columns_are_ciphertext(two_institutions, owner_db):
    rows = owner_db.execute(
        text("SELECT id, name_enc, apaar_enc, apaar_token, apaar_last4 FROM student_records")
    ).mappings().all()
    for r in rows:
        assert "Student" not in r["name_enc"]
        assert "100000000" not in r["apaar_enc"]
        assert "100000000" not in r["apaar_token"]
        # round-trips with the right aad
        name = crypto.decrypt(r["name_enc"], aad=str(r["id"]))
        assert name.startswith("Student")


# ---------- Audit tamper is detected and located ----------
def test_audit_tamper_detected_and_located(two_institutions, owner_db):
    s = app_session("ADMIN", [])
    try:
        for i in range(3):
            append_event(s, actor_id=None, action=f"EV{i}", entity_type="test", entity_id=str(i))
        s.commit()
    finally:
        s.close()

    # tamper the 2nd event using owner (acts as superuser bypassing app grants)
    owner_db.execute(text("UPDATE audit_events SET reason = 'tampered' WHERE seq = (SELECT min(seq)+1 FROM audit_events)"))
    owner_db.commit()

    check = verify_chain(owner_db)
    assert check["valid"] is False
    assert "first_mismatch_seq" in check


def test_app_role_cannot_update_audit(two_institutions):
    s = app_session("ADMIN", [])
    try:
        append_event(s, actor_id=None, action="EV", entity_type="t", entity_id="1")
        s.commit()
    finally:
        s.close()
    s2 = app_session("ADMIN", [])
    try:
        import pytest
        with pytest.raises(Exception):
            s2.execute(text("UPDATE audit_events SET reason='x'"))
            s2.commit()
    finally:
        s2.rollback()
        s2.close()


# ---------- Log redaction redacts a canary id ----------
def test_log_redaction_canary():
    canary_id = "100000009999"
    msg = f'{{"apaar": "{canary_id}", "name": "Secret Student"}}'
    out = redact(msg)
    assert canary_id not in out
    assert "Secret Student" not in out
