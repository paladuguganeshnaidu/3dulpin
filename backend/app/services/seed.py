"""Seed service: development users + deterministic pilot demo data.

Demo credentials are DEVELOPMENT ONLY:
    admin@demo.local / Admin@12345   (role: admin)
    surveyor@demo.local / Survey@12345 (role: surveyor)
    viewer@demo.local / Viewer@12345   (role: viewer)
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.enums import PropertyType, PropertyStatus, SourceType
from ..core.security import hash_password
from ..db.models import AiPrediction, OwnershipRecord, Submission, User
from ..engines import demo_data as dd
from .audit import audit
from . import catalog
from .validation import run_validation

DEV_USERS = [
    {
        "email": "admin@demo.local",
        "username": "admin",
        "full_name": "Demo Admin",
        "password": "Admin@12345",
        "role": "admin",
    },
    {
        "email": "surveyor@demo.local",
        "username": "surveyor",
        "full_name": "Demo Surveyor",
        "password": "Survey@12345",
        "role": "surveyor",
    },
    {
        "email": "viewer@demo.local",
        "username": "viewer",
        "full_name": "Demo Viewer",
        "password": "Viewer@12345",
        "role": "viewer",
    },
]


def seed_users(session: Session) -> dict[str, int]:
    created = 0
    for spec in DEV_USERS:
        exists = session.execute(
            select(User).where(User.email == spec["email"])
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                User(
                    email=spec["email"],
                    username=spec["username"],
                    full_name=spec["full_name"],
                    password_hash=hash_password(spec["password"]),
                    role=spec["role"],
                    is_active=True,
                )
            )
            created += 1
    session.commit()
    return {"users_created": created, "users_total": 3}


def seed_demo_dataset(session: Session, *, rows: int = 6, cols: int = 10) -> dict[str, Any]:
    """Persist the deterministic pilot dataset and run validation."""
    ds = dd.generate_demo_dataset(rows=rows, cols=cols)
    admin = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
    admin_id = admin.id if admin else None

    parcel_by_id: dict[str, Any] = {}
    for par in ds["parcels"]:
        row = catalog.create_parcel(
            session,
            ref_id=par["parcel_id"],
            footprint_data=par["footprint"],
            state_code=dd.STATE_CODE,
            district_code=dd.DISTRICT_CODE,
            locality=dd.PILOT_NAME,
            source_type=SourceType.SYNTHETIC_DEMO,
            source_name="SyntheticDemoAdapter",
            source_file="data/samples/demo_dataset.json",
            status="approved",
            actor_id=admin_id,
        )
        parcel_by_id[par["parcel_id"]] = row

    # build properties in dependency order (parent before child)
    order = {t: i for i, t in enumerate(PropertyType)}
    props_by_ref: dict[str, Any] = {}
    count_created = 0
    for prop in sorted(ds["properties"], key=lambda x: order.get(x["property_type"], 99)):
        ptype = prop["property_type"]
        if not isinstance(ptype, PropertyType):
            ptype = PropertyType(ptype)
        parcel = parcel_by_id.get(prop["parcel_id"])
        parent = props_by_ref.get(prop["parent_ref"]) if prop["parent_ref"] else None
        status = prop["status"]
        if not isinstance(status, PropertyStatus):
            status = PropertyStatus(status)
        model_name = prop["ai_fields"].get("model_name") if prop["ai_fields"] else None
        model_version = prop["ai_fields"].get("model_version") if prop["ai_fields"] else None
        confidence = prop["ai_fields"].get("confidence") if prop["ai_fields"] else None

        row = catalog.create_property(
            session,
            ref_key=prop["ref_id"],
            property_type=ptype,
            footprint_data=prop["footprint"],
            zmin=prop["zmin"],
            zmax=prop["zmax"],
            parcel=parcel,
            parent=parent,
            name=prop["name"],
            status=status,
            source_type=prop["source"],
            source_name="SyntheticDemoAdapter",
            source_file="data/samples/demo_dataset.json",
            model_name=model_name,
            model_version=model_version,
            confidence=confidence,
            actor_id=admin_id,
        )
        props_by_ref[prop["ref_id"]] = row
        count_created += 1

    session.commit()

    # AI-derived candidate -> ai_predictions row
    _seed_ai_and_workflow(session, props_by_ref, admin_id)

    # ownership records for a few demo units
    for ref in ("B001-F01-U1", "B001-F01-U2", "B002-F01-U1"):
        p = props_by_ref.get(ref)
        if p:
            session.add(
                OwnershipRecord(
                    property_id=p.id,
                    owner_name="Demo Owner (Synthetic)",
                    share_pct=100.0,
                    document_ref="SYNTHETIC-DOC-NONE",
                    verified=False,
                )
            )
    session.commit()

    # submissions for submitted properties
    for ref, p in props_by_ref.items():
        if p.status == PropertyStatus.SUBMITTED.value:
            session.add(
                Submission(
                    property_id=p.id,
                    submitted_by=admin_id or 1,
                    status="submitted",
                    review_note="Synthetic demo submission.",
                )
            )
    session.commit()

    # global + parcel validations
    run_validation(session, persist=True)

    audit(
        session,
        "geometry_create",
        user_id=admin_id,
        target_type="dataset",
        target_id="demo:bengaluru",
        detail={"parcels": len(ds["parcels"]), "properties": count_created},
    )

    return {
        "meta": ds["meta"],
        "parcels_created": len(ds["parcels"]),
        "properties_created": count_created,
    }


def _seed_ai_and_workflow(session: Session, props_by_ref: dict, admin_id: int | None) -> None:
    ai = props_by_ref.get("B-AI-001")
    if ai:
        session.add(
            AiPrediction(
                prediction_type="building_extraction",
                property_id=ai.id,
                input_ref="synthetic:drone-ortho-block-3",
                output={
                    "detected": True,
                    "footprint_source": "AI-derived (pretrained segmentation)",
                    "needs_verification": True,
                    "note": "AI candidate. Must be verified by a surveyor before use.",
                },
                confidence=ai.confidence,
                model_name=ai.model_name or "ai-assist/building-extraction-v0",
                model_version=ai.model_version or "0.1.0",
                requires_verification=True,
            )
        )


def seed_all(session: Session) -> dict[str, Any]:
    users = seed_users(session)
    data = seed_demo_dataset(session)
    return {"users": users, "data": data}
