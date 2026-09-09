"""Room division + ownership services.

Flexible addition of floors, rooms (units) and owners. Room division splits a
floor footprint into horizontal bands (rows); each band becomes a unit with its
own ownership record(s). Splits are deterministic and preserve provenance.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.enums import PropertyStatus, PropertyType, SourceType
from ..db.models import OwnershipRecord, Parcel, Property, User
from . import catalog
from .audit import audit


def split_rect_into_bands(footprint_geojson: dict, n: int) -> list[dict]:
    """Split a rectangular-ish footprint into `n` horizontal latitude bands.

    Returns a list of GeoJSON polygons, one per band, in top-to-bottom order.
    """
    coords = footprint_geojson.get("coordinates")
    if not coords or not coords[0] or len(coords[0]) < 4:
        raise ValueError("Footprint must be a closed polygon ring.")
    ring = coords[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    y0, y1 = min(ys), max(ys)
    x0, x1 = min(xs), max(xs)
    span = (y1 - y0) / n
    bands: list[dict] = []
    for i in range(n):
        ylo = y0 + i * span
        yhi = ylo + span
        bands.append(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [x0, ylo],
                        [x1, ylo],
                        [x1, yhi],
                        [x0, yhi],
                        [x0, ylo],
                    ]
                ],
            }
        )
    return bands


def divide_floor_into_rooms(
    session: Session,
    floor: Property,
    *,
    rooms: list[dict[str, Any]],
    actor: User | None = None,
) -> list[Property]:
    """Create `unit` children under a floor, one per room spec.

    Each room spec may include: name, owner_name, share_pct, document_ref.
    The floor footprint is split into bands; each unit inherits the floor's
    z-range and parcel, gets a deterministic ULPIN and (optionally) ownership.
    """
    if floor.property_type != PropertyType.FLOOR.value:
        raise ValueError("Room division is supported on floors only.")
    if not rooms:
        raise ValueError("Provide at least one room to divide the floor.")

    bands = split_rect_into_bands(json.loads(floor.footprint_geojson), len(rooms))
    created: list[Property] = []
    for band, spec in zip(bands, rooms):
        name = str(spec.get("name") or f"{floor.name} room {len(created) + 1}")
        seq = len(created) + 1
        ref_key = f"{floor.ref_key}-R{seq}"
        if catalog.find_property(session, ref_key):
            # avoid collisions on repeated division
            ref_key = f"{floor.ref_key}-R{seq}-{abs(hash(name)) % 1000}"
        unit = catalog.create_property(
            session,
            ref_key=ref_key,
            property_type=PropertyType.UNIT,
            footprint_data=band,
            zmin=floor.zmin,
            zmax=floor.zmax,
            parcel=floor.parcel,
            parent=floor,
            name=name,
            status=PropertyStatus.DRAFT,
            source_type=SourceType.SURVEY_UPLOADED,
            source_name=actor.email if actor else "surveyor",
            actor_id=actor.id if actor else None,
        )
        if spec.get("owner_name"):
            add_owner(
                session,
                unit,
                owner_name=str(spec["owner_name"]),
                share_pct=float(spec.get("share_pct", 100.0)),
                document_ref=str(spec.get("document_ref", "")),
                verified=bool(spec.get("owner_verified", False)),
            )
        created.append(unit)
    session.commit()
    audit(
        session,
        "geometry_create",
        user_id=actor.id if actor else None,
        target_type="floor_division",
        target_id=floor.ref_key,
        detail={"rooms": len(rooms)},
    )
    return created


# ---------------------------------------------------------------------------
# Ownership CRUD
# ---------------------------------------------------------------------------


def list_owners(session: Session, prop: Property) -> list[dict]:
    rows = (
        session.execute(select(OwnershipRecord).where(OwnershipRecord.property_id == prop.id))
        .scalars()
        .all()
    )
    return [owner_to_dict(o) for o in rows]


def owner_to_dict(o: OwnershipRecord) -> dict:
    return {
        "id": o.id,
        "property_id": o.property_id,
        "owner_name": o.owner_name,
        "share_pct": o.share_pct,
        "document_ref": o.document_ref,
        "verified": o.verified,
        "created_at": o.created_at.isoformat(),
    }


def add_owner(
    session: Session,
    prop: Property,
    *,
    owner_name: str,
    share_pct: float = 100.0,
    document_ref: str = "",
    verified: bool = False,
    commit: bool = True,
) -> OwnershipRecord:
    if not owner_name.strip():
        raise ValueError("owner_name is required.")
    row = OwnershipRecord(
        property_id=prop.id,
        owner_name=owner_name.strip(),
        share_pct=max(0.0, min(100.0, float(share_pct))),
        document_ref=document_ref.strip(),
        verified=bool(verified),
    )
    session.add(row)
    if commit:
        session.commit()
    return row


def update_owner(
    session: Session,
    owner: OwnershipRecord,
    *,
    owner_name: str | None = None,
    share_pct: float | None = None,
    document_ref: str | None = None,
    verified: bool | None = None,
    commit: bool = True,
) -> OwnershipRecord:
    if owner_name is not None and owner_name.strip():
        owner.owner_name = owner_name.strip()
    if share_pct is not None:
        owner.share_pct = max(0.0, min(100.0, float(share_pct)))
    if document_ref is not None:
        owner.document_ref = document_ref.strip()
    if verified is not None:
        owner.verified = bool(verified)
    if commit:
        session.commit()
    return owner
