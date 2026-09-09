# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — Initial MVP (SIH 2026 Problem 26011)

### Added (PHASE 0-1: Foundations)
- Repository audit, architecture, docs skeleton, Docker + Git scaffolding.
- Config (`app/core/config.py`), structured logging, security helpers (PBKDF2 password hashing, JWT).

### Added (PHASE 2-3: Map + schema)
- Deterministic synthetic Bengaluru pilot dataset generator.
- Cesium India-globe frontend with fly-to navigation (Karnataka / Bengaluru).

### Added (PHASE 4-6: Core engines)
- 3D volume/geometry engine (footprint + zmin/zmax -> prism, metrics, underground support).
- Deterministic project-specific 3D ULPIN engine.
- Topology validation engine (PASS / WARNING / CONFLICT / ERROR with diagnostics).

### Added (PHASE 7-8: Properties + ingestion)
- Hierarchical properties (parcel -> building -> floor -> unit; basement/parking/underground).
- Ingestion for JSON, JSONL, GeoJSON, CityJSON (+ format detection, CRS handling).

### Added (PHASE 9-14: Workflows + AI)
- Surveyor / admin / viewer roles, submissions & approvals.
- Assistive ML adapters (building extraction, height/floor estimation, anomaly detection) with graceful fallbacks.
- Optional OpenRouter LLM assistant backed by safe query tools.

### Added (PHASE 15-17: Reporting, hardening, deploy)
- Reports, geometry versioning, audit log.
- Tests, CI workflow, Docker compose, production build docs.
