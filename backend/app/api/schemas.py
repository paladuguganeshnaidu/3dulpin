"""Pydantic schemas (also power the OpenAPI docs)."""
from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiError(BaseModel):
    detail: str = Field(..., description="Human readable error message")
    code: str = "error"


class HealthOut(BaseModel):
    status: str
    version: str
    name: str


class HealthDbOut(BaseModel):
    status: str
    database: str
    detail: str = ""


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    email: str
    username: str
    full_name: str = ""
    password: str = Field(min_length=8)


class PropertyCreateIn(BaseModel):
    """Surveyor create-property payload."""

    property_type: Literal[
        "building", "floor", "unit", "basement", "parking", "underground_asset", "volume"
    ] = "volume"
    parcel_id: str
    parent_id: str | None = None
    name: str = ""
    footprint_geojson: Any  # Polygon geometry or ring
    zmin: float | None = None
    zmax: float | None = None


class SubmitIn(BaseModel):
    note: str = ""


class ReviewIn(BaseModel):
    action: Literal["approve", "reject", "return"]
    note: str = ""


class SearchOut(BaseModel):
    query: str
    results: list[dict[str, Any]]


class UlpinSearch(BaseModel):
    ulpin: str


class RegionOut(BaseModel):
    id: str
    name: str
    kind: Literal["country", "state", "city", "pilot"]
    center: dict[str, float]
    description: str = ""


class MessageOut(BaseModel):
    message: str


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
