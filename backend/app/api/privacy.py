from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.deps import Principal, get_scoped_db, require_roles
from ..services import privacy_scan

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


@router.get("/proof")
def proof(principal: Principal = Depends(require_roles(
        "AICTE_REVIEWER", "AICTE_SUPERVISOR", "AUDITOR", "ADMIN")),
        db: Session = Depends(get_scoped_db)):
    return privacy_scan.scan(db)
