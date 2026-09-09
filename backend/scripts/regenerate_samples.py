"""Regenerate the deterministic sample import files under data/samples/.

Run from backend/:
    ..\\.venv\\Scripts\\python.exe scripts/regenerate_samples.py

Writes:
  sample.parcels.geojson      - FeatureCollection of demo parcels
  sample.properties.json      - normalized collection of a building/floor/unit
  sample.properties.jsonl     - one spatial record per line (import demo)
  sample.city.json            - a minimal valid CityJSON building
  demo_dataset.json           - full deterministic pilot dataset (compact)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SAMPLES = BACKEND_DIR / "data" / "samples"


def _ring(lon, lat, w=30, h=26):
    import math

    dlat = h / 2.0 / 111320.0
    dlon = w / 2.0 / (111320.0 * math.cos(math.radians(lat)))
    return [
        [round(lon - dlon, 7), round(lat - dlat, 7)],
        [round(lon + dlon, 7), round(lat - dlat, 7)],
        [round(lon + dlon, 7), round(lat + dlat, 7)],
        [round(lon - dlon, 7), round(lat + dlat, 7)],
        [round(lon - dlon, 7), round(lat - dlat, 7)],
    ]


def generate_all() -> dict[str, Path]:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # --- demo_dataset.json (full deterministic pilot dataset) ---
    from app.engines import demo_data

    ds = demo_data.generate_demo_dataset(rows=6, cols=10)
    p = SAMPLES / "demo_dataset.json"
    p.write_text(json.dumps(ds, default=str, indent=1), encoding="utf-8")
    paths["demo_dataset"] = p

    # --- sample.parcels.geojson (first 5 parcels) ---
    feats = []
    for par in ds["parcels"][:5]:
        feats.append({
            "type": "Feature",
            "properties": {
                "id": par["parcel_id"], "type": "parcel",
                "state_code": "KA", "district_code": "BLR",
                "locality": "Bengaluru Pilot Zone (Synthetic)",
                "source_type": "synthetic_demo",
            },
            "geometry": {"type": "Polygon", "coordinates": [par["footprint"]]},
        })
    p = SAMPLES / "sample.parcels.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, indent=1), encoding="utf-8")
    paths["parcels_geojson"] = p

    # --- sample.properties.json (a building + 2 floors + unit on parcel P00001) ---
    par0 = ds["parcels"][0]
    fp = par0["footprint"]
    jsonl_props = {
        "type": "collection",
        "metadata": {"crs": "EPSG:4326", "notice": "Demonstration dataset — not an official land record."},
        "records": [
            {"type": "building", "id": "SB1", "parcel_id": par0["parcel_id"],
             "name": "Sample Building 1", "footprint": fp, "zmin": 0, "zmax": 9},
            {"type": "floor", "id": "SB1-F1", "building_id": "SB1", "footprint": fp, "zmin": 0, "zmax": 3},
            {"type": "floor", "id": "SB1-F2", "building_id": "SB1", "footprint": fp, "zmin": 3, "zmax": 6},
            {"type": "unit", "id": "SB1-F1-U1", "floor_id": "SB1-F1", "footprint": fp, "zmin": 0, "zmax": 3},
        ],
    }
    p = SAMPLES / "sample.properties.json"
    p.write_text(json.dumps(jsonl_props, indent=1), encoding="utf-8")
    paths["properties_json"] = p

    # --- sample.properties.jsonl ---
    lines = [json.dumps(r) for r in jsonl_props["records"]]
    p = SAMPLES / "sample.properties.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    paths["properties_jsonl"] = p

    # --- sample.city.json (valid minimal CityJSON) ---
    lon, lat = 77.6402, 12.9098
    fp2 = _ring(lon, lat, 22, 18)
    city = {
        "type": "CityJSON",
        "version": "2.0",
        "metadata": {"title": "Sample building (synthetic)", "epsg": 4326,
                     "notice": "Demonstration dataset — not an official land record."},
        "transform": None,
        "vertices": [
            [round(c[0], 7), round(c[1], 7), 0.0] for c in fp2[:-1]
        ],
        "CityObjects": {
            "SAMPLE-BLD-1": {
                "type": "Building",
                "attributes": {"measuredHeight": 12.0, "name": "Sample Building 1 (CityJSON)"},
                "geometry": [
                    {
                        "type": "Solid", "lod": "2.2",
                        "boundaries": [[[list(range(len(fp2) - 1)) + [0]]]],
                    }
                ],
            }
        },
    }
    p = SAMPLES / "sample.city.json"
    p.write_text(json.dumps(city, indent=1), encoding="utf-8")
    paths["cityjson"] = p

    return paths


if __name__ == "__main__":
    out = generate_all()
    for name, path in out.items():
        print(f"{name}: {path} ({path.stat().st_size} bytes)")
