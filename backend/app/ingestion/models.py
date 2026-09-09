"""Common ingestion data structures.

Every imported spatial object carries provenance (source_type, source_name,
source_file) and optional AI metadata (model_name, confidence ...). Parsers
return normalized records that the import service later persists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.enums import PropertyType, SourceType


class FormatError(ValueError):
    """User-facing structured error for an ingestion problem."""


class UnsupportedFormatError(FormatError):
    """Raised for a format that is recognized but not enabled in the MVP."""


@dataclass
class ImportedRecord:
    kind: str  # 'parcel' | PropertyType value | 'building' | 'floor' | 'unit' ...
    external_id: str
    footprint: Any  # GeoJSON geometry or ring list, validated later
    zmin: float | None = None
    zmax: float | None = None
    height: float | None = None
    parcel_ref: str | None = None
    parent_ref: str | None = None
    name: str | None = None
    area_hint: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "external_id": self.external_id,
            "footprint": self.footprint,
            "zmin": self.zmin,
            "zmax": self.zmax,
            "height": self.height,
            "parcel_ref": self.parcel_ref,
            "parent_ref": self.parent_ref,
            "name": self.name,
            "attributes": self.attributes,
            "warnings": self.warnings,
        }


@dataclass
class ParseResult:
    format_name: str
    crs_epsg: int | None
    crs_note: str
    records: list[ImportedRecord]
    file_meta: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def record_count(self) -> int:
        return len(self.records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format_name,
            "crs": {"epsg": self.crs_epsg, "note": self.crs_note},
            "record_count": len(self.records),
            "records": [r.to_dict() for r in self.records],
            "file_meta": self.file_meta,
            "warnings": self.warnings,
        }


def map_kind(kind: str | None) -> str:
    """Map a loose kind/type label to a canonical kind string."""
    if not kind:
        return "parcel"
    k = str(kind).strip().lower()
    aliases = {
        "parcel": "parcel",
        "land": "parcel",
        "plot": "parcel",
        "building": "building",
        "buildings": "building",
        "floor": "floor",
        "unit": "unit",
        "apartment": "unit",
        "basement": "basement",
        "parking": "parking",
        "underground": "underground_asset",
        "underground_asset": "underground_asset",
        "utility": "underground_asset",
        "volume": "volume",
        "3d": "volume",
    }
    if k in aliases:
        return aliases[k]
    for pt in PropertyType:
        if pt.value == k:
            return pt.value
    return "parcel"


def to_property_type(kind: str) -> PropertyType | None:
    mapped = map_kind(kind)
    for pt in PropertyType:
        if pt.value == mapped:
            return pt
    return None
