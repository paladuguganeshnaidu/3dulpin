# Deployment

## Local (no Docker)

```bash
# 1) backend
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python scripts/seed.py
uvicorn app.main:app --reload --port 8000

# 2) frontend (new terminal)
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxies /api -> :8000)
```

Demo login: `admin@demo.local` / `Admin@12345` (see README table).

## Docker (PostGIS)

```bash
docker compose up --build
```

`db` (postgis) + `api` + `web` (nginx SPA). Frontend proxies `/api` → `api:8000`.

## Render (recommended hosted demo)

The repository includes `render.yaml` for an API service, PostgreSQL database,
and static frontend. In Render:

1. Open **New → Blueprint**, connect the GitHub repository, and apply the
  blueprint. Render creates `3dulpin-api`, `3dulpin-web`, and `3dulpin-db`.
2. The Blueprint automatically wires the Render API hostname into
  `VITE_API_HOST` and the frontend hostname into `CORS_ORIGIN_HOST`.
3. If your Render workspace does not resolve Blueprint service references,
  set these manually: API `CORS_ORIGINS=https://YOUR-WEB.onrender.com` and
  frontend `VITE_API_BASE=https://YOUR-API.onrender.com/api/v1`, then redeploy
  the web service. Vite variables are embedded during the build.
4. Check `https://3dulpin-api.onrender.com/health` and
  `/health/db`. The API creates its schema and, because the Blueprint sets
  `SEED_DEMO_DATA=true`, seeds the synthetic Bengaluru demo dataset on its
  first startup.
5. Open the frontend URL and use the development-only demo credentials from
  the README. Change or disable demo seeding before using real data.

### Free-only deployment

The Blueprint sets the API and Postgres database to the `free` plans; the
static frontend is free by default. No credit card should be needed where
Render free resources are available for your account. Free web services sleep
when idle, so the first request after inactivity can take a little longer.
Free Postgres availability, storage, expiry, and account limits are controlled
by Render and can change; check the plan shown before confirming deployment.
For a longer-lived zero-cost demo, use a free external Postgres provider such
as Supabase or Neon and put its connection string in the API's `DATABASE_URL`.

Render free services may sleep when idle. The PostgreSQL service must be
available while the API starts. The application uses SQLAlchemy text/metrics
storage and therefore works with Render PostgreSQL; native PostGIS columns can
be added later using the Alembic scaffold.
The app automatically converts Render's `postgresql://...` connection string
to the installed `postgresql+psycopg://...` SQLAlchemy dialect.

## Production

- **Frontend on Vercel**: import this GitHub repository, set the Vercel project
  Root Directory to `frontend`, Framework Preset to `Vite`, Build Command to
  `npm run build`, and Output Directory to `dist`. Set `VITE_API_BASE` to the
  deployed backend URL plus `/api/v1`, for example
  `https://your-api.onrender.com/api/v1`. `frontend/vercel.json` handles SPA
  rewrites so direct visits to `/map` and `/property/:id` work.
- **Backend**: Vercel is not the current backend target. Run FastAPI on
  Render/Railway/Fly.io or a VM using `uvicorn app.main:app --host 0.0.0.0
  --port $PORT`, and use a managed PostgreSQL + PostGIS database. Set its
  `DATABASE_URL`, `JWT_SECRET_KEY`, `APP_ENV=production`, and
  `CORS_ORIGINS=https://your-frontend.vercel.app`.
- **Frontend elsewhere**: `npm run build` → static `frontend/dist`; deploy to
  Netlify or any static host; set `VITE_API_BASE` to the backend origin during build.
- **Database schema**: MVP uses `create_all` (via `scripts/seed.py`). For a
  PostGIS deployment, prefer migrations:
  ```bash
  cd backend
  alembic revision --autogenerate -m "initial schema"
  alembic upgrade head
  ```
- **CORS**: set `CORS_ORIGINS` to the real frontend origin.
- **Secrets**: set `JWT_SECRET_KEY`, `OPENROUTER_API_KEY` (optional) in the host
  environment, never in the repo.

## Health

- `GET /health` → `{status, version, name}`
- `GET /health/db` → `{status, database, detail}`

## Env vars

Full table in `.env.example` / README §8. Minimum for production:
`DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `APP_ENV=production`.
