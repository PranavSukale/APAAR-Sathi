from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..core import crypto
from ..core.audit import append_event
from ..models.models import RevealRequest, StudentRecord

# Purpose-bound, dual-approved, single-use, expiring reveal.
# Governance rules (never relaxed):
#  - purpose from a controlled list + free text
#  - a DIFFERENT supervisor approves (self-approval rejected)
#  - approval sets a short expiry
#  - consume decrypts ONCE, marks consumed, audits; expired/consumed reject

PURPOSES = {
    "DUPLICATE_CONFIRMATION",
    "CONCURRENT_ENROLMENT_REVIEW",
    "INTAKE_VERIFICATION",
    "EXTERNAL_VERIFICATION_PREP",
}
DEFAULT_EXPIRY_MINUTES = 15


class RevealError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def request_reveal(db: Session, *, requester_id: uuid.UUID, record_id: uuid.UUID,
                   case_id: uuid.UUID | None, purpose: str, purpose_detail: str) -> RevealRequest:
    if purpose not in PURPOSES:
        raise RevealError("INVALID_PURPOSE", f"purpose must be one of {sorted(PURPOSES)}")
    rr = RevealRequest(
        requester_id=requester_id, record_id=record_id, case_id=case_id,
        purpose=purpose, purpose_detail=purpose_detail, status="REQUESTED",
    )
    db.add(rr)
    db.flush()
    append_event(db, actor_id=requester_id, action="REVEAL_REQUEST",
                 entity_type="reveal_request", entity_id=str(rr.id),
                 after={"purpose": purpose, "record_id": str(record_id)})
    return rr


def approve_reveal(db: Session, *, reveal_id: uuid.UUID, approver_id: uuid.UUID,
                   approver_role: str, expiry_minutes: int = DEFAULT_EXPIRY_MINUTES) -> RevealRequest:
    rr = db.get(RevealRequest, reveal_id)
    if rr is None:
        raise RevealError("NOT_FOUND", "reveal request not found")
    if approver_role != "AICTE_SUPERVISOR":
        raise RevealError("FORBIDDEN", "only a supervisor may approve a reveal")
    if rr.requester_id == approver_id:
        raise RevealError("SELF_APPROVAL", "self-approval is rejected")
    if rr.status != "REQUESTED":
        raise RevealError("BAD_STATE", f"cannot approve a reveal in state {rr.status}")
    rr.status = "APPROVED"
    rr.approver_id = approver_id
    rr.approved_at = datetime.now(timezone.utc)
    rr.expires_at = rr.approved_at + timedelta(minutes=expiry_minutes)
    db.flush()
    append_event(db, actor_id=approver_id, action="REVEAL_APPROVE",
                 entity_type="reveal_request", entity_id=str(rr.id),
                 after={"expires_at": rr.expires_at.isoformat()})
    return rr


def consume_reveal(db: Session, *, reveal_id: uuid.UUID, actor_id: uuid.UUID) -> dict:
    rr = db.get(RevealRequest, reveal_id)
    if rr is None:
        raise RevealError("NOT_FOUND", "reveal request not found")
    if rr.status == "CONSUMED" or rr.consumed_at is not None:
        raise RevealError("ALREADY_CONSUMED", "reveal is single-use and already consumed")
    if rr.status != "APPROVED":
        raise RevealError("NOT_APPROVED", "reveal is not approved")
    now = datetime.now(timezone.utc)
    expires = rr.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is None or now > expires:
        rr.status = "EXPIRED"
        db.flush()
        raise RevealError("EXPIRED", "reveal window has expired")

    rec = db.get(StudentRecord, rr.record_id)
    if rec is None:
        raise RevealError("NOT_FOUND", "record not found")
    name = crypto.decrypt(rec.name_enc, aad=str(rec.id)) if rec.name_enc else None
    apaar = crypto.decrypt(rec.apaar_enc, aad=str(rec.id)) if rec.apaar_enc else None

    rr.status = "CONSUMED"
    rr.consumed_at = now
    db.flush()
    append_event(db, actor_id=actor_id, action="REVEAL_CONSUME",
                 entity_type="reveal_request", entity_id=str(rr.id),
                 reason=rr.purpose)
    return {"record_id": str(rec.id), "name": name, "apaar": apaar,
            "expires_at": expires.isoformat(), "single_use": True}
