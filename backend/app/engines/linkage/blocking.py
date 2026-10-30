from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from .model import RecordView

# Candidate generation via blocking. Keys are keyed/derived (no plaintext names needed in DB).
# Union of several blocking rules; de-duplicated; oversize blocks capped and reported.

MAX_BLOCK = 500  # cap; larger blocks reported as a data-quality warning


def _admission_year(r: RecordView) -> str:
    return str(r.admission_date.year) if r.admission_date else ""


def blocking_keys(r: RecordView) -> list[str]:
    f = r.features
    keys = []
    if r.apaar_token:
        keys.append(f"tok:{r.apaar_token}")
    if r.dob_year:
        keys.append(f"ph:{f['phonetic_key']}|dob:{r.dob_year}")
    if r.program_code:
        keys.append(f"st:{f['sorted_token_key']}|prog:{r.program_code}")
    # Fallback for sparse data: first token + admission year + state (state cuts block size).
    keys.append(f"ft:{f['first_token']}|yr:{_admission_year(r)}|loc:{r.state}")
    return keys


def generate_candidates(records: list[RecordView]) -> tuple[list[tuple[str, str]], list[dict]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    index = {r.record_id: r for r in records}
    for r in records:
        for k in blocking_keys(r):
            buckets[k].append(r.record_id)

    warnings: list[dict] = []
    pairs: set[tuple[str, str]] = set()
    for key, members in buckets.items():
        members = list(dict.fromkeys(members))
        if len(members) < 2:
            continue
        if len(members) > MAX_BLOCK:
            warnings.append({"block_key_class": key.split(":", 1)[0], "size": len(members)})
            members = members[:MAX_BLOCK]
        for a, b in combinations(sorted(members), 2):
            pairs.add((a, b))
    return sorted(pairs), warnings


def candidate_views(records: list[RecordView]) -> tuple[list[tuple[RecordView, RecordView]], list[dict]]:
    index = {r.record_id: r for r in records}
    pair_ids, warnings = generate_candidates(records)
    return [(index[a], index[b]) for a, b in pair_ids], warnings
