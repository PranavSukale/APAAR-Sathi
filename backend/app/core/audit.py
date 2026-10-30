from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.models import AuditEvent

_ADVISORY_LOCK_KEY = 918273645  # arbitrary constant for audit chain ordering


def canonical_json(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)


def _compute_hash(prev_hash: str, event: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(event)).encode("utf-8")).hexdigest()


def append_event(
    session: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    institution_id: uuid.UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str = "",
    request_id: str = "",
) -> AuditEvent:
    """Append a hash-chained audit event. Serialised with a transaction advisory lock."""
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
    prev_hash = session.execute(
        text("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1")
    ).scalar()
    prev_hash = prev_hash or ""
    occurred_at = datetime.now(timezone.utc)
    event = {
        "actor": str(actor_id) if actor_id else None,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before": before or {},
        "after": after or {},
        "reason": reason,
        "request_id": request_id,
        "occurred_at": occurred_at.isoformat(),
    }
    h = _compute_hash(prev_hash, event)
    ev = AuditEvent(
        actor_id=actor_id,
        institution_id=institution_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before or {},
        after_json=after or {},
        reason=reason,
        request_id=request_id,
        occurred_at=occurred_at,
        prev_hash=prev_hash,
        hash=h,
    )
    session.add(ev)
    session.flush()
    return ev


def verify_chain(session: Session) -> dict[str, Any]:
    """Recompute the chain from genesis. Returns first mismatch or ok."""
    rows = session.execute(
        text(
            "SELECT seq, actor_id, action, entity_type, entity_id, before_json, after_json, "
            "reason, request_id, occurred_at, prev_hash, hash FROM audit_events ORDER BY seq ASC"
        )
    ).mappings().all()

    prev_hash = ""
    for r in rows:
        event = {
            "actor": str(r["actor_id"]) if r["actor_id"] else None,
            "action": r["action"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "before": r["before_json"] or {},
            "after": r["after_json"] or {},
            "reason": r["reason"],
            "request_id": r["request_id"],
            "occurred_at": r["occurred_at"].isoformat(),
        }
        expected = _compute_hash(prev_hash, event)
        if r["prev_hash"] != prev_hash or r["hash"] != expected:
            return {
                "valid": False,
                "first_mismatch_seq": r["seq"],
                "expected_hash": expected,
                "stored_hash": r["hash"],
            }
        prev_hash = r["hash"]
    return {"valid": True, "events": len(rows)}
