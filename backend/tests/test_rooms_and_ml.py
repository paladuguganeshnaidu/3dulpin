"""Tests for ML-assisted building placement, room division, and owners."""
from __future__ import annotations

import pytest

from app.ml.building import extract_building_footprint, regularize_footprint
from app.services.rooms import split_rect_into_bands

PARCEL_RING = [
    [77.6400, 12.9100],
    [77.6406, 12.9100],
    [77.6406, 12.9106],
    [77.6400, 12.9106],
    [77.6400, 12.9100],
]


# ---- ML building placement (deterministic path) ----
def test_regularize_footprint_returns_orthogonal_candidate():
    res = regularize_footprint(PARCEL_RING)
    assert res["method"] == "orthogonal_snap_regularization"
    assert res["requires_verification"] is True
    ring = res["footprint_geojson"]["coordinates"][0]
    assert len(ring) == 5  # 4 corners + closing point
    assert 0.0 < res["confidence"] <= 1.0


def test_extract_without_geometry_raises():
    with pytest.raises(ValueError):
        extract_building_footprint(image_bytes=None, points=None)


def test_regularize_insets_from_parcel_border():
    res = regularize_footprint(PARCEL_RING, inset_m=2.0)
    ring = res["footprint_geojson"]["coordinates"][0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    # in-set building must be strictly inside the parcel border
    assert min(xs) > 77.6400 and max(xs) < 77.6406
    assert min(ys) > 12.9100 and max(ys) < 12.9106


# ---- Room division (bands) ----
def test_split_rect_into_bands():
    bands = split_rect_into_bands({"type": "Polygon", "coordinates": [PARCEL_RING]}, 3)
    assert len(bands) == 3
    for b in bands:
        assert b["type"] == "Polygon"
        assert len(b["coordinates"][0]) == 5


# ---- API: AI building-footprint endpoint ----
def test_building_footprint_endpoint(client, surveyor_headers):
    r = client.post(
        "/api/v1/ai/building-footprint",
        headers=surveyor_headers,
        json={"points": PARCEL_RING},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["requires_verification"] is True
    assert body["footprint_geojson"]["type"] == "Polygon"


# ---- API: assisted property creation ----
def test_create_assisted_property(client, surveyor_headers):
    parcels = client.get("/api/v1/parcels", headers=surveyor_headers).json()
    par = parcels["items"][0]["id"]
    r = client.post(
        "/api/v1/workflow/properties",
        headers=surveyor_headers,
        json={
            "property_type": "building",
            "parcel_id": par,
            "name": "Assisted building",
            "footprint_points": PARCEL_RING,
            "zmin": 0,
            "zmax": 12,
            "assisted": True,
            "model_name": "ai-assist/building-placement",
            "model_version": "0.2.0",
            "confidence": 0.84,
        },
    )
    assert r.status_code == 201, r.text
    prop = r.json()["property"]
    assert prop["source_type"] == "ai_derived"
    assert prop["status"] == "pending_verification"
    assert prop["model_name"] is not None


def test_create_building_auto_generates_floors(client, surveyor_headers):
    parcels = client.get("/api/v1/parcels", headers=surveyor_headers).json()
    par = parcels["items"][0]["id"]
    r = client.post(
        "/api/v1/workflow/properties",
        headers=surveyor_headers,
        json={
            "property_type": "building",
            "parcel_id": par,
            "name": "Floored building",
            "footprint_points": PARCEL_RING,
            "floors": 3,
            "floor_height": 3,
        },
    )
    assert r.status_code == 201, r.text
    floors = r.json().get("floors_created", [])
    assert len(floors) == 3
    assert floors[0]["zmin"] == 0 and floors[0]["zmax"] == 3
    assert floors[1]["zmin"] == 3 and floors[2]["zmax"] == 9


def test_auto_place_building_from_parcel(client, surveyor_headers):
    """One-click ML block placement from a parcel."""
    parcels = client.get("/api/v1/parcels", headers=surveyor_headers).json()
    par = parcels["items"][0]["id"]
    r = client.post(
        "/api/v1/workflow/buildings/auto-place",
        headers=surveyor_headers,
        json={"parcel_id": par, "floors": 2, "floor_height": 3},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["candidate"]["method"] == "orthogonal_snap_regularization"
    assert body["building"]["source_type"] == "ai_derived"
    assert body["building"]["status"] == "pending_verification"
    assert len(body["floors_created"]) == 2
    # edge-fit: the block should share the parcel border exactly (inset_m=0)
    ring = body["candidate"]["footprint_geojson"]["coordinates"][0]
    assert len(ring) == 5


def test_auto_place_by_right_click_center(client, surveyor_headers):
    """Right-click ML block mapping creates a parcel when none is near."""
    r = client.post(
        "/api/v1/workflow/buildings/auto-place",
        headers=surveyor_headers,
        json={"center_lon": 77.93, "center_lat": 13.02, "floors": 2, "floor_height": 3},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["building"]["parcel_id"].startswith("P-ML-")
    assert len(body["floors_created"]) == 2
    # confirm the parcel now exists and carries the block
    assert client.get(f"/api/v1/parcels/{body['building']['parcel_id']}", headers=surveyor_headers).status_code == 200


# ---- API: divide floor into rooms + owners ----
def test_divide_floor_and_owner_crud(client, surveyor_headers):
    floors = client.get("/api/v1/properties?property_type=floor&limit=5", headers=surveyor_headers).json()
    assert floors["total"] >= 1
    floor = floors["items"][0]

    divide = client.post(
        f"/api/v1/workflow/properties/{floor['id']}/divide",
        headers=surveyor_headers,
        json={
            "rooms": [
                {"name": "101", "owner_name": "Ananya R", "share_pct": 100, "document_ref": "SALE-101"},
                {"name": "102", "owner_name": "Vikram S", "share_pct": 100},
            ]
        },
    )
    assert divide.status_code == 201, divide.text
    created = divide.json()["created"]
    assert len(created) == 2

    first_unit = created[0]["id"]
    owners = client.get(f"/api/v1/workflow/properties/{first_unit}/owners", headers=surveyor_headers).json()
    assert owners["total"] == 1
    assert owners["items"][0]["owner_name"] == "Ananya R"

    # update owner
    owner_id = owners["items"][0]["id"]
    upd = client.put(
        f"/api/v1/workflow/owners/{owner_id}",
        headers=surveyor_headers,
        json={"share_pct": 60.0, "verified": True},
    )
    assert upd.status_code == 200
    assert upd.json()["owner"]["share_pct"] == 60.0

    # delete owner
    dele = client.delete(f"/api/v1/workflow/owners/{owner_id}", headers=surveyor_headers)
    assert dele.status_code == 200
    assert client.get(f"/api/v1/workflow/properties/{first_unit}/owners", headers=surveyor_headers).json()["total"] == 0
