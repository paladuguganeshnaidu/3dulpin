# India 3D ULPIN (3dulpin)

## Project overview
India 3D ULPIN is a full-stack demonstration platform for 3D cadastral and vertical property mapping. It combines a React + Cesium frontend with a FastAPI backend, deterministic geometry/ULPIN/topology engines, and optional AI/LLM assistive features.

> **Important**
> - This repository is explicitly a **demo/prototype** and not an official land-record system.
> - Synthetic demo data is included; no official cadastral dataset is redistributed.
> - AI-derived outputs require human verification.

## Executive summary
The system models parcel and vertical-property data (building/floor/unit and underground assets), supports multi-format ingestion, validates geometry/topology, and runs a surveyor→admin workflow with auditability. It is designed to run locally with SQLite by default and can be deployed with PostgreSQL/PostGIS.

## Problem statement
Enable interoperable 3D property identity and mapping workflows for surface, vertical, and underground spatial entities while keeping human approval in control.

## Background and motivation
The repository aligns with a demo context for SIH 2026 Problem 26011 and focuses on showing an end-to-end implementation architecture (import, modeling, validation, workflow, reporting) rather than legal cadastral production.

## Proposed solution
- FastAPI API (`/api/v1`) with JWT auth and role guards.
- SQLAlchemy data model for parcels, hierarchical properties, validation, uploads, submissions, ownership, ULPIN registry, and audit logs.
- Deterministic engines for geometry metrics, ULPIN generation/validation, CRS handling, and topology checks.
- React + Cesium web UI for map and workflow operations.
- Optional ML analysis and optional OpenRouter-backed assistant through constrained backend tools.

## Objectives
- Demonstrate 3D cadastre workflows with reproducible local setup.
- Keep GIS/database state authoritative and AI assistive.
- Provide import, validation, and approval paths with traceability.

## Scope
### In scope
- Demo map and property workflows
- Upload preview/commit for JSON, JSONL, GeoJSON, CityJSON
- 3D ULPIN generation/validation APIs
- Surveyor/admin workflow, audit logs, and health endpoints
- Local Docker and non-Docker development

### Out of scope
- Official/legal cadastral operations
- Automatic legal approval by AI/LLM
- Production-grade SLAs documented in this repo

### Future scope
- Native PostGIS geometry migrations as documented by Alembic scaffolding
- Potential expansion of import format handling currently recognized but not enabled

## Target users
- Surveyors (data creation/verification/submission)
- Admin/authority reviewers (review/approve/reject)
- Viewers/stakeholders (read access to map/property data)

## Real-world use cases
- Demonstrating vertical parcel modeling and conflict checks
- Demonstrating ingestion pipelines from common geospatial/JSON formats
- Demonstrating controlled AI-assisted geometry analysis pending human validation

## Key features
- Cesium-based map experience with authenticated routes
- Hierarchical property modeling (parcel → building → floor → unit, plus basement/parking/underground)
- Deterministic 3D ULPIN generation and validation
- Topology validation with persisted conflict states
- Upload preview/commit workflow with provenance tracking
- Surveyor/admin submission and review workflow
- Optional AI analysis and optional assistant endpoint

## Functional requirements (implemented)
- User registration/login and current-user retrieval
- Region/parcels/properties/buildings/search/reports APIs
- ULPIN generate/validate/lookup APIs
- Validation run/latest/conflicts APIs
- Workflow endpoints for verify/submit/review and ownership operations
- Upload preview/commit endpoints
- AI model listing/analyse/assistant query endpoints

## Non-functional requirements (implemented/documented)
- Deterministic core engine behavior
- Structured error responses
- Environment-driven configuration
- Cross-backend portability (SQLite default, PostgreSQL/PostGIS deploy path)

## Roles and permissions
- `viewer`: browse data
- `surveyor`: create/verify/submit
- `admin`: review/approve/manage/audit

## Workflow
1. Authenticate.
2. Browse parcels/properties or import data.
3. Run validation and inspect conflicts.
4. Surveyor verifies/submits.
5. Admin reviews and finalizes status.
6. Audit and reporting endpoints capture actions.

## Technology stack
### Frontend
- React 18, TypeScript, Vite 5, Tailwind CSS, CesiumJS

### Backend
- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x

### Database
- SQLite default (local/demo/tests)
- PostgreSQL/PostGIS path for deployment

### APIs
- REST endpoints under `/api/v1` plus `/health`, `/health/db`, `/info`

### Authentication
- JWT (HS256), password hashing (PBKDF2-HMAC-SHA256)

### Cloud/Infrastructure
- Docker Compose stack
- Render Blueprint (`render.yaml`)
- Vercel static frontend config (`frontend/vercel.json`)

### DevOps/CI
- GitHub Actions workflow: backend pytest + frontend build

### Testing tools
- `pytest` (backend)
- TypeScript + Vite build checks (frontend)

## Architecture
Layered architecture:
- Frontend UI/routes
- FastAPI routers (auth/geo/workflow/uploads/ai/misc)
- Engines (geometry, topology, ulpin, crs, demo data)
- Ingestion parsers/services
- SQLAlchemy persistence

For deeper design details: `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`.

## Application and data flow
High-level ingest flow: upload → format detection/parsing → preview → commit → topology validation → audit log.

## Project structure
```text
.github/workflows/ci.yml
backend/   # API, engines, ingestion, ORM, tests, scripts
frontend/  # React/Cesium app
docs/      # architecture, data model, security, deployment, etc.
docker-compose.yml
render.yaml
```

## Database documentation
Core ORM entities include:
`users`, `parcels`, `properties`, `ulpin_records`, `geometry_versions`, `validation_results`, `submissions`, `uploads`, `ai_predictions`, `audit_logs`, `ownership_records`.

Details: `backend/app/db/models.py`, `docs/DATA_MODEL.md`.

## API documentation
- Interactive Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`
- Route definitions: `backend/app/api/`

## Authentication and security
- JWT auth, role-based authorization, PBKDF2 password hashing
- CORS allow-list from env
- Upload size/type checks and sanitized filenames
- Structured error handling to avoid leaking internals in production

Details: `docs/SECURITY.md`.

## Installation and setup
### Prerequisites
- Python 3.11+
- Node.js 20+

### Clone
```bash
git clone https://github.com/paladuguganeshnaidu/3dulpin.git
cd 3dulpin
```

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\\.venv\\Scripts\\activate
pip install -r requirements.txt
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker compose up --build
```

## Environment variables
Use `.env.example` as the template. Key variables include:
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`
- `MAX_UPLOAD_MB`, `UPLOAD_DIR`
- `SEED_DEMO_DATA`, `SEED_DEMO_USERS`
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`
- `ML_BUILDING_MODEL_ENABLED`
- `VITE_API_BASE`

## Local development
- Backend defaults to SQLite and can seed demo data.
- Frontend talks to backend via configured API base.

## Running and deployment
- Local non-Docker and Docker instructions above.
- Hosted deployment guidance: `docs/DEPLOYMENT.md` and `render.yaml`.

## User guide (evidence-based)
1. Login (`/login`) using seeded demo users (if seeding enabled).
2. Open map (`/map`) and inspect parcels/properties.
3. Use import page (`/import`) for preview/commit data ingestion.
4. Use surveyor/admin pages for verification/review workflows.

## Screenshots / demo assets
No repository screenshots are currently stored in this repo. A community demo HTML/data asset exists under `frontend/public/community-demo/`.

## Testing strategy and observed results
Repository-defined CI checks:
- Backend: `python -m pytest tests -q`
- Frontend: `npm run build`

Additional frontend script present:
- `npm run lint`

### Validation executed in this update (2026-09-26)
- ✅ `backend`: `python -m pytest tests -q` → **32 passed**, 1 deprecation warning.
- ✅ `frontend`: `npm run build` → successful production build.
- ⚠️ `frontend`: `npm run lint` → failed with `eslint: not found` (script exists but eslint package is not installed in current devDependencies).

## Performance
No benchmark or latency measurements are published in this repository.

## Limitations
- Demo/prototype scope; not a legal cadastral system
- Synthetic demo data
- Optional AI/LLM outputs are non-authoritative and require verification
- Some formats are recognized but intentionally not enabled in MVP import path

## Known issues
- Frontend lint script cannot run in current repository state because `eslint` is not installed.

## Troubleshooting
- If API cannot start, confirm Python dependencies are installed and `DATABASE_URL` is valid.
- If frontend cannot reach API, verify `VITE_API_BASE` and backend CORS settings.
- For Docker startup, ensure port availability for 5173/8000/5432.

## Logging and monitoring
- Structured backend logging is implemented (`backend/app/core/logging.py`).
- Health endpoints: `/health`, `/health/db`.
- No separate metrics/tracing stack is configured in this repository.

## CI/CD
GitHub Actions workflow (`.github/workflows/ci.yml`):
- Backend job installs requirements and runs pytest.
- Frontend job installs npm dependencies and runs build.

Recent workflow observation: latest PR CI run recorded `action_required` with no failed jobs reported by job-log query.

## Backup, privacy, compliance
- No formal backup/recovery policy or compliance certification is documented in this repository.
- Security and provenance boundaries are documented in `docs/SECURITY.md` and `docs/DATA_MODEL.md`.

## Dependencies and integrations
- Python deps: `backend/requirements.txt`
- Frontend deps: `frontend/package.json`
- Optional integrations: OpenRouter API, PostgreSQL/PostGIS, Render, Vercel

## Versioning and releases
- Current app version in code: `0.1.0`
- Changelog format present in `CHANGELOG.md`
- No formal release-tag policy documented in repository files

## Roadmap
- See phase-oriented entries in `CHANGELOG.md` and architecture/deployment docs for next-step direction.

## Contribution and development guidelines
No dedicated `CONTRIBUTING.md` is currently present.

Practical guidance from current repository:
- Keep changes aligned to backend/frontend split.
- Ensure backend tests and frontend build pass before PR merge.

## Branching / commit / PR guidance
No explicit branching convention document is present. CI runs on pushes to `main` and on pull requests.

## License
This project is licensed under the MIT License. See [LICENSE](./LICENSE).

## Authors and contributors
- Repository owner: [@paladuguganeshnaidu](https://github.com/paladuguganeshnaidu)
- Additional contributors are not formally listed in repository metadata files.

## Acknowledgements
- SIH 2026 problem context referenced in project docs.
- Open-source ecosystem used by FastAPI, React, Cesium, SQLAlchemy, and related tooling.

## References
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/INGESTION.md`
- `docs/ULPIN.md`
- `docs/ML.md`
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `.github/workflows/ci.yml`

## FAQ
**Q: Is this an official land-record system?**  
No. It is a demo/prototype framework.

**Q: Does it require cloud services to run locally?**  
No. Default local setup works with SQLite; optional services are available for deployment scenarios.

**Q: Are AI-generated geometries automatically accepted?**  
No. AI outputs are assistive and require human verification/approval.
