from __future__ import annotations

import httpx

BASE = "http://127.0.0.1:8000"


def login(email, pw):
    r = httpx.post(f"{BASE}/api/v1/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["access_token"]


def main():
    print("health:", httpx.get(f"{BASE}/health").json())
    rev = login("reviewer@aicte.syn", "demo1234")
    h = {"Authorization": f"Bearer {rev}"}

    pairs = httpx.get(f"{BASE}/api/v1/linkage/pairs", headers=h, timeout=60).json()
    print("candidate_count:", pairs["candidate_count"])
    print("baseline false positives caught by model:", len(pairs["baseline_false_positives"]))
    print("true duplicates (High band):", len(pairs["true_duplicates"]))
    if pairs["baseline_false_positives"]:
        d = pairs["baseline_false_positives"][0]
        print("  sample FP band/prob:", d["band"], d["probability"], "| baseline2 flagged:", d["baseline2_match"])

    intake = httpx.get(f"{BASE}/api/v1/intake/results", headers=h, timeout=60).json()
    statuses = {}
    for r in intake["results"]:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    print("intake statuses:", statuses)
    for r in intake["results"]:
        if r["status"] in ("OVER_LIMIT", "CANNOT_EVALUATE"):
            print(f"  {r['status']}: num={r['numerator']} limit={r['limit']} ref={r.get('approval_reference','')} reason={r.get('reason','')}")

    proof = httpx.get(f"{BASE}/api/v1/privacy/proof", headers=h, timeout=60).json()
    print("privacy proof passed:", proof["passed"], "| rows scanned:",
          next(c["rows_scanned"] for c in proof["checks"] if c["target"] == "db_ciphertext_columns"))

    aud = login("auditor@aicte.syn", "demo1234")
    ha = {"Authorization": f"Bearer {aud}"}
    audit = httpx.get(f"{BASE}/api/v1/audit/verify", headers=ha, timeout=60).json()
    print("audit chain valid:", audit.get("valid"), "events:", audit.get("events"))

    # Reveal governance happy path.
    sup = login("supervisor@aicte.syn", "demo1234")
    hs = {"Authorization": f"Bearer {sup}"}
    target = pairs["pairs"][0]["record_a"]
    rr = httpx.post(f"{BASE}/api/v1/reveals", headers=h,
                    json={"record_id": target, "purpose": "DUPLICATE_CONFIRMATION",
                          "purpose_detail": "demo"}).json()
    appr = httpx.post(f"{BASE}/api/v1/reveals/{rr['id']}/approve", headers=hs).json()
    consumed = httpx.post(f"{BASE}/api/v1/reveals/{rr['id']}/consume", headers=h).json()
    print("reveal consumed once; name present:", bool(consumed.get("name")),
          "expires_at set:", bool(appr.get("expires_at")))
    again = httpx.post(f"{BASE}/api/v1/reveals/{rr['id']}/consume", headers=h)
    print("second consume blocked:", again.status_code == 400)


if __name__ == "__main__":
    main()
