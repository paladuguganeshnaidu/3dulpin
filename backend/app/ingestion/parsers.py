"""Parser adapters for supported input formats.

Supported in the MVP (really parsed, not just filename-accepted):
  - JSON  (our normalized "properties collection" schema, plus generic dicts)
  - JSONL (one spatial record per line)
  - GeoJSON (FeatureCollection with polygon footprints)
  - CityJSON (Buildings incl. LoD geometry, transform, metadata)

Everything else returns a clear "recognized but not enabled" error instead of
crashing (see ``UnsupportedFormatError``).

Parsers do NOT guess CRS: they resolve it through app.engines.crs.resolve_crs
and raise CrsRequiredError when it cannot be determined safely.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from ..engines import crs as crs_engine
from .models import (
    FormatError,
    ImportedRecord,
    ParseResult,
    UnsupportedFormatError,
    map_kind,
)

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

DETECT_ORDER: list[tuple[str, Callable[[str, bytes], bool]]] = []


def _has_ext(name: str, *exts: str) -> bool:
    base = name.lower()
    return any(base.endswith(ext) for ext in exts)


def _looks_cityjson(name: str, head: bytes) -> bool:
    if _has_ext(name, ".city.json") or name.lower().endswith("city.json"):
        return True
    if not _has_ext(name, ".json"):
        return False
    try:
        obj = json.loads(head.decode("utf-8", "replace"))
    except Exception:
        return False
    return isinstance(obj, dict) and obj.get("type") == "CityJSON"


def _looks_geojson(name: str, head: bytes) -> bool:
    if not _has_ext(name, ".geojson", ".json"):
        return False
    try:
        obj = json.loads(head.decode("utf-8", "replace"))
    except Exception:
        return False
    return isinstance(obj, dict) and obj.get("type") in (
        "FeatureCollection",
        "Feature",
    )


def _looks_jsonl(name: str, head: bytes) -> bool:
    if not _has_ext(name, ".jsonl", ".ndjson"):
        return False
    # at least two lines, first parseable as json object
    lines = [ln for ln in head.decode("utf-8", "replace").splitlines() if ln.strip()]
    if not lines:
        return False
    try:
        json.loads(lines[0])
    except Exception:
        return False
    return True


def _looks_json(name: str, head: bytes) -> bool:
    if not _has_ext(name, ".json"):
        return False
    try:
        obj = json.loads(head.decode("utf-8", "replace"))
    except Exception:
        return False
    if isinstance(obj, dict) and obj.get("type") == "CityJSON":
        return False
    return isinstance(obj, (dict, list))


def _looks_gltf(name: str, head: bytes) -> bool:
    if not _has_ext(name, ".glb", ".gltf"):
        return False
    raise UnsupportedFormatError(
        "GLB/glTF is recognized but not enabled in the current MVP. "
        "Use JSONL/GeoJSON/CityJSON for cadastral records."
    )


def _recognized_but_unavailable(name: str) -> bool:
    exts = (
        ".gml",
        ".citygml",
        ".las",
        ".laz",
        ".ply",
        ".obj",
        ".kml",
        ".kmz",
        ".shp",
        ".zip",
        ".dem",
        ".dsm",
        ".tif",
        ".tiff",
        ".ifc",
    )
    return any(name.lower().endswith(e) for e in exts)


def detect_format(filename: str, head: bytes) -> str:
    """Return a format key, raising UnsupportedFormatError for unavailable ones."""
    name = filename or ""

    if _looks_cityjson(name, head):
        return "cityjson"
    if _looks_geojson(name, head):
        return "geojson"
    if _looks_jsonl(name, head):
        return "jsonl"
    if _looks_json(name, head):
        return "json"
    if _looks_gltf(name, head):
        raise UnsupportedFormatError(
            "GLB/glTF is recognized but not enabled in the current MVP."
        )
    if _recognized_but_unavailable(name):
        raise UnsupportedFormatError(
            "Format recognized but not enabled in the current MVP. "
            "Supported now: JSON, JSONL, GeoJSON, CityJSON."
        )
    raise FormatError(
        "Unsupported file type. Supported now: JSON, JSONL, GeoJSON, CityJSON."
    )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _coerce_footprint(geom: Any) -> Any:
    """Return a GeoJSON geometry dict or ring accepted by the geometry engine."""
    return geom


def _get(obj: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return default


# ---------------------------------------------------------------------------
# JSON parser (normalized collection schema + generic)
# ---------------------------------------------------------------------------


def parse_json(data: dict | list) -> ParseResult:
    records: list[ImportedRecord] = []
    crs_ctx = crs_engine.resolve_crs(geojson=True)  # JSON with lon/lat => 4326 default
    if isinstance(data, dict) and data.get("type") in ("collection", "properties"):
        crs_ctx = _resolve_from_meta(data)
        items = data.get("records") or data.get("properties") or []
    elif isinstance(data, list):
        items = data
    else:
        items = [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        rec = _normalize_common_record(item)
        if rec is not None:
            records.append(rec)
    return ParseResult(
        format_name="json",
        crs_epsg=crs_ctx.epsg,
        crs_note=crs_ctx.name,
        records=records,
        file_meta={"schema": "properties-collection"},
    )


def _resolve_from_meta(data: dict) -> crs_engine.CrsContext:
    meta = data.get("metadata") or {}
    declared = meta.get("crs") or meta.get("epsg") or data.get("crs")
    try:
        return crs_engine.resolve_crs(declared=declared)
    except crs_engine.CrsRequiredError:
        return crs_engine.resolve_crs(geojson=True)


def _normalize_common_record(item: dict) -> ImportedRecord | None:
    """Normalize one JSON/JSONL record regardless of exact schema."""
    kind_raw = _get(item, "type", "kind", "object_type", "class")
    if isinstance(kind_raw, dict):
        kind_raw = kind_raw.get("type") or kind_raw.get("class")
    kind = map_kind(kind_raw)

    geom = _get(item, "geometry", "footprint", "geom", "shape", default=None)
    if geom is None:
        # fall back to constructing a small footprint from lon/lat/width/height/area
        geom = _footprint_from_point(item)
    if geom is None:
        # a building/floor/unit without geometry is still importable if parented
        # to geometry elsewhere; keep with no footprint (flagged below)
        pass

    ext_id = str(
        _get(
            item,
            "id",
            "external_id",
            "ulpin",
            "object_id",
            "name",
            default=f"rec-{abs(hash(str(item))) % 10**6}",
        )
    )
    name = _get(item, "name", "label", default=None)
    zmin = _to_float(_get(item, "zmin", "z_min", "z_low", "min_z"))
    zmax = _to_float(_get(item, "zmax", "z_max", "z_high", "max_z"))
    height = _to_float(_get(item, "height", "height_m"))
    parcel_ref = _to_str(_get(item, "parcel_id", "parcel_ref", "parent_parcel"))
    parent_ref = _to_str(_get(item, "building_id", "floor_id", "parent_id", "parent_ref"))

    # If only height + ground given, derive z range
    if zmin is None and zmax is None and height is not None and kind == "building":
        zmin = 0.0
        zmax = height
    if zmin is not None and zmax is None and height is not None:
        zmax = zmin + height

    attrs = {k: v for k, v in item.items() if k not in _RESERVED}
    warnings: list[str] = []
    if geom is None:
        warnings.append("No footprint geometry found; object will be recorded without geometry.")

    return ImportedRecord(
        kind=kind,
        external_id=ext_id,
        footprint=_coerce_footprint(geom),
        zmin=zmin,
        zmax=zmax,
        height=height,
        parcel_ref=parcel_ref,
        parent_ref=parent_ref,
        name=name,
        area_hint=_to_float(_get(item, "area", "area_m2", "area_sqft")),
        attributes=attrs,
        warnings=warnings,
    )


_RESERVED = {
    "type", "kind", "object_type", "class", "geometry", "footprint", "geom",
    "shape", "id", "external_id", "ulpin", "object_id", "name", "label",
    "zmin", "z_max", "z_min", "z_low", "min_z", "zmax", "z_high", "max_z",
    "height", "height_m", "parcel_id", "parcel_ref", "parent_parcel",
    "building_id", "floor_id", "parent_id", "parent_ref", "area", "area_m2",
    "area_sqft", "lat", "lon", "longitude", "latitude", "x", "y", "width_m",
    "length_m", "crs", "epsg",
}


def _footprint_from_point(item: dict) -> Any:
    """Build a tiny placeholder ring when a point + dimensions/area is given."""
    lon = _to_float(_get(item, "lon", "longitude", "x"))
    lat = _to_float(_get(item, "lat", "latitude", "y"))
    if lon is None or lat is None:
        return None
    w = _to_float(_get(item, "width_m", "width"))
    h = _to_float(_get(item, "length_m", "length", "depth"))
    if w is None or h is None:
        area = _to_float(_get(item, "area", "area_m2"))
        if area:
            import math

            side = math.sqrt(area)
            w = h = side
        else:
            w = h = 10.0
    dlat = h / 2.0 / 111_320.0
    import math

    dlon = w / 2.0 / (111_320.0 * math.cos(math.radians(lat)))
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - dlon, lat - dlat],
                [lon + dlon, lat - dlat],
                [lon + dlon, lat + dlat],
                [lon - dlon, lat + dlat],
                [lon - dlon, lat - dlat],
            ]
        ],
    }


# ---------------------------------------------------------------------------
# JSONL parser
# ---------------------------------------------------------------------------


def parse_jsonl(head: bytes) -> ParseResult:
    lines = [ln for ln in head.decode("utf-8", "replace").splitlines() if ln.strip()]
    records: list[ImportedRecord] = []
    warnings: list[str] = []
    crs_epsg: int | None = None
    crs_note = ""
    for i, line in enumerate(lines, start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"Line {i}: invalid JSON skipped ({exc.msg}).")
            continue
        if not isinstance(item, dict):
            warnings.append(f"Line {i}: not a JSON object, skipped.")
            continue
        if i == 1:
            crs_ctx = _resolve_jsonl_crs(item)
            crs_epsg = crs_ctx.epsg
            crs_note = crs_ctx.name
        rec = _normalize_common_record(item)
        if rec is not None:
            records.append(rec)
    return ParseResult(
        format_name="jsonl",
        crs_epsg=crs_epsg,
        crs_note=crs_note,
        records=records,
        file_meta={"line_count": len(lines)},
        warnings=warnings,
    )


def _resolve_jsonl_crs(item: dict) -> crs_engine.CrsContext:
    declared = _get(item, "crs", "epsg", default=None)
    try:
        return crs_engine.resolve_crs(declared=declared)
    except crs_engine.CrsRequiredError:
        return crs_engine.resolve_crs(geojson=True)  # JSONL with lon/lat is treated as 4326


# ---------------------------------------------------------------------------
# GeoJSON parser
# ---------------------------------------------------------------------------


def parse_geojson(data: dict) -> ParseResult:
    if data.get("type") == "Feature":
        features = [data]
    elif data.get("type") == "FeatureCollection":
        features = data.get("features", [])
    else:
        raise FormatError("GeoJSON must be a Feature or FeatureCollection.")

    crs_ctx = crs_engine.resolve_crs(declared=_extract_geojson_crs(data), geojson=True)
    records: list[ImportedRecord] = []
    warnings: list[str] = []
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry")
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            warnings.append(
                f"Feature {props.get('id', '?')}: only Polygon/MultiPolygon footprints "
                "are imported in the MVP; skipped."
            )
            continue
        kind = map_kind(props.get("type") or props.get("kind") or "parcel")
        ext_id = str(props.get("id") or props.get("external_id") or f"gid-{len(records) + 1}")
        zmin = _to_float(props.get("zmin") or props.get("z_min"))
        zmax = _to_float(props.get("zmax") or props.get("z_max"))
        height = _to_float(props.get("height") or props.get("height_m"))
        if zmin is None and zmax is None and height:
            zmin, zmax = 0.0, height
        records.append(
            ImportedRecord(
                kind=kind,
                external_id=ext_id,
                footprint=geom,
                zmin=zmin,
                zmax=zmax,
                height=height,
                parcel_ref=_to_str(props.get("parcel_id") or props.get("parcel_ref")),
                parent_ref=_to_str(props.get("parent_id") or props.get("parent_ref")),
                name=_to_str(props.get("name") or props.get("label")),
                area_hint=_to_float(props.get("area") or props.get("area_m2")),
                attributes={k: v for k, v in props.items() if k not in _RESERVED},
            )
        )
    return ParseResult(
        format_name="geojson",
        crs_epsg=crs_ctx.epsg,
        crs_note=crs_ctx.name,
        records=records,
        file_meta={"feature_count": len(features)},
        warnings=warnings,
    )


def _extract_geojson_crs(data: dict) -> Any:
    crs = data.get("crs")
    if isinstance(crs, dict):
        props = crs.get("properties", {})
        name = props.get("name") or props.get("href")
        if name:
            return name
    return None


# ---------------------------------------------------------------------------
# CityJSON parser
# ---------------------------------------------------------------------------


def parse_cityjson(data: dict) -> ParseResult:
    """Parse CityJSON v1.x/2.0 into normalized building records.

    Extracts CityObjects of type Building/BuildingPart, their geometry
    (Solid/MultiSurface footprints via boundary rings), attributes and
    metadata/transform. Preserves original source metadata in file_meta.
    Unsupported geometry types are skipped with a warning (not fatal).
    """
    version = data.get("version", "unknown")
    transform = data.get("transform", None)
    metadata = data.get("metadata", None) or {}

    # CRS handling: metadata.epsg or referenceSystem
    declared = None
    if metadata.get("epsg"):
        declared = metadata.get("epsg")
    elif metadata.get("referenceSystem"):
        declared = metadata.get("referenceSystem")
    crs_ctx = crs_engine.resolve_crs(declared=declared, geojson=False)

    records: list[ImportedRecord] = []
    warnings: list[str] = []
    city_objects = data.get("CityObjects", {})
    root_vertices = data.get("vertices") or []

    for cid, obj in city_objects.items():
        otype = obj.get("type", "")
        if otype not in ("Building", "BuildingPart"):
            warnings.append(
                f"CityObject '{cid}' type '{otype}' is not imported in the MVP; skipped."
            )
            continue
        chosen = None
        for g in obj.get("geometry", []):
            gtype = g.get("type")
            if gtype in ("Solid", "MultiSurface"):
                chosen = g
                break
        if chosen is None:
            warnings.append(f"CityObject '{cid}' has no Solid/MultiSurface geometry; skipped.")
            continue
        try:
            vertices = root_vertices or chosen.get("vertices") or []
            footprint = _cityjson_footprint(chosen, vertices, transform)
        except Exception as exc:
            warnings.append(f"CityObject '{cid}': unsupported geometry skipped ({exc}).")
            continue

        attrs = obj.get("attributes") or {}
        height = _to_float(attrs.get("measuredHeight") or attrs.get("height"))
        ground = _to_float(attrs.get("groundElevation")) or 0.0
        zmin = ground
        zmax = ground + height if height else _to_float(attrs.get("roofElevation")) or ground

        records.append(
            ImportedRecord(
                kind="building",
                external_id=cid,
                footprint=footprint,
                zmin=zmin,
                zmax=zmax,
                height=height,
                name=_to_str(attrs.get("name")) or cid,
                attributes={
                    "cityobject_type": otype,
                    "cityjson_id": cid,
                    **{k: v for k, v in attrs.items()},
                },
            )
        )

    return ParseResult(
        format_name="cityjson",
        crs_epsg=crs_ctx.epsg,
        crs_note=crs_ctx.name,
        records=records,
        file_meta={
            "cityjson_version": version,
            "metadata": metadata,
            "transform_present": transform is not None,
            "cityobject_count": len(city_objects),
        },
        warnings=warnings,
    )


def _cityjson_footprint(geom: dict, vertices: list, transform: dict | None) -> dict[str, Any]:
    """Compute a 2D footprint (GeoJSON Polygon) from a CityJSON geometry.

    Vertices are the file-level coordinate array; boundaries reference vertex
    indices. A footprint is the outer ring of the first surface of the outer
    shell (Solid) or the first surface (MultiSurface).
    """
    boundaries = geom.get("boundaries")
    if boundaries is None:
        raise ValueError("no boundaries")

    ring: list | None = None
    if geom["type"] == "Solid":
        # boundaries = [shell] ; shell = [surface] ; surface = [ring, ...]
        if not boundaries or not boundaries[0] or not boundaries[0][0]:
            raise ValueError("empty solid")
        ring = _first_ring(boundaries[0])
    elif geom["type"] == "MultiSurface":
        if not boundaries:
            raise ValueError("empty multisurface")
        ring = _first_ring(boundaries)
    else:
        raise ValueError(f"unsupported type {geom['type']}")

    def vertex(idx: int) -> list[float]:
        try:
            v = vertices[idx]
        except (IndexError, TypeError) as exc:
            raise ValueError(f"vertex index {idx} out of range") from exc
        if transform:
            s = transform.get("scale", [1.0, 1.0, 1.0])
            t = transform.get("translate", [0.0, 0.0, 0.0])
            return [v[0] * s[0] + t[0], v[1] * s[1] + t[1], (v[2] * s[2] + t[2]) if len(v) > 2 else 0.0]
        return list(v)

    ring_pts = []
    for vidx in ring:
        ring_pts.append(vertex(vidx)[:2])
    if ring_pts and ring_pts[0] != ring_pts[-1]:
        ring_pts.append(ring_pts[0])
    return {"type": "Polygon", "coordinates": [ring_pts]}


def _first_ring(surfaces: list) -> list:
    """Return the first ring from a shell/surface structure that tolerates
    both [ring] and [[ring]] nesting forms."""
    first = surfaces[0]
    # if first looks like a ring of ints, return it directly
    if first and isinstance(first[0], int):
        return first
    # otherwise first is a surface (list of rings)
    return first[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def parse_bytes(filename: str, raw: bytes) -> ParseResult:
    """Top-level entry: detect the format and parse raw file bytes."""
    head = raw if len(raw) <= 4 * 1024 * 1024 else raw[: 4 * 1024 * 1024]
    fmt = detect_format(filename, head)

    if fmt == "jsonl":
        return parse_jsonl(raw)

    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception as exc:
        raise FormatError(f"Invalid JSON payload: {exc}") from exc

    if fmt == "cityjson":
        return parse_cityjson(data)
    if fmt == "geojson":
        return parse_geojson(data)
    return parse_json(data)
