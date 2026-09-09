"""3D geometry engine built on Shapely.

Conceptual model (project-specific, NOT an official legal standard):

    P3D = P2D x [zmin, zmax]

A volumetric property = a 2D footprint extruded vertically between zmin and
zmax. We store the footprint as GeoJSON (EPSG:4326) plus scalar metrics
(area in m^2 using a local tangential projection, volume = area * height).

Underground features simply have negative z ranges (e.g. zmin=-6, zmax=-2).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from shapely import geometry as shp
from shapely.geometry import Polygon, shape
from shapely.validation import explain_validity

EARTH_RADIUS_M = 6_371_008.8

MAX_Z_ABS = 10_000.0  # sanity bound for heights in metres
MIN_FLOOR_HEIGHT_M = 1.5
MAX_FLOOR_HEIGHT_M = 8.0


class GeometryError(ValueError):
    """Raised for invalid geometry input."""


@dataclass
class FootprintMetrics:
    area_m2: float
    perimeter_m: float | None = None
    bbox: tuple[float, float, float, float] | None = None  # lon_min, lat_min, lon_max, lat_max
    centroid: tuple[float, float] | None = None  # lon, lat


def _local_xy(geom: Polygon) -> tuple[float, float, float]:
    """Approx local tangential projection around centroid to get metre units."""
    cx = geom.centroid.x
    cy = geom.centroid.y
    coslat = math.cos(math.radians(cy)) or 1e-9
    return cx, cy, coslat


def footprint_metrics(geom: Polygon) -> FootprintMetrics:
    cx, cy, coslat = _local_xy(geom)
    # scale lon/lat degree deltas to metres around centroid
    # (1 degree latitude ~ R * pi/180; longitude shrinks by cos(latitude))
    xs = [(x - cx) * EARTH_RADIUS_M * coslat * math.pi / 180.0 for x, _ in geom.exterior.coords]
    ys = [(y - cy) * EARTH_RADIUS_M * math.pi / 180.0 for _, y in geom.exterior.coords]
    poly_m = Polygon(list(zip(xs, ys)))
    area = abs(poly_m.area)
    bbox = geom.bounds
    return FootprintMetrics(
        area_m2=round(float(area), 3),
        perimeter_m=round(float(poly_m.length), 3),
        bbox=(round(bbox[0], 8), round(bbox[1], 8), round(bbox[2], 8), round(bbox[3], 8)),
        centroid=(round(float(geom.centroid.x), 8), round(float(geom.centroid.y), 8)),
    )


def parse_footprint(data: Any) -> Polygon:
    """Parse a footprint from GeoJSON geometry, dict, or [lon,lat] ring list.

    Supports GeoJSON Polygon/MultiPolygon, and the convenience forms used by
    JSONL ingestion: ring of [lon, lat] or [x, y].
    """
    if data is None:
        raise GeometryError("Footprint geometry is required.")

    # Bare ring (list of coordinate pairs) -> Polygon
    if isinstance(data, list):
        if data and isinstance(data[0], (list, tuple)):
            pts = [list(p) for p in data]
            if isinstance(pts[0][0], (list, tuple)):  # nested => multipolygon-ish
                raise GeometryError("Expected a single footprint ring; got nested list.")
            poly = Polygon(pts)
        else:
            raise GeometryError("Footprint ring must be a list of coordinate pairs.")
    else:
        try:
            poly = shape(data)  # GeoJSON dict
        except Exception as exc:  # pragma: no cover - shapely may raise generically
            raise GeometryError(f"Could not parse footprint geometry: {exc}") from exc

    if isinstance(poly, Polygon):
        return poly
    if poly.geom_type == "MultiPolygon":
        # take the largest component as the footprint (documented behaviour)
        parts = sorted(poly.geoms, key=lambda p: p.area, reverse=True)
        return parts[0]
    raise GeometryError(f"Footprint must be a Polygon, got {poly.geom_type}.")


def validate_2d(geom: Polygon, *, raise_on_invalid: bool = False) -> tuple[bool, str]:
    """Validate a 2D polygon. Returns (valid, message)."""
    if geom is None or geom.is_empty:
        return False, "Geometry is empty."
    if geom.geom_type != "Polygon":
        return False, f"Expected Polygon, got {geom.geom_type}."
    if geom.area <= 0:
        return False, "Polygon area is zero or negative (degenerate footprint)."
    if not geom.is_valid:
        reason = explain_validity(geom)
        msg = f"Polygon is invalid: {reason}"
        if raise_on_invalid:
            raise GeometryError(msg)
        return False, msg
    return True, "OK"


def validate_z_range(zmin: float | int | None, zmax: float | int | None) -> tuple[float, float]:
    """Validate and coerce a z range. Raises GeometryError when impossible."""
    if zmin is None or zmax is None:
        raise GeometryError("zmin and zmax are required to define a 3D volume.")
    try:
        lo = float(zmin)
        hi = float(zmax)
    except (TypeError, ValueError) as exc:
        raise GeometryError("zmin/zmax must be numeric metres.") from exc
    if math.isnan(lo) or math.isnan(hi):
        raise GeometryError("zmin/zmax cannot be NaN.")
    if abs(lo) > MAX_Z_ABS or abs(hi) > MAX_Z_ABS:
        raise GeometryError(
            f"z range outside sanity bounds (+/- {MAX_Z_ABS} m): [{lo}, {hi}]"
        )
    if hi - lo < 1e-6:
        raise GeometryError(f"Invalid z range: zmax must be greater than zmin (got [{lo}, {hi}]).")
    return round(lo, 3), round(hi, 3)


def height_of(zmin: float, zmax: float) -> float:
    return round(zmax - zmin, 3)


def compute_volume(area_m2: float, zmin: float, zmax: float) -> float:
    return round(float(area_m2) * (zmax - zmin), 3)


def footprint_to_geojson(geom: Polygon) -> dict[str, Any]:
    """Serialize a footprint to a minimal GeoJSON geometry dict (EPSG:4326)."""
    return {
        "type": "Polygon",
        "coordinates": [list(geom.exterior.coords)],
    }


@dataclass
class Volume3D:
    """A validated volumetric property."""

    footprint: Polygon
    footprint_geojson: dict[str, Any]
    zmin: float
    zmax: float
    height: float
    area_m2: float
    volume_m3: float
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "footprint_geojson": self.footprint_geojson,
            "zmin": self.zmin,
            "zmax": self.zmax,
            "height_m": self.height,
            "area_m2": self.area_m2,
            "volume_m3": self.volume_m3,
            "centroid": {"lon": self.centroid[0], "lat": self.centroid[1]},
            "bbox": self.bbox,
        }


def build_volume(
    footprint_data: Any,
    zmin: float | int,
    zmax: float | int,
    *,
    allow_underground: bool = True,
) -> Volume3D:
    """Validate footprint + z-range and compute a full 3D volume.

    footrpint + [zmin, zmax] => prism (conceptually; we store footprint +
    scalar metrics rather than explicit triangulated walls).
    """
    poly = parse_footprint(footprint_data)
    ok, msg = validate_2d(poly)
    if not ok:
        raise GeometryError(msg)
    lo, hi = validate_z_range(zmin, zmax)
    metrics = footprint_metrics(poly)
    vol = compute_volume(metrics.area_m2, lo, hi)
    return Volume3D(
        footprint=poly,
        footprint_geojson=footprint_to_geojson(poly),
        zmin=lo,
        zmax=hi,
        height=height_of(lo, hi),
        area_m2=metrics.area_m2,
        volume_m3=vol,
        centroid=metrics.centroid or (0.0, 0.0),
        bbox=metrics.bbox,
    )


def polygon_from_ring_xy(x: Iterable[float], y: Iterable[float]) -> Polygon:
    """Build a closed polygon from parallel x/y arrays (e.g. CityJSON ring)."""
    coords = list(zip(x, y))
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return Polygon(coords)


def vertical_overlap_m(z1min: float, z1max: float, z2min: float, z2max: float) -> float:
    """Length of the shared z interval, 0.0 when disjoint."""
    return round(max(0.0, min(z1max, z2max) - max(z1min, z2min)), 3)


def z_intervals_touch(z1min: float, z1max: float, z2min: float, z2max: float) -> bool:
    """True when intervals are adjacent (share only a plane) => not a conflict."""
    return min(z1max, z2max) == max(z1min, z2min)
