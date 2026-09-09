# Data model

## Conceptual 3D model

Volumetric property is modelled (project-specific, **not** an official legal
standard) as:

```
P3D = P2D × [zmin, zmax]
```

i.e. a 2D footprint extruded between zmin and zmax (metres). Underground
features use negative z ranges. Height = zmax − zmin; volume = area × height.

## Entities

- `users` (roles: admin / surveyor / viewer)
- `parcels` — 2D surface parcels (base spatial identity)
- `properties` — single-table hierarchy with self-referencing `parent_id`:
  building → floor → unit, plus basement, parking, underground_asset, volume.
- `ulpin_records` — registry of generated identities (separate from geometry
  and approval state, so identity never changes when geometry is corrected).
- `geometry_versions` — every geometry change snapshots the previous version.
- `validation_results` — persisted topology runs (scope, state, summary, issues).
- `submissions` — surveyor → admin workflow (submitted/approved/rejected/returned).
- `uploads`, `ai_predictions`, `ownership_records`, `audit_logs`.

## Provenance (on every parcel/property)

`source_type` ∈ {official_reference, open_data, survey_uploaded, imported_3d,
ai_derived, synthetic_demo}, plus source_name/source_file, AI model/version and
confidence when applicable, verified/verified_by/verification_time.

## Spatial storage

- Canonical CRS: **EPSG:4326** (lon/lat) for footprints (GeoJSON text).
- Scalar metrics: area_m2 (via local tangential projection), volume_m3,
  centroid, bbox — for fast filtering and cross-backend portability.
- PostGIS production note: the same tables work on PostGIS; native geometry
  columns can be added via migrations (alembic scaffold provided). SQLite keeps
  demo/tests zero-config.

## Why single `properties` table (STI)

The vertical hierarchy (building/floor/unit/basement/parking/underground) shares
the same shape — footprint + z-range + provenance + status. Single-table
inheritance keeps parent/child and topology checks simple and lets later phases
introduce sub-type tables without rewriting the core.
