from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from rapidfuzz.distance import JaroWinkler

from . import normalise

# Fellegi-Sunter record linkage.
# Each comparison yields a *level*; each (comparison, level) has an m and u probability.
# Partial weight = log2(m/u). Total weight = sum of partial weights -> probability via logistic.
# This produces the per-field "evidence waterfall" the UI renders.


@dataclass
class CompLevel:
    comparison: str
    level: str
    m: float  # P(level | records are the same person)
    u: float  # P(level | records are different people)

    @property
    def weight(self) -> float:
        return math.log2(self.m / self.u)


# --- Default (sane, hand-set) m/u parameters. EM can refine m later. ---
# u = chance agreement among non-matches; m = agreement among true matches.
PARAMS: dict[str, list[CompLevel]] = {
    "identifier": [
        CompLevel("identifier", "exact", m=0.99, u=0.0001),
        # Two different valid identifiers strongly indicate different people (IDs are per-person).
        CompLevel("identifier", "different", m=0.01, u=0.97),
        CompLevel("identifier", "null", m=0.35, u=0.35),
    ],
    "name": [
        # Common Indian names collide often, so name agreement alone is only moderate evidence.
        CompLevel("name", "exact", m=0.55, u=0.02),
        CompLevel("name", "order_swapped", m=0.15, u=0.01),
        CompLevel("name", "high_jw", m=0.18, u=0.03),
        CompLevel("name", "medium_jw", m=0.08, u=0.09),
        CompLevel("name", "initial_consistent", m=0.03, u=0.05),
        CompLevel("name", "else", m=0.01, u=0.80),
    ],
    "program_year": [
        CompLevel("program_year", "same_prog_same_year", m=0.45, u=0.05),
        CompLevel("program_year", "same_prog", m=0.20, u=0.10),
        CompLevel("program_year", "same_year", m=0.20, u=0.20),
        CompLevel("program_year", "else", m=0.15, u=0.65),
    ],
    "admission_proximity": [
        CompLevel("admission_proximity", "same_cycle", m=0.50, u=0.15),
        CompLevel("admission_proximity", "near", m=0.30, u=0.25),
        CompLevel("admission_proximity", "far", m=0.20, u=0.60),
    ],
    "dob_year": [
        # Only ~a handful of plausible birth years, so agreement is weak evidence on its own.
        CompLevel("dob_year", "equal", m=0.92, u=0.20),
        CompLevel("dob_year", "diff", m=0.08, u=0.80),
        CompLevel("dob_year", "null", m=0.30, u=0.30),
    ],
}

BANDS = {"high": 0.90, "medium": 0.60}  # probability thresholds


@dataclass
class RecordView:
    """In-memory decrypted view used only inside the linkage worker."""
    record_id: str
    name: str
    apaar_token: str | None
    program_code: str
    academic_year: str
    admission_date: date | None
    dob_year: int | None = None
    state: str = ""

    features: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.features:
            self.features = normalise.feature_bundle(self.name)


def _mask_name(name: str) -> str:
    toks = name.split()
    return " ".join((t[0] + "***") for t in toks) if toks else "***"


def _level(comparison: str, level: str) -> CompLevel:
    for cl in PARAMS[comparison]:
        if cl.level == level:
            return cl
    raise KeyError(f"{comparison}:{level}")


def _cmp_identifier(a: RecordView, b: RecordView) -> str:
    if not a.apaar_token or not b.apaar_token:
        return "null"
    return "exact" if a.apaar_token == b.apaar_token else "different"


def _cmp_name(a: RecordView, b: RecordView) -> str:
    fa, fb = a.features, b.features
    if fa["sorted_token_key"] == fb["sorted_token_key"]:
        # exact if same order too, else order-swapped
        return "exact" if fa["tokens"] == fb["tokens"] else "order_swapped"
    jw = JaroWinkler.similarity(fa["sorted_token_key"], fb["sorted_token_key"])
    if jw >= 0.92:
        return "high_jw"
    if jw >= 0.85:
        return "medium_jw"
    # initials consistent (e.g. "r kumar" vs "rahul kumar")
    if _initials_consistent(fa, fb):
        return "initial_consistent"
    return "else"


def _initials_consistent(fa: dict, fb: dict) -> bool:
    short, long = sorted([fa["tokens"], fb["tokens"]], key=len)
    if not short or len(short) != len(long):
        # allow abbreviation where short has initials
        pass
    # each short token is a prefix of the corresponding long token (order-insensitive greedy)
    remaining = list(long)
    for t in short:
        hit = next((x for x in remaining if x.startswith(t[0]) and (len(t) == 1 or x.startswith(t))), None)
        if hit is None:
            return False
        remaining.remove(hit)
    return True


def _cmp_program_year(a: RecordView, b: RecordView) -> str:
    same_prog = a.program_code and a.program_code == b.program_code
    same_year = a.academic_year and a.academic_year == b.academic_year
    if same_prog and same_year:
        return "same_prog_same_year"
    if same_prog:
        return "same_prog"
    if same_year:
        return "same_year"
    return "else"


def _cmp_admission(a: RecordView, b: RecordView) -> str:
    if not a.admission_date or not b.admission_date:
        return "far"
    days = abs((a.admission_date - b.admission_date).days)
    if days <= 120:
        return "same_cycle"
    if days <= 420:
        return "near"
    return "far"


def _cmp_dob(a: RecordView, b: RecordView) -> str:
    if a.dob_year is None or b.dob_year is None:
        return "null"
    return "equal" if a.dob_year == b.dob_year else "diff"


def score_pair(a: RecordView, b: RecordView) -> dict:
    """Returns total weight, probability, band, and the per-comparison evidence waterfall."""
    chosen = [
        _level("identifier", _cmp_identifier(a, b)),
        _level("name", _cmp_name(a, b)),
        _level("program_year", _cmp_program_year(a, b)),
        _level("admission_proximity", _cmp_admission(a, b)),
        _level("dob_year", _cmp_dob(a, b)),
    ]
    total = sum(cl.weight for cl in chosen)
    probability = 1.0 / (1.0 + 2.0 ** (-total))
    band = "High" if probability >= BANDS["high"] else "Medium" if probability >= BANDS["medium"] else "Low"

    evidence = [
        {
            "comparison": cl.comparison,
            "level": cl.level,
            "weight": round(cl.weight, 3),
            "direction": "up" if cl.weight > 0 else "down" if cl.weight < 0 else "neutral",
        }
        for cl in chosen
    ]
    # exact token repeat is ALWAYS a rule exception regardless of score
    exact_token_repeat = _cmp_identifier(a, b) == "exact"
    return {
        "record_a": a.record_id,
        "record_b": b.record_id,
        "masked_a": _mask_name(a.name),
        "masked_b": _mask_name(b.name),
        "total_weight": round(total, 3),
        "probability": round(probability, 4),
        "band": band,
        "evidence": evidence,
        "exact_token_repeat": exact_token_repeat,
        "model_version": "fs-1",
    }
