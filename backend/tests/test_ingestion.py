"""Ingestion + CRS tests: GeoJSON, JSONL, CityJSON, CRS rules."""
from __future__ import annotations

import json

import pytest

from app.engines import crs as crs_engine
from app.ingestion.models import FormatError, UnsupportedFormatError
from app.ingestion.parsers import parse_bytes

FP = [
    [77.6400, 12.9100],
    [77.6403, 12.9100],
    [77.6403, 12.9103],
    [77.6400, 12.9103],
    [77.6400, 12.9100],
]


def _geojson(n=3):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": f"P{i}", "type": "parcel"},
                "geometry": {"type": "Polygon", "coordinates": [FP]},
            }
            for i in range(n)
        ],
    }


def _jsonl_building_floor():
    lines = [
        json.dumps({"type": "building", "id": "B1", "footprint": FP, "zmin": 0, "zmax": 12}),
        json.dumps({"type": "floor", "id": "B1-F1", "building_id": "B1", "footprint": FP, "zmin": 0, "zmax": 3}),
    ]
    return ("\n".join(lines)).encode()


def _cityjson():
    return json.dumps({
        "type": "CityJSON", "version": "2.0",
        "metadata": {"epsg": 4326},
        "vertices": [[77.64, 12.91, 0], [77.641, 12.91, 0], [77.641, 12.911, 0], [77.64, 12.911, 0]],
        "CityObjects": {
            "BLD1": {"type": "Building", "attributes": {"measuredHeight": 12},
                     "geometry": [{"type": "Solid", "boundaries": [[[[0, 1, 2, 3, 0]]]]}]}
        },
    }).encode()


# ---- 9. GeoJSON import ----
def test_geojson_import():
    res = parse_bytes("parcels.geojson", json.dumps(_geojson()).encode())
    assert res.format_name == "geojson"
    assert res.record_count == 3
    assert res.crs_epsg == 4326


# ---- 10. JSONL import ----
def test_jsonl_import():
    res = parse_bytes("props.jsonl", _jsonl_building_floor())
    assert res.format_name == "jsonl"
    assert res.record_count == 2
    kinds = [r.kind for r in res.records]
    assert kinds == ["building", "floor"]
    assert res.records[1].parent_ref == "B1"


# ---- 11. CityJSON import ----
def test_cityjson_import():
    res = parse_bytes("demo.city.json", _cityjson())
    assert res.format_name == "cityjson"
    assert res.record_count == 1
    rec = res.records[0]
    assert rec.kind == "building"
    assert rec.external_id == "BLD1"
    assert rec.footprint["type"] == "Polygon"
    assert len(rec.footprint["coordinates"][0]) == 5


# ---- 12. CRS validation ----
def test_crs_resolution_rules():
    # explicit EPSG declared
    ctx = crs_engine.resolve_crs(declared="EPSG:32643")
    assert ctx.epsg == 32643
    # geojson -> 4326
    assert crs_engine.resolve_crs(geojson=True).epsg == 4326
    # geographic-looking bbox
    assert crs_engine.resolve_crs(bbox_geographic=True).epsg == 4326
    # ambiguous -> CrsRequiredError (never silently guess)
    with pytest.raises(crs_engine.CrsRequiredError):
        crs_engine.resolve_crs()


def test_unsupported_format_graceful():
    with pytest.raises(UnsupportedFormatError):
        parse_bytes("file.las", b"LASF")
    with pytest.raises(FormatError):
        parse_bytes("file.txt", b"hello")
