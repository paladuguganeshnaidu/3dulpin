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

- **Frontend**: `npm run build` → static `frontend/dist`; deploy to Vercel/
  Netlify/any static host; set `VITE_API_BASE` to the backend origin during build.
- **Backend**: `uvicorn app.main:app` behind a TLS proxy, or `docker build` the
  `backend/` image. Render/Railway supported. Add PostGIS as a managed DB and
  set `DATABASE_URL`.
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
