"""Topology validation engine.

Checks are deterministic GIS/rule-based (Shapely) first. Each check returns a
result with a severity:

    PASS      - nothing wrong
    WARNING   - needs attention but not necessarily illegal
    CONFLICT  - spatial/vertical overlap between distinct 3D properties
    ERROR     - impossible/invalid geometry or hierarchy

Overlap rules used (project-specific):
    Two volumetric properties conflict only when their 2D footprints overlap
    AND their z intervals overlap with positive length. Merely touching
    footprints or sharing only a horizontal plane (z2min == z1max) is PASS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from ..core.enums import PropertyType, ValidationState
from . import geometry as geo
from .geometry import Polygon as _P  # noqa: F401  (re-export hint)

# Excluded from vertical-conflict pairing (children vs their own parent etc.)
_SELF_HIERARCHY_TYPES = {PropertyType.BUILDING, PropertyType.FLOOR, PropertyType.UNIT}


@dataclass
class ValidationIssue:
    code: str  # machine readable
    message: str
    state: ValidationState
    object_ids: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "state": self.state.value,
            "object_ids": self.object_ids,
            "detail": self.detail,
        }


@dataclass
class VolumetricObject:
    """Lightweight handle for validation input."""

    id: str
    footprint: Polygon
    zmin: float
    zmax: float
    property_type: PropertyType | None = None
    parent_id: str | None = None
    parcel_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _overlap_volume_m3(a: VolumetricObject, b: VolumetricObject) -> float:
    inter = a.footprint.intersection(b.footprint)
    if inter.is_empty:
        return 0.0
    # local metric area of the intersection
    try:
        metric = geo.footprint_metrics(_as_polygon(inter))
    except Exception:
        return 0.0
    zover = geo.vertical_overlap_m(a.zmin, a.zmax, b.zmin, b.zmax)
    return round(metric.area_m2 * zover, 3)


def _as_polygon(geom: BaseGeometry) -> Polygon:
    if isinstance(geom, Polygon):
        return geom
    if geom.geom_type == "MultiPolygon" and len(geom.geoms) > 0:
        parts = sorted(geom.geoms, key=lambda p: p.area, reverse=True)
        return parts[0]
    raise geo.GeometryError(f"Cannot reduce geometry type {geom.geom_type} to polygon.")


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def run_individual_checks(obj: VolumetricObject) -> list[ValidationIssue]:
    """Checks that apply to a single object."""
    issues: list[ValidationIssue] = []

    ok, msg = geo.validate_2d(obj.footprint)
    if not ok:
        issues.append(
            ValidationIssue(
                code="invalid_footprint",
                message=msg,
                state=ValidationState.ERROR,
                object_ids=[obj.id],
            )
        )
        return issues

    # Z range sanity
    if obj.zmax <= obj.zmin:
        issues.append(
            ValidationIssue(
                code="invalid_z_range",
                message=f"zmax ({obj.zmax}) must be greater than zmin ({obj.zmin}).",
                state=ValidationState.ERROR,
                object_ids=[obj.id],
                detail={"zmin": obj.zmin, "zmax": obj.zmax},
            )
        )

    # Extreme geometry
    metric = geo.footprint_metrics(obj.footprint)
    area = metric.area_m2
    height = obj.zmax - obj.zmin
    if area <= 1.0:
        issues.append(
            ValidationIssue(
                code="tiny_footprint",
                message=f"Footprint area is very small ({area:.3f} m^2).",
                state=ValidationState.WARNING,
                object_ids=[obj.id],
                detail={"area_m2": area},
            )
        )
    if height > 500:
        issues.append(
            ValidationIssue(
                code="extreme_height",
                message=f"Vertical extent {height:.1f} m exceeds 500 m sanity bound.",
                state=ValidationState.WARNING,
                object_ids=[obj.id],
                detail={"height_m": height},
            )
        )
    if height < 0.5 and obj.property_type not in (PropertyType.UNIT,):
        # very thin volumes may be intentional planes; warn, not error
        issues.append(
            ValidationIssue(
                code="thin_volume",
                message=f"Vertical extent {height:.2f} m is unusually thin.",
                state=ValidationState.WARNING,
                object_ids=[obj.id],
                detail={"height_m": height},
            )
        )
    return issues


def run_conflict_checks(objects: list[VolumetricObject]) -> list[ValidationIssue]:
    """Pairwise 3D conflict detection between distinct objects.

    A conflict = 2D footprint overlap + positive-length vertical overlap.
    Only sibling objects at the same level are compared (buildings vs
    buildings, floors vs floors, units vs units) plus underground assets, so
    parent/child containment is reported separately (it is expected).
    """
    issues: list[ValidationIssue] = []
    by_id: dict[str, VolumetricObject] = {o.id: o for o in objects}
    seen: set[tuple[str, str]] = set()

    # group objects by comparison class
    groups: dict[str, list[VolumetricObject]] = {}
    for o in objects:
        if o.property_type in (PropertyType.BUILDING, PropertyType.BASEMENT, PropertyType.PARKING):
            grp = "building_level"
        elif o.property_type == PropertyType.FLOOR:
            grp = "floor_level"
        elif o.property_type in (PropertyType.UNIT,):
            grp = "unit_level"
        elif o.property_type == PropertyType.UNDERGROUND_ASSET:
            grp = "underground"
        else:
            grp = "generic"
        groups.setdefault(grp, []).append(o)

    for grp, members in groups.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                # skip when one is ancestor of the other (containment check covers it)
                if a.parent_id == b.id or b.parent_id == a.id:
                    continue
                if _pair_key(a.id, b.id) in seen:
                    continue
                seen.add(_pair_key(a.id, b.id))
                zover = geo.vertical_overlap_m(a.zmin, a.zmax, b.zmin, b.zmax)
                inter = a.footprint.intersection(b.footprint)
                if inter.is_empty or inter.area <= 1e-9:
                    # no meaningful 2D area overlap (shared edge only is PASS)
                    continue
                # only touch at boundaries -> pass
                if zover <= 0 and (a.zmax == b.zmin or b.zmax == a.zmin):
                    continue
                if zover <= 0:
                    # footprints overlap but z intervals disjoint => PASS case
                    continue
                inter_area = _overlap_volume_m3(a, b)
                issues.append(
                    ValidationIssue(
                        code="vertical_overlap_conflict",
                        message=(
                            f"3D overlap between '{a.id}' (z {a.zmin}..{a.zmax}) and "
                            f"'{b.id}' (z {b.zmin}..{b.zmax}); vertical overlap "
                            f"{zover} m."
                        ),
                        state=ValidationState.CONFLICT,
                        object_ids=[a.id, b.id],
                        detail={
                            "object_a": {
                                "id": a.id,
                                "zmin": a.zmin,
                                "zmax": a.zmax,
                            },
                            "object_b": {
                                "id": b.id,
                                "zmin": b.zmin,
                                "zmax": b.zmax,
                            },
                            "vertical_overlap_m": zover,
                            "overlap_volume_m3": inter_area,
                        },
                    )
                )
    return issues


def run_hierarchy_checks(objects: list[VolumetricObject]) -> list[ValidationIssue]:
    """Parent-child consistency checks."""
    issues: list[ValidationIssue] = []
    by_id = {o.id: o for o in objects}
    for child in objects:
        if not child.parent_id:
            continue
        parent = by_id.get(child.parent_id)
        if parent is None:
            issues.append(
                ValidationIssue(
                    code="missing_parent",
                    message=f"'{child.id}' references parent '{child.parent_id}' which does not exist.",
                    state=ValidationState.ERROR,
                    object_ids=[child.id],
                )
            )
            continue
        # child footprint should be inside parent footprint (buffer for units/parcels)
        buffered_parent = parent.footprint.buffer(0.00001)  # ~1m at equator tolerance
        inter_area = child.footprint.intersection(buffered_parent).area
        child_area = child.footprint.area
        if child_area > 0 and inter_area / child_area < 0.999:
            issues.append(
                ValidationIssue(
                    code="child_outside_parent",
                    message=f"'{child.id}' footprint extends outside its parent '{parent.id}'.",
                    state=ValidationState.ERROR,
                    object_ids=[child.id, parent.id],
                )
            )
        # child z should be inside parent z (floors inside building etc.)
        if not (child.zmin >= parent.zmin - 1e-6 and child.zmax <= parent.zmax + 1e-6):
            issues.append(
                ValidationIssue(
                    code="child_z_outside_parent",
                    message=(
                        f"'{child.id}' z [{child.zmin},{child.zmax}] is not contained by "
                        f"parent '{parent.id}' z [{parent.zmin},{parent.zmax}]."
                    ),
                    state=ValidationState.ERROR,
                    object_ids=[child.id, parent.id],
                    detail={
                        "child_z": [child.zmin, child.zmax],
                        "parent_z": [parent.zmin, parent.zmax],
                    },
                )
            )
    return issues


def run_duplicate_checks(objects: list[VolumetricObject]) -> list[ValidationIssue]:
    """Duplicate footprint + same z range detection.

    Objects that are in a direct ancestor/descendant relationship are excluded:
    a single unit that occupies its whole floor legitimately replicates the
    floor's volume without being a cadastral conflict.
    """
    issues: list[ValidationIssue] = []
    by_id = {o.id: o for o in objects}
    groups: dict[tuple, list[VolumetricObject]] = {}
    for o in objects:
        ring = tuple(
            (round(float(c[0]), 6), round(float(c[1]), 6))
            for c in o.footprint.exterior.coords
        )
        key = (ring, round(o.zmin, 2), round(o.zmax, 2))
        groups.setdefault(key, []).append(o)

    def _is_ancestor(anc: VolumetricObject, node: VolumetricObject) -> bool:
        """Is anc an ancestor of node following the parent_id chain?"""
        seen: set[str] = set()
        cur = node.parent_id
        while cur:
            if cur in seen:
                return False
            seen.add(cur)
            if cur == anc.id:
                return True
            parent = by_id.get(cur)
            cur = parent.parent_id if parent else None
        return False

    for key, members in groups.items():
        if len(members) < 2:
            continue
        # keep members that have no ancestor within this same group
        independent = [
            m for m in members if not any(_is_ancestor(o, m) for o in members if o.id != m.id)
        ]
        if len(independent) < 2:
            continue
        ids = [m.id for m in independent]
        issues.append(
            ValidationIssue(
                code="duplicate_geometry",
                message=(
                    f"{len(ids)} objects share an identical footprint and z range: "
                    + ", ".join(ids)
                ),
                state=ValidationState.CONFLICT,
                object_ids=ids,
                detail={"footprint_ring_count": len(key[0])},
            )
        )
    return issues


def validate_objects(objects: list[VolumetricObject]) -> list[ValidationIssue]:
    """Run the full deterministic validation suite over a set of objects."""
    issues: list[ValidationIssue] = []
    for o in objects:
        issues.extend(run_individual_checks(o))
    issues.extend(run_duplicate_checks(objects))
    issues.extend(run_conflict_checks(objects))
    issues.extend(run_hierarchy_checks(objects))
    return issues


def summarize(issues: list[ValidationIssue]) -> dict[str, Any]:
    """Summarize a list of issues into an overall state + counts."""
    counts = {state.value: 0 for state in ValidationState}
    for issue in issues:
        counts[issue.state.value] += 1
    if counts["ERROR"] > 0:
        overall = ValidationState.ERROR
    elif counts["CONFLICT"] > 0:
        overall = ValidationState.CONFLICT
    elif counts["WARNING"] > 0:
        overall = ValidationState.WARNING
    else:
        overall = ValidationState.PASS
    return {
        "state": overall.value,
        "counts": counts,
        "issue_count": len(issues),
    }
