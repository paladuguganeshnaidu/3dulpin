"""Misc routes: health checks + info."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..db.session import engine, get_db
from ..services.validation import latest_global_state

router = APIRouter(tags=["misc"])


@router.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "version": "0.1.0", "name": settings.project_name}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # structured, no raw traceback
        return {"status": "error", "database": engine.url.drivername, "detail": f"{type(exc).__name__}"}
    return {"status": db_status, "database": engine.url.drivername, "detail": ""}


@router.get("/info")
def info(db: Session = Depends(get_db)):
    state = latest_global_state(db)
    return {
        "name": "India 3D ULPIN API",
        "version": "0.1.0",
        "demo_mode": True,
        "notice": "Demonstration dataset — not an official land record.",
        "latest_validation_state": state,
    }
