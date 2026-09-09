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
