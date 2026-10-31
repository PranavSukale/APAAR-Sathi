# Deploy APAAR Sathi to Vercel (frontend + backend) with Neon Postgres

Two Vercel projects from one repo: the **backend** (serverless Python API, repo root) and the
**frontend** (Vite static build, `frontend/`). Postgres is hosted on **Neon** (Vercel does not host DBs).

> Serverless caveats (be aware for the demo): cold starts add latency; the audit-chain advisory lock
> only orders writes within a single invocation; the crypto key comes from an env var, not a file. All
> fine for a hackathon demo, not production hardening.

## 1. Create the database (Neon)

1. Create a free project at neon.tech → copy the connection string.
2. Make it psycopg-style: `postgresql+psycopg://USER:PASS@HOST/db?sslmode=require`.
   Use the **non-pooled** host for migrations and the pooled host for the app if you like; a single
   URL works for both here.

## 2. One-time: create schema, RLS, and seed (run locally, pointed at Neon)

Serverless can't run `create_all`/seed, so do it once from your machine:

```bash
# point the tooling at Neon (owner + app can be the SAME Neon role for the demo)
$env:DATABASE_OWNER_URL = "postgresql+psycopg://USER:PASS@HOST/db?sslmode=require"
$env:DATABASE_APP_URL   = "postgresql+psycopg://USER:PASS@HOST/db?sslmode=require"
$env:APP_DB_USER = "USER"; $env:APP_DB_PASSWORD = "PASS"

python -m backend.app.core.dbinit     # tables + RLS + app-role grants
python -m scripts.seed                # synthetic demo data (6 beats)
python -m scripts.benchmark --n 8000 --seed 7   # benchmark.json (commit it)
```

Note: on a single Neon role, RLS still works (FORCE ROW LEVEL SECURITY applies to the owner too), but
the owner can bypass grants — acceptable for a demo. For stronger isolation create a separate Neon role
for the app and set `DATABASE_APP_URL`/`APP_DB_USER`/`APP_DB_PASSWORD` to it.

## 3. Generate the crypto key for serverless

```bash
python -c "import json,base64,os;print(json.dumps({'active_version':1,'versions':{'1':{'data':base64.b64encode(os.urandom(32)).decode(),'token':base64.b64encode(os.urandom(32)).decode()}}}))"
```

IMPORTANT: use the SAME key JSON that encrypted the seeded rows. The simplest path: set
`APAAR_KEYS_JSON` locally to this value BEFORE running step 2's seed, then reuse it in Vercel. If the
Vercel key differs from the seed key, decrypt/reveal will fail.

## 4. Deploy the backend (Vercel project #1)

- Import the repo, **Root Directory = repo root** (leave as `/`).
- Framework preset: **Other**. Vercel picks up `vercel.json` + `api/index.py` + `requirements.txt`.
- Environment variables:
  - `DATABASE_OWNER_URL`, `DATABASE_APP_URL` = Neon URL(s)
  - `APP_DB_USER`, `APP_DB_PASSWORD`
  - `APAAR_KEYS_JSON` = the JSON from step 3 (the seed key)
  - `JWT_SECRET` = a long random string
  - `CORS_ORIGINS` = your frontend URL (fill in after step 5, then redeploy)
  - `SERVERLESS` = `1`
- Deploy → note the URL, e.g. `https://apaar-sathi-api.vercel.app`. Check `/health`.

## 5. Deploy the frontend (Vercel project #2)

- Import the SAME repo again, **Root Directory = `frontend`**.
- Framework preset: **Vite** (build `npm run build`, output `dist`).
- Environment variable: `VITE_API_BASE` = the backend URL from step 4.
- Deploy → note the URL, e.g. `https://apaar-sathi.vercel.app`.

## 6. Close the loop

- Set the backend's `CORS_ORIGINS` to the frontend URL → redeploy the backend.
- Open the frontend, log in with a demo user (`reviewer@aicte.syn` / `demo1234`), click through the 6 beats.

## Troubleshooting

- **401/CORS errors in browser:** `CORS_ORIGINS` must exactly match the frontend origin (scheme + host, no trailing slash). Redeploy backend after changing it.
- **Reveal returns a decrypt error:** `APAAR_KEYS_JSON` on Vercel differs from the key used to seed. Reseed with the Vercel key, or set the key first then seed.
- **Function size limit / build fails:** pandas+scipy are heavy. For the demo the API only needs them for import/benchmark paths; if you hit the 250MB limit, deploy the backend on Render instead and keep the frontend on Vercel.
- **Cold start timeout on first linkage call:** it recomputes candidates live; hit `/health` first to warm the function, or lower the seeded record count.
