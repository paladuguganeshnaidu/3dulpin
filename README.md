# India 3D ULPIN — AI-Assisted 3D Cadastre and Vertical Property Mapping

> Demonstration framework for **SIH 2026 · Problem 26011 · "3D ULPIN Generation and
> vertical Property Mapping System"**.

A full-stack GIS/3D web application that creates unique spatial identities for
**surface land parcels**, **multi-storey apartments** and **underground
infrastructure**, with assisted ML analysis and human-controlled approval.

> **Important disclaimers**
> - This is a **demonstration / prototype framework**, not an official land-record system.
> - **Synthetic data are not official land records** ("Demonstration dataset — not an official land record.").
> - **AI-derived geometries require human verification** and are never legal cadastral boundaries by default.
> - The project's **3D ULPIN extension is not the adopted national ULPIN format** (see `docs/ULPIN.md`).

---

## 1. Problem statement

Scalable, interoperable 3D cadastral framework producing unique spatial identities for:

- Surface land parcels
- Multi-storey apartments
- Underground infrastructure

integrating drone imagery, LiDAR/point clouds, GIS parcel layers, floor plans,
GNSS/CORS coordinates and DEM/DSM, with AI/ML for building extraction, floor
segmentation, vertical parcel delineation and topology validation.

**Core product principle** (never inverted):

```
GIS / database   = source of truth
ML               = assistive inference (marked AI-derived, needs verification)
LLM              = assistive search/explanation over safe backend tools
Human surveyor   = verification
Admin / authority= approval
```

The core GIS, 3D geometry, ingestion, ULPIN, topology, workflow and persistence
all work **independently of any LLM/ML service** (offline demo mode is default).

---

## 2. What is built (feature highlights)

- **India-wide map** (CesiumJS globe, OSM basemap) with India / Karnataka /
  Bengaluru / **Bengaluru Pilot Zone (Synthetic)** navigation and search.
- **Deterministic pilot dataset**: 60 parcels, 25 buildings, 114 floors, 216 units,
  basements, underground parking, water/sewer lines, utility tunnel and **seeded
  demonstration cases** (PASS / CONFLICT / ERROR / AI-pending).
- **3D volume engine** — `footprint + [zmin, zmax] → prism metrics`
  (area in m², volume, centroid, bbox; underground negative Z supported).
- **Deterministic 3D ULPIN engine** — stable, checksummed, project-specific
  identifiers with registry, validation and versioning.
- **Topology validation** — PASS / WARNING / CONFLICT / ERROR with exact
  diagnostics (conflicting ids, overlap extent/volume), visualized in Cesium.
- **Hierarchical properties** — Parcel → Building → Floor → Unit, plus Basement,
  Parking and Underground Assets; parent/child consistency checks.
- **Real ingestion** — JSON, JSONL, GeoJSON, CityJSON (format detection, schema
  classification, CRS handling, provenance, import preview → commit).
- **Role workflows** — Viewer (browse), Surveyor (create/verify/submit), Admin
  (approve/reject/return, audit, stats).
- **Assistive AI** — model registry, deterministic height/floor estimation and
  anomaly detection, AI building candidates labelled `AI-derived · requires
  verification`. Optional OpenRouter LLM assistant that **only answers from safe
  backend tools** (no arbitrary SQL/shell/filesystem, no auto-approval).
- **Versioning, audit log, property reports, health endpoints, error
  sanitization, structured logging.**

---

## 3. Architecture

```
┌─────────────────────────── Frontend (React+TS+Vite+Tailwind+Cesium) ───────────────┐
│  /map  /import  /surveyor  /admin  /login  /property/:id                          │
│  Cesium globe + layer panel + info panel + conflict view + AI Analyse modal       │
└───────────────┬────────────────────────────────────────────────────────────────────┘
                │  REST /api/v1 (JWT, role checks)
┌───────────────▼────────────────────────────────────────────────────────────────────┐
│ Backend (FastAPI + SQLAlchemy 2.x)                                                  │
│  auth · parcels · properties · buildings · ulpin · uploads · validation ·          │
│  ai · assistant · admin · audit · reports · health                                  │
│                                                                                     │
│  engines:  ulpin · geometry · topology · crs · demo_data                            │
│  ingestion: parsers (json/jsonl/geojson/cityjson) · provenance                      │
│  ml: registry · analysis (height/floors/anomaly) · optional external models         │
│  llm: OpenRouter assistant (optional) over safe tools                               │
└───────────────┬────────────────────────────────────────────────────────────────────┘
                │ SQLAlchemy
        ┌───────▼─────────┐     ┌───────────────────────────────┐
        │ SQLite (default)│     │ PostgreSQL + PostGIS (prod)   │
        │ demo / tests    │     │ via DATABASE_URL (documented) │
        └─────────────────┘     └───────────────────────────────┘
```

Full design rationale: `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`.

---

## 4. Tech stack

| Layer | Tech |
|---|---|
| Frontend | React 18, TypeScript, Vite 5, CesiumJS, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x |
| GIS/3D | Shapely, PostGIS (prod), GeoJSON (canonical EPSG:4326), CesiumJS |
| Auth | JWT (PyJWT) + PBKDF2 password hashing, role-based access |
| Data | SQLite (default, zero-config), PostgreSQL/PostGIS (managed/prod) |
| ML | Optional pretrained models (lazy-loaded); deterministic heuristics by default |
| LLM | Optional OpenRouter (tool-backed assistant) |
| Deploy | Docker / docker-compose, Vercel/static + Render/Railway ready |
| CI | GitHub Actions (backend pytest + frontend build) |

---

## 5. Repository layout

```
.github/workflows/ci.yml
backend/
  app/
    core/          config, logging, security, enums
    engines/       geometry, ulpin, topology, crs, demo_data
    ingestion/     parsers + models (json/jsonl/geojson/cityjson)
    ml/            registry + analysis (heuristics)
    db/            session + ORM models
    services/      catalog, seed, imports, validation, audit
    api/           routers (auth, geo, workflow, uploads, ai, misc) + schemas
    main.py        FastAPI app
  data/samples/    sample.parcels.geojson, sample.properties.json,
                   sample.properties.jsonl, sample.city.json, demo_dataset.json
  scripts/         seed.py, regenerate_samples.py
  tests/           pytest suite (20 tests)
  requirements.txt, Dockerfile, pyproject.toml
frontend/
  src/             React app (map, import, surveyor, admin, login, report)
  Dockerfile, nginx.conf, package.json, vite.config.ts, tailwind.config.js
docs/              ARCHITECTURE · DATA_MODEL · INGESTION · ULPIN · ML ·
                   DEPLOYMENT · SECURITY · DECISIONS
docker-compose.yml, .env.example, README.md, CHANGELOG.md
```

---

## 6. Local setup

Requirements: **Python 3.11+** and **Node 20+**. Docker is optional (see §7).

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
source .venv/bin/activate            # macOS/Linux
pip install -r requirements.txt

# schema + demo users + demo data (SQLite default, no external DB needed)
python scripts/seed.py

# run API  ->  http://localhost:8000/docs
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # -> http://localhost:5173  (proxies /api to :8000)
```

### Demo accounts (DEVELOPMENT ONLY — never for production)

| Role | Email | Password |
|---|---|---|
| Admin | `admin@demo.local` | `Admin@12345` |
| Surveyor | `surveyor@demo.local` | `Survey@12345` |
| Viewer | `viewer@demo.local` | `Viewer@12345` |

---

## 7. Docker

```bash
docker compose up --build
# Frontend http://localhost:5173 · API http://localhost:8000/docs
# (spins up PostGIS db + api + web)
```

---

## 8. Environment variables

See `.env.example` (never commit real secrets):

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./data/3dulpin.db` |
| `JWT_SECRET_KEY` | JWT signing secret | change me |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | token lifetime | 1440 |
| `CORS_ORIGINS` | allowed browser origins | `http://localhost:5173,...` |
| `MAX_UPLOAD_MB` / `UPLOAD_DIR` | upload limits/storage | 50 / `./data/uploads` |
| `SEED_DEMO_DATA` / `SEED_DEMO_USERS` | auto-seed on startup | true |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | optional LLM assistant | empty (offline) |
| `ML_BUILDING_MODEL_ENABLED` | optional heavy building model | false |
| `VITE_API_BASE` | frontend API base URL | `/api/v1` |

---

## 9. Supported import formats

**Parsed and supported in the MVP:** JSON, JSONL, GeoJSON, CityJSON (Buildings,
Solid/MultiSurface geometry).
**Recognized but not enabled in the MVP** (clean error, no crash): GLB/glTF,
CityGML, LAS/LAZ, PLY, OBJ, KML/KMZ, SHP/ZIP, DEM/DSM, IFC.
Sample files are under `backend/data/samples/`.

---

## 10. AI/ML components

- `building_extraction` — optional pretrained model adapter (disabled by default;
  lazy-loaded, no multi-GB downloads at startup).
- `height_estimation` — deterministic (DSM/DEM difference or supplied metadata).
- `floor_segmentation` — explicit floors (surveyor) vs estimated levels.
- `anomaly_detection` — deterministic GIS rules.
- `assistant` — OpenRouter LLM (optional) that can only call safe read tools.
Everything AI is labelled and requires verification. See `docs/ML.md`.

---

## 11. 3D ULPIN conceptual model

Project-specific (NOT the national standard). Conceptually:

```
3D ULPIN = <base parcel identity> + <3D extension> + <stable sequence/type> + <version> + <checksum>
         = IN3D-<STATE>-<DISTRICT>-<PARCEL>-<KIND>-<SEQ>-V<VER>-<CHECK>
```

Deterministic for identical stable inputs; identity is stored separately from
geometry, ownership, provenance and approval state. See `docs/ULPIN.md`.

The spatial model is: **P3D = P2D × [zmin, zmax]** (project concept, documented in
`docs/DATA_MODEL.md`, not claimed as an official legal standard).

---

## 12. Database setup (PostGIS / production)

MVP runs on SQLite with zero external services. For a managed PostGIS deployment:

1. Create a Postgres database with the PostGIS extension.
2. Point `DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DBNAME`.
3. Run schema + seed:
   ```bash
   python scripts/seed.py            # create_all (works on PostGIS too)
   ```
4. Alembic is scaffolded (`alembic.ini` + `alembic/env.py`) — in a PostGIS
   deployment generate the initial revision with
   `alembic revision --autogenerate` from `app.db.models:Base`. See
   `docs/DEPLOYMENT.md` for the trade-off (MVP uses `create_all`).

---

## 13. Testing

```bash
cd backend
python -m pytest tests -q     # 20 tests
```

Covers: ULPIN determinism/uniqueness, valid volume creation, invalid Z rejection,
topology PASS/CONFLICT, parent-child validation, duplicate detection, GeoJSON /
JSONL / CityJSON import, CRS validation, role authorization, upload validation,
audit logging, plus an API demo smoke flow (parcels→building→floors→ULPIN→
validation→conflict→AI analyse→underground→persistence).

---

## 14. Security

PBKDF2 password hashing, JWT, role checks, input validation, file size/type
limits, safe upload storage, path traversal protection (sanitised filenames),
CORS, structured error responses (no raw stack traces in production), parameterized
SQL (SQLAlchemy), audit log, `JWT_SECRET_KEY` from env. **No real keys in the repo.**
See `docs/SECURITY.md`.

---

## 15. Deployment

- **Frontend on Vercel**: import the repo, set Root Directory to `frontend`,
  Framework Preset to `Vite`, Build Command to `npm run build`, Output Directory
  to `dist`, and add `VITE_API_BASE=https://YOUR-BACKEND/api/v1`. SPA rewrites
  are included in `frontend/vercel.json`.
- **Backend**: run `uvicorn app.main:app --host 0.0.0.0 --port $PORT` on
  Render/Railway/Fly.io, or deploy the `backend/` Docker image. Add managed
  PostgreSQL + PostGIS and set `CORS_ORIGINS` to the Vercel URL.
- **Render Blueprint**: use `render.yaml` with **New → Blueprint** to create
  the API, PostgreSQL database, and static frontend together. Set the generated
  API URL in frontend `VITE_API_BASE`, then set the generated frontend URL in
  API `CORS_ORIGINS` and redeploy.
- **Free-only**: `render.yaml` explicitly sets the API and database to `free`;
  the static site is free by default. Render may limit or change free Postgres
  availability, so verify the plan before confirming. Free web services sleep
  when idle.
- **Frontend elsewhere**: `npm run build` → static `dist/` (Netlify/nginx/Docker).

---

## 16. SIH demo flow (works end-to-end)

1. Open app → India globe. 2. Fly to Karnataka → Bengaluru → **Pilot zone**.
3. Parcels + 3D buildings load. 4. Select a building → view floors → **Explode floors**.
5. Select an apartment → show 3D ULPIN + zmin/zmax. 6. Run topology validation → PASS.
7. Select a conflicting property → 3D conflict shown. 8. Open **Underground** layer →
   basement/utility shown. 9. Open **Import** → upload `sample.properties.jsonl` →
   parse/process → new geometry appears on the map. 10. **AI Analyse** → AI candidate +
   confidence + verification status. 11. Surveyor verifies → submits → Admin approves →
   audit entry appears. 12. Refresh → all data persists.

---

## 17. Limitations (honest)

- Synthetic/demo data only; no official cadastral dataset is included or claimed.
- MVP stores footprints as canonical GeoJSON (EPSG:4326) + scalar metrics; PostGIS
  geometry columns/migrations are documented for production (see `docs/DATA_MODEL.md`).
- CityJSON support covers Building/BuildingPart with Solid/MultiSurface geometry.
- Heavy pretrained building-extraction models are **optional** and not downloaded
  by default; ML output is always assistive.
- The LLM assistant is optional; without `OPENROUTER_API_KEY` it answers from tools
  directly (offline mode).
- Not "fully accurate" in a legal sense — geometry/topology are **validated against
  automated tests** (ULPIN determinism, volume math, topology cases), not against
  on-ground surveys.

---

## 18. Data provenance & licensing

Every object records `source_type` (`official_reference`, `open_data`,
`survey_uploaded`, `imported_3d`, `ai_derived`, `synthetic_demo`), source name/file,
AI model + confidence when applicable, verification state. OSM basemap tiles are
fetched at runtime from public tile servers (subject to their usage policy); all
committed demo data is synthetically generated by this project. No restricted
government datasets are redistributed.

---

**Docs:** `docs/ARCHITECTURE.md` · `docs/DATA_MODEL.md` · `docs/INGESTION.md` ·
`docs/ULPIN.md` · `docs/ML.md` · `docs/DEPLOYMENT.md` · `docs/SECURITY.md` ·
`docs/DECISIONS.md` · `CHANGELOG.md`
