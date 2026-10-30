from __future__ import annotations

from rapidfuzz.distance import JaroWinkler

from . import normalise
from .model import RecordView

# Baselines for the benchmark comparison.
# baseline1: exact identifier token only.
# baseline2: exact token OR high fuzzy name score (the common "naive" approach).


def baseline1_match(a: RecordView, b: RecordView) -> bool:
    return bool(a.apaar_token and b.apaar_token and a.apaar_token == b.apaar_token)


def baseline2_match(a: RecordView, b: RecordView, name_threshold: float = 0.90) -> bool:
    if baseline1_match(a, b):
        return True
    ka = normalise.sorted_token_key(a.name)
    kb = normalise.sorted_token_key(b.name)
    return JaroWinkler.similarity(ka, kb) >= name_threshold
