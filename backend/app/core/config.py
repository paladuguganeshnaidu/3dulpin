"""Application configuration via environment variables.

Everything is environment-driven; no secrets are hardcoded in the repo.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
ROOT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General
    app_env: str = "development"
    debug: bool = False
    project_name: str = "India 3D ULPIN"
    api_v1_prefix: str = "/api/v1"

    # Database
    # sqlite default keeps demo/tests runnable with zero external services.
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / '3dulpin.db').as_posix()}"
    database_backend: str = "sqlite"  # sqlite | postgis (informational for migrations)

    # Auth
    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    cors_origin_host: str = ""

    # Uploads
    max_upload_mb: int = 50
    upload_dir: str = "./data/uploads"
    allowed_upload_types: str = "json,jsonl,geojson,glb,gltf,cityjson"

    # Demo seeding
    seed_demo_data: bool = True
    seed_demo_users: bool = True

    # LLM assistant (optional)
    openrouter_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "OPENROUTER_API"),
    )
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    # ML (optional)
    ml_building_model_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if self.cors_origin_host.strip():
            host = self.cors_origin_host.strip()
            if not host.startswith(("http://", "https://")):
                host = "https://" + host
            if host not in origins:
                origins.append(host.rstrip("/"))
        return origins

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
