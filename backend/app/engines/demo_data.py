"""Deterministic synthetic demo dataset for the Bengaluru pilot zone.

This is SYNTHETIC DEMO DATA -- not an official land record. It is regenerable:
the same seed always produces the same layout, so the demo can be reproduced
and tests are stable.

Zone: "Bengaluru Pilot Zone (Synthetic)" near 77.640 E, 12.910 N.

Included demonstration cases:
  CASE A - two volumes, same footprint, disjoint z intervals -> PASS
  CASE B - two volumes, same footprint, overlapping z intervals -> CONFLICT
  CASE C - a child floor that extends outside its parent building -> ERROR
  CASE D - an AI-derived building candidate -> PENDING VERIFICATION

Underground assets use negative z ranges (basement, parking, utilities).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from ..core.enums import PropertyType, PropertyStatus, SourceType

SEED = 26011
STATE_CODE = "KA"
DISTRICT_CODE = "BLR"
PILOT_CENTER = (77.6402, 12.9098)  # lon, lat (synthetic reference)
M_PER_DEG_LAT = 111_320.0

PILOT_NAME = "Bengaluru Pilot Zone (Synthetic)"
NOTICE = "Demonstration dataset — not an official land record."


@dataclass
class DemoRecord:
    pass


@dataclass
class DemoParcel:
    parcel_id: str
    center: tuple[float, float]
    footprint: list[list[float]]
    area_m2: float
    source: SourceType = SourceType.SYNTHETIC_DEMO
    source_name: str = "SyntheticDemoAdapter"


@dataclass
class DemoProperty:
    ref_id: str  # internal reference used while building (e.g. "B001")
    property_type: PropertyType
    parcel_id: str | None
    parent_ref: str | None  # reference to parent DemoProperty.ref_id
    name: str
    footprint: list[list[float]]
    zmin: float
    zmax: float
    status: PropertyStatus = PropertyStatus.VERIFIED
    source: SourceType = SourceType.SYNTHETIC_DEMO
    ai_fields: dict[str, Any] = field(default_factory=dict)
    seq_key: str = "0"  # used to derive sequence number


def rect_footprint(center_lon: float, center_lat: float, w_m: float, h_m: float) -> list[list[float]]:
    """Build a closed lon/lat ring for a rectangle centred at (lon, lat)."""
    dlat = h_m / 2.0 / M_PER_DEG_LAT
    dlon = w_m / 2.0 / (M_PER_DEG_LAT * math.cos(math.radians(center_lat)))
    x0, x1 = center_lon - dlon, center_lon + dlon
    y0, y1 = center_lat - dlat, center_lat + dlat
    return [
        [round(x0, 7), round(y0, 7)],
        [round(x1, 7), round(y0, 7)],
        [round(x1, 7), round(y1, 7)],
        [round(x0, 7), round(y1, 7)],
        [round(x0, 7), round(y0, 7)],
    ]


def _poly_area_m2(ring: list[list[float]], center_lat: float) -> float:
    """Shoelace area of a ring, converted to m^2 using a local scale."""
    coslat = math.cos(math.radians(center_lat))
    pts = [(c[0] * M_PER_DEG_LAT * coslat, c[1] * M_PER_DEG_LAT) for c in ring]
    s = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        s += x1 * y2 - x2 * y1
    return round(abs(s) / 2.0, 2)


def _footprint_from_meters(lon: float, lat: float, w: float, h: float) -> list[list[float]]:
    return rect_footprint(lon, lat, w, h)


def generate_demo_dataset(
    *,
    rows: int = 6,
    cols: int = 10,
    parcel_w: float = 30.0,
    parcel_h: float = 26.0,
    seed: int = SEED,
) -> dict[str, Any]:
    """Generate the deterministic pilot dataset."""
    rng = random.Random(seed)
    cx, cy = PILOT_CENTER

    gap_x = 8.0  # lane between blocks (metres)
    gap_y = 6.0
    block_w = parcel_w + gap_x
    block_h = parcel_h + gap_y
    total_w = cols * block_w
    total_h = rows * block_h
    x_start = cx - total_w / 2.0 / (M_PER_DEG_LAT * math.cos(math.radians(cy)))
    y_start = cy - total_h / 2.0 / M_PER_DEG_LAT

    parcels: list[DemoParcel] = []
    properties: list[DemoProperty] = []

    parcel_no = 0
    for r in range(rows):
        for c in range(cols):
            parcel_no += 1
            lon = x_start + (c * block_w + parcel_w / 2.0) / (M_PER_DEG_LAT * math.cos(math.radians(cy)))
            lat = y_start + (r * block_h + parcel_h / 2.0) / M_PER_DEG_LAT
            fp = _footprint_from_meters(lon, lat, parcel_w, parcel_h)
            pid = f"P{parcel_no:05d}"
            parcels.append(
                DemoParcel(
                    parcel_id=pid,
                    center=(lon, lat),
                    footprint=fp,
                    area_m2=_poly_area_m2(fp, cy),
                )
            )

    # ---- Buildings on a deterministic subset of parcels ----
    building_parcels = [p for p in parcels if (parcel_no_index(p.parcel_id) % 3) != 0]
    # keep case parcels 0..3 free of regular buildings so the demo cases stay clean
    reserved = {parcels[i].parcel_id for i in range(min(4, len(parcels)))}
    building_parcels = [p for p in building_parcels if p.parcel_id not in reserved]
    # keep a bit under target: ~ (rows*cols)=60 parcels; buildings on ~2/3 => 40 candidates
    # choose ~24 via stable stride
    chosen: list[DemoParcel] = []
    for p in building_parcels:
        idx = parcel_no_index(p.parcel_id)
        if (idx % 5) in (1, 3):  # deterministic ~ pattern
            chosen.append(p)
    if len(chosen) < 20:  # fallback guarantee
        chosen = building_parcels[:24]

    building_counter = 0
    unit_ref_counter = 0
    floor_ref_counter = 0

    def ref_building() -> str:
        nonlocal building_counter
        building_counter += 1
        return f"B{building_counter:03d}"

    for p in chosen:
        bid = ref_building()
        rng_j = random.Random(seed + building_counter)
        has_basement = building_counter % 4 == 0
        floors = rng_j.randint(3, 6)
        floor_h = 3.0
        b_height = round(floors * floor_h, 1)
        # building footprint slightly smaller than parcel
        bfp = _footprint_from_meters(
            p.center[0], p.center[1], parcel_w * 0.8, parcel_h * 0.8
        )
        bstatus = PropertyStatus.VERIFIED
        if building_counter % 11 == 0:
            bstatus = PropertyStatus.SUBMITTED

        # A building with a basement spans the full vertical extent including
        # below ground (zmin < 0) so the basement is contained by the building.
        b_zmin = -3.0 if has_basement else 0.0
        properties.append(
            DemoProperty(
                ref_id=bid,
                property_type=PropertyType.BUILDING,
                parcel_id=p.parcel_id,
                parent_ref=None,
                name=f"Building {building_counter}",
                footprint=bfp,
                zmin=b_zmin,
                zmax=b_height,
                status=bstatus,
                seq_key="0",
            )
        )

        if has_basement:
            properties.append(
                DemoProperty(
                    ref_id=bid + "-BSMT",
                    property_type=PropertyType.BASEMENT,
                    parcel_id=p.parcel_id,
                    parent_ref=bid,
                    name=f"{bid} Basement",
                    footprint=bfp,
                    zmin=-3.0,
                    zmax=0.0,
                    status=PropertyStatus.VERIFIED,
                    seq_key="0",
                )
            )

        # floors
        for f in range(floors):
            floor_ref_counter += 1
            fid = f"{bid}-F{f + 1:02d}"
            z0 = f * floor_h
            z1 = z0 + floor_h
            is_top = f == floors - 1
            # --- CASE C: one deliberately bad floor outside its parent ---
            bad_floor = (building_counter == 7) and (f == 1)
            ffp = bfp
            if bad_floor:
                # offset footprint outside the building
                off = _footprint_from_meters(
                    p.center[0] + 0.0009, p.center[1] + 0.0008, parcel_w * 0.8, parcel_h * 0.8
                )
                ffp = off
            properties.append(
                DemoProperty(
                    ref_id=fid,
                    property_type=PropertyType.FLOOR,
                    parcel_id=p.parcel_id,
                    parent_ref=bid,
                    name=f"{bid} Floor {f + 1}",
                    footprint=ffp,
                    zmin=z0,
                    zmax=z1,
                    status=PropertyStatus.VERIFIED,
                    seq_key=str(f + 1),
                )
            )

            # units per floor: split the building footprint into up to 2 bands
            units_per_floor = 2 if not is_top else 1
            if building_counter % 9 == 0:
                units_per_floor = 3
            for u in range(units_per_floor):
                unit_ref_counter += 1
                uid = f"{fid}-U{u + 1}"
                ufp = _split_footprint(bfp, u + 1, units_per_floor)
                ustatus = PropertyStatus.VERIFIED
                # a couple of units left pending verification as demo of workflow
                if unit_ref_counter % 17 == 0:
                    ustatus = PropertyStatus.PENDING_VERIFICATION
                properties.append(
                    DemoProperty(
                        ref_id=uid,
                        property_type=PropertyType.UNIT,
                        parcel_id=p.parcel_id,
                        parent_ref=fid,
                        name=f"{bid} {f + 1}0{u + 1}",
                        footprint=ufp,
                        zmin=z0,
                        zmax=z1,
                        status=ustatus,
                        seq_key=str(u + 1),
                    )
                )

    # ---- Underground assets along the main lanes ----
    # water line along y mid of first row of lanes
    ug_lat = y_start + (rows * block_h) / 2.0 / M_PER_DEG_LAT  # approx midline
    properties.append(
        DemoProperty(
            ref_id="UG-WTR-01",
            property_type=PropertyType.UNDERGROUND_ASSET,
            parcel_id=None,
            parent_ref=None,
            name="Water supply line",
            footprint=_corridor(x_start, ug_lat, w=0.7, l=total_w),
            zmin=-1.5,
            zmax=-0.8,
            status=PropertyStatus.VERIFIED,
            seq_key="1",
        )
    )
    properties.append(
        DemoProperty(
            ref_id="UG-SWR-01",
            property_type=PropertyType.UNDERGROUND_ASSET,
            parcel_id=None,
            parent_ref=None,
            name="Sewer line",
            footprint=_corridor(x_start, ug_lat + 0.0004, w=0.8, l=total_w),
            zmin=-3.2,
            zmax=-2.4,
            status=PropertyStatus.VERIFIED,
            seq_key="2",
        )
    )
    # utility tunnel
    tunnel_lat = y_start + 0.0005
    properties.append(
        DemoProperty(
            ref_id="UG-TNL-01",
            property_type=PropertyType.UNDERGROUND_ASSET,
            parcel_id=None,
            parent_ref=None,
            name="Utility tunnel",
            footprint=_corridor(x_start + 0.001, tunnel_lat, w=2.6, l=total_h * 0.6),
            zmin=-5.0,
            zmax=-3.4,
            status=PropertyStatus.VERIFIED,
            seq_key="3",
        )
    )

    # ---- CASE A & B volumes (same footprint on a dedicated parcel) ----
    case_parcel = parcels[0]
    cp_fp = case_parcel.footprint
    properties.append(
        DemoProperty(
            ref_id="CASE-A1",
            property_type=PropertyType.VOLUME,
            parcel_id=case_parcel.parcel_id,
            parent_ref=None,
            name="Demo Case A - lower volume (PASS)",
            footprint=cp_fp,
            zmin=0.0,
            zmax=4.0,
            status=PropertyStatus.VERIFIED,
            seq_key="10",
        )
    )
    properties.append(
        DemoProperty(
            ref_id="CASE-A2",
            property_type=PropertyType.VOLUME,
            parcel_id=case_parcel.parcel_id,
            parent_ref=None,
            name="Demo Case A - upper volume (PASS)",
            footprint=cp_fp,
            zmin=4.0,
            zmax=8.0,
            status=PropertyStatus.VERIFIED,
            seq_key="11",
        )
    )
    properties.append(
        DemoProperty(
            ref_id="CASE-B1",
            property_type=PropertyType.VOLUME,
            parcel_id=parcels[1].parcel_id,
            parent_ref=None,
            name="Demo Case B - conflict volume 1",
            footprint=parcels[1].footprint,
            zmin=0.0,
            zmax=6.0,
            status=PropertyStatus.SUBMITTED,
            seq_key="12",
        )
    )
    properties.append(
        DemoProperty(
            ref_id="CASE-B2",
            property_type=PropertyType.VOLUME,
            parcel_id=parcels[1].parcel_id,
            parent_ref=None,
            name="Demo Case B - conflict volume 2",
            footprint=parcels[1].footprint,
            zmin=4.0,
            zmax=9.0,
            status=PropertyStatus.SUBMITTED,
            seq_key="13",
        )
    )

    # ---- CASE D: AI-derived building candidate (pending verification) ----
    ai_parcel = parcels[2]
    ai_fp = _footprint_from_meters(
        ai_parcel.center[0], ai_parcel.center[1], parcel_w * 0.7, parcel_h * 0.7
    )
    properties.append(
        DemoProperty(
            ref_id="B-AI-001",
            property_type=PropertyType.BUILDING,
            parcel_id=ai_parcel.parcel_id,
            parent_ref=None,
            name="AI candidate building (needs verification)",
            footprint=ai_fp,
            zmin=0.0,
            zmax=21.0,
            status=PropertyStatus.PENDING_VERIFICATION,
            source=SourceType.AI_DERIVED,
            ai_fields={
                "model_name": "ai-assist/building-extraction-v0",
                "model_version": "0.1.0",
                "confidence": 0.82,
                "method": "pretrained segmentation -> footprint vectorization",
            },
            seq_key="14",
        )
    )
    # parking (basement of a building without basement) => underground parking
    pk_parcel = parcels[3]
    pk_fp = _footprint_from_meters(
        pk_parcel.center[0], pk_parcel.center[1], parcel_w * 0.8, parcel_h * 0.8
    )
    properties.append(
        DemoProperty(
            ref_id="B-PK-001",
            property_type=PropertyType.PARKING,
            parcel_id=pk_parcel.parcel_id,
            parent_ref=None,
            name="Underground parking",
            footprint=pk_fp,
            zmin=-3.5,
            zmax=-0.5,
            status=PropertyStatus.VERIFIED,
            seq_key="15",
        )
    )

    return {
        "meta": {
            "name": PILOT_NAME,
            "notice": NOTICE,
            "state_code": STATE_CODE,
            "district_code": DISTRICT_CODE,
            "center": {"lon": cx, "lat": cy},
            "seed": seed,
            "rows": rows,
            "cols": cols,
            "counts": {
                "parcels": len(parcels),
                "properties": len(properties),
                "buildings": sum(1 for p in properties if p.property_type == PropertyType.BUILDING),
                "floors": sum(1 for p in properties if p.property_type == PropertyType.FLOOR),
                "units": sum(1 for p in properties if p.property_type == PropertyType.UNIT),
                "underground": sum(
                    1
                    for p in properties
                    if p.property_type in (PropertyType.UNDERGROUND_ASSET, PropertyType.BASEMENT, PropertyType.PARKING)
                ),
            },
        },
        "parcels": [p.__dict__ for p in parcels],
        "properties": [p.__dict__ for p in properties],
    }


def parcel_no_index(parcel_id: str) -> int:
    return int(parcel_id.replace("P", "")) if parcel_id.startswith("P") else int(parcel_id)


def _split_footprint(fp: list[list[float]], band: int, bands: int) -> list[list[float]]:
    """Split a rectangular ring into `bands` horizontal bands and return `band`."""
    y0 = fp[0][1]
    y1 = fp[2][1]
    span = (y1 - y0) / bands
    ylo = y0 + (band - 1) * span
    yhi = ylo + span
    return [
        [fp[0][0], round(ylo, 7)],
        [fp[1][0], round(ylo, 7)],
        [fp[1][0], round(yhi, 7)],
        [fp[0][0], round(yhi, 7)],
        [fp[0][0], round(ylo, 7)],
    ]


def _corridor(lon0: float, lat: float, w: float, l: float) -> list[list[float]]:
    """Horizontal corridor ring starting at lon0, length l metres along lon."""
    dlon_h = l / 2.0 / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    dlat_h = w / 2.0 / M_PER_DEG_LAT
    xa, xb = lon0, lon0 + dlon_h * 2.0
    ya, yb = lat - dlat_h, lat + dlat_h
    return [
        [round(xa, 7), round(ya, 7)],
        [round(xb, 7), round(ya, 7)],
        [round(xb, 7), round(yb, 7)],
        [round(xa, 7), round(yb, 7)],
        [round(xa, 7), round(ya, 7)],
    ]
