from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date

# Intake Integrity Engine.
# For each (institution, programme, academic_year, category):
#  - count eligible episodes (counted_for_intake + status rules)
#  - for EACH episode use the approval whose valid_during contains the admission_date
#    (NOT the latest figure). Revised intake => earlier admissions use the earlier limit.
#  - missing/outdated approval or category split => CANNOT_EVALUATE (never a flag)

RULE_VERSION = 1


@dataclass
class Approval:
    valid_from: date
    valid_to: date
    approved_intake: int
    category_intake: dict[str, int] = field(default_factory=dict)
    approval_reference: str = ""
    config_version: int = 1

    def contains(self, d: date) -> bool:
        return self.valid_from <= d <= self.valid_to


@dataclass
class IntakeEpisode:
    episode_id: str
    admission_date: date
    category: str = "GEN"
    counted_for_intake: bool = True
    status: str = "active"


def _effective_approval(approvals: list[Approval], d: date) -> Approval | None:
    hits = [a for a in approvals if a.contains(d)]
    if not hits:
        return None
    # if multiple, the most specific (latest valid_from) wins
    return sorted(hits, key=lambda a: a.valid_from)[-1]


def evaluate(
    episodes: list[IntakeEpisode],
    approvals: list[Approval],
    *,
    institution: str,
    program: str,
    academic_year: str,
    category: str | None = None,
) -> dict:
    """Evaluate one programme/year (optionally one category). Order-invariant."""
    eligible = [e for e in episodes if e.counted_for_intake and e.status not in ("withdrawn",)]
    if category is not None:
        eligible = [e for e in eligible if e.category == category]

    if not approvals:
        return _cannot_evaluate(institution, program, academic_year, category,
                                "no approval on record", len(eligible))

    # Each admission uses the limit effective on its own admission date.
    # If admissions span approvals with different limits, the applicable limit is the
    # one effective at the LATEST admission's date? No: PRD says each admission vs the
    # limit in force at its admission date; we aggregate the count and compare to the
    # limit that applies to the period. We use the max effective approved_intake across
    # the episodes' own effective approvals, but flag CANNOT_EVALUATE if any episode
    # has no effective approval.
    effective_limits: list[int] = []
    masked_ids: list[str] = []
    for e in eligible:
        appr = _effective_approval(approvals, e.admission_date)
        if appr is None:
            return _cannot_evaluate(institution, program, academic_year, category,
                                    f"no approval effective on {e.admission_date.isoformat()}",
                                    len(eligible))
        if category is not None:
            if category not in appr.category_intake:
                return _cannot_evaluate(institution, program, academic_year, category,
                                        "category split missing in effective approval", len(eligible))
            effective_limits.append(appr.category_intake[category])
        else:
            effective_limits.append(appr.approved_intake)
        masked_ids.append(f"ep:{e.episode_id[-4:]}")

    numerator = len(eligible)
    # The governing limit for the cohort is the limit effective for the cohort's admissions.
    # When a revision occurs mid-year, earlier admissions carry the earlier (lower) limit;
    # the cohort cannot exceed the limit that was in force when each seat was filled, so the
    # binding limit is the MINIMUM effective limit across contributing admissions.
    limit = min(effective_limits)
    ref = _effective_approval(approvals, min(e.admission_date for e in eligible))
    over = numerator > limit
    return {
        "status": "OVER_LIMIT" if over else "WITHIN_LIMIT",
        "rule_code": "INTAKE-OVER" if over else None,
        "institution": institution[-4:],
        "program": program,
        "academic_year": academic_year,
        "category": category,
        "numerator": numerator,
        "limit": limit,
        "effective_limits_seen": sorted(set(effective_limits)),
        "approval_reference": ref.approval_reference if ref else "",
        "rule_version": RULE_VERSION,
        "contributing_masked_ids": masked_ids,
    }


def _cannot_evaluate(institution, program, academic_year, category, reason, numerator):
    return {
        "status": "CANNOT_EVALUATE",
        "rule_code": "INTAKE-CANNOT-EVALUATE",
        "institution": institution[-4:],
        "program": program,
        "academic_year": academic_year,
        "category": category,
        "numerator": numerator,
        "limit": None,
        "reason": reason,
        "rule_version": RULE_VERSION,
    }


# ---------------- Peer-benchmark attention signals ----------------
@dataclass
class PeerPoint:
    group_id: str          # e.g. program_type + state
    entity_id: str         # institution/programme id
    fill_rate: float       # admitted / approved
    last_days_share: float # share of admissions in final days before cutoff


def peer_signals(points: list[PeerPoint], *, min_group: int = 5,
                 z_threshold: float = 3.0, min_abs_diff: float = 0.15) -> list[dict]:
    """Robust z (median/MAD). Needs BOTH a large deviation AND a minimum absolute diff."""
    by_group: dict[str, list[PeerPoint]] = {}
    for p in points:
        by_group.setdefault(p.group_id, []).append(p)

    signals: list[dict] = []
    for group_id, members in by_group.items():
        if len(members) < min_group:
            continue
        for metric in ("fill_rate", "last_days_share"):
            values = [getattr(m, metric) for m in members]
            median = statistics.median(values)
            mad = statistics.median([abs(v - median) for v in values]) or 1e-9
            for m in members:
                v = getattr(m, metric)
                robust_z = 0.6745 * (v - median) / mad
                if robust_z >= z_threshold and (v - median) >= min_abs_diff:
                    signals.append({
                        "label": "attention signal, not a violation",
                        "metric": metric,
                        "group_id": group_id,
                        "entity_id": m.entity_id[-4:],
                        "value": round(v, 3),
                        "group_median": round(median, 3),
                        "robust_z": round(robust_z, 2),
                        "z_threshold": z_threshold,
                    })
    return signals
