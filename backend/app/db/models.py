"""SQLAlchemy 2.0 ORM models.

Schema design notes (see docs/DATA_MODEL.md for the full rationale):

- ``parcels``     : 2D surface parcels (the base identity).
- ``properties``  : single-table inheritance of the vertical hierarchy
                    (building -> floor -> unit, plus basement, parking,
                    underground_asset, volume) with a self-referencing
                    ``parent_id``. Keeps parent-child + topology checks simple
                    while still mapping 1:1 to the concept tables.
- ``users``/``audit_logs``/``uploads``/``submissions``/``geometry_versions``/
  ``validation_results``/``ai_predictions``/``ulpin_records``/``ownership_records``.

Spatial columns are stored as GeoJSON (canonical EPSG:4326) text plus scalar
metrics, so both SQLite (demo/tests) and PostgreSQL/PostGIS (production) work
with the same models. Migrations may add native geometry columns on PostGIS.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class User(TimestampMixin, Base):  # type: ignore[name-defined]
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), default="viewer", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Parcel(TimestampMixin, Base):  # type: ignore[name-defined]
    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    state_code: Mapped[str] = mapped_column(String(8), default="KA")
    district_code: Mapped[str] = mapped_column(String(16), default="BLR")
    locality: Mapped[str] = mapped_column(String(255), default="")
    footprint_geojson: Mapped[str] = mapped_column(Text)  # canonical EPSG:4326
    centroid_lon: Mapped[float] = mapped_column(Float, default=0.0)
    centroid_lat: Mapped[float] = mapped_column(Float, default=0.0)
    area_m2: Mapped[float] = mapped_column(Float, default=0.0)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="synthetic_demo")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    source_file: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="approved")
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    properties: Mapped[list["Property"]] = relationship(back_populates="parcel")


class Property(TimestampMixin, Base):  # type: ignore[name-defined]
    __tablename__ = "properties"
    __table_args__ = (UniqueConstraint("ref_key", name="uq_properties_ref_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    parcel_id: Mapped[int | None] = mapped_column(ForeignKey("parcels.id"), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)
    property_type: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")

    footprint_geojson: Mapped[str] = mapped_column(Text)
    zmin: Mapped[float | None] = mapped_column(Float, nullable=True)
    zmax: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_m2: Mapped[float] = mapped_column(Float, default=0.0)
    volume_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_lon: Mapped[float] = mapped_column(Float, default=0.0)
    centroid_lat: Mapped[float] = mapped_column(Float, default=0.0)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="synthetic_demo")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    source_file: Mapped[str] = mapped_column(String(255), default="")
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verification_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    ulpin: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    parcel: Mapped[Parcel | None] = relationship(back_populates="properties")
    parent: Mapped["Property | None"] = relationship(remote_side="Property.id", back_populates="children")
    children: Mapped[list["Property"]] = relationship(back_populates="parent")


class UlpinRecord(Base):  # type: ignore[name-defined]
    __tablename__ = "ulpin_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ulpin: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    base_parcel_key: Mapped[str] = mapped_column(String(64), index=True)
    kind_code: Mapped[str] = mapped_column(String(4))
    sequence: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(24), default="current")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GeometryVersion(Base):  # type: ignore[name-defined]
    __tablename__ = "geometry_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    footprint_geojson: Mapped[str] = mapped_column(Text)
    zmin: Mapped[float | None] = mapped_column(Float, nullable=True)
    zmax: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(String(255), default="")
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    previous_version_id: Mapped[int | None] = mapped_column(ForeignKey("geometry_versions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ValidationResult(Base):  # type: ignore[name-defined]
    __tablename__ = "validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(128), index=True)  # e.g. 'parcel:P00001' or 'global'
    state: Mapped[str] = mapped_column(String(16), index=True)
    summary: Mapped[dict] = mapped_column(JSON)
    issues: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Submission(Base):  # type: ignore[name-defined]
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="submitted", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Upload(Base):  # type: ignore[name-defined]
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(40), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(40), default="received", index=True)
    crs_epsg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    stored_path: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiPrediction(Base):  # type: ignore[name-defined]
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_type: Mapped[str] = mapped_column(String(40), index=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    input_ref: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str] = mapped_column(String(255), default="")
    model_version: Mapped[str] = mapped_column(String(64), default="")
    requires_verification: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLog(Base):  # type: ignore[name-defined]
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str] = mapped_column(String(64), default="")
    target_id: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OwnershipRecord(Base):  # type: ignore[name-defined]
    __tablename__ = "ownership_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    owner_name: Mapped[str] = mapped_column(String(255))
    share_pct: Mapped[float] = mapped_column(Float, default=100.0)
    document_ref: Mapped[str] = mapped_column(String(255), default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
