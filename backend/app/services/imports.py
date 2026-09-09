"""Import service: commit parsed uploads into the catalog with provenance."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..core.enums import PropertyStatus, SourceType
from ..db.models import Parcel, Property, Upload
from ..engines import geometry as geo
from . import catalog
from .audit import audit
from .validation import run_validation

_RECORD_KINDS = {
    "parcel": None,
    "building": "building",
    "floor": "floor",
    "unit": "unit",
    "basement": "basement",
    "parking": "parking",
    "underground_asset": "underground_asset",
    "volume": "volume",
}

_COUNT_KEYS = {
    "building": "buildings",
    "floor": "floors",
    "unit": "units",
    "basement": "basements",
    "parking": "parking",
    "underground_asset": "underground_assets",
    "volume": "volumes",
}


def new_import_token() -> str:
    return "imp-" + uuid.uuid4().hex[:10]


def _ref_key(token: str, kind: str, external_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]", "_", str(external_id))[:80]
    return f"{token}:{kind}:{slug}"


def commit_import(
    session: Session,
    *,
    user_id: int | None,
    parse_result: Any,
    filename: str,
    source_type: SourceType | str = SourceType.SURVEY_UPLOADED,
    source_name: str = "",
) -> dict[str, Any]:
    """Persist parsed records as parcels/properties. Returns summary."""
    token = new_import_token()
    counts = {
        "parcels": 0,
        "buildings": 0,
        "floors": 0,
        "units": 0,
        "basements": 0,
        "parking": 0,
        "underground_assets": 0,
        "volumes": 0,
        "skipped": 0,
    }
    warnings: list[str] = list(parse_result.warnings or [])
    ref_to_db_id: dict[str, int] = {}  # external id (sanitized) -> property db id
    created_ids: list[int] = []

    # Pass 1: parcels (need to exist before properties reference them)
    parcel_rows: dict[str, Parcel] = {}
    for rec in parse_result.records:
        if rec.kind != "parcel":
            continue
        try:
            row = catalog.create_parcel(
                session,
                ref_id=str(rec.external_id),
                footprint_data=rec.footprint,
                source_type=source_type,
                source_name=source_name or filename,
                source_file=filename,
                status="approved",
                actor_id=user_id,
            )
            parcel_rows[str(rec.external_id)] = row
            counts["parcels"] += 1
        except geo.GeometryError as exc:
            warnings.append(f"Parcel '{rec.external_id}': {exc}")

    # Pass 2: other records in file order (parents first by nature of data)
    parent_db: dict[str, int] = {}
    for rec in parse_result.records:
        if rec.kind == "parcel":
            continue
        ptype_name = _RECORD_KINDS.get(rec.kind)
        if ptype_name is None:
            counts["skipped"] += 1
            warnings.append(f"Record '{rec.external_id}': unsupported kind '{rec.kind}' skipped.")
            continue
        parcel = parcel_rows.get(str(rec.parcel_ref or "")) or _find_parcel_by_ref(
            session, rec.parcel_ref
        )
        parent_db_id = None
        if rec.parent_ref:
            parent_db_id = parent_db.get(_ext_key(rec.parent_ref))
            if parent_db_id is None:
                counts["skipped"] += 1
                warnings.append(
                    f"Record '{rec.external_id}': parent '{rec.parent_ref}' not found; skipped."
                )
                continue
        parent = None
        if parent_db_id is not None:
            parent = session.get(Property, parent_db_id)
        try:
            row = catalog.create_property(
                session,
                ref_key=_ref_key(token, rec.kind, rec.external_id),
                property_type=_to_property_type(ptype_name),
                footprint_data=rec.footprint,
                zmin=rec.zmin,
                zmax=rec.zmax,
                parcel=parcel,
                parent=parent,
                name=rec.name or str(rec.external_id),
                status=PropertyStatus.DRAFT,
                source_type=source_type,
                source_name=source_name or filename,
                source_file=filename,
                actor_id=user_id,
            )
        except geo.GeometryError as exc:
            counts["skipped"] += 1
            warnings.append(f"Record '{rec.external_id}': {exc}")
            continue
        parent_db[_ext_key(rec.external_id)] = row.id
        created_ids.append(row.id)
        counts[_COUNT_KEYS[ptype_name]] += 1

    session.commit()

    validation = run_validation(session, persist=True)
    audit(
        session,
        "upload",
        user_id=user_id,
        target_type="upload",
        target_id=filename,
        detail={
            "counts": counts,
            "validation_state": validation["summary"]["state"],
        },
    )
    return {
        "token": token,
        "filename": filename,
        "counts": counts,
        "warnings": warnings,
        "validation": {"state": validation["summary"]["state"]},
        "created_property_ids": created_ids,
    }


def _ext_key(external_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(external_id))


def _find_parcel_by_ref(session: Session, ref: str | None):
    if not ref:
        return None
    return catalog.find_parcel(session, str(ref))


def _to_property_type(name: str):
    from ..core.enums import PropertyType

    return PropertyType(name)
