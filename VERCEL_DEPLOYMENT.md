# Deploy the Campus Platform to Vercel

This repository can deploy as **one Vercel project** while keeping `frontend/` and `backend/` as separate folders. Do not move or merge the source folders. The root `vercel.json` defines two Vercel Services and routes `/api/*` to FastAPI and all other app paths to the Vite frontend.

Vercel Services are currently documented as Beta. The project configuration follows Vercel's Services routing model.

## What is wired

- Frontend service root: `frontend/`, Vite build, output `dist/`.
- Backend service root: `backend/`, FastAPI entrypoint `app.main:app`.
- `/api/*`, `/health`, `/docs`, and `/openapi.json` route to the backend service.
- All other paths route to the frontend service; the Vite rewrite serves `index.html` for client-side routes.
- The frontend Axios client uses relative `/api` URLs, so browser API requests use the same Vercel domain. `CAMPUS_API_PROXY` is only for local Vite development.

## Deployment prerequisites

### 1. Push the repository

Commit and push the repository root containing `vercel.json`, `frontend/`, and `backend/` to GitHub, GitLab, or Bitbucket. Do not configure `frontend/` as the Vercel project root; the Services config must be read from the repository root.

### 2. Provision persistent PostgreSQL

Do **not** deploy with SQLite as the production database. Vercel Functions are ephemeral/serverless; a local SQLite file is not durable shared storage, and `backend/data/` is excluded by `.gitignore`.

Create a hosted PostgreSQL database (for example, Neon) and copy its connection URL. The backend has `psycopg[binary]` installed and normalizes `postgresql://` URLs for SQLAlchemy. Prefer a provider's pooled connection string when the provider recommends it for serverless workloads.

**Current data-transfer blocker:** the existing demo dataset is `backend/data/campus_demo.db`, and database files are ignored by Git. The project population scripts explicitly require the SQLite URL `sqlite:///./data/campus_demo.db`; they are not a PostgreSQL import/migration tool. A fresh hosted database will not contain the current demo accounts, timetable, or published versions. Do not assume deploying the source code transfers that data. Before a data-backed public demo, choose and validate a controlled SQLite-to-PostgreSQL migration/import process, including passwords, IDs, foreign keys, scenario versions, and provenance.

The default `backend/campus.db` is a different database and is not the intended competition demo store. Do not upload either SQLite file to Git or rely on it as Vercel persistent storage.

### 3. Generate production secrets

In a local backend virtual environment, generate non-default values with the project's key generator:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.seed.gen_keys
```

Use the generated values in Vercel Project Settings → Environment Variables. Never commit `backend/.env` or paste real secrets into source files.

Required variables:

- `DATABASE_URL`: hosted PostgreSQL connection string.
- `JWT_SECRET`: long, random secret; not `change-me`.
- `APP_ENCRYPTION_KEY`: valid Fernet key; not empty or `change-me`.

Recommended explicit variables:

- `DEMO_MODE=false` for a public deployment. Note that currently verified demo users/passwords remain demo-only and should not be exposed publicly.
- `CAMPUS_TZ=Asia/Kolkata`.
- `LLM_PROVIDER=none` unless an optional provider is deliberately configured.
- `SOLVER_TIME_LIMIT_SEC=8` unless a different limit is tested.

Set secrets for the Production environment and Preview environments as needed. Keep preview and production databases separate if previews can write data.

## Create the Vercel project

1. In Vercel, import the pushed Git repository.
2. Set **Root Directory** to the repository root (`.`). Do not select `frontend/` or `backend/` as the overall project root.
3. Let the committed `vercel.json` define the frontend and backend services and routes.
4. Add the production environment variables above.
5. Deploy a Preview first. Confirm the Preview uses the intended PostgreSQL database before exercising any write workflows.
6. After checking `/health`, `/docs`, frontend route navigation, login, and representative reads, promote/deploy to Production.

If Vercel's project settings ask for one framework/build command despite the service configuration, stop and review the Vercel Services setup rather than overriding the repository with one subfolder root. Services build independently from their configured roots.

## Local verification before deployment

From the repository root, run the frontend build:

```powershell
cd frontend
npm ci
npm run build
```

For local full-stack development, run the existing demo backend in one terminal:

```powershell
cd backend
$env:DATABASE_URL = "sqlite:///./data/campus_demo.db"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8766
```

Run the frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

The local frontend proxy targets `http://localhost:8766` by default. The local UI is normally at `http://localhost:5173`.

Run backend tests against an isolated in-memory database, never the demo or protected DB:

```powershell
cd backend
$env:DATABASE_URL = "sqlite://"
.\.venv\Scripts\python.exe -m pytest -q
```

## Important application constraints before going public

- `backend/app/main.py` runs `Base.metadata.create_all()` and additive schema migrations when the FastAPI service loads. Test startup and migrations against a disposable PostgreSQL database before Production.
- The app currently stores access tokens in browser `localStorage`; this proof of concept has no MFA or production session-hardening workflow.
- The default database configuration is `sqlite:///./campus.db`; always configure `DATABASE_URL` explicitly in Vercel.
- Current demo data includes demo credentials and incomplete/empty academic, food, event, attendance, and navigation datasets. Do not use demo accounts or claim unavailable campus data is populated.
- The current deployment route wiring does not solve database population, account security review, or operational readiness. Those must be completed and verified separately.

## Current status

The old Vercel configuration pointed to nonexistent `backend/main.py` and used legacy `builds` routing. The root config has been updated to Vercel Services with the actual FastAPI entrypoint and Vite frontend. The Vercel CLI is not installed in the current environment, and no Vercel account, hosted PostgreSQL instance, or production secrets are configured here, so an actual cloud deployment has not been run.

References: [Vercel Services](https://vercel.com/docs/services), [Services routing](https://vercel.com/docs/services/routing), [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi).
