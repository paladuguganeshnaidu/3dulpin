"""SQLAlchemy engine/session helpers.

Works with SQLite (default, zero external services) and PostgreSQL/PostGIS
(when DATABASE_URL points at one). Spatial values are stored as GeoJSON text
plus scalar metrics so the same models run on both backends; a PostGIS
deployment additionally enables ST_* functions via migrations (see docs).
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(db_url: str | None = None):
    settings = get_settings()
    url = db_url or settings.database_url
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # ensure parent dir exists for file-based sqlite
        if url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "", 1)
            if path and path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_conn, _record):  # pragma: no cover - trivial
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db():
    """FastAPI dependency yielding a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_schema() -> None:
    """Create all tables (for demo/tests). Use Alembic for production."""
    from . import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)
