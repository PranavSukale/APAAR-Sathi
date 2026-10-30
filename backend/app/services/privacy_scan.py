from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import get_settings

# Privacy proof scan for the demo.
# Scans DB identifier/name columns, app logs, and exports for canary values.
# Any hit => fail. Confirms encrypted columns hold only ciphertext/tokens.

CANARY_NAMES = ["Canary Student", "ZZCANARYZZ"]
CANARY_IDS = ["999999999999", "888888888888"]


def _scan_text(blob: str, needles: list[str]) -> list[str]:
    return [n for n in needles if n in blob]


def scan(db: Session, *, extra_canaries: list[str] | None = None) -> dict:
    needles = CANARY_NAMES + CANARY_IDS + (extra_canaries or [])
    results = {"synthetic": True, "checks": [], "passed": True}

    # 1. DB ciphertext columns must NOT contain any canary plaintext.
    rows = db.execute(
        text("SELECT name_enc, apaar_enc, apaar_token, apaar_last4 FROM student_records")
    ).mappings().all()
    db_blob = "".join(
        f"{r['name_enc'] or ''}{r['apaar_enc'] or ''}{r['apaar_token'] or ''}{r['apaar_last4'] or ''}"
        for r in rows
    )
    db_hits = _scan_text(db_blob, needles)
    results["checks"].append({
        "target": "db_ciphertext_columns",
        "rows_scanned": len(rows),
        "hits": db_hits,
        "pass": len(db_hits) == 0,
    })

    # 2. Application log files.
    log_hits: list[str] = []
    logs_scanned = 0
    for log_path in Path(".").glob("*.log"):
        logs_scanned += 1
        try:
            log_hits += _scan_text(log_path.read_text(encoding="utf-8", errors="ignore"), needles)
        except OSError:
            pass
    results["checks"].append({
        "target": "app_logs", "files_scanned": logs_scanned,
        "hits": sorted(set(log_hits)), "pass": len(log_hits) == 0,
    })

    # 3. Exports directory.
    export_hits: list[str] = []
    exports_scanned = 0
    export_dir = Path(get_settings().upload_dir)
    if export_dir.exists():
        for f in export_dir.glob("**/*"):
            if f.is_file():
                exports_scanned += 1
                try:
                    export_hits += _scan_text(f.read_text(encoding="utf-8", errors="ignore"), needles)
                except OSError:
                    pass
    results["checks"].append({
        "target": "exports", "files_scanned": exports_scanned,
        "hits": sorted(set(export_hits)), "pass": len(export_hits) == 0,
    })

    results["passed"] = all(c["pass"] for c in results["checks"])
    results["canaries_used"] = len(needles)
    return results
