from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from backend.app.core import crypto
from backend.app.models.models import RevealRequest, User
from backend.app.services import privacy_scan, reveal as reveal_svc
from backend.app.services.reveal import RevealError
from backend.tests.conftest import _make_record, app_session


@pytest.fixture
def reveal_setup(owner_db):
    for tbl in ["audit_events", "reveal_requests", "student_records", "users", "institutions"]:
        owner_db.execute(text(f"DELETE FROM {tbl}"))
    owner_db.commit()
    from backend.app.models.models import Institution

    inst = Institution(official_institution_code="INST-R", name="R", normalized_name="r")
    owner_db.add(inst)
    owner_db.flush()
    reviewer = User(email="r1@aicte.gov", full_name="Rev", password_hash="x",
                    role="AICTE_REVIEWER", institution_ids=[])
    sup1 = User(email="s1@aicte.gov", full_name="Sup1", password_hash="x",
                role="AICTE_SUPERVISOR", institution_ids=[])
    sup2 = User(email="s2@aicte.gov", full_name="Sup2", password_hash="x",
                role="AICTE_SUPERVISOR", institution_ids=[])
    owner_db.add_all([reviewer, sup1, sup2])
    owner_db.flush()
    rec = _make_record(inst.id, "Reveal Target", "123412341234")
    owner_db.add(rec)
    owner_db.commit()
    return {"reviewer": reviewer.id, "sup1": sup1.id, "sup2": sup2.id, "record": rec.id}


def test_reveal_requires_valid_purpose(reveal_setup):
    s = app_session("AICTE_REVIEWER", [])
    try:
        with pytest.raises(RevealError) as e:
            reveal_svc.request_reveal(s, requester_id=reveal_setup["reviewer"],
                                      record_id=reveal_setup["record"], case_id=None,
                                      purpose="NONSENSE", purpose_detail="")
        assert e.value.code == "INVALID_PURPOSE"
    finally:
        s.rollback(); s.close()


def test_reveal_self_approval_rejected(reveal_setup):
    s = app_session("AICTE_SUPERVISOR", [])
    try:
        rr = reveal_svc.request_reveal(s, requester_id=reveal_setup["sup1"],
                                       record_id=reveal_setup["record"], case_id=None,
                                       purpose="DUPLICATE_CONFIRMATION", purpose_detail="x")
        s.flush()
        with pytest.raises(RevealError) as e:
            reveal_svc.approve_reveal(s, reveal_id=rr.id, approver_id=reveal_setup["sup1"],
                                      approver_role="AICTE_SUPERVISOR")
        assert e.value.code == "SELF_APPROVAL"
    finally:
        s.rollback(); s.close()


def test_reveal_happy_path_single_use(reveal_setup):
    s = app_session("AICTE_REVIEWER", [])
    try:
        rr = reveal_svc.request_reveal(s, requester_id=reveal_setup["reviewer"],
                                       record_id=reveal_setup["record"], case_id=None,
                                       purpose="DUPLICATE_CONFIRMATION", purpose_detail="x")
        reveal_svc.approve_reveal(s, reveal_id=rr.id, approver_id=reveal_setup["sup2"],
                                  approver_role="AICTE_SUPERVISOR")
        out = reveal_svc.consume_reveal(s, reveal_id=rr.id, actor_id=reveal_setup["reviewer"])
        assert out["name"] == "Reveal Target"
        assert out["apaar"] == "123412341234"
        # second consume fails
        with pytest.raises(RevealError) as e:
            reveal_svc.consume_reveal(s, reveal_id=rr.id, actor_id=reveal_setup["reviewer"])
        assert e.value.code == "ALREADY_CONSUMED"
        s.commit()
    except Exception:
        s.rollback(); raise
    finally:
        s.close()


def test_reveal_expired_rejected(reveal_setup):
    s = app_session("AICTE_REVIEWER", [])
    try:
        rr = reveal_svc.request_reveal(s, requester_id=reveal_setup["reviewer"],
                                       record_id=reveal_setup["record"], case_id=None,
                                       purpose="INTAKE_VERIFICATION", purpose_detail="x")
        reveal_svc.approve_reveal(s, reveal_id=rr.id, approver_id=reveal_setup["sup2"],
                                  approver_role="AICTE_SUPERVISOR")
        # force expiry into the past
        rr.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        s.flush()
        with pytest.raises(RevealError) as e:
            reveal_svc.consume_reveal(s, reveal_id=rr.id, actor_id=reveal_setup["reviewer"])
        assert e.value.code == "EXPIRED"
    finally:
        s.rollback(); s.close()


def test_privacy_proof_passes_with_canary(reveal_setup, owner_db):
    # add a canary record whose plaintext must never appear in ciphertext columns
    from backend.app.models.models import Institution, StudentRecord

    inst_id = owner_db.execute(text("SELECT id FROM institutions LIMIT 1")).scalar()
    rec = _make_record(inst_id, "Canary Student", "999999999999")
    owner_db.add(rec)
    owner_db.commit()

    s = app_session("AUDITOR", [])
    try:
        result = privacy_scan.scan(s)
        assert result["passed"] is True
        db_check = next(c for c in result["checks"] if c["target"] == "db_ciphertext_columns")
        assert db_check["hits"] == []
        assert db_check["rows_scanned"] >= 1
    finally:
        s.rollback(); s.close()


def test_privacy_proof_detects_leak_in_log(reveal_setup, tmp_path, monkeypatch):
    # Write a log file containing a canary; scan must catch it.
    import os
    leak = tmp_path / "leak.log"
    leak.write_text("ERROR processed apaar 999999999999 for Canary Student")
    monkeypatch.chdir(tmp_path)
    s = app_session("AUDITOR", [])
    try:
        result = privacy_scan.scan(s)
        log_check = next(c for c in result["checks"] if c["target"] == "app_logs")
        assert log_check["pass"] is False
        assert "999999999999" in log_check["hits"]
        assert result["passed"] is False
    finally:
        s.rollback(); s.close()
