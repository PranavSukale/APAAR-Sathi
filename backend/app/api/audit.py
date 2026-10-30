from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.audit import verify_chain
from ..core.deps import Principal, get_scoped_db, require_roles

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/verify")
def verify(
    principal: Principal = Depends(require_roles("AUDITOR", "ADMIN", "AICTE_SUPERVISOR")),
    db: Session = Depends(get_scoped_db),
):
    return verify_chain(db)
