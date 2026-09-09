"""Validation service: load volumetric objects and run the topology engine."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.enums import ValidationState
from ..db.models import Parcel, Property, ValidationResult
from ..engines import topology as topo
from ..engines.geometry import parse_footprint


def _object_from_db_pair(p: Property, parent_map: dict[int, str]) -> topo.VolumetricObject:
    footprint = parse_footprint(json.loads(p.footprint_geojson))
    from ..core.enums import PropertyType

    try:
        ptype = PropertyType(p.property_type)
    except ValueError:
        ptype = None
    parent_ref = parent_map.get(p.parent_id) if p.parent_id else None
    return topo.VolumetricObject(
        id=p.ref_key,
        footprint=footprint,
        zmin=p.zmin or 0.0,
        zmax=p.zmax or 0.0,
        property_type=ptype,
        parent_id=parent_ref,
    )


def load_properties(session: Session, *, parcel_ref: str | None = None) -> list[Property]:
    stmt = select(Property).where(Property.active.is_(True))
    if parcel_ref:
        parcel = session.execute(select(Parcel).where(Parcel.ref_id == parcel_ref)).scalar_one_or_none()
        if parcel is None:
            return []
        stmt = stmt.where(Property.parcel_id == parcel.id)
    return list(session.execute(stmt).scalars().all())


def run_validation(
    session: Session,
    *,
    parcel_ref: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Run the full topology suite over properties in a scope.

    Scope 'parcel_ref' limits to one parcel; None runs over the whole dataset.
    Returns summary + issues and optionally persists a ValidationResult.
    """
    props = load_properties(session, parcel_ref=parcel_ref)
    id_map: dict[int, str] = {p.id: p.ref_key for p in props}
    objects = [_object_from_db_pair(p, id_map) for p in props if p.zmin is not None and p.zmax is not None]
    issues = topo.validate_objects(objects)
    summary = topo.summarize(issues)
    scope_key = f"parcel:{parcel_ref}" if parcel_ref else "global"

    if persist:
        session.add(
            ValidationResult(
                scope_key=scope_key,
                state=summary["state"],
                summary=summary,
                issues=[i.to_dict() for i in issues],
            )
        )
        session.commit()

    return {
        "scope": scope_key,
        "summary": summary,
        "issues": [i.to_dict() for i in issues],
    }


def latest_global_state(session: Session) -> str:
    row = (
        session.execute(
            select(ValidationResult)
            .where(ValidationResult.scope_key == "global")
            .order_by(ValidationResult.created_at.desc())
        )
        .scalars()
        .first()
    )
    return row.state if row else ValidationState.PASS.value
