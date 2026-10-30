from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.deps import Principal, require_roles

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/seed-reset")
def seed_reset(principal: Principal = Depends(require_roles("ADMIN"))):
    from scripts.seed import seed

    info = seed()
    return {"status": "reseeded", "institutions": len(info["institutions"])}
