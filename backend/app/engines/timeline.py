from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Enrolment Timeline Integrity engine.
# Operates on episodes grouped by identity (cluster or shared identifier token).
# Rules are versioned config; evidence holds dates + approval refs (masked identifiers).

RULE_VERSION = 1


@dataclass
class TimelineConfig:
    tolerance_days: int = 30            # transfer gap tolerance / overlap tolerance
    rule_version: int = RULE_VERSION


@dataclass
class Episode:
    episode_id: str
    student_record_id: str
    institution_id: str
    program_id: str
    admission_date: date
    start: date
    end: date | None                      # None = open-ended
    status: str = "active"                # active/transferred_out/withdrawn/graduated
    end_reason: str | None = None
    transfer_from_episode_id: str | None = None
    approval_valid_from: date | None = None
    approval_valid_to: date | None = None
    approval_reference: str = ""
    admission_window_start: date | None = None
    admission_window_end: date | None = None
    created_at: date | None = None        # when the record was created (for late-change)
    cycle_locked_at: date | None = None


def _mask(ep: Episode) -> str:
    return f"ep:{ep.episode_id[-4:]}"


def _overlap_days(a: Episode, b: Episode) -> int:
    a_end = a.end or date.max
    b_end = b.end or date.max
    lo = max(a.start, b.start)
    hi = min(a_end, b_end)
    return (hi - lo).days if hi > lo else 0


def _valid_transfer(a: Episode, b: Episode, cfg: TimelineConfig) -> bool:
    """B is a recorded transfer from A, and A ends within tolerance of B starting."""
    for first, second in ((a, b), (b, a)):
        if second.transfer_from_episode_id == first.episode_id and first.end is not None:
            gap = abs((second.start - first.end).days)
            if gap <= cfg.tolerance_days:
                return True
    return False


def evaluate_group(episodes: list[Episode], cfg: TimelineConfig | None = None) -> list[dict]:
    """Return a list of findings (exceptions/info) for one identity group."""
    cfg = cfg or TimelineConfig()
    findings: list[dict] = []

    # Pairwise overlap / transfer / readmit across institutions or programmes.
    for i in range(len(episodes)):
        for j in range(i + 1, len(episodes)):
            a, b = episodes[i], episodes[j]
            different_context = (a.institution_id != b.institution_id) or (a.program_id != b.program_id)
            if not different_context:
                continue
            overlap = _overlap_days(a, b)
            if _valid_transfer(a, b, cfg):
                findings.append({
                    "rule_code": "TL-TRANSFER-OK",
                    "severity": "info",
                    "rule_version": cfg.rule_version,
                    "evidence": {
                        "episodes": [_mask(a), _mask(b)],
                        "note": "recorded transfer within tolerance; cleared",
                        "tolerance_days": cfg.tolerance_days,
                    },
                })
            elif overlap > cfg.tolerance_days:
                findings.append({
                    "rule_code": "TL-OVERLAP",
                    "severity": "high",
                    "rule_version": cfg.rule_version,
                    "evidence": {
                        "episodes": [_mask(a), _mask(b)],
                        "overlap_days": overlap,
                        "a_period": [a.start.isoformat(), a.end.isoformat() if a.end else None],
                        "b_period": [b.start.isoformat(), b.end.isoformat() if b.end else None],
                        "institutions": [a.institution_id[-4:], b.institution_id[-4:]],
                    },
                })

    # Re-admission: a new episode after graduation/withdrawal for the same identity (informational).
    ended = [e for e in episodes if e.status in ("graduated", "withdrawn") and e.end]
    for prior in ended:
        for later in episodes:
            if later is prior:
                continue
            if later.start > (prior.end or date.min):
                findings.append({
                    "rule_code": "TL-READMIT",
                    "severity": "info",
                    "rule_version": cfg.rule_version,
                    "evidence": {
                        "prior": _mask(prior),
                        "later": _mask(later),
                        "prior_end": prior.end.isoformat() if prior.end else None,
                        "later_start": later.start.isoformat(),
                        "prior_status": prior.status,
                    },
                })
                break

    # Per-episode window checks.
    for e in episodes:
        if e.approval_valid_from and e.approval_valid_to:
            if not (e.approval_valid_from <= e.admission_date <= e.approval_valid_to):
                findings.append({
                    "rule_code": "TL-APPROVAL-WINDOW",
                    "severity": "high",
                    "rule_version": cfg.rule_version,
                    "evidence": {
                        "episode": _mask(e),
                        "admission_date": e.admission_date.isoformat(),
                        "approval_window": [e.approval_valid_from.isoformat(), e.approval_valid_to.isoformat()],
                        "approval_reference": e.approval_reference,
                    },
                })
        if e.admission_window_start and e.admission_window_end:
            if not (e.admission_window_start <= e.admission_date <= e.admission_window_end):
                findings.append({
                    "rule_code": "TL-ADMISSION-WINDOW",
                    "severity": "medium",
                    "rule_version": cfg.rule_version,
                    "evidence": {
                        "episode": _mask(e),
                        "admission_date": e.admission_date.isoformat(),
                        "admission_window": [e.admission_window_start.isoformat(), e.admission_window_end.isoformat()],
                    },
                })
        if e.created_at and e.cycle_locked_at and e.created_at > e.cycle_locked_at:
            findings.append({
                "rule_code": "TL-LATE-CHANGE",
                "severity": "warning",
                "rule_version": cfg.rule_version,
                "evidence": {
                    "episode": _mask(e),
                    "created_at": e.created_at.isoformat(),
                    "cycle_locked_at": e.cycle_locked_at.isoformat(),
                    "note": "record created/edited after cycle lock; requires reason",
                },
            })

    return findings
