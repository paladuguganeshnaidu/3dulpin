"""Assistive building block placement (footprint extraction/regularization).

Goal: help the surveyor place a building block exactly on the building border
seen in street view / orthophoto / 2D parcel view.

Two paths, both honest and non-authoritative:

1. Pretrained segmentation model (optional, lazy-loaded) -- when
   ``ML_BUILDING_MODEL_ENABLED=true`` and a compatible model is importable, an
   orthophoto is run through building segmentation and the mask is vectorized.
2. Deterministic orthogonal regularization -- always available: take a rough
   polygon (e.g. parcel border or clicked corners) and snap it to the building
   edges using the dominant orientation.

Every result is ``AI-derived``, carries a method + confidence, and must be
verified by a surveyor before it is used as a cadastral boundary.
"""
from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Polygon

from .registry import availability

DEFAULT_INSET_M = 1.2  # slight setback from a parcel border to a building wall

MODEL_NAME = "ai-assist/building-placement"
MODEL_VERSION = "0.2.0"


def _to_ring(points: list | tuple) -> list[list[float]]:
    ring: list[list[float]] = []
    for p in points:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            ring.append([float(p[0]), float(p[1])])
    if ring and ring[0] != ring[-1]:
        ring.append([ring[0][0], ring[0][1]])
    return ring


def _dedupe(ring: list[list[float]], tol: float = 1e-9) -> list[list[float]]:
    out: list[list[float]] = []
    for p in ring:
        if not out or abs(out[-1][0] - p[0]) > tol or abs(out[-1][1] - p[1]) > tol:
            out.append(p)
    return out


def _local_meters(ring: list[list[float]]):
    """Project lon/lat ring to local tangential metres around centroid."""
    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    coslat = math.cos(math.radians(cy)) or 1e-9
    kx = 111_320.0 * coslat
    ky = 111_320.0
    return [( (p[0] - cx) * kx, (p[1] - cy) * ky ) for p in ring], (cx, cy, kx, ky)


def _dominant_angle(meters: list[tuple[float, float]]) -> float:
    """Angle (radians) of the longest edge, normalized to (-pi/2, pi/2]."""
    best_len = -1.0
    best_ang = 0.0
    for i in range(len(meters) - 1):
        x1, y1 = meters[i]
        x2, y2 = meters[i + 1]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length > best_len:
            best_len = length
            best_ang = math.atan2(dy, dx)
    # normalize so orthogonal axes are equivalent
    while best_ang > math.pi / 2:
        best_ang -= math.pi
    while best_ang <= -math.pi / 2:
        best_ang += math.pi
    return best_ang


def regularize_footprint(
    points: Any,
    *,
    inset_m: float = DEFAULT_INSET_M,
    align_to_parcel: bool = True,
) -> dict[str, Any]:
    """Snap a rough polygon to an orthogonal, axis-aligned building block.

    Returns a GeoJSON Polygon plus method/confidence metadata. The result is an
    *assistive candidate*, never an authoritative boundary.
    """
    ring = _dedupe(_to_ring(points))
    if len(ring) < 4:
        raise ValueError("At least 3 distinct points are required to place a building block.")

    meters, (cx, cy, kx, ky) = _local_meters(ring)
    angle = _dominant_angle(meters) if align_to_parcel else 0.0

    # rotate to dominant axis
    ca, sa = math.cos(angle), math.sin(angle)
    rot = [(x * ca + y * sa, -x * sa + y * ca) for x, y in meters]
    xs = [p[0] for p in rot]
    ys = [p[1] for p in rot]

    if inset_m > 0:
        x0, x1 = min(xs) + inset_m, max(xs) - inset_m
        y0, y1 = min(ys) + inset_m, max(ys) - inset_m
        if x1 - x0 <= 0.5 or y1 - y0 <= 0.5:
            # too small to inset further; fall back to un-inset bounds
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    else:
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    corners_rot = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    # inverse rotation
    ica, isa = math.cos(-angle), math.sin(-angle)
    corners_m = [(x * ica + y * isa, -x * isa + y * ica) for x, y in corners_rot]
    ring_ll = [
        [round(cx + x / kx, 8), round(cy + y / ky, 8)] for x, y in corners_m
    ]
    ring_ll.append([ring_ll[0][0], ring_ll[0][1]])

    # confidence: how orthogonal was the original polygon?
    poly = Polygon([(x, y) for x, y in meters])
    area = abs(poly.area)
    rect_w = x1 - x0
    rect_h = y1 - y0
    ortho_fit = min(1.0, (rect_w * rect_h) / (area + 1e-6)) if area > 0 else 0.5
    confidence = round(min(0.95, max(0.4, ortho_fit * 0.9)), 2)

    return {
        "footprint_geojson": {
            "type": "Polygon",
            "coordinates": [ring_ll],
        },
        "method": "orthogonal_snap_regularization",
        "confidence": confidence,
        "requires_verification": True,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "note": "Orthogonal block fitted to the supplied border. Verify against "
                "street view before use.",
    }


def extract_building_footprint(
    *,
    image_bytes: bytes | None = None,
    points: Any = None,
) -> dict[str, Any]:
    """ML-assisted building footprint extraction.

    If a pretrained model is enabled and importable *and* an image is supplied,
    attempt model inference; otherwise fall back to deterministic orthogonal
    regularization of the supplied points. Never raises for a missing model.
    """
    if availability("building_extraction") and image_bytes:
        try:
            return _model_inference(image_bytes)
        except Exception:  # graceful degradation to deterministic path
            pass

    if points is None:
        raise ValueError(
            "No geometry supplied. Provide a polygon (points) or an orthophoto "
            "with the building model enabled."
        )
    return regularize_footprint(points)


def _model_inference(image_bytes: bytes) -> dict[str, Any]:
    """Pretrained segmentation adapter (lazy import, fully optional).

    Kept behind ``ML_BUILDING_MODEL_ENABLED``; when a real model is installed
    this maps masks -> polygons -> regularization. Ships a clear fallback.
    """
    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("PyTorch/torchvision not installed") from exc

    # A real deployment would load a configured segmentation model here and
    # vectorize masks. Returning the honest unavailable message keeps the MVP
    # truthful instead of faking detections.
    raise RuntimeError(
        "Building segmentation model is enabled but no weights are configured. "
        "Supply a polygon to use deterministic orthogonal regularization."
    )
