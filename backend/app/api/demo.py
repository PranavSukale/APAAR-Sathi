from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.deps import Principal, get_scoped_db, require_roles
from ..services import demo_queries

router = APIRouter(prefix="/api/v1", tags=["demo"])

AICTE = ("AICTE_REVIEWER", "AICTE_SUPERVISOR", "AUDITOR", "ADMIN")


@router.get("/linkage/pairs")
def linkage_pairs(principal: Principal = Depends(require_roles(*AICTE)),
                  db: Session = Depends(get_scoped_db)):
    return demo_queries.linkage_pairs(db)


@router.get("/linkage/pairs/evidence")
def pair_evidence(record_a: str, record_b: str,
                  principal: Principal = Depends(require_roles(*AICTE)),
                  db: Session = Depends(get_scoped_db)):
    return demo_queries.pair_evidence(db, record_a, record_b)


@router.get("/identity-clusters/timeline")
def timeline(record_a: str, record_b: str,
             principal: Principal = Depends(require_roles(*AICTE)),
             db: Session = Depends(get_scoped_db)):
    return demo_queries.timeline_for_pair(db, record_a, record_b)


@router.get("/intake/results")
def intake_results(principal: Principal = Depends(require_roles(*AICTE)),
                   db: Session = Depends(get_scoped_db)):
    return demo_queries.intake_results(db)


@router.get("/analytics/benchmark")
def benchmark(principal: Principal = Depends(require_roles(*AICTE))):
    return demo_queries.benchmark_data()
