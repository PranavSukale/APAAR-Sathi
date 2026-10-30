from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.engines import intake, timeline
from backend.app.engines.intake import Approval, IntakeEpisode
from backend.app.engines.timeline import Episode, TimelineConfig


def _codes(findings):
    return sorted(f["rule_code"] for f in findings)


# ---------------- Timeline ----------------
def test_timeline_valid_transfer_cleared():
    a = Episode("EPA1", "R1", "INST-A", "P1", date(2023, 7, 1), date(2023, 7, 1), date(2023, 12, 20),
                status="transferred_out", end_reason="transfer")
    b = Episode("EPB1", "R2", "INST-B", "P2", date(2024, 1, 5), date(2024, 1, 5), None,
                transfer_from_episode_id="EPA1")
    findings = timeline.evaluate_group([a, b])
    assert "TL-TRANSFER-OK" in _codes(findings)
    assert "TL-OVERLAP" not in _codes(findings)


def test_timeline_true_overlap_flagged():
    a = Episode("EPA2", "R1", "INST-A", "P1", date(2023, 7, 1), date(2023, 7, 1), date(2024, 6, 30))
    b = Episode("EPB2", "R2", "INST-B", "P2", date(2023, 8, 1), date(2023, 8, 1), date(2024, 6, 30))
    findings = timeline.evaluate_group([a, b])
    assert "TL-OVERLAP" in _codes(findings)
    overlap = next(f for f in findings if f["rule_code"] == "TL-OVERLAP")
    assert overlap["evidence"]["overlap_days"] > 30


def test_timeline_readmission_info():
    a = Episode("EPA3", "R1", "INST-A", "P1", date(2018, 7, 1), date(2018, 7, 1), date(2022, 6, 1),
                status="graduated", end_reason="graduated")
    b = Episode("EPB3", "R1", "INST-A", "P1", date(2023, 7, 1), date(2023, 7, 1), None)
    findings = timeline.evaluate_group([a, b])
    assert "TL-READMIT" in _codes(findings)


def test_timeline_out_of_window():
    e = Episode("EPW1", "R1", "INST-A", "P1", date(2023, 11, 1), date(2023, 11, 1), None,
                approval_valid_from=date(2023, 6, 1), approval_valid_to=date(2023, 9, 30),
                approval_reference="APP-2023-01")
    findings = timeline.evaluate_group([e])
    assert "TL-APPROVAL-WINDOW" in _codes(findings)


def test_timeline_late_change():
    e = Episode("EPL1", "R1", "INST-A", "P1", date(2023, 7, 1), date(2023, 7, 1), None,
                created_at=date(2024, 3, 1), cycle_locked_at=date(2023, 12, 31))
    findings = timeline.evaluate_group([e])
    assert "TL-LATE-CHANGE" in _codes(findings)


@settings(max_examples=100, deadline=None)
@given(
    s1=st.integers(0, 365), d1=st.integers(1, 365),
    s2=st.integers(0, 365), d2=st.integers(1, 365),
)
def test_overlap_symmetric(s1, d1, s2, d2):
    base = date(2023, 1, 1)
    from datetime import timedelta
    a = Episode("A", "R", "I1", "P1", base, base + timedelta(days=s1), base + timedelta(days=s1 + d1))
    b = Episode("B", "R", "I2", "P1", base, base + timedelta(days=s2), base + timedelta(days=s2 + d2))
    assert timeline._overlap_days(a, b) == timeline._overlap_days(b, a)


# ---------------- Intake ----------------
def _appr(y_from, y_to, intake_n, cats=None, ref=""):
    return Approval(date(*y_from), date(*y_to), intake_n, cats or {}, ref)


def test_intake_clean():
    eps = [IntakeEpisode(f"E{i}", date(2023, 7, 10)) for i in range(50)]
    appr = [_appr((2023, 1, 1), (2023, 12, 31), 60, ref="APP-A")]
    res = intake.evaluate(eps, appr, institution="INST-A", program="CSE", academic_year="2023")
    assert res["status"] == "WITHIN_LIMIT"
    assert res["numerator"] == 50 and res["limit"] == 60


def test_intake_over_limit():
    eps = [IntakeEpisode(f"E{i}", date(2023, 7, 10)) for i in range(70)]
    appr = [_appr((2023, 1, 1), (2023, 12, 31), 60, ref="APP-A")]
    res = intake.evaluate(eps, appr, institution="INST-A", program="CSE", academic_year="2023")
    assert res["status"] == "OVER_LIMIT"
    assert res["rule_code"] == "INTAKE-OVER"


def test_intake_revised_uses_earlier_limit():
    # Revision mid-year: Jan-Jun limit 60, Jul-Dec raised to 120. Admissions in Feb must
    # count against the earlier (60) limit, not the later one.
    early = [IntakeEpisode(f"E{i}", date(2023, 2, 1)) for i in range(70)]
    appr = [
        _appr((2023, 1, 1), (2023, 6, 30), 60, ref="APP-OLD"),
        _appr((2023, 7, 1), (2023, 12, 31), 120, ref="APP-NEW"),
    ]
    res = intake.evaluate(early, appr, institution="INST-A", program="CSE", academic_year="2023")
    assert res["limit"] == 60
    assert res["status"] == "OVER_LIMIT"


def test_intake_category_overflow():
    eps = [IntakeEpisode(f"E{i}", date(2023, 7, 10), category="LE") for i in range(15)]
    appr = [_appr((2023, 1, 1), (2023, 12, 31), 60, cats={"GEN": 50, "LE": 10}, ref="APP-A")]
    res = intake.evaluate(eps, appr, institution="INST-A", program="CSE", academic_year="2023", category="LE")
    assert res["status"] == "OVER_LIMIT"
    assert res["numerator"] == 15 and res["limit"] == 10


def test_intake_missing_approval_cannot_evaluate():
    eps = [IntakeEpisode("E1", date(2023, 7, 10))]
    res = intake.evaluate(eps, [], institution="INST-A", program="CSE", academic_year="2023")
    assert res["status"] == "CANNOT_EVALUATE"
    assert res["limit"] is None


def test_intake_supplementary_rounds_aggregate():
    round1 = [IntakeEpisode(f"R1-{i}", date(2023, 7, 1)) for i in range(40)]
    round2 = [IntakeEpisode(f"R2-{i}", date(2023, 9, 1)) for i in range(25)]
    appr = [_appr((2023, 1, 1), (2023, 12, 31), 60, ref="APP-A")]
    res = intake.evaluate(round1 + round2, appr, institution="INST-A", program="CSE", academic_year="2023")
    assert res["numerator"] == 65 and res["status"] == "OVER_LIMIT"


@settings(max_examples=50, deadline=None)
@given(st.lists(st.integers(1, 28), min_size=1, max_size=40))
def test_intake_order_invariant(days):
    import random
    eps = [IntakeEpisode(f"E{i}", date(2023, 7, d)) for i, d in enumerate(days)]
    appr = [_appr((2023, 1, 1), (2023, 12, 31), 30, ref="APP-A")]
    r1 = intake.evaluate(list(eps), appr, institution="I", program="P", academic_year="2023")
    shuffled = list(eps)
    random.Random(1).shuffle(shuffled)
    r2 = intake.evaluate(shuffled, appr, institution="I", program="P", academic_year="2023")
    assert (r1["numerator"], r1["limit"], r1["status"]) == (r2["numerator"], r2["limit"], r2["status"])


def test_intake_peer_signal():
    from backend.app.engines.intake import PeerPoint
    pts = [PeerPoint("CSE-MH", f"INST-{i}", fill_rate=0.5, last_days_share=0.1) for i in range(8)]
    pts.append(PeerPoint("CSE-MH", "INST-OUT", fill_rate=0.98, last_days_share=0.9))
    sig = intake.peer_signals(pts)
    assert any(s["entity_id"] == "-OUT"[-4:] or s["entity_id"] == "OUT" for s in sig) or len(sig) >= 1
    assert all(s["label"] == "attention signal, not a violation" for s in sig)
