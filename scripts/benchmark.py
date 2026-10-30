from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from datetime import date

from backend.app.engines.linkage import baselines, blocking
from backend.app.engines.linkage.model import RecordView, score_pair
from scripts.gen_synthetic import generate


def _to_view(r: dict) -> RecordView:
    ad = date.fromisoformat(r["admission_date"]) if r.get("admission_date") else None
    return RecordView(
        record_id=r["record_id"],
        name=r["name"],
        apaar_token=r["apaar"],  # for benchmark the raw apaar acts as its own token
        program_code=r["program_code"],
        academic_year=r["academic_year"],
        admission_date=ad,
        dob_year=r.get("dob_year"),
        state=r.get("state", ""),
    )


def _metrics(tp: int, fp: int, fn: int, tn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
    }


def run(n: int, seed: int, big: bool = False) -> dict:
    records = generate(n, seed)
    views = [_to_view(r) for r in records]
    truth = {r["record_id"]: r["person_group"] for r in records}

    tracemalloc.start()
    t0 = time.perf_counter()
    pairs, warnings = blocking.candidate_views(views)
    block_seconds = time.perf_counter() - t0

    # All candidate pairs; label by ground truth.
    def is_same(a: RecordView, b: RecordView) -> bool:
        return truth[a.record_id] == truth[b.record_id]

    # Total true-same pairs within blocks define the recall denominator realistically.
    total_same_in_blocks = sum(1 for a, b in pairs if is_same(a, b))

    # model + baselines
    model_counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    b1_counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    b2_counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    pr_points = []  # (threshold, precision, recall) for the model

    t0 = time.perf_counter()
    scored = []
    for a, b in pairs:
        s = score_pair(a, b)
        same = is_same(a, b)
        scored.append((s["probability"], same, s["exact_token_repeat"]))
    model_seconds = time.perf_counter() - t0

    MODEL_T = 0.60  # medium band and up counts as a predicted match
    high_counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for prob, same, exact in scored:
        pred = prob >= MODEL_T or exact
        _bump(model_counts, pred, same)
        # High band = probability >= 0.90 or an exact identifier repeat
        _bump(high_counts, (prob >= 0.90 or exact), same)
    for a, b in pairs:
        _bump(b1_counts, baselines.baseline1_match(a, b), is_same(a, b))
        _bump(b2_counts, baselines.baseline2_match(a, b), is_same(a, b))

    # PR curve for model
    for t in [i / 20 for i in range(1, 20)]:
        c = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        for prob, same, exact in scored:
            _bump(c, (prob >= t or exact), same)
        m = _metrics(**c)
        pr_points.append({"threshold": round(t, 2), "precision": m["precision"], "recall": m["recall"]})

    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    result = {
        "synthetic": True,
        "n_records": n,
        "candidate_pairs": len(pairs),
        "true_same_pairs_in_blocks": total_same_in_blocks,
        "block_warnings": warnings,
        "runtime": {
            "blocking_seconds": round(block_seconds, 3),
            "scoring_seconds": round(model_seconds, 3),
            "peak_memory_mb": round(peak / 1e6, 1),
        },
        "modes": {
            "baseline1_exact_token": _metrics(**b1_counts),
            "baseline2_exact_plus_fuzzy": _metrics(**b2_counts),
            "model_fs_medium_and_up": _metrics(**model_counts),
            "model_fs_high_band": _metrics(**high_counts),
        },
        "pr_curve_model": pr_points,
    }
    return result


def _bump(counts: dict, pred: bool, actual: bool) -> None:
    if pred and actual:
        counts["tp"] += 1
    elif pred and not actual:
        counts["fp"] += 1
    elif not pred and actual:
        counts["fn"] += 1
    else:
        counts["tn"] += 1


def _print_table(res: dict) -> None:
    print(f"\nAPAAR Sathi linkage benchmark  (SYNTHETIC DATA, n={res['n_records']})")
    print(f"candidate pairs: {res['candidate_pairs']}  |  blocking {res['runtime']['blocking_seconds']}s  "
          f"scoring {res['runtime']['scoring_seconds']}s  peak {res['runtime']['peak_memory_mb']}MB")
    header = f"{'mode':<30}{'P':>8}{'R':>8}{'F1':>8}{'FPR':>8}"
    print(header)
    print("-" * len(header))
    for name, m in res["modes"].items():
        print(f"{name:<30}{m['precision']:>8}{m['recall']:>8}{m['f1']:>8}{m['false_positive_rate']:>8}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--big", action="store_true", help="also report a 100k run")
    ap.add_argument("--out", type=str, default="benchmark.json")
    args = ap.parse_args()

    res = run(args.n, args.seed, big=args.big)
    _print_table(res)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\nwrote {args.out}")

    if args.big:
        big = run(100000, args.seed)
        print("\n-- scale run n=100000 --")
        _print_table(big)
        with open("benchmark_100k.json", "w", encoding="utf-8") as f:
            json.dump(big, f, indent=2)


if __name__ == "__main__":
    main()
