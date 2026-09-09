"""Model registry: metadata for ML components and their availability.

Model metadata describes name/version/source/license/input/output/confidence
semantics. Models are never auto-downloaded at startup; heavy ones load lazily
and only when explicitly enabled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MODELS: dict[str, dict[str, Any]] = {
    "building_extraction": {
        "name": "ai-assist/building-extraction",
        "version": "0.1.0",
        "source": "Hugging Face ecosystem / torchvision (configurable)",
        "license": "model-specific; check before production use",
        "input_type": "image / orthophoto / compatible raster",
        "output": "building candidate polygons + confidence",
        "confidence_semantics": "probability that a segmented region is a building footprint",
        "download_size_hint_mb": None,
        "enabled_env": "ML_BUILDING_MODEL_ENABLED",
    },
    "height_estimation": {
        "name": "heuristic/height-estimation",
        "version": "1.0.0",
        "source": "built-in deterministic (DSM/DEM or metadata)",
        "license": "MIT (project)",
        "input_type": "elevation surfaces or structured metadata",
        "output": "estimated building height + method",
        "confidence_semantics": "derived from method quality; low when only inferred",
        "download_size_hint_mb": 0,
        "enabled_env": None,
    },
    "floor_segmentation": {
        "name": "heuristic/floor-estimation",
        "version": "1.0.0",
        "source": "built-in deterministic (floor count x height)",
        "license": "MIT (project)",
        "input_type": "height + optional floor count",
        "output": "estimated floor levels (explicit vs estimated)",
        "confidence_semantics": "explicit = high; estimated = medium; never recovers actual unit boundaries from photos",
        "download_size_hint_mb": 0,
        "enabled_env": None,
    },
    "anomaly_detection": {
        "name": "rules/anomaly-detection",
        "version": "1.0.0",
        "source": "built-in deterministic GIS rules",
        "license": "MIT (project)",
        "input_type": "validated geometries + attributes",
        "output": "anomaly list with plain-language explanations",
        "confidence_semantics": "rule-based => deterministic when triggered",
        "download_size_hint_mb": 0,
        "enabled_env": None,
    },
}


def registry() -> list[dict[str, Any]]:
    out = []
    for key, meta in MODELS.items():
        item = dict(meta)
        item["key"] = key
        item["available"] = availability(key)
        out.append(item)
    return out


def availability(key: str) -> bool:
    """Whether a model is currently usable. Heavy model requires explicit env."""
    meta = MODELS.get(key, {})
    env_flag = meta.get("enabled_env")
    if not env_flag:
        return True  # deterministic heuristics always available
    import os

    return os.getenv(env_flag, "false").lower() in ("1", "true", "yes")
