"""Geo/catalog routes: regions, parcels, properties, search, ULPIN, reports."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.enums import PropertyStatus, PropertyType, Role, SourceType
from ..db.models import Parcel, Property, UlpinRecord
from ..db.session import get_db
from ..engines import ulpin as ulpin_engine
from ..services.catalog import (
    parcel_to_dict,
    property_to_dict,
)
from .deps import get_current_user, require_roles

router = APIRouter(tags=["geo"])

REGIONS = [
    {
        "id": "india",
        "name": "India",
        "kind": "country",
        "center": {"lon": 78.9629, "lat": 20.5937},
        "description": "National context (no detailed cadastre here).",
    },
    {
        "id": "karnataka",
        "name": "Karnataka",
        "kind": "state",
        "center": {"lon": 75.7139, "lat": 15.3173},
        "description": "State context.",
    },
    {
        "id": "bengaluru",
        "name": "Bengaluru",
        "kind": "city",
        "center": {"lon": 77.5946, "lat": 12.9716},
        "description": "City context.",
    },
    {
        "id": "pilot-bengaluru",
        "name": "Bengaluru Pilot Zone (Synthetic)",
        "kind": "pilot",
        "center": {"lon": 77.6402, "lat": 12.9098},
        "description": "Detailed 3D cadastral demo dataset — not an official land record.",
    },
    {
        "id": "nagarjuna-campus",
        "name": "Nagarjuna College Campus (Synthetic)",
        "kind": "pilot",
        "center": {"lon": 77.6285, "lat": 12.9218},
        "description": "Demo campus for right-click ML block mapping. Not an official land record.",
    },
]


@router.get("/regions")
def regions():
    return REGIONS


@router.get("/parcels")
def list_parcels(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    locality: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Parcel).where(Parcel.active.is_(True))
    if locality:
        stmt = stmt.where(Parcel.locality == locality)
    total = len(db.execute(stmt).scalars().all())
    rows = db.execute(stmt.order_by(Parcel.ref_id).limit(limit).offset(offset)).scalars().all()
    return {"items": [parcel_to_dict(p) for p in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/parcels/{ref_id}")
def get_parcel(ref_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.execute(select(Parcel).where(Parcel.ref_id == ref_id)).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, f"Parcel '{ref_id}' not found.")
    data = parcel_to_dict(p)
    props = db.execute(
        select(Property).where(Property.parcel_id == p.id, Property.active.is_(True))
    ).scalars().all()
    data["properties"] = [property_to_dict(x) for x in props]
    data["property_count"] = len(props)
    return data


@router.get("/properties")
def list_properties(
    parcel_id: str | None = None,
    property_type: str | None = None,
    status: str | None = None,
    limit: int = Query(200, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    stmt = select(Property).where(Property.active.is_(True))
    if parcel_id:
        parcel = db.execute(select(Parcel).where(Parcel.ref_id == parcel_id)).scalar_one_or_none()
        if parcel:
            stmt = stmt.where(Property.parcel_id == parcel.id)
    if property_type:
        stmt = stmt.where(Property.property_type == property_type)
    if status:
        stmt = stmt.where(Property.status == status)
    total = len(db.execute(stmt).scalars().all())
    rows = db.execute(stmt.order_by(Property.id).limit(limit).offset(offset)).scalars().all()
    return {"items": [property_to_dict(x) for x in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/properties/{ref_key}")
def get_property(ref_key: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.execute(select(Property).where(Property.ref_key == ref_key)).scalar_one_or_none()
    if p is None or not p.active:
        raise HTTPException(404, f"Property '{ref_key}' not found.")
    data = property_to_dict(p, include_children=True)
    children = db.execute(
        select(Property).where(Property.parent_id == p.id, Property.active.is_(True)).order_by(Property.id)
    ).scalars().all()
    data["children"] = [property_to_dict(c) for c in children]
    return data


@router.get("/properties/{ref_key}/children")
def get_children(
    ref_key: str,
    child_type: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    p = db.execute(select(Property).where(Property.ref_key == ref_key)).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, f"Property '{ref_key}' not found.")
    stmt = select(Property).where(Property.parent_id == p.id, Property.active.is_(True))
    if child_type:
        stmt = stmt.where(Property.property_type == child_type)
    rows = db.execute(stmt.order_by(Property.id)).scalars().all()
    return {"items": [property_to_dict(x) for x in rows], "total": len(rows)}


@router.get("/buildings")
def list_buildings(
    parcel_id: str | None = None,
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    stmt = select(Property).where(
        Property.property_type == PropertyType.BUILDING.value, Property.active.is_(True)
    )
    if parcel_id:
        parcel = db.execute(select(Parcel).where(Parcel.ref_id == parcel_id)).scalar_one_or_none()
        if parcel:
            stmt = stmt.where(Property.parcel_id == parcel.id)
    rows = db.execute(stmt.limit(limit)).scalars().all()
    return {"items": [property_to_dict(x) for x in rows], "total": len(rows)}


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    needle = f"%{q.strip()}%"
    results: list[dict[str, Any]] = []

    # ULPIN exact match
    ulpin_rows = db.execute(
        select(Property).where(Property.ulpin == q.strip().upper())
    ).scalars().all()
    for p in ulpin_rows:
        results.append({"kind": "property", "item": property_to_dict(p)})

    prop_rows = db.execute(
        select(Property).where(
            Property.active.is_(True),
            or_(Property.ref_key.like(needle), Property.name.like(needle)),
        ).limit(20)
    ).scalars().all()
    for p in prop_rows:
        results.append({"kind": "property", "item": property_to_dict(p)})

    par_rows = db.execute(
        select(Parcel).where(Parcel.active.is_(True), Parcel.ref_id.like(needle)).limit(20)
    ).scalars().all()
    for p in par_rows:
        results.append({"kind": "parcel", "item": parcel_to_dict(p)})

    return {"query": q, "results": results, "total": len(results)}


# ---------------------------------------------------------------------------
# 3D ULPIN API
# ---------------------------------------------------------------------------


@router.post("/ulpin/generate")
def generate_ulpin(payload: dict, db: Session = Depends(require_roles(Role.SURVEYOR, Role.ADMIN))):
    try:
        code = ulpin_engine.generate_3d_ulpin(
            str(payload.get("parcel_no", "P00001")),
            str(payload.get("kind", "volume")),
            int(payload.get("sequence", 0)),
            state_code=str(payload.get("state_code", "KA")),
            district_code=str(payload.get("district_code", "BLR")),
            version=int(payload.get("version", 1)),
        )
    except Exception as exc:
        raise HTTPException(422, str(exc))
    return {"ulpin": code, "valid": ulpin_engine.validate_3d_ulpin(code)}


@router.get("/ulpin/{ulpin}")
def lookup_ulpin(
    ulpin: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    value = ulpin.upper()
    rec = db.execute(select(UlpinRecord).where(UlpinRecord.ulpin == value)).scalar_one_or_none()
    if rec is None or not ulpin_engine.validate_3d_ulpin(value):
        raise HTTPException(404, f"3D ULPIN '{value}' not found.")
    prop = db.get(Property, rec.property_id) if rec.property_id else None
    payload = ulpin_engine.parse_3d_ulpin(value)
    payload["registered"] = True
    payload["state"] = rec.state
    payload["version"] = rec.version
    if prop:
        payload["property"] = property_to_dict(prop)
    return payload


@router.post("/ulpin/validate")
def validate_ulpin(payload: dict):
    value = str(payload.get("ulpin", ""))
    return {"ulpin": value, "valid": ulpin_engine.validate_3d_ulpin(value)}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@router.get("/reports/property/{ref_key}")
def property_report(ref_key: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from datetime import datetime, timezone

    p = db.execute(select(Property).where(Property.ref_key == ref_key)).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, f"Property '{ref_key}' not found.")
    return {
        "report": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "3D Property Report",
            "property": property_to_dict(p),
            "notice": "Demonstration dataset — not an official land record.",
            "fields": [
                "ulpin", "parcel_id", "property_type", "zmin", "zmax", "height_m",
                "area_m2", "volume_m3", "status", "source_type", "verified", "version",
            ],
        }
    }
