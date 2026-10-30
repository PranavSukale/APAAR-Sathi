from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.engines.linkage import normalise
from backend.app.engines.linkage.model import RecordView, score_pair
from scripts.benchmark import run

# These tests do not need the database.
import pytest  # noqa: E402


@settings(max_examples=200, deadline=None)
@given(st.text(min_size=0, max_size=40))
def test_normalisation_idempotent(s: str):
    once = normalise.basic_clean(s)
    twice = normalise.basic_clean(once)
    assert once == twice
    # feature keys stable under re-normalisation of the cleaned string
    assert normalise.sorted_token_key(s) == normalise.sorted_token_key(once)


def test_variants_map_together():
    assert normalise.sorted_token_key("Mohammed Khan") == normalise.sorted_token_key("Mohammad Khan")
    assert normalise.sorted_token_key("Rajiv Sharma") == normalise.sorted_token_key("Rajeev Sharma")
    # order swap handled
    assert normalise.sorted_token_key("Khan Mohammad") == normalise.sorted_token_key("Mohammad Khan")


def test_every_candidate_has_full_evidence():
    a = RecordView("A", "Rahul Sharma", "100000000001", "CSE", "2023", date(2023, 7, 1), 2004)
    b = RecordView("B", "Sharma Rahul", "100000000001", "CSE", "2023", date(2023, 7, 10), 2004)
    s = score_pair(a, b)
    comparisons = {e["comparison"] for e in s["evidence"]}
    assert comparisons == {"identifier", "name", "program_year", "admission_proximity", "dob_year"}
    assert all("weight" in e and "direction" in e for e in s["evidence"])
    assert s["exact_token_repeat"] is True
    assert s["band"] == "High"
    # masked, never raw
    assert "Rahul" not in s["masked_a"]


def test_common_name_not_auto_matched():
    # same common name, different people (no shared token, different program/year/dob)
    a = RecordView("A", "Amit Kumar", "100000000010", "CSE", "2022", date(2022, 7, 1), 2003)
    b = RecordView("B", "Amit Kumar", "200000000020", "MECH", "2024", date(2024, 8, 1), 2005)
    s = score_pair(a, b)
    assert s["band"] != "High"  # name alone must not push to High


def test_model_beats_baseline2_on_f1_and_fpr():
    res = run(n=4000, seed=7)
    model = res["modes"]["model_fs_medium_and_up"]
    high = res["modes"]["model_fs_high_band"]
    b2 = res["modes"]["baseline2_exact_plus_fuzzy"]
    assert model["f1"] >= b2["f1"], res["modes"]
    assert model["false_positive_rate"] <= b2["false_positive_rate"], res["modes"]
    # High band is the precision story: far cleaner than the naive baseline.
    assert high["precision"] >= b2["precision"], res["modes"]
