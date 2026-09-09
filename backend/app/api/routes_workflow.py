"""Workflow routes: validation, surveyor workflow, admin review, audit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.enums import AuditAction, PropertyStatus, Role
from ..db.models import (
    AiPrediction,
    AuditLog,
    Parcel,
    Property,
    Submission,
    User,
    ValidationResult,
)
from ..db.session import get_db
from ..services.audit import audit
from ..services.catalog import (
    create_property,
    property_to_dict,
    set_verified,
    update_geometry,
)
from ..services.validation import run_validation
from .deps import get_current_user, require_roles

router = APIRouter(tags=["workflow"])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@router.post("/validation/run")
def run_validate(
    parcel_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    result = run_validation(db, parcel_ref=parcel_id, persist=True)
    audit(
        db,
        AuditAction.VALIDATION,
        user_id=user.id,
        target_type="validation",
        target_id=result["scope"],
        detail={"state": result["summary"]["state"]},
    )
    return result


@router.get("/validation/latest")
def latest_validation(
    parcel_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    scope = f"parcel:{parcel_id}" if parcel_id else "global"
    row = (
        db.execute(
            select(ValidationResult)
            .where(ValidationResult.scope_key == scope)
            .order_by(ValidationResult.created_at.desc())
        )
        .scalars()
        .first()
    )
    if row is None:
        return {"scope": scope, "summary": None, "issues": []}
    return {
        "scope": row.scope_key,
        "state": row.state,
        "summary": row.summary,
        "issues": row.issues,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/validation/conflicts")
def list_conflicts(
    state: str = Query("CONFLICT"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return currently active validation issues of a given state with objects."""
    latest = (
        db.execute(
            select(ValidationResult)
            .where(ValidationResult.scope_key == "global")
            .order_by(ValidationResult.created_at.desc())
        )
        .scalars()
        .first()
    )
    if latest is None:
        return {"items": [], "total": 0}
    issues = [i for i in (latest.issues or []) if i.get("state") == state]
    return {"items": issues, "total": len(issues), "run_at": latest.created_at.isoformat()}


# ---------------------------------------------------------------------------
# Surveyor workflow
# ---------------------------------------------------------------------------


@router.post("/workflow/properties", status_code=201)
def create_surveyor_property(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    from ..core.enums import PropertyType, SourceType

    ptype = PropertyType(str(payload.get("property_type", "volume")))
    parcel = db.execute(select(Parcel).where(Parcel.ref_id == payload["parcel_id"])).scalar_one_or_none()
    if parcel is None:
        raise HTTPException(404, f"Parcel '{payload['parcel_id']}' not found.")
    parent = None
    if payload.get("parent_id"):
        parent = db.execute(select(Property).where(Property.ref_key == payload["parent_id"])).scalar_one_or_none()
        if parent is None:
            raise HTTPException(404, f"Parent '{payload['parent_id']}' not found.")

    ref_key = f"usr-{user.id}-{ptype.value}-{abs(hash(str(payload))) % 10**7}"
    try:
        prop = create_property(
            db,
            ref_key=ref_key,
            property_type=ptype,
            footprint_data=payload["footprint_geojson"],
            zmin=payload.get("zmin"),
            zmax=payload.get("zmax"),
            parcel=parcel,
            parent=parent,
            name=payload.get("name") or ref_key,
            status=PropertyStatus.DRAFT,
            source_type=SourceType.SURVEY_UPLOADED,
            source_name=user.email,
            actor_id=user.id,
        )
    except Exception as exc:
        raise HTTPException(422, str(exc))
    db.commit()
    result = run_validation(db, parcel_ref=parcel.ref_id, persist=True)
    return {"property": property_to_dict(prop), "validation": result["summary"]}


@router.post("/workflow/properties/{ref_key}/verify")
def verify_property(
    ref_key: str,
    payload: dict | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    p = db.execute(select(Property).where(Property.ref_key == ref_key)).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "Property not found.")
    # surveyor cannot approve final record, only verify AI-derived geometry
    if p.status == PropertyStatus.SUBMITTED.value:
        raise HTTPException(409, "Property is already submitted; only an admin can decide.")
    set_verified(db, p, user=user, verified=True)
    audit(db, AuditAction.VALIDATION, user_id=user.id, target_type="property", target_id=ref_key,
          detail={"action": "verify", "ai_candidate": p.source_type == "ai_derived"})
    db.commit()
    return {"property": property_to_dict(p)}


@router.post("/workflow/properties/{ref_key}/submit")
def submit_property(
    ref_key: str,
    payload: dict | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    p = db.execute(select(Property).where(Property.ref_key == ref_key)).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "Property not found.")
    if not p.verified and p.source_type == "ai_derived":
        raise HTTPException(409, "AI-derived geometry must be verified before submission.")
    if p.status == PropertyStatus.APPROVED.value:
        raise HTTPException(409, "Property already approved.")
    p.status = PropertyStatus.SUBMITTED.value
    db.add(Submission(property_id=p.id, submitted_by=user.id, status="submitted",
                      review_note=(payload or {}).get("note", "")))
    audit(db, AuditAction.SUBMISSION, user_id=user.id, target_type="property", target_id=ref_key)
    db.commit()
    return {"property": property_to_dict(p)}


@router.get("/workflow/my-submissions")
def my_submissions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(
        select(Submission)
        .join(Property, Submission.property_id == Property.id)
        .where(Submission.submitted_by == user.id)
        .order_by(Submission.created_at.desc())
    ).scalars().all()
    out = []
    for s in rows:
        p = db.get(Property, s.property_id)
        out.append({"submission_id": s.id, "status": s.status, "note": s.review_note,
                    "created_at": s.created_at.isoformat(), "property": property_to_dict(p) if p else None})
    return {"items": out, "total": len(out)}


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


@router.get("/admin/submissions")
def admin_submissions(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.ADMIN)),
):
    stmt = select(Submission).order_by(Submission.created_at.desc())
    if status_filter:
        stmt = stmt.where(Submission.status == status_filter)
    rows = db.execute(stmt).scalars().all()
    out = []
    for s in rows:
        p = db.get(Property, s.property_id)
        out.append({
            "submission_id": s.id, "status": s.status, "note": s.review_note,
            "created_at": s.created_at.isoformat(), "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
            "submitted_by": s.submitted_by, "property": property_to_dict(p) if p else None,
        })
    return {"items": out, "total": len(out)}


@router.post("/admin/submissions/{submission_id}/review")
def review_submission(
    submission_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.ADMIN)),
):
    action = payload.get("action")
    if action not in ("approve", "reject", "return"):
        raise HTTPException(422, "action must be approve|reject|return")
    s = db.get(Submission, submission_id)
    if s is None:
        raise HTTPException(404, "Submission not found.")
    p = db.get(Property, s.property_id)
    if p is None:
        raise HTTPException(404, "Property not found.")
    from datetime import datetime, timezone

    s.status = "approved" if action == "approve" else ("rejected" if action == "reject" else "returned")
    s.reviewed_by = user.id
    s.reviewed_at = datetime.now(timezone.utc)
    s.review_note = payload.get("note", s.review_note)
    if action == "approve":
        p.status = PropertyStatus.APPROVED.value
        p.verified = True
    elif action == "reject":
        p.status = PropertyStatus.REJECTED.value
    else:
        p.status = PropertyStatus.DRAFT.value
    audit(db, AuditAction.APPROVAL if action == "approve" else AuditAction.REJECTION,
          user_id=user.id, target_type="property", target_id=p.ref_key,
          detail={"action": action, "submission_id": submission_id})
    db.commit()
    return {"submission_id": submission_id, "status": s.status, "property": property_to_dict(p)}


@router.get("/admin/users")
def admin_users(db: Session = Depends(get_db), user=Depends(require_roles(Role.ADMIN))):
    rows = db.execute(select(User).order_by(User.id)).scalars().all()
    return {"items": [{"id": u.id, "email": u.email, "username": u.username,
                       "role": u.role, "active": u.is_active} for u in rows], "total": len(rows)}


@router.get("/admin/stats")
def admin_stats(db: Session = Depends(get_db), user=Depends(require_roles(Role.ADMIN))):
    def count(model, *where):
        stmt = select(func.count()).select_from(model)
        if where:
            stmt = stmt.where(*where)
        return db.execute(stmt).scalar_one()

    latest = db.execute(
        select(ValidationResult).where(ValidationResult.scope_key == "global").order_by(ValidationResult.created_at.desc())
    ).scalars().first()
    return {
        "parcels": count(Parcel, Parcel.active.is_(True)),
        "properties": count(Property, Property.active.is_(True)),
        "buildings": count(Property, Property.property_type == "building", Property.active.is_(True)),
        "floors": count(Property, Property.property_type == "floor", Property.active.is_(True)),
        "units": count(Property, Property.property_type == "unit", Property.active.is_(True)),
        "users": count(User),
        "submissions_pending": count(Submission, Submission.status == "submitted"),
        "ai_predictions": count(AiPrediction),
        "latest_validation": {"state": latest.state if latest else None, "counts": latest.summary if latest else None},
    }


@router.get("/audit")
def audit_log(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    rows = db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).scalars().all()
    return {"items": [
        {"id": a.id, "user_id": a.user_id, "action": a.action, "target_type": a.target_type,
         "target_id": a.target_id, "detail": a.detail, "created_at": a.created_at.isoformat()}
        for a in rows], "total": len(rows)}
