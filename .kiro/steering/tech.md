# Stack
Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL 16 (RLS, daterange, GiST), pytest+httpx, rapidfuzz, cryptography, argon2-cffi, pandas+openpyxl.
Frontend: React+TS+Vite, Tailwind, React Router, TanStack Query, Recharts. Plain, accessible UI; status never colour-only.
Infra: docker-compose = postgres only. Run `make up|seed|test|demo`.
Layout: backend/app/{core,models,api,services,engines}/ , backend/tests/, frontend/src/{pages,components,api}/, scripts/ (seed, benchmark).
# Security rules
- App DB role is NOT table owner; RLS on every institution-scoped table; per request: SET LOCAL app.scope_ids / app.role.
- apaar_enc/name_enc = AES-256-GCM (aad=record_id, key from local key file via KMS abstraction, key_version col). apaar_token = HMAC-SHA256 (separate key). apaar_last4 for masked display. No unsalted hashes.
- Logging filter redacts ids/names; never log request bodies of student endpoints.
- audit_events hash-chained: hash=SHA256(prev_hash||canonical_json(event)); app role has INSERT/SELECT only.
- Reveal: purpose + different supervisor approver + expiry + single-use + audited. Self-approval rejected.
# Working style (credit saving)
Write code, not prose. Final reply max 5 lines. No README/docs/extra comments. Don't re-read unchanged files.
Edit minimal files. Run tests once at end of task; if still failing after 2 fixes, STOP and report the failure.
All endpoints under /api/v1, error shape {"error":{"code","message","details"}}.
