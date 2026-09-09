"""Catalog service: parcels + properties creation, serialization, ULPINs."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.enums import PropertyType, PropertyStatus, SourceType
from ..db.models import (
    GeometryVersion,
    Parcel,
    Property,
    UlpinRecord,
    User,
)
from ..engines import geometry as geo
from ..engines import ulpin as ulpin_engine
from .audit import audit

# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def parcel_to_dict(p: Parcel) -> dict[str, Any]:
    return {
        "id": p.ref_id,
        "state_code": p.state_code,
        "district_code": p.district_code,
        "locality": p.locality,
        "footprint_geojson": json.loads(p.footprint_geojson),
        "centroid": {"lon": p.centroid_lon, "lat": p.centroid_lat},
        "area_m2": p.area_m2,
        "bbox": p.bbox,
        "source_type": p.source_type,
        "source_name": p.source_name,
        "source_file": p.source_file,
        "status": p.status,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


def property_to_dict(p: Property, *, include_children: bool = False) -> dict[str, Any]:
    return {
        "id": p.ref_key,
        "ulpin": p.ulpin,
        "property_type": p.property_type,
        "name": p.name,
        "parcel_id": p.parcel.ref_id if p.parcel else None,
        "parent_id": p.parent.ref_key if p.parent else None,
        "footprint_geojson": json.loads(p.footprint_geojson),
        "zmin": p.zmin,
        "zmax": p.zmax,
        "height_m": p.height_m,
        "area_m2": p.area_m2,
        "volume_m3": p.volume_m3,
        "centroid": {"lon": p.centroid_lon, "lat": p.centroid_lat},
        "bbox": p.bbox,
        "status": p.status,
        "source_type": p.source_type,
        "source_name": p.source_name,
        "source_file": p.source_file,
        "model_name": p.model_name,
        "model_version": p.model_version,
        "confidence": p.confidence,
        "verified": p.verified,
        "verified_by": p.verified_by,
        "verification_time": _iso(p.verification_time),
        "version": p.version,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
        "child_count": len(p.children) if include_children else None,
    }


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


# ---------------------------------------------------------------------------
# ULPIN helpers
# ---------------------------------------------------------------------------


def assign_ulpin(
    session: Session,
    prop: Property,
    parcel_key: str,
    kind: PropertyType,
) -> str:
    """Allocate a deterministic 3D ULPIN for a property row.

    Sequence is derived deterministically from the count of existing ULPINs for
    the same (base parcel key, kind code), which yields stable unique IDs per
    property while remaining stable for identical inputs.
    """
    kind_code = ulpin_engine.kind_from_type(kind)
    count = (
        session.execute(
            select(func.count(UlpinRecord.id)).where(
                UlpinRecord.base_parcel_key == parcel_key,
                UlpinRecord.kind_code == kind_code,
            )
        )
    ).scalar_one()
    ulpin = ulpin_engine.generate_3d_ulpin(
        parcel_key,
        kind,
        count,
        state_code=prop.parcel.state_code if prop.parcel else "KA",
        district_code=prop.parcel.district_code if prop.parcel else "BLR",
        version=prop.version or 1,
    )
    prop.ulpin = ulpin
    session.add(
        UlpinRecord(
            ulpin=ulpin,
            base_parcel_key=parcel_key,
            kind_code=kind_code,
            sequence=count,
            version=prop.version or 1,
            property_id=prop.id,
            state="current",
        )
    )
    return ulpin


# ---------------------------------------------------------------------------
# Parcels
# ---------------------------------------------------------------------------


def find_parcel(session: Session, ref_id: str) -> Parcel | None:
    return session.execute(select(Parcel).where(Parcel.ref_id == ref_id)).scalar_one_or_none()


def create_parcel(
    session: Session,
    *,
    ref_id: str,
    footprint_data: Any,
    state_code: str = "KA",
    district_code: str = "BLR",
    locality: str = "",
    source_type: SourceType | str = SourceType.SYNTHETIC_DEMO,
    source_name: str = "",
    source_file: str = "",
    status: str = "approved",
    extra: dict | None = None,
    actor_id: int | None = None,
) -> Parcel:
    existing = find_parcel(session, ref_id)
    if existing:
        return existing
    vol = geo.build_volume(footprint_data, 0.0, 1.0)  # parcel thickness not used; just metrics
    row = Parcel(
        ref_id=ref_id,
        state_code=state_code,
        district_code=district_code,
        locality=locality,
        footprint_geojson=json.dumps(vol.footprint_geojson),
        centroid_lon=vol.centroid[0],
        centroid_lat=vol.centroid[1],
        area_m2=vol.area_m2,
        bbox=vol.bbox,
        source_type=source_type.value if isinstance(source_type, SourceType) else str(source_type),
        source_name=source_name,
        source_file=source_file,
        status=status,
        extra=extra,
    )
    session.add(row)
    session.flush()
    audit(
        session,
        "geometry_create",
        user_id=actor_id,
        target_type="parcel",
        target_id=ref_id,
        detail={"area_m2": vol.area_m2},
        commit=False,
    )
    return row


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


def create_property(
    session: Session,
    *,
    ref_key: str,
    property_type: PropertyType,
    footprint_data: Any,
    zmin: float | None,
    zmax: float | None,
    parcel: Parcel | None,
    parent: Property | None = None,
    name: str = "",
    status: PropertyStatus | str = PropertyStatus.DRAFT,
    source_type: SourceType | str = SourceType.SURVEY_UPLOADED,
    source_name: str = "",
    source_file: str = "",
    model_name: str | None = None,
    model_version: str | None = None,
    confidence: float | None = None,
    verified: bool = False,
    verified_by: int | None = None,
    extra: dict | None = None,
    actor_id: int | None = None,
    assign_ulpin_id: bool = True,
) -> Property:
    """Create a property row, computing geometry metrics from footprint + z."""
    # Use a thin reference volume for metrics even when z is absent
    zlo = zmin if zmin is not None else 0.0
    zhi = zmax if zmax is not None else max(zlo + 1.0, 1.0)
    vol = geo.build_volume(footprint_data, zlo, zhi)
    height = (zmax - zmin) if (zmin is not None and zmax is not None) else None
    volume = vol.volume_m3 if (zmin is not None and zmax is not None) else None

    row = Property(
        ref_key=ref_key,
        parcel_id=parcel.id if parcel else None,
        parent_id=parent.id if parent else None,
        property_type=property_type.value,
        name=name,
        footprint_geojson=json.dumps(vol.footprint_geojson),
        zmin=zmin,
        zmax=zmax,
        height_m=height,
        area_m2=vol.area_m2,
        volume_m3=volume,
        centroid_lon=vol.centroid[0],
        centroid_lat=vol.centroid[1],
        bbox=vol.bbox,
        status=status.value if isinstance(status, PropertyStatus) else str(status),
        source_type=source_type.value if isinstance(source_type, SourceType) else str(source_type),
        source_name=source_name,
        source_file=source_file,
        model_name=model_name,
        model_version=model_version,
        confidence=confidence,
        verified=verified,
        verified_by=verified_by,
        extra=extra,
    )
    session.add(row)
    session.flush()

    # version 1 snapshot
    session.add(
        GeometryVersion(
            property_id=row.id,
            version_number=1,
            footprint_geojson=row.footprint_geojson,
            zmin=row.zmin,
            zmax=row.zmax,
            change_summary="initial geometry",
            actor_id=actor_id,
        )
    )

    if assign_ulpin_id and parcel is not None:
        parcel_key = _base_key_for(parcel, property_type)
        assign_ulpin(session, row, parcel_key, property_type)
    elif assign_ulpin_id and parcel is None:
        # underground assets / volumes may not belong to a parcel; derive a
        # stable parcel-less base token from the property key
        parcel_key = _slug(ref_key)
        assign_ulpin(session, row, parcel_key, property_type)

    session.flush()
    audit(
        session,
        "geometry_create",
        user_id=actor_id,
        target_type="property",
        target_id=ref_key,
        detail={"type": row.property_type, "ulpin": row.ulpin},
        commit=False,
    )
    return row


def _base_key_for(parcel: Parcel, property_type: PropertyType) -> str:
    if property_type in (PropertyType.PARCEL, PropertyType.BUILDING, PropertyType.FLOOR, PropertyType.UNIT):
        return parcel.ref_id
    return parcel.ref_id


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^A-Z0-9]", "", value.upper())[:12] or "OBJ"


def find_property(session: Session, ref_key: str) -> Property | None:
    return session.execute(select(Property).where(Property.ref_key == ref_key)).scalar_one_or_none()


def resolve_property_parent_ref_key(prop: Property) -> str | None:
    return prop.parent.ref_key if prop.parent else None


def update_geometry(
    session: Session,
    prop: Property,
    *,
    footprint_data: Any | None = None,
    zmin: float | None = None,
    zmax: float | None = None,
    reason: str = "",
    actor_id: int | None = None,
    change_summary: str = "geometry modified",
) -> Property:
    """Update geometry with versioning (never silently overwrite)."""
    if footprint_data is None:
        footprint_data = json.loads(prop.footprint_geojson)
    nzmin = prop.zmin if zmin is None else zmin
    nzmax = prop.zmax if zmax is None else zmax
    prev_version_id = (
        session.execute(
            select(GeometryVersion)
            .where(GeometryVersion.property_id == prop.id)
            .order_by(GeometryVersion.version_number.desc())
        )
        .scalars()
        .first()
    )
    vol = geo.build_volume(footprint_data, nzmin or 0.0, nzmax or (nzmin or 0.0) + 1.0)

    # snapshot the OLD geometry
    session.add(
        GeometryVersion(
            property_id=prop.id,
            version_number=prop.version,
            footprint_geojson=prop.footprint_geojson,
            zmin=prop.zmin,
            zmax=prop.zmax,
            change_summary=f"previous version V{prop.version}",
            actor_id=actor_id,
            previous_version_id=prev_version_id.id if prev_version_id else None,
            reason=reason,
        )
    )

    prop.footprint_geojson = json.dumps(vol.footprint_geojson)
    prop.zmin = nzmin
    prop.zmax = nzmax
    prop.height_m = (nzmax - nzmin) if (nzmin is not None and nzmax is not None) else None
    prop.volume_m3 = vol.volume_m3 if (nzmin is not None and nzmax is not None) else None
    prop.area_m2 = vol.area_m2
    prop.centroid_lon = vol.centroid[0]
    prop.centroid_lat = vol.centroid[1]
    prop.bbox = vol.bbox
    prop.version = prop.version + 1
    session.flush()
    audit(
        session,
        "geometry_modify",
        user_id=actor_id,
        target_type="property",
        target_id=prop.ref_key,
        detail={"new_version": prop.version, "reason": reason},
        commit=False,
    )
    return prop


def set_verified(
    session: Session,
    prop: Property,
    *,
    user: User,
    verified: bool = True,
    commit: bool = False,
) -> Property:
    prop.verified = verified
    prop.verified_by = user.id
    from datetime import datetime, timezone

    prop.verification_time = datetime.now(timezone.utc)
    if verified and prop.status in (PropertyStatus.PENDING_VERIFICATION.value, PropertyStatus.DRAFT.value):
        prop.status = PropertyStatus.VERIFIED.value
    if commit:
        session.commit()
    return prop
