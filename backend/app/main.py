"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .core.config import get_settings
from .core.logging import get_logger
from .db.models import Parcel
from .db.session import SessionLocal, create_schema

logger = get_logger("app.main")

settings = get_settings()


def _bootstrap() -> None:
    """Create schema and seed demo data (dev only, idempotent)."""
    create_schema()
    if not settings.seed_demo_data:
        logger.info("demo seed disabled")
        return
    db = SessionLocal()
    try:
        count = db.execute(select(Parcel).limit(1)).scalar_one_or_none()
        if count is None:
            from .services.seed import seed_all

            logger.info("database empty - seeding demo data")
            result = seed_all(db)
            logger.info("seeded", extra={"extra_fields": {
                "parcels": result["data"]["parcels_created"],
                "properties": result["data"]["properties_created"],
            }})
        else:
            logger.info("database already seeded; skipping")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: connecting to database", extra={"extra_fields": {"driver": settings.database_url.split(":")[0]}})
    _bootstrap()
    yield
    logger.info("shutdown complete")


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description=(
        "3D ULPIN Generation and Vertical Property Mapping (SIH 2026 Problem 26011) — "
        "demonstration framework. AI-derived geometries require human verification; "
        "synthetic data are not official land records; the 3D ULPIN extension is not an "
        "adopted national legal identifier."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.error("unhandled error", exc_info=exc)
    # never leak internal details in production
    detail = "An unexpected error occurred." if settings.is_production else f"{type(exc).__name__}: {exc}"
    return JSONResponse(status_code=500, content={"detail": detail})


# --- Routers (health at root; everything else versioned under /api/v1) ---
from .api.routes_misc import router as misc_router  # noqa: E402

app.include_router(misc_router)

API_PREFIX = settings.api_v1_prefix

from .api.routes_ai import router as ai_router  # noqa: E402
from .api.routes_auth import router as auth_router  # noqa: E402
from .api.routes_geo import router as geo_router  # noqa: E402
from .api.routes_uploads import router as uploads_router  # noqa: E402
from .api.routes_workflow import router as workflow_router  # noqa: E402

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(geo_router, prefix=API_PREFIX)
app.include_router(uploads_router, prefix=API_PREFIX)
app.include_router(workflow_router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
