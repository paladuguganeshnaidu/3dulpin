"""Upload/import routes: multipart preview + commit."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.enums import Role, SourceType, UploadState
from ..db.models import Upload
from ..db.session import get_db
from ..ingestion.models import FormatError, UnsupportedFormatError
from ..ingestion.parsers import parse_bytes
from ..services.audit import audit
from ..services.imports import commit_import
from .deps import get_current_user, require_roles

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_EXTS = {"json", "jsonl", "geojson", "glb", "gltf", "cityjson"}
# Recognized but not enabled in the MVP => forwarded to the parser so it can
# return the informative "recognized but not enabled" message.
RECOGNIZED_EXTS = ALLOWED_EXTS | {
    "gml", "citygml", "las", "laz", "ply", "obj", "kml", "kmz", "shp", "zip",
    "dem", "dsm", "tif", "tiff", "ifc",
}


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]


@router.post("/preview")
async def preview_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    """Step 1-9 of the import workflow: detect, validate, parse, normalize,
    compute geometry, then return a preview. Nothing is committed."""
    settings = get_settings()
    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB limit.")
    filename = _safe_name(file.filename or "upload")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in RECOGNIZED_EXTS:
        raise HTTPException(415, "Unsupported file type. Supported: JSON, JSONL, GeoJSON, CityJSON, GLB/glTF.")

    try:
        parsed = parse_bytes(filename, raw)
    except UnsupportedFormatError as exc:
        raise HTTPException(422, str(exc))
    except FormatError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:  # structured, not raw
        raise HTTPException(422, f"Could not parse file: {type(exc).__name__}")

    # keep the file bytes so a later commit can reuse the same parse
    token = "up-" + uuid.uuid4().hex[:10]
    dirpath = settings.upload_path / token
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / filename
    path.write_bytes(raw)

    row = Upload(
        user_id=user.id,
        filename=filename,
        format=parsed.format_name,
        size_bytes=len(raw),
        state=UploadState.PREVIEWED.value,
        crs_epsg=parsed.crs_epsg,
        record_count=parsed.record_count,
        stored_path=str(path),
        warnings=parsed.warnings,
    )
    db.add(row)
    db.commit()

    return {
        "token": token,
        "upload_id": row.id,
        "filename": filename,
        "format": parsed.format_name,
        "crs": {"epsg": parsed.crs_epsg, "note": parsed.crs_note},
        "record_count": parsed.record_count,
        "warnings": parsed.warnings,
        "file_meta": parsed.file_meta,
        # lightweight preview records (kinds + ids + z) without full geometry blobs
        "records": [
            {"kind": r.kind, "external_id": r.external_id,
             "zmin": r.zmin, "zmax": r.zmax,
             "parcel_ref": r.parcel_ref, "parent_ref": r.parent_ref,
             "warnings": r.warnings}
            for r in parsed.records
        ],
        "notice": "Preview only — nothing has been committed yet.",
    }


@router.post("/{token}/commit")
def commit_preview(
    token: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    """Step 10: import the previewed file."""
    settings = get_settings()
    upload = (
        db.query(Upload)
        .filter(Upload.user_id == user.id, Upload.stored_path.like(f"%{token}%"))
        .order_by(Upload.id.desc())
        .first()
    )
    if upload is None:
        raise HTTPException(404, "Preview token not found for this user.")
    path = Path(upload.stored_path)
    if not path.exists():
        raise HTTPException(410, "Stored file no longer available.")
    raw = path.read_bytes()
    try:
        parsed = parse_bytes(upload.filename, raw)
    except Exception as exc:
        raise HTTPException(422, str(exc))
    upload.state = UploadState.COMMITTED.value
    db.commit()
    source_type = SourceType.SURVEY_UPLOADED
    result = commit_import(
        db,
        user_id=user.id,
        parse_result=parsed,
        filename=upload.filename,
        source_type=source_type,
        source_name=user.email,
    )
    return result


@router.get("/")
def list_uploads(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Upload).filter(Upload.user_id == user.id).order_by(Upload.id.desc()).limit(100).all()
    return {"items": [
        {"id": u.id, "filename": u.filename, "format": u.format, "state": u.state,
         "record_count": u.record_count, "crs_epsg": u.crs_epsg,
         "created_at": u.created_at.isoformat(), "warnings": u.warnings}
        for u in rows], "total": len(rows)}
