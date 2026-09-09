"""Shared domain enums (roles, source types, statuses, validation states)."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class Role(StrEnum):
    ADMIN = "admin"
    SURVEYOR = "surveyor"
    VIEWER = "viewer"


class PropertyType(StrEnum):
    PARCEL = "parcel"
    BUILDING = "building"
    FLOOR = "floor"
    UNIT = "unit"
    BASEMENT = "basement"
    PARKING = "parking"
    UNDERGROUND_ASSET = "underground_asset"
    VOLUME = "volume"


class SourceType(StrEnum):
    OFFICIAL_REFERENCE = "official_reference"
    OPEN_DATA = "open_data"
    SURVEY_UPLOADED = "survey_uploaded"
    IMPORTED_3D = "imported_3d"
    AI_DERIVED = "ai_derived"
    SYNTHETIC_DEMO = "synthetic_demo"


class PropertyStatus(StrEnum):
    DRAFT = "draft"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class ValidationState(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"


class AuditAction(StrEnum):
    LOGIN = "login"
    UPLOAD = "upload"
    GEOMETRY_CREATE = "geometry_create"
    GEOMETRY_MODIFY = "geometry_modify"
    AI_ANALYSIS = "ai_analysis"
    VALIDATION = "validation"
    SUBMISSION = "submission"
    APPROVAL = "approval"
    REJECTION = "rejection"


class UploadState(StrEnum):
    RECEIVED = "received"
    DETECTED = "detected"
    VALIDATED = "validated"
    CRS_RESOLVED = "crs_resolved"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    GEOMETRY_PROCESSED = "geometry_processed"
    TOPOLOGY_CHECKED = "topology_checked"
    PREVIEWED = "previewed"
    COMMITTED = "committed"
    ERROR = "error"
