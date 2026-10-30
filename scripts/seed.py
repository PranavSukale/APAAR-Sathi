from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text

from backend.app.core import crypto
from backend.app.core.dbinit import reset_db
from backend.app.core.security import hash_password
from backend.app.models.models import (
    EnrolmentEpisode,
    Institution,
    Program,
    ProgramApproval,
    SeatCategory,
    StudentRecord,
    User,
)
from backend.app.core.db import owner_session

# Seed synthetic demo data that triggers all 6 demo beats. SYNTHETIC DATA ONLY.
# 6 institutions (labelled SYNTHETIC), programmes, approvals incl. one REVISED and one MISSING,
# 7 demo users (one per role, 2 operators in different institutions), and the records/episodes
# that produce: common-name false positive (baseline) vs model-correct, a legit transfer,
# a true concurrent enrolment, an over-limit programme, a revised-intake case, an out-of-window.

DEMO_PASSWORD = "demo1234"


def _rec(session, institution_id, name, apaar, dob_year, academic_year="2023"):
    rid = uuid.uuid4()
    from backend.app.engines.linkage import normalise

    f = normalise.feature_bundle(name)
    rec = StudentRecord(
        id=rid,
        institution_id=institution_id,
        academic_year=academic_year,
        name_enc=crypto.encrypt(name, aad=str(rid)),
        name_norm_key=crypto.keyed_blocking_key(f["sorted_token_key"]),
        apaar_enc=crypto.encrypt(apaar, aad=str(rid)) if apaar else None,
        apaar_token=crypto.token(apaar) if apaar else None,
        apaar_last4=crypto.last4(apaar) if apaar else "",
        key_version=crypto.get_key_manager().active_version,
        dob_year=dob_year,
        verification_status="FORMAT_VALID" if apaar else "UNVERIFIED",
        phonetic_key=f["phonetic_key"][:32],
        sorted_token_key=f["sorted_token_key"][:64],
        first_token_key=f["first_token"][:32],
    )
    session.add(rec)
    return rec


def seed() -> dict:
    reset_db()
    s = owner_session()
    try:
        # Institutions (clearly labelled SYNTHETIC).
        insts = []
        meta = [
            ("SYN-INST-01", "SYNTHETIC Institute of Technology, Pune", "MH"),
            ("SYN-INST-02", "SYNTHETIC College of Engineering, Mumbai", "MH"),
            ("SYN-INST-03", "SYNTHETIC Institute of Science, Bengaluru", "KA"),
            ("SYN-INST-04", "SYNTHETIC Technical University, Chennai", "TN"),
            ("SYN-INST-05", "SYNTHETIC Polytechnic, Delhi", "DL"),
            ("SYN-INST-06", "SYNTHETIC Engineering College, Ahmedabad", "GJ"),
        ]
        for code, name, state in meta:
            inst = Institution(official_institution_code=code, name=name,
                               normalized_name=name.lower(), state=state, status="ACTIVE")
            s.add(inst)
            insts.append(inst)
        s.flush()

        # Programmes (CSE per institution for simplicity).
        progs = []
        for inst in insts:
            p = Program(institution_id=inst.id, program_code="CSE",
                        program_name="Computer Science & Engineering", program_type="BE")
            s.add(p)
            progs.append(p)
        s.flush()

        # Seat categories.
        for code, name, counts in [("GEN", "General", True), ("LE", "Lateral Entry", True),
                                   ("SUP", "Supernumerary", False)]:
            s.add(SeatCategory(code=code, name=name, counts_toward_intake=counts))

        # Approvals:
        #  inst1 CSE 2023: over-limit (intake 60)
        #  inst2 CSE 2023: REVISED mid-year (Jan-Jun 60, Jul-Dec 120)
        #  inst3 CSE 2023: MISSING approval -> CANNOT_EVALUATE
        #  others: clean
        s.add(ProgramApproval(program_id=progs[0].id, academic_year="2023", approved_intake=60,
                              category_intake_json={"GEN": 50, "LE": 10},
                              valid_during="[2023-01-01,2023-12-31]", approval_reference="SYN-APP-01"))
        s.add(ProgramApproval(program_id=progs[1].id, academic_year="2023", approved_intake=60,
                              category_intake_json={"GEN": 50, "LE": 10},
                              valid_during="[2023-01-01,2023-06-30]", approval_reference="SYN-APP-02A"))
        s.add(ProgramApproval(program_id=progs[1].id, academic_year="2023", approved_intake=120,
                              category_intake_json={"GEN": 100, "LE": 20},
                              valid_during="[2023-07-01,2023-12-31]", approval_reference="SYN-APP-02B"))
        # inst3: intentionally no approval row (MISSING)
        for p in progs[3:]:
            s.add(ProgramApproval(program_id=p.id, academic_year="2023", approved_intake=120,
                                  category_intake_json={"GEN": 100, "LE": 20},
                                  valid_during="[2023-01-01,2023-12-31]", approval_reference="SYN-APP-CLEAN"))
        s.flush()

        # Users: one per role + a second operator.
        roles = [
            ("operator1@syn.edu", "Operator One", "OPERATOR", [str(insts[0].id)]),
            ("operator2@syn.edu", "Operator Two", "OPERATOR", [str(insts[1].id)]),
            ("approver@syn.edu", "Approver", "APPROVER", [str(insts[0].id)]),
            ("reviewer@aicte.syn", "AICTE Reviewer", "AICTE_REVIEWER", []),
            ("supervisor@aicte.syn", "AICTE Supervisor", "AICTE_SUPERVISOR", []),
            ("admin@aicte.syn", "Administrator", "ADMIN", []),
            ("auditor@aicte.syn", "Auditor", "AUDITOR", []),
        ]
        for email, name, role, scope in roles:
            s.add(User(email=email, full_name=name, password_hash=hash_password(DEMO_PASSWORD),
                       role=role, institution_ids=scope))

        # --- Records & episodes for the demo beats ---
        # Beat: common-name FALSE POSITIVE (baseline) vs model correct.
        # Two DIFFERENT "Amit Kumar" that a naive matcher wrongly links: same name, and we
        # put them in same-state institutions so they share a blocking key (baseline2 flags
        # them on name similarity), but DIFFERENT apaar + different dob => model keeps them Low.
        amit_a = _rec(s, insts[0].id, "Amit Kumar", "111122223333", 2003)   # MH
        amit_b = _rec(s, insts[1].id, "Amit Kumar", "444455556666", 2005)   # MH (same state)

        # Beat: TRUE DUPLICATE the model should catch (same apaar, spelling variant, order swap).
        dup_a = _rec(s, insts[0].id, "Mohammed Khan", "777788889999", 2004)
        dup_b = _rec(s, insts[1].id, "Khan Mohammad", "777788889999", 2004)

        # Beat: legit TRANSFER (same person, A ends, B begins within tolerance).
        tr_a = _rec(s, insts[0].id, "Priya Sharma", "121212121212", 2004)
        tr_b = _rec(s, insts[1].id, "Priya Sharma", "121212121212", 2004)

        # Beat: TRUE CONCURRENT ENROLMENT (overlapping episodes, no transfer).
        cc_a = _rec(s, insts[0].id, "Rahul Verma", "343434343434", 2004)
        cc_b = _rec(s, insts[1].id, "Rahul Verma", "343434343434", 2004)
        s.flush()

        # Episodes.
        def ep(rec, inst, prog, admission, start, end=None, status="active", reason=None,
               transfer_from=None, approval_from=None, approval_to=None, approval_ref=""):
            e = EnrolmentEpisode(
                student_record_id=rec.id, institution_id=inst.id, program_id=prog.id,
                admission_date=admission,
                valid_period=f"[{start.isoformat()},{end.isoformat()}]" if end else f"[{start.isoformat()},)",
                status=status, end_reason=reason, transfer_from_episode_id=transfer_from,
                counted_for_intake=True)
            s.add(e)
            s.flush()
            return e

        # Amit pair: episodes in the same admission year + same state so they share a blocking
        # key and baseline2 compares them (and wrongly matches on the common name).
        ep(amit_a, insts[0], progs[0], date(2023, 7, 15), date(2023, 7, 15), None)
        ep(amit_b, insts[1], progs[1], date(2023, 7, 20), date(2023, 7, 20), None)
        # True duplicate (Mohammed/Khan) episodes (they already block on shared apaar_token).
        ep(dup_a, insts[0], progs[0], date(2023, 7, 1), date(2023, 7, 1), None)
        ep(dup_b, insts[1], progs[1], date(2023, 7, 5), date(2023, 7, 5), None)

        # Transfer: A (inst0) ends 2023-12-20 transferred_out; B (inst1) starts 2024-01-05.
        tr_ep_a = ep(tr_a, insts[0], progs[0], date(2023, 7, 1), date(2023, 7, 1), date(2023, 12, 20),
                     status="transferred_out", reason="transfer")
        ep(tr_b, insts[1], progs[1], date(2024, 1, 5), date(2024, 1, 5), None, transfer_from=tr_ep_a.id)

        # Concurrent: overlapping full-year episodes, no transfer link.
        ep(cc_a, insts[0], progs[0], date(2023, 7, 1), date(2023, 7, 1), date(2024, 6, 30))
        ep(cc_b, insts[1], progs[1], date(2023, 8, 1), date(2023, 8, 1), date(2024, 6, 30))

        # Over-limit programme (inst0 CSE 2023, intake 60): seed 70 admissions.
        for i in range(70):
            r = _rec(s, insts[0].id, f"Student Over{i:03d}", f"60{i:010d}", 2004)
            s.flush()
            ep(r, insts[0], progs[0], date(2023, 7, 10), date(2023, 7, 10), None)

        # Revised intake (inst1 CSE 2023): 70 admissions in FEBRUARY -> must use earlier limit 60.
        for i in range(70):
            r = _rec(s, insts[1].id, f"Student Rev{i:03d}", f"70{i:010d}", 2004)
            s.flush()
            ep(r, insts[1], progs[1], date(2023, 2, 1), date(2023, 2, 1), None)

        # MISSING approval beat: inst index 2 (progs[2]) has NO approval row. A few admissions
        # there must yield CANNOT_EVALUATE (never a flag).
        for i in range(12):
            r = _rec(s, insts[2].id, f"Student Miss{i:03d}", f"20{i:010d}", 2004)
            s.flush()
            ep(r, insts[2], progs[2], date(2023, 7, 10), date(2023, 7, 10), None)

        # Out-of-window admission (inst3, approval valid Jan-Dec but admission in a bad window demo):
        ow = _rec(s, insts[3].id, "Window Case", "131313131313", 2004)
        s.flush()
        ep(ow, insts[3], progs[3], date(2023, 11, 1), date(2023, 11, 1), None,
           approval_from=date(2023, 6, 1), approval_to=date(2023, 9, 30), approval_ref="SYN-APP-CLEAN")

        s.commit()
        return {
            "institutions": [str(i.id) for i in insts],
            "pairs": {
                "common_name": [str(amit_a.id), str(amit_b.id)],
                "true_duplicate": [str(dup_a.id), str(dup_b.id)],
                "transfer": [str(tr_a.id), str(tr_b.id)],
                "concurrent": [str(cc_a.id), str(cc_b.id)],
            },
        }
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def main() -> None:
    info = seed()
    print("seeded SYNTHETIC demo data")
    print("institutions:", len(info["institutions"]))
    print("demo users password:", DEMO_PASSWORD)


if __name__ == "__main__":
    main()
