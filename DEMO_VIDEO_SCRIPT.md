# APAAR Sathi — Demo Video Script (4–5 min)

**Project:** APAAR Sathi · *verify without exposing* · SIH26263
**Repo:** https://github.com/PranavSukale/APAAR-Sathi
**Total runtime:** ~4 min 30 sec · **Data:** 100% synthetic

> Narrator reads the **Say** column. Presenter does the **Show / Do** column. Timings are cumulative targets —
> if you run long, trim the Timeline section first (it's the one beat you can describe verbally).

---

## Before you hit record (setup checklist)

1. Start Postgres: `docker compose up -d`
2. Reseed clean demo data: `python -m scripts.seed`
3. Make sure `benchmark.json` exists: `python -m scripts.benchmark --n 8000 --seed 7`
4. Start backend: `python -m uvicorn backend.app.main:app --port 8000`
5. Start frontend: `cd frontend && npm run dev` → open **http://localhost:5173**
6. Log in as **AICTE Reviewer** (quick-pick, password `demo1234`). Keep a second tab logged in as **AICTE Supervisor** for the reveal step.
7. Browser at 110–125% zoom, close dev tools, full-screen the window.

---

## SECTION 1 — Problem & Context  ·  0:00–0:20  (20 sec)

| Say | Show / Do |
|---|---|
| "Across AICTE institutions, the same student can appear in multiple colleges. Records live in disconnected spreadsheets, so duplicate and concurrent enrolments, and admissions beyond the approved intake, slip through." | Title slide: **APAAR Sathi — verify without exposing**. Sub-line: *SIH26263 · synthetic data*. |
| "But the obvious fix — one giant central database of student IDs — is itself a privacy risk. A name-only duplicate checker also drowns reviewers in false matches for common Indian names." | Optional: a simple two-box graphic — "Central DB = breach risk" and "Name-only matching = false positives". |

---

## SECTION 2 — Solution & Impact  ·  0:20–0:50  (30 sec)

| Say | Show / Do |
|---|---|
| "APAAR Sathi's thesis is *verify without exposing*. It finds these problems without becoming a surveillance database." | Login screen with the amber **SYNTHETIC DATA ONLY** banner visible. |
| "Five things make it different: explainable probabilistic matching with per-field evidence; dated enrolment episodes that tell a transfer apart from a double enrolment; effective-dated intake rules; a privacy architecture with tokens, encryption and row-level security; and an assisted import that never sends personal data to an AI." | Click **AICTE Reviewer** quick-pick to sign in; the role-aware dashboard loads. |
| "Every flag is a review signal for a human. The system never auto-merges records, rejects a student, or labels anyone fraudulent." | Point to the top banner line: *flags are review signals, never proof*. |

---

## SECTION 3 — Live Prototype Demo  ·  0:50–2:50  (2 min)

### 3a. Explainable Identity Linkage  (0:50–1:25)

| Say | Show / Do |
|---|---|
| "Here are candidate matches. This one is a true duplicate — same identifier, with a spelling and word-order variation across two colleges." | On **Identity Linkage**, click **View evidence** on a row in *True duplicates*. |
| "This is the evidence waterfall — *why* these two records match. Each bar is one field: the identifier token and name agreement push the score up; everything is shown with masked values." | Point at the waterfall bars (blue = toward same person). Read the band = **High**, probability ~100%. |
| "Now the hard case: two different students who happen to share a common name. A naive matcher would flag them." | Click **View evidence** on a row in *Common-name trap*. |
| "APAAR Sathi keeps it in the **Low** band — the two different identifiers push the score down. Same name is not enough." | Point to the red bars and the note: *naive baseline would falsely flag; model keeps it Low*. |

### 3b. Benchmark — the credibility shot  (1:25–1:45)

| Say | Show / Do |
|---|---|
| "We measured this. Against a naive exact-plus-fuzzy baseline on an adversarial synthetic set, our model's high-confidence band cuts the false-positive rate from about 41% to under 4% — while still catching every true duplicate." | Go to **Privacy & Integrity**, scroll to the benchmark table. Highlight the blue `model_fs_high_band` row vs `baseline2`. |
| "Precision, recall, F1 and false-positive rate — all reported, with a PR curve. No target claimed before measurement." | Gesture at the PR curve below the table. |

### 3c. Enrolment Timeline  (1:45–2:10)

| Say | Show / Do |
|---|---|
| "Repeated identifiers aren't always bad. With dated episodes we can tell them apart." | Go to **Enrolment Timeline**, pick a pair. |
| "A recorded transfer — one college ends, another begins within tolerance — is cleared automatically." | Point to a `TL-TRANSFER-OK` finding and the bars that don't overlap. |
| "But overlapping episodes at two colleges with no transfer is a true concurrent enrolment, opened for review with both timelines as evidence." | Select the concurrent pair; point to the shaded overlap and the `TL-OVERLAP` flag. |

### 3d. Intake Integrity  (2:10–2:35)

| Say | Show / Do |
|---|---|
| "Intake is checked against the approval in force *on each admission date* — not the latest number." | Go to **Intake Integrity**. |
| "This college raised its intake mid-year, but these students were admitted in February, so the engine correctly applies the *earlier* limit of 60 — and flags the overflow." | Point to the revised-intake row: numerator 73, limit **60**, note *earlier limit applied*. |
| "And when an approval is missing, it refuses to guess: it returns **CANNOT_EVALUATE** with a reason, never a false accusation." | Point to the `CANNOT_EVALUATE` row. |

### 3e. Privacy — Proof  (2:35–2:50)

| Say | Show / Do |
|---|---|
| "Privacy here is measurable, not a promise. Run the scan: the database, logs and exports contain no raw identifiers — only ciphertext and keyed tokens." | On **Privacy & Integrity**, click **Run privacy scan** → green **PASS**. |
| "And the audit trail is tamper-evident. Verify the chain — if anyone alters a stored event, verification fails and points to the exact row." | Click **Verify audit chain** → **Chain intact**. (Optional: mention the tamper test passes in CI.) |

---

## SECTION 4 — Controlled Reveal (privacy governance)  ·  2:50–3:15  (25 sec)

| Say | Show / Do |
|---|---|
| "When a reviewer truly needs the raw value, it's a governed exception — not a free lookup." | Go to **Controlled Reveal**. As the reviewer, pick a purpose and click **Request reveal**. |
| "A *different* supervisor must approve — self-approval is rejected — and approval sets a short expiry." | Switch to the Supervisor tab, click **Approve** in the queue. |
| "The value is shown once, then it's consumed, it expires, and every step is in the audit log." | Back as reviewer, click **Reveal once**; show the one-time panel with the countdown. Note a second reveal is blocked. |

---

## SECTION 5 — Business, Scalability & Feasibility  ·  3:15–4:00  (45 sec)

| Say | Show / Do |
|---|---|
| "The market is every AICTE-approved institution and the regulators who reconcile their data — a recurring, compliance-driven need." | Return to the dashboard or a closing slide. |
| "It's built to scale: candidate generation uses keyed blocking so matching never needs plaintext names in the database, work is incremental per batch, and queries are indexed by academic year — designed for millions of records." | Optional: show the candidate-pair count on the linkage screen as a scale hint. |
| "It's feasible today: a standard FastAPI, PostgreSQL and React stack, with row-level security and field encryption as defence in depth. The matching has a clear production path to Splink, and the identifier verification is a labelled mock behind a clean interface, ready for an authorised APAAR integration." | — |
| "Roadmap: reviewer-feedback recalibration, authorised APAAR and DigiLocker integration under consent, and blinded tokenisation so even the central service never sees a raw identifier." | — |

---

## SECTION 6 — Close  ·  4:00–4:15  (15 sec)

| Say | Show / Do |
|---|---|
| "APAAR Sathi: find the duplicate, the concurrent enrolment, the intake overflow — with explainable evidence and a human in the loop — without ever becoming a surveillance database. Verify without exposing." | Closing title: **APAAR Sathi · verify without exposing · SIH26263**. GitHub URL on screen. |

---

## One-line beat cheat-sheet (for the editor)

1. Evidence waterfall — *why these match* (0:50)
2. Benchmark — 41% → <4% false positives (1:25)
3. Transfer cleared vs concurrent flagged (1:45)
4. Revised-intake earlier limit + CANNOT_EVALUATE (2:10)
5. Privacy scan PASS + audit chain intact (2:35)
6. Dual-approved, single-use, expiring reveal (2:50)

## Things to say once, clearly (compliance)

- All data is **synthetic**.
- **No** Aadhaar/UIDAI, **no** live APAAR/DigiLocker/AICTE integration.
- **No** auto-merge, auto-reject, or fraud labelling — every flag is a human review signal.
- The APAAR identifier pattern shown is an **unverified placeholder**; mock verification is labelled **MOCK**.
