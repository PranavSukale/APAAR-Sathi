from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core import crypto
from ..engines import intake as intake_engine
from ..engines import timeline as timeline_engine
from ..engines.linkage import baselines, blocking
from ..engines.linkage.model import RecordView, score_pair

# Read-side helpers that power the demo screens. Runs the real engines on seeded data.
# All identifiers returned masked; decryption only happens inside the worker here (trusted).


def _load_views(db: Session) -> list[RecordView]:
    rows = db.execute(text(
        "SELECT sr.id, sr.name_enc, sr.apaar_token, sr.academic_year, sr.dob_year, "
        "sr.institution_id, i.state, "
        "(SELECT program_id FROM enrolment_episodes e WHERE e.student_record_id = sr.id LIMIT 1) AS program_id, "
        "(SELECT admission_date FROM enrolment_episodes e WHERE e.student_record_id = sr.id LIMIT 1) AS admission_date, "
        "(SELECT p.program_code FROM enrolment_episodes e JOIN programs p ON p.id = e.program_id "
        " WHERE e.student_record_id = sr.id LIMIT 1) AS program_code "
        "FROM student_records sr JOIN institutions i ON i.id = sr.institution_id "
        "WHERE sr.archived_at IS NULL"
    )).mappings().all()
    views = []
    for r in rows:
        name = crypto.decrypt(r["name_enc"], aad=str(r["id"])) if r["name_enc"] else ""
        views.append(RecordView(
            record_id=str(r["id"]),
            name=name,
            apaar_token=r["apaar_token"],
            program_code=r["program_code"] or "",
            academic_year=r["academic_year"] or "",
            admission_date=r["admission_date"],
            dob_year=r["dob_year"],
            state=r["state"] or "",
        ))
    return views


def linkage_pairs(db: Session, *, top: int = 25) -> dict:
    views = _load_views(db)
    pairs, warnings = blocking.candidate_views(views)
    scored = []
    for a, b in pairs:
        s = score_pair(a, b)
        s["baseline1_match"] = baselines.baseline1_match(a, b)
        s["baseline2_match"] = baselines.baseline2_match(a, b)
        # the "wow": baseline2 flags, model keeps it Low (common-name trap)
        s["baseline_false_positive"] = s["baseline2_match"] and s["band"] == "Low"
        scored.append(s)
    scored.sort(key=lambda x: x["probability"], reverse=True)
    # Curated lists for the demo contrast:
    #  - true_duplicates: High band exact-token repeats (model + rule agree)
    #  - baseline_false_positives: baseline2 flags them, model keeps them Low (common-name trap)
    true_duplicates = [p for p in scored if p["exact_token_repeat"] and p["band"] == "High"]
    baseline_false_positives = [p for p in scored if p["baseline_false_positive"]]
    return {
        "pairs": scored[:top],
        "true_duplicates": true_duplicates[:top],
        "baseline_false_positives": baseline_false_positives[:top],
        "candidate_count": len(pairs),
        "block_warnings": warnings,
    }


def pair_evidence(db: Session, record_a: str, record_b: str) -> dict:
    views = {v.record_id: v for v in _load_views(db)}
    a, b = views.get(record_a), views.get(record_b)
    if not a or not b:
        return {"error": "record not found"}
    s = score_pair(a, b)
    s["baseline1_match"] = baselines.baseline1_match(a, b)
    s["baseline2_match"] = baselines.baseline2_match(a, b)
    return s


def _episodes_for_records(db: Session, record_ids: list[str]) -> list[timeline_engine.Episode]:
    rows = db.execute(text(
        "SELECT e.id, e.student_record_id, e.institution_id, e.program_id, e.admission_date, "
        "lower(e.valid_period) AS start, upper(e.valid_period) AS fin, e.status, e.end_reason, "
        "e.transfer_from_episode_id "
        "FROM enrolment_episodes e WHERE e.student_record_id = ANY(:ids)"
    ), {"ids": record_ids}).mappings().all()
    eps = []
    for r in rows:
        eps.append(timeline_engine.Episode(
            episode_id=str(r["id"]),
            student_record_id=str(r["student_record_id"]),
            institution_id=str(r["institution_id"]),
            program_id=str(r["program_id"]),
            admission_date=r["admission_date"],
            start=r["start"],
            end=r["fin"],
            status=r["status"],
            end_reason=r["end_reason"],
            transfer_from_episode_id=str(r["transfer_from_episode_id"]) if r["transfer_from_episode_id"] else None,
        ))
    return eps


def timeline_for_pair(db: Session, record_a: str, record_b: str) -> dict:
    eps = _episodes_for_records(db, [record_a, record_b])
    findings = timeline_engine.evaluate_group(eps)
    bars = [{
        "episode_id": e.episode_id[-4:],
        "institution": e.institution_id[-4:],
        "start": e.start.isoformat(),
        "end": e.end.isoformat() if e.end else None,
        "status": e.status,
        "transfer_from": e.transfer_from_episode_id[-4:] if e.transfer_from_episode_id else None,
    } for e in eps]
    return {"bars": bars, "findings": findings}


def intake_results(db: Session) -> dict:
    # For each programme/year, pull episodes + the effective approvals and evaluate.
    progs = db.execute(text(
        "SELECT p.id AS program_id, p.program_code, p.institution_id, i.name AS inst_name "
        "FROM programs p JOIN institutions i ON i.id = p.institution_id"
    )).mappings().all()
    results = []
    for p in progs:
        eps_rows = db.execute(text(
            "SELECT id, admission_date, seat_category_id, counted_for_intake, status "
            "FROM enrolment_episodes WHERE program_id = :pid "
            "AND admission_date BETWEEN '2023-01-01' AND '2023-12-31'"
        ), {"pid": p["program_id"]}).mappings().all()
        if not eps_rows:
            continue
        episodes = [intake_engine.IntakeEpisode(
            episode_id=str(e["id"]), admission_date=e["admission_date"],
            counted_for_intake=e["counted_for_intake"], status=e["status"] or "active")
            for e in eps_rows]
        appr_rows = db.execute(text(
            "SELECT approved_intake, category_intake_json, lower(valid_during) AS vf, "
            "upper(valid_during) AS vt, approval_reference "
            "FROM program_approvals WHERE program_id = :pid"
        ), {"pid": p["program_id"]}).mappings().all()
        approvals = [intake_engine.Approval(
            valid_from=a["vf"], valid_to=a["vt"], approved_intake=a["approved_intake"],
            category_intake=a["category_intake_json"] or {}, approval_reference=a["approval_reference"])
            for a in appr_rows]
        res = intake_engine.evaluate(
            episodes, approvals, institution=str(p["institution_id"]),
            program=p["program_code"], academic_year="2023")
        res["institution_name"] = p["inst_name"]
        results.append(res)
    return {"results": results}


def benchmark_data() -> dict:
    path = Path("benchmark.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"error": "run scripts.benchmark to generate benchmark.json"}
