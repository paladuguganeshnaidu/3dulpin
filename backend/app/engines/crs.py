"""CRS (Coordinate Reference System) handling.

The canonical internal CRS for cadastral footprints is EPSG:4326 (lon/lat),
because it is what CesiumJS and the browser map consume natively. Heights are
stored in metres above a local reference.

Source CRS is always preserved on provenance metadata. If a dataset has no CRS
and it cannot be safely inferred, we DO NOT guess -- we report that the CRS is
required so the surveyor can supply it (e.g. EPSG:4326, EPSG:32643 for
Bengaluru UTM 43N, or the local India projected codes).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# EPSG:4326 is the canonical display/storage CRS used by this project.
CANONICAL_EPSG = 4326
CANONICAL_NAME = "EPSG:4326 (WGS84 lon/lat)"

# A small allowlist of common CRS codes a surveyor may supply. It is not
# exhaustive; CRS metadata is preserved verbatim for any valid EPSG code.
COMMON_EPSG: dict[int, str] = {
    4326: "WGS84 geographic (lon/lat)",
    3857: "Web Mercator",
    32643: "WGS84 / UTM zone 43N (covers Bengaluru)",
    32644: "WGS84 / UTM zone 44N",
    7755: "WGS 84 / India NSF LCC",
    24378: "Kalyanpur 1880 / India zone IIa",
}


@dataclass
class CrsContext:
    """Result of CRS resolution for an incoming dataset."""

    epsg: int | None
    name: str
    resolved: bool
    note: str = ""
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "epsg": self.epsg,
            "name": self.name,
            "resolved": self.resolved,
            "note": self.note,
        }


class CrsRequiredError(ValueError):
    """Raised when no CRS can be determined and guessing is unsafe."""


def is_geographic_epsg(epsg: int | None) -> bool:
    """Return True when the code is in lon/lat degrees (e.g. 4326)."""
    return epsg in (4326, 4269, 4258) or (epsg is not None and 4000 <= epsg <= 4999)


def describe_epsg(epsg: int | None) -> str:
    if epsg is None:
        return "unknown"
    if epsg in COMMON_EPSG:
        return f"EPSG:{epsg} - {COMMON_EPSG[epsg]}"
    if is_geographic_epsg(epsg):
        return f"EPSG:{epsg} - geographic (lon/lat)"
    return f"EPSG:{epsg} - projected (metres)"


def normalize_epsg(raw: Any) -> int | None:
    """Best-effort parse of an EPSG code from JSON, int or str like 'EPSG:4326'."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if 1000 <= raw <= 99999 else None
    text = str(raw).strip().upper()
    if not text:
        return None
    # Handle "urn:ogc:def:crs:EPSG::4326", "EPSG:4326", "4326"
    if "EPSG" in text:
        # take the last integer group after EPSG
        import re

        m = re.findall(r"\d{4,5}", text)
        return int(m[0]) if m else None
    if text.isdigit():
        return int(text)
    return None


def resolve_crs(
    *,
    declared: Any = None,
    geojson: bool = False,
    bbox_geographic: bool = False,
) -> CrsContext:
    """Resolve the CRS for a dataset.

    Rules:
    - declared EPSG code wins.
    - GeoJSON per RFC 7946 defaults to EPSG:4326 (unless declared).
    - bbox_geographic => coords already look like lon/lat degrees -> 4326.
    - Otherwise: raise CrsRequiredError (never silently guess).
    """
    epsg = normalize_epsg(declared)
    if epsg is not None:
        return CrsContext(epsg=epsg, name=describe_epsg(epsg), resolved=True)
    if geojson:
        return CrsContext(
            epsg=4326,
            name=CANONICAL_NAME,
            resolved=True,
            note="GeoJSON coordinates are treated as EPSG:4326 (RFC 7946).",
        )
    if bbox_geographic:
        return CrsContext(
            epsg=4326,
            name=CANONICAL_NAME,
            resolved=True,
            note="Coordinates are within geographic lon/lat bounds; assumed EPSG:4326.",
        )
    raise CrsRequiredError(
        "Coordinate reference system required. Supply an EPSG code "
        "(e.g. EPSG:4326 for lon/lat or EPSG:32643 for Bengaluru UTM 43N)."
    )


def looks_geographic_bbox(minx: float, miny: float, maxx: float, maxy: float) -> bool:
    """Heuristic: is this bounding box plausibly lon/lat in degrees?"""
    return (
        -180.0 <= minx <= 180.0
        and -90.0 <= miny <= 90.0
        and -180.0 <= maxx <= 180.0
        and -90.0 <= maxy <= 90.0
    )
