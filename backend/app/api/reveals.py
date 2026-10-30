from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.deps import Principal, _error, current_principal, get_scoped_db, require_roles
from ..models.models import RevealRequest
from ..services import reveal as reveal_svc

router = APIRouter(prefix="/api/v1/reveals", tags=["reveals"])


class RevealIn(BaseModel):
    record_id: str
    case_id: str | None = None
    purpose: str
    purpose_detail: str = ""


def _handle(fn):
    try:
        return fn()
    except reveal_svc.RevealError as e:
        status = {"NOT_FOUND": 404, "SELF_APPROVAL": 403, "FORBIDDEN": 403}.get(e.code, 400)
        raise _error(e.code, e.message, status)


@router.get("")
def list_reveals(principal: Principal = Depends(require_roles(
        "AICTE_REVIEWER", "AICTE_SUPERVISOR", "AUDITOR", "ADMIN")),
        db: Session = Depends(get_scoped_db)):
    rows = db.execute(select(RevealRequest).order_by(RevealRequest.created_at.desc())).scalars().all()
    return [{
        "id": str(r.id), "record_id": str(r.record_id), "purpose": r.purpose,
        "status": r.status, "requester_id": str(r.requester_id),
        "approver_id": str(r.approver_id) if r.approver_id else None,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "consumed_at": r.consumed_at.isoformat() if r.consumed_at else None,
    } for r in rows]


@router.post("")
def create_reveal(body: RevealIn,
                  principal: Principal = Depends(require_roles("AICTE_REVIEWER", "AICTE_SUPERVISOR")),
                  db: Session = Depends(get_scoped_db)):
    rr = _handle(lambda: reveal_svc.request_reveal(
        db, requester_id=principal.id, record_id=uuid.UUID(body.record_id),
        case_id=uuid.UUID(body.case_id) if body.case_id else None,
        purpose=body.purpose, purpose_detail=body.purpose_detail))
    return {"id": str(rr.id), "status": rr.status, "purpose": rr.purpose}


@router.post("/{reveal_id}/approve")
def approve(reveal_id: str,
            principal: Principal = Depends(require_roles("AICTE_SUPERVISOR")),
            db: Session = Depends(get_scoped_db)):
    rr = _handle(lambda: reveal_svc.approve_reveal(
        db, reveal_id=uuid.UUID(reveal_id), approver_id=principal.id, approver_role=principal.role))
    return {"id": str(rr.id), "status": rr.status, "expires_at": rr.expires_at.isoformat()}


@router.post("/{reveal_id}/consume")
def consume(reveal_id: str,
            principal: Principal = Depends(require_roles("AICTE_REVIEWER", "AICTE_SUPERVISOR")),
            db: Session = Depends(get_scoped_db)):
    return _handle(lambda: reveal_svc.consume_reveal(
        db, reveal_id=uuid.UUID(reveal_id), actor_id=principal.id))
