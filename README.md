# India 3D ULPIN — AI-Assisted 3D Cadastre and Vertical Property Mapping

> Demonstration framework for SIH 2026 · Problem 26011.

A full-stack GIS/3D web application for demonstrating 3D spatial identities across surface parcels, multi-storey properties and underground assets, with ingestion, topology checks, role workflows and optional AI assistance.

> **Prototype disclaimer:** this is not an official land-record, land-title, survey or national ULPIN system. Synthetic/demo records are not official records. AI-derived geometry requires human verification.

## What is implemented

- CesiumJS India/Karnataka/Bengaluru/pilot-map workflow.
- Deterministic synthetic pilot dataset: 60 parcels, 25 buildings, 114 floors and 216 units, plus underground demo assets.
- 3D prism metrics from footprint + [zmin, zmax].
- Project-specific deterministic 3D ULPIN-style identifiers with validation/versioning.
- Topology validation with PASS / WARNING / CONFLICT / ERROR diagnostics.
- Parcel → Building → Floor → Unit hierarchy, plus basement, parking and underground assets.
- JSON, JSONL, GeoJSON and CityJSON ingestion with preview/provenance flow.
- Viewer, Surveyor and Admin workflows.
- Optional deterministic ML analysis and optional OpenRouter assistant.
- Audit logging, reporting, health endpoints and structured error handling.

## Architecture

```text
React + TypeScript + Vite + Tailwind + Cesium
                    |
                 REST /api/v1
                    |
          FastAPI + SQLAlchemy
                    |
        +-----------+-----------+
        |                       |
     SQLite              PostgreSQL/PostGIS
       demo                  production option
```

The GIS/database is treated as the source of truth. ML is assistive; the optional LLM is tool-backed and does not perform automatic approvals.

## Technology stack

| Area | Current implementation |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, CesiumJS |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x |
| GIS / 3D | Shapely, GeoJSON, CesiumJS, PostGIS production option |
| Auth | JWT, PBKDF2 hashing, role-based authorization |
| Data | SQLite by default; PostgreSQL/PostGIS documented for production |
| ML | Deterministic heuristics plus optional pretrained-model adapters |
| LLM | Optional OpenRouter assistant |
| Deployment | Docker / docker-compose; Vercel/static + Render/Railway-ready |
| CI | GitHub Actions backend/frontend checks |

## Local setup

Requirements: Python 3.11+ and Node 20+.

Backend:

```bash
cd backend
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install and seed:

```bash
pip install -r requirements.txt
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Frontend:

```bash
cd ../frontend
npm install
npm run dev
```

Default frontend: http://localhost:5173

## Development demo accounts

| Role | Email | Password |
|---|---|---|
| Admin | admin@demo.local | Admin@12345 |
| Surveyor | surveyor@demo.local | Survey@12345 |
| Viewer | viewer@demo.local | Viewer@12345 |

These credentials are for development/demo use only.

## Environment

The main settings are documented in .env.example, including DATABASE_URL, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ORIGINS, MAX_UPLOAD_MB, UPLOAD_DIR, SEED_DEMO_DATA, OPENROUTER_API_KEY, OPENROUTER_MODEL, ML_BUILDING_MODEL_ENABLED and VITE_API_BASE.

Never commit production secrets.

## Supported ingestion

Implemented MVP formats:

- JSON
- JSONL
- GeoJSON
- CityJSON

The repository also recognizes GLB/glTF, CityGML, LAS/LAZ, PLY, OBJ, KML/KMZ, SHP/ZIP, DEM/DSM and IFC, but these are not enabled as full MVP parsers.

## 3D ULPIN model

The project uses a project-specific deterministic identifier model rather than claiming a new national standard:

```text
IN3D-<STATE>-<DISTRICT>-<PARCEL>-<KIND>-<SEQ>-V<VER>-<CHECK>
```

The spatial concept is:

```text
P3D = P2D × [zmin, zmax]
```

This is an implementation concept for the prototype, not an official legal cadastral formula.

## Testing

The repository includes a pytest suite and an end-to-end API demo smoke flow covering ULPIN determinism/uniqueness, 3D volume validation, topology PASS/CONFLICT, parent-child validation, duplicate detection, supported data import, CRS validation, role authorization, upload validation, audit logging, and persistence/workflow checks.

Run:

```bash
cd backend
python -m pytest tests -q
```

The repository documents 20 tests in the current suite. Treat that as the current repository state, not a permanent count.

## Security

The implementation includes JWT authentication, PBKDF2 password hashing, role checks, input validation, upload limits, path-traversal protections, CORS controls, parameterized SQL through SQLAlchemy, structured errors and audit logging.

Production review remains necessary for secrets, identity-provider integration, infrastructure hardening and authoritative data handling.

## Deployment

### Docker

```bash
docker compose up --build
```

### Frontend

```bash
npm run build
```

The repository documents Vercel/static hosting for the frontend.

### Backend

Render/Railway/Fly.io or container deployment is documented. PostgreSQL/PostGIS is recommended for production.

## Data provenance

Objects carry provenance such as official_reference, open_data, survey_uploaded, imported_3d, ai_derived and synthetic_demo.

The default committed demonstration records are synthetic. OSM basemap data is fetched at runtime and remains subject to the relevant OSM/tile-provider terms.

## SIH demonstration flow

1. Open the India globe.
2. Navigate to Karnataka → Bengaluru → pilot zone.
3. Inspect parcels/buildings.
4. Open a building and inspect floors.
5. View a property's 3D identifier and vertical extent.
6. Run topology validation.
7. Inspect a seeded conflict case.
8. Open the underground layer.
9. Import a supported sample file.
10. Run optional AI analysis.
11. Surveyor verifies and submits.
12. Admin approves and an audit entry is recorded.

## Limitations

- Demo data are synthetic.
- The current MVP uses SQLite by default.
- Some heavy ML integrations are optional and lazy-loaded.
- The LLM is optional and not required for core GIS functionality.
- Geometry is tested computationally but is not survey-certified.
- No official cadastral or ownership determination is performed.

## License

No explicit open-source license file is currently declared for this repository.

Until a license is added by the copyright holder, the code should not be treated as MIT/Apache/public-domain software.

## References

Project documentation includes docs/ARCHITECTURE.md, docs/DATA_MODEL.md, docs/INGESTION.md, docs/ULPIN.md, docs/ML.md, docs/DEPLOYMENT.md, docs/SECURITY.md and docs/DECISIONS.md.

Repository: https://github.com/paladuguganeshnaidu/3dulpin
