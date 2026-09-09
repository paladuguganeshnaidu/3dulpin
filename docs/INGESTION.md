# Ingestion

## Supported in the MVP (really parsed)

| Format | What is extracted |
|---|---|
| JSON | normalized record collection (schema detection, classification) |
| JSONL | one spatial record per line (parcel/building/floor/unit/…) |
| GeoJSON | FeatureCollection/Feature Polygon/MultiPolygon footprints |
| CityJSON | Building/BuildingPart, Solid/MultiSurface, transform, metadata |

Recognized-but-disabled (clean error, no crash): GLB/glTF, CityGML, LAS/LAZ,
PLY, OBJ, KML/KMZ, SHP/ZIP, DEM/DSM, IFC.

## Pipeline

1. **Detect** file (extension + head sniffing).
2. **Validate** size/type.
3. **Determine CRS** — declared EPSG, else GeoJSON=4326, else geographic bbox
   heuristic; otherwise raises `Coordinate reference system required`
   (never silently guess).
4. **Parse** into normalized `ImportedRecord`s.
5. **Normalize** kinds (parcel/building/floor/unit/basement/parking/
   underground_asset/volume) and z-ranges.
6. **Preview** — nothing committed.
7. **Commit** — parcels first, then properties resolving parents by reference,
   ULPINs assigned, geometry v1 snapshotted, topology run and persisted.

## CRS handling

Canonical internal = EPSG:4326. Source CRS metadata is preserved. For
projected sources a future phase transforms via pyproj before storage; the
boundary already requires an explicit EPSG on ambiguous uploads.

## Sample files

`backend/data/samples/` — regenerate with
`python scripts/regenerate_samples.py`.
