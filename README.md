# APAAR Sathi

**Privacy-first student data verification for AICTE institutions** · SIH26263 · *verify without exposing*

> All data is **synthetic**. No Aadhaar/UIDAI, no live APAAR/DigiLocker/AICTE integration. Every flag is a review
> signal for a human — the system never auto-merges records, rejects a student, or labels anyone fraudulent. The
> APAAR identifier pattern is an unverified, configurable placeholder.

APAAR Sathi helps authorised AICTE reviewers find identity and admission anomalies (duplicate / concurrent
enrolment, malformed identifiers, intake overflow) **without becoming a surveillance database**: tokenised
matching, field encryption, row-level security, and a purpose-bound, dual-approved reveal.

## The 6 demo beats

| # | Screen | What it shows |
|---|--------|---------------|
| 1 | Identity Linkage | Per-field **evidence waterfall** — why two records match, with masked values |
| 2 | Privacy & Integrity | **Benchmark** — Fellegi-Sunter model vs naive baseline (far lower false-positive rate) |
| 3 | Enrolment Timeline | A legit **transfer cleared** vs a true **concurrent enrolment** flagged, as date bars |
| 4 | Intake Integrity | Over-limit, **revised-intake uses the earlier limit**, and **CANNOT_EVALUATE** (no guess) |
| 5 | Privacy & Integrity | DB has **no raw identifiers**; tamper an audit row → **chain verification fails** at that row |
| 6 | Controlled Reveal | **Dual-approved, expiring, single-use** reveal (self-approval rejected, every step audited) |

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2, PostgreSQL 16 (RLS, daterange), pytest + hypothesis,
  AES-256-GCM + HMAC tokens (KMS abstraction), hash-chained audit.
- **Frontend**: React + TypeScript + Vite + Tailwind + TanStack Query + Recharts.
- **Linkage**: ~Fellegi-Sunter in pure Python (log2 Bayes factors, per-field evidence). Splink is the production path.
- **Infra**: Docker only for Postgres; API and web run locally.

## Run it

Prerequisites: Docker Desktop, Python 3.11+, Node 18+.

```bash
# 1. Start Postgres + create schema and RLS (host port 5544)
docker compose up -d
python -m backend.app.core.dbinit

# 2. Install backend deps (a venv is recommended)
python -m pip install -r backend/requirements.txt

# 3. Seed the synthetic demo data (6 beats) and the benchmark artifact
python -m scripts.seed
python -m scripts.benchmark --n 8000 --seed 7      # writes benchmark.json

# 4. Backend API (http://localhost:8000, docs at /docs)
python -m uvicorn backend.app.main:app --port 8000

# 5. Frontend (http://localhost:5173)
cd frontend && npm install && npm run dev
```

Demo logins (password `demo1234`): `reviewer@aicte.syn`, `supervisor@aicte.syn`, `auditor@aicte.syn`,
`admin@aicte.syn`, `operator1@syn.edu`.

## Tests

```bash
python -m pytest backend/tests -q
```

Covers: cross-institution RLS isolation (API + raw SQL), ciphertext-only columns, audit tamper
detection/location, log redaction, name normalisation (idempotent), model-beats-baseline, timeline + intake
fixtures, reveal governance, and the privacy canary scan.

## Notes / honest scope

- Postgres runs on host port **5544** (avoids a conflicting local Postgres on 5433).
- Lean choices vs the full TRD: FastAPI BackgroundTasks + local dir instead of Celery/Redis/MinIO; pure-Python
  Fellegi-Sunter instead of Splink/DuckDB; `create_all` + `rls.sql` instead of Alembic. All PRD "never-cut"
  items are present: tokens + encryption + RLS, linkage with per-field evidence, timeline rules, effective-dated
  intake, audit hash chain, baseline comparison.
