# Architecture

## Layers

1. **Frontend** — React + TypeScript + Vite + Tailwind + CesiumJS.
   - Routes: `/map`, `/import`, `/surveyor`, `/admin`, `/login`, `/property/:id`.
   - Single Cesium globe is the primary surface; layer panel, info panel,
     conflict drawer, AI Analyse modal, import wizard.
2. **API** — FastAPI under `/api/v1`. Routers: auth, geo (parcels/properties/
   buildings/search/ulpin/reports), workflow (validation + surveyor + admin),
   uploads, ai (analyse + assistant), misc (health). JWT + role guards.
3. **Engines** (pure functions, DB-agnostic, fully unit-tested):
   - `geometry`: footprint validation, `footprint+[zmin,zmax]` metrics, underground.
   - `ulpin`: deterministic identifier generation/validation/lookup/versioning.
   - `topology`: PASS/WARNING/CONFLICT/ERROR checks with diagnostics.
   - `crs`: EPSG resolution (never silently guesses).
   - `demo_data`: deterministic seeded pilot dataset.
4. **Ingestion** — format detection → parsers (JSON/JSONL/GeoJSON/CityJSON) →
   normalized records with provenance → import service → catalog.
5. **Persistence** — SQLAlchemy 2.x ORM; SQLite for demo/tests, PostGIS for
   production via `DATABASE_URL`. Footprints are canonical GeoJSON EPSG:4326 +
   scalar metrics so both backends share one model.

## Data flow (import)

```
upload bytes
  → detect format (extension + head sniffing)
  → parse → normalized ImportedRecords (+ CRS context + warnings)
  → preview (nothing committed)
  → commit: parcels → properties (resolve parents) → ULPINs → geometry v1
  → run topology validation (persisted)
  → audit log entry
```

## ML/LLM placement

ML and LLM are optional adapters behind the same API. They never write
authoritative records directly; `ai_derived` candidates start
`pending_verification` and require a surveyor `verify` and admin `submit/approve`.

## Failure behaviour

- No blank pages: frontend shows structured messages; backend returns
  `{ "detail": <human message> }`.
- Degradation: no OpenRouter → assistant answers from tools; no ML model →
  deterministic heuristics; unsupported format → clean "recognized but not
  enabled" message.
