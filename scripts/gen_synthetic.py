from __future__ import annotations

import argparse
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta

# Adversarial synthetic generator (seeded). SYNTHETIC DATA ONLY.
# Produces records grouped by person_group (ground truth). Adversarial cases:
#  - true duplicates with spelling / order variants and transliteration
#  - twins and relatives (similar name, different person)
#  - SAME COMMON NAME different people (the baseline false-positive trap)
#  - missing fields

FIRST = ["Rahul", "Priya", "Amit", "Sunita", "Mohammed", "Aishwarya", "Vijay",
         "Deepak", "Neha", "Arjun", "Kavya", "Siddharth", "Lakshmi", "Rajiv", "Geeta"]
LAST = ["Sharma", "Patel", "Kumar", "Reddy", "Singh", "Gupta", "Nair", "Iyer",
        "Das", "Khan", "Mehta", "Rao", "Joshi", "Verma", "Shah"]
PROGRAMS = ["CSE", "ECE", "MECH", "CIVIL", "IT", "EEE"]
STATES = ["MH", "KA", "TN", "DL", "UP", "GJ"]

VARIANTS = {
    "Mohammed": ["Mohammad", "Muhammad", "Mohamad"],
    "Rajiv": ["Rajeev"],
    "Lakshmi": ["Laxmi"],
    "Siddharth": ["Sidharth", "Siddhartha"],
    "Aishwarya": ["Aiswarya"],
    "Deepak": ["Dipak"],
    "Geeta": ["Gita"],
    "Sunita": ["Suniti"],
    "Priya": ["Priyaa"],
}


@dataclass
class Rec:
    record_id: str
    person_group: int
    name: str
    apaar: str | None
    program_code: str
    academic_year: str
    admission_date: str
    dob_year: int | None
    state: str
    institution: int


def _spelling_variant(rng: random.Random, first: str) -> str:
    if first in VARIANTS and rng.random() < 0.8:
        return rng.choice(VARIANTS[first])
    return first


def _order_swap(name: str) -> str:
    parts = name.split()
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return name


def generate(n: int = 20000, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    records: list[Rec] = []
    rid = 0
    group = 0

    def next_id() -> str:
        nonlocal rid
        rid += 1
        return f"R{rid:06d}"

    def rand_date(year: int) -> str:
        start = date(year, 6, 1)
        return (start + timedelta(days=rng.randint(0, 120))).isoformat()

    def rand_apaar() -> str:
        return "".join(str(rng.randint(0, 9)) for _ in range(12))

    while len(records) < n:
        group += 1
        first = rng.choice(FIRST)
        last = rng.choice(LAST)
        base_name = f"{first} {last}"
        apaar = rand_apaar()
        prog = rng.choice(PROGRAMS)
        state = rng.choice(STATES)
        year = rng.choice([2022, 2023, 2024])
        dob = rng.randint(2002, 2006)
        roll = rng.random()

        if roll < 0.18:
            # true duplicate across two institutions: spelling/order variant, same apaar sometimes
            records.append(Rec(next_id(), group, base_name, apaar, prog, str(year), rand_date(year), dob, state, 1))
            vfirst = _spelling_variant(rng, first)
            vname = f"{vfirst} {last}"
            if rng.random() < 0.5:
                vname = _order_swap(vname)
            dup_apaar = apaar if rng.random() < 0.6 else rand_apaar()
            records.append(Rec(next_id(), group, vname, dup_apaar, prog, str(year),
                               rand_date(year), dob, state, 2))
        elif roll < 0.30:
            # SAME COMMON NAME, different people (baseline false-positive trap): different group ids
            records.append(Rec(next_id(), group, base_name, apaar, prog, str(year), rand_date(year), dob, state, 1))
            group += 1
            records.append(Rec(next_id(), group, base_name, rand_apaar(), rng.choice(PROGRAMS),
                               str(rng.choice([2022, 2023, 2024])), rand_date(year),
                               rng.randint(2002, 2006), rng.choice(STATES), 2))
        elif roll < 0.38:
            # twins/relatives: same last name, different first, same dob/state
            records.append(Rec(next_id(), group, base_name, apaar, prog, str(year), rand_date(year), dob, state, 1))
            group += 1
            other_first = rng.choice([f for f in FIRST if f != first])
            records.append(Rec(next_id(), group, f"{other_first} {last}", rand_apaar(), prog,
                               str(year), rand_date(year), dob, state, 1))
        elif roll < 0.46:
            # missing fields duplicate
            records.append(Rec(next_id(), group, base_name, apaar, prog, str(year), rand_date(year), dob, state, 1))
            records.append(Rec(next_id(), group, base_name, None, prog, str(year),
                               rand_date(year), None, state, 2))
        else:
            # singleton
            records.append(Rec(next_id(), group, base_name, apaar, prog, str(year), rand_date(year), dob, state, 1))

    records = records[:n]
    return [asdict(r) for r in records]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="synthetic.json")
    args = ap.parse_args()
    import json

    data = generate(args.n, args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"generated {len(data)} synthetic records (SYNTHETIC DATA) -> {args.out}")


if __name__ == "__main__":
    main()
