"""Assistive analysis: height/floor estimation + anomaly detection.

These are deterministic, explainable helpers. Every estimate exposes method and
confidence and is clearly non-authoritative. AI building extraction from
imagery is behind the model registry and only runs when enabled.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.enums import PropertyType
from ..db.models import AiPrediction, Parcel, Property

# ---------------------------------------------------------------------------
# Height estimation
# ---------------------------------------------------------------------------


def estimate_height(*, roof_elevation: float | None = None,
                    ground_elevation: float | None = None,
                    metadata_height: float | None = None,
                    floor_count: int | None = None,
                    floor_height_m: float = 3.0) -> dict[str, Any]:
    """Estimate building height by method priority.

    - direct metadata height is best
    - DEM/DSM (roof - ground) is next
    - floor_count * typical floor height is a rough estimate
    """
    if metadata_height and metadata_height > 0:
        return {"height_m": round(float(metadata_height), 2), "method": "supplied_metadata",
                "confidence": 0.98, "note": "Height supplied with the source data."}
    if roof_elevation is not None and ground_elevation is not None:
        h = roof_elevation - ground_elevation
        if h > 0:
            return {"height_m": round(float(h), 2), "method": "dsm_dem_difference",
                    "confidence": 0.8, "note": "Height from roof minus ground elevation (DSM/DEM)."}
    if floor_count and floor_count > 0:
        return {"height_m": round(floor_count * floor_height_m, 2), "method": "floor_count_estimate",
                "confidence": 0.5, "note": "Estimated as floor_count x typical floor height. Requires verification."}
    return {"height_m": None, "method": "unavailable", "confidence": 0.0,
            "note": "Not enough information to estimate height."}


# ---------------------------------------------------------------------------
# Floor estimation
# ---------------------------------------------------------------------------

DEFAULT_FLOOR_HEIGHT = 3.0


def estimate_floors(*, height_m: float | None, explicit_floors: int | None = None,
                    floor_height_m: float = DEFAULT_FLOOR_HEIGHT) -> dict[str, Any]:
    """Two paths:
    PATH A - explicit floors supplied.
    PATH B - estimated from height / typical floor height.
    """
    if explicit_floors and explicit_floors > 0:
        return {"count": explicit_floors, "path": "explicit",
                "confidence": 1.0, "note": "Floor count supplied by surveyor/import."}
    if height_m and height_m > 0:
        count = max(1, round(height_m / floor_height_m))
        return {"count": count, "path": "estimated", "confidence": 0.5,
                "note": "Estimated floor levels derived from height. Requires verification."}
    return {"count": None, "path": "unknown", "confidence": 0.0, "note": "Insufficient data."}


# ---------------------------------------------------------------------------
# Anomaly detection (deterministic)
# ---------------------------------------------------------------------------


def detect_property_anomalies(prop: Property) -> list[dict[str, Any]]:
    """Rule-based anomaly checks on a single property. Plain-language output."""
    out: list[dict[str, Any]] = []
    zmin = prop.zmin if prop.zmin is not None else 0.0
    zmax = prop.zmax if prop.zmax is not None else 0.0
    height = zmax - zmin
    area = prop.area_m2 or 0.0

    if prop.property_type == PropertyType.BUILDING.value:
        if height > 120:
            out.append({"type": "extreme_height", "severity": "warning",
                        "message": f"Building '{prop.ref_key}' has an extreme height of {height:.0f} m.",
                        "method": "rule: height > 120m"})
        if area > 0 and (area / (height or 1)) > 5000:
            out.append({"type": "suspicious_volume", "severity": "warning",
                        "message": f"Building '{prop.ref_key}' footprint is very large relative to height.",
                        "method": "rule: area/height ratio"})
    if height <= 0 and prop.property_type not in (PropertyType.UNIT.value,):
        out.append({"type": "impossible_z", "severity": "error",
                    "message": f"'{prop.ref_key}' has a non-positive vertical extent.",
                    "method": "rule: zmax <= zmin"})
    if area <= 1.0:
        out.append({"type": "tiny_footprint", "severity": "warning",
                    "message": f"'{prop.ref_key}' has an unusually small footprint ({area:.2f} m^2).",
                    "method": "rule: area < 1 m^2"})
    return out


def analyse_dataset(session: Session, *, parcel_ref: str | None = None) -> dict[str, Any]:
    """AI Analyse action. Produces structured, verifiable findings.

    Results reference existing records/AI predictions and rule-based anomalies.
    Nothing here is legally authoritative.
    """
    stmt = select(Property).where(Property.active.is_(True))
    if parcel_ref:
        parcel = session.execute(select(Parcel).where(Parcel.ref_id == parcel_ref)).scalar_one_or_none()
        if parcel is None:
            return {"scope": parcel_ref, "error": "Parcel not found", "findings": []}
        stmt = stmt.where(Property.parcel_id == parcel.id)
    props = list(session.execute(stmt).scalars().all())

    anomalies: list[dict] = []
    for p in props:
        anomalies.extend(detect_property_anomalies(p))

    ai_candidates = [
        {
            "ref_key": p.ref_key, "name": p.name, "confidence": p.confidence,
            "model_name": p.model_name, "status": p.status,
            "needs_verification": not p.verified,
        }
        for p in props
        if p.source_type == "ai_derived"
    ]

    # explicit floors present?
    buildings_with_explicit = sum(1 for p in props if p.property_type == "floor")

    # floor/height estimates for buildings lacking explicit height
    estimates: list[dict] = []
    for p in props:
        if p.property_type != PropertyType.BUILDING.value:
            continue
        if p.height_m is None or p.height_m <= 0:
            est = estimate_height(floor_count=None)
            estimates.append({"ref_key": p.ref_key, "height": est})
        else:
            floors = estimate_floors(height_m=p.height_m)
            estimates.append({"ref_key": p.ref_key, "height_m": p.height_m,
                              "floors": floors, "method": "from building height"})

    return {
        "scope": parcel_ref or "global",
        "generated_at": None,  # set by route with real timestamp
        "summary": {
            "objects_analysed": len(props),
            "buildings": sum(1 for p in props if p.property_type == PropertyType.BUILDING.value),
            "floors_explicit": buildings_with_explicit,
            "ai_candidates": len(ai_candidates),
            "anomalies": len(anomalies),
        },
        "anomalies": anomalies,
        "ai_candidates": ai_candidates,
        "height_and_floor_estimates": estimates,
        "recommended_verification": [
            "Surveyor verification required for every AI-derived geometry.",
            "Estimated floor counts must be confirmed against floor plans.",
            "Topology conflicts require on-ground survey confirmation.",
        ],
        "disclaimer": "AI results are assistive only and are not legal cadastral truth.",
    }
