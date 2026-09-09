"""API integration tests: upload workflow, RBAC, audit, demo smoke."""
from __future__ import annotations

import json
import math

# ---- 13. role authorization ----
def test_role_authorization_viewer_cannot_upload(viewer_headers, client):
    r = client.post(
        "/api/v1/uploads/preview",
        headers=viewer_headers,
        files={"file": ("x.jsonl", b"{}\n", "application/json")},
    )
    assert r.status_code == 403


def test_role_authorization_anon_denied(client):
    assert client.get("/api/v1/parcels").status_code == 401


# ---- 14. upload validation ----
def test_upload_validation_bad_type(surveyor_headers, client):
    r = client.post(
        "/api/v1/uploads/preview",
        headers=surveyor_headers,
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 415


def test_upload_validation_recognized_but_unavailable(surveyor_headers, client):
    r = client.post(
        "/api/v1/uploads/preview",
        headers=surveyor_headers,
        files={"file": ("x.las", b"LASF", "application/octet-stream")},
    )
    assert r.status_code == 422
    assert "not enabled" in r.json()["detail"]


# ---- upload preview + commit (JSONL) ----
def test_upload_jsonl_preview_and_commit(client, surveyor_headers):
    parcels = client.get("/api/v1/parcels", headers=surveyor_headers).json()
    par = parcels["items"][0]
    lon, lat = par["centroid"]["lon"], par["centroid"]["lat"]
    dlat = 5.0 / 2 / 111320.0
    dlon = 6.0 / 2 / (111320.0 * math.cos(math.radians(lat)))

    def ring():
        return [[round(lon - dlon, 7), round(lat - dlat, 7)],
                [round(lon + dlon, 7), round(lat - dlat, 7)],
                [round(lon + dlon, 7), round(lat + dlat, 7)],
                [round(lon - dlon, 7), round(lat + dlat, 7)],
                [round(lon - dlon, 7), round(lat - dlat, 7)]]

    data = "\n".join([
        json.dumps({"type": "building", "id": "TESTB", "parcel_id": par["id"], "footprint": ring(), "zmin": 0, "zmax": 6}),
        json.dumps({"type": "floor", "id": "TESTF", "building_id": "TESTB", "footprint": ring(), "zmin": 0, "zmax": 3}),
        json.dumps({"type": "unit", "id": "TESTU", "floor_id": "TESTF", "footprint": ring(), "zmin": 0, "zmax": 3}),
    ]).encode()

    prev = client.post("/api/v1/uploads/preview", headers=surveyor_headers,
                       files={"file": ("test.jsonl", data, "application/json")})
    assert prev.status_code == 200
    body = prev.json()
    assert body["format"] == "jsonl"
    assert body["record_count"] == 3

    com = client.post(f"/api/v1/uploads/{body['token']}/commit", headers=surveyor_headers)
    assert com.status_code == 200
    counts = com.json()["counts"]
    assert counts["buildings"] == 1 and counts["floors"] == 1 and counts["units"] == 1

    # newly imported building reachable + has ULPIN
    got = client.get(f"/api/v1/properties/{com.json()['token']}:building:TESTB", headers=surveyor_headers)
    assert got.status_code == 200
    assert got.json()["ulpin"]


# ---- 15. audit logging ----
def test_audit_logging_on_login_and_actions(client, admin_headers):
    # admin login already recorded; verify at least one audit row exists
    aud = client.get("/api/v1/audit", headers=admin_headers)
    assert aud.status_code == 200
    assert aud.json()["total"] >= 1
    assert any(a["action"] == "login" for a in aud.json()["items"])


# ---- demo smoke via API ----
def test_demo_smoke_flow(client, admin_headers):
    h = admin_headers
    # pilot dataset present
    assert client.get("/api/v1/parcels", headers=h).json()["total"] >= 50
    buildings = client.get("/api/v1/buildings", headers=h).json()
    assert buildings["total"] >= 20

    # select a building -> floors -> ulpin
    b = buildings["items"][0]
    detail = client.get(f"/api/v1/properties/{b['id']}", headers=h).json()
    assert len(detail["children"]) > 0
    assert detail["ulpin"]
    lu = client.get(f"/api/v1/ulpin/{detail['ulpin']}", headers=h).json()
    assert lu["registered"] is True

    # conflicts exist (seeded CASE B)
    conflicts = client.get("/api/v1/validation/conflicts", headers=h).json()
    assert conflicts["total"] >= 1

    # AI analyse returns candidates with verification requirement
    ai = client.post("/api/v1/ai/analyse", headers=h, json={}).json()
    assert ai["summary"]["ai_candidates"] >= 1
    assert ai["ai_candidates"][0]["needs_verification"] is True

    # underground assets are present (SIH underground requirement)
    props = client.get("/api/v1/properties?property_type=underground_asset", headers=h).json()
    assert props["total"] >= 1

    # persistence: admin stats reflect stored counts
    stats = client.get("/api/v1/admin/stats", headers=h).json()
    assert stats["parcels"] >= 50 and stats["properties"] >= 300
