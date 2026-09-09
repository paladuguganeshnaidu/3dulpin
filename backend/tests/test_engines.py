"""Mandatory backend engine tests: ULPIN, geometry, topology."""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from app.core.enums import PropertyType, ValidationState
from app.engines import geometry as geo
from app.engines import topology as topo
from app.engines import ulpin

# shared footprint ring (~small parcel near 77.64,12.91)
FP = [
    [77.6400, 12.9100],
    [77.6403, 12.9100],
    [77.6403, 12.9103],
    [77.6400, 12.9103],
    [77.6400, 12.9100],
]


def _vol(oid, zmin, zmax, ptype=PropertyType.BUILDING, parent=None, ring=FP):
    return topo.VolumetricObject(oid, Polygon(ring), zmin, zmax, ptype, parent_id=parent)


# ---- 1. ULPIN deterministic generation ----
def test_ulpin_deterministic_generation():
    a = ulpin.generate_3d_ulpin("P00042", PropertyType.UNIT, 3)
    b = ulpin.generate_3d_ulpin("P00042", PropertyType.UNIT, 3)
    assert a == b
    assert ulpin.validate_3d_ulpin(a)
    assert ulpin.checksum_valid(a)


# ---- 2. ULPIN uniqueness for distinct vertical properties ----
def test_ulpin_uniqueness_distinct_properties():
    ids = {
        ulpin.generate_3d_ulpin("P00042", PropertyType.UNIT, seq)
        for seq in range(50)
    }
    assert len(ids) == 50
    # different kind -> different id
    assert ulpin.generate_3d_ulpin("P00042", PropertyType.UNIT, 0) != ulpin.generate_3d_ulpin(
        "P00042", PropertyType.FLOOR, 0
    )


# ---- 3. valid 3D volume creation ----
def test_valid_3d_volume_creation():
    v = geo.build_volume(FP, 0.0, 36.0)
    assert v.height == 36.0
    assert v.area_m2 > 100  # sanity: a real metric area in m^2
    assert v.volume_m3 == pytest.approx(v.area_m2 * 36.0, rel=1e-6)


# ---- 4. invalid Z-range rejection ----
def test_invalid_z_range_rejection():
    with pytest.raises(geo.GeometryError):
        geo.build_volume(FP, 10.0, 10.0)
    with pytest.raises(geo.GeometryError):
        geo.build_volume(FP, 15.0, 5.0)


# ---- 5. topology PASS case (touching z intervals) ----
def test_topology_pass_case():
    objs = [_vol("A", 0, 5), _vol("B", 5, 10)]
    issues = topo.validate_objects(objs)
    assert topo.summarize(issues)["state"] == ValidationState.PASS.value


# ---- 6. topology CONFLICT case (overlapping z) ----
def test_topology_conflict_case():
    objs = [_vol("A", 0, 7), _vol("B", 5, 10)]
    issues = topo.validate_objects(objs)
    s = topo.summarize(issues)
    assert s["state"] == ValidationState.CONFLICT.value
    conflict = [i for i in issues if i.code == "vertical_overlap_conflict"]
    assert conflict and conflict[0].detail["vertical_overlap_m"] == 2.0


# ---- 7. parent-child validation ----
def test_parent_child_validation():
    parent = _vol("PAR", -3, 30)
    good_child = _vol("OK", 0, 3, ptype=PropertyType.FLOOR, parent="PAR")
    outside = topo.VolumetricObject(
        "OUT",
        Polygon([[77.7, 12.99], [77.7005, 12.99], [77.7005, 12.9905], [77.7, 12.9905], [77.7, 12.99]]),
        0,
        3,
        PropertyType.FLOOR,
        parent_id="PAR",
    )
    issues = topo.validate_objects([parent, good_child, outside])
    codes = {i.code for i in issues}
    assert "child_outside_parent" in codes
    # parent/child that are contained raise no hierarchy error
    assert not any(i.code == "child_outside_parent" and "OK" in i.object_ids for i in issues)


# ---- 8. duplicate detection ----
def test_duplicate_detection():
    objs = [_vol("X", 0, 5), _vol("Y", 0, 5), _vol("Z", 0, 6)]
    issues = topo.validate_objects(objs)
    dup = [i for i in issues if i.code == "duplicate_geometry"]
    assert dup and set(dup[0].object_ids) == {"X", "Y"}
