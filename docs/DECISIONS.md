# Decisions (ADR-style log)

## D1 — Storage backend portability (SQLite default + PostGIS-ready)
MVP runs on SQLite with zero external services so demo/tests/CI work anywhere;
production uses PostGIS via `DATABASE_URL`. Spatial values are stored as
canonical GeoJSON (EPSG:4326) + scalar metrics on **both** backends so the same
models/tests run everywhere. PostGIS native geometry columns are documented for
production migrations (alembic scaffold). Cost: we do not rely on PostGIS 3D
operators inside engine code; topology/geometry runs in Python (Shapely) which
keeps behaviour identical across backends.

## D2 — Single-table inheritance for the vertical hierarchy
Buildings/floors/units/basements/parking/underground share footprint + z + status
+ provenance. One `properties` table with `parent_id` keeps hierarchy + topology
+ validation code simple. Separate concept tables can be introduced later
without a rewrite.

## D3 — Project-specific 3D ULPIN (not the national format)
We deliberately do not claim `IN3D-…` is the official ULPIN. The engine is
deterministic and checksummed; identity is stored apart from geometry/provenance/
approval. A future national format can be swapped behind the same functions.

## D4 — ML/LLM optional and assistive only
No multi-GB models downloaded at startup; heavy building extraction is opt-in.
Deterministic heuristics (heights, floors, anomalies) are the default and always
available offline. LLM (OpenRouter) only phrases answers over safe read tools.

## D5 — demo data synthetic + seeded cases
Bengaluru pilot is synthetic (`SyntheticDemoAdapter`), deterministic (seed
26011), clearly labelled, and includes the required PASS/CONFLICT/ERROR/AI
cases. No restricted datasets are redistributed; basemap tiles are fetched at
runtime from public OSM servers.

## D6 — Validation states map to demo workflow
`ERROR`/`CONFLICT` results are displayed but the demo intentionally contains
seeded conflicts so the review workflow can be demonstrated. Approved records
remain under human control.

## D7 — Manual schema bootstrap for MVP
`scripts/seed.py` uses SQLAlchemy `create_all`; Alembic is scaffolded and is the
recommended path for PostGIS production. This keeps the demo runnable without a
migration server while staying honest that migrations are the production norm.

## D8 — Areas in m² via local tangential projection
Footprints are stored in degrees (EPSG:4326); areas are computed with a local
scale (R·cos φ) around the centroid which is accurate for small parcels and
deterministic. PostGIS deployments can recompute with a UTM projection.
