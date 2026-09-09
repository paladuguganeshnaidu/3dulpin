"""Pytest shared fixtures.

Sets a fresh file-based SQLite database (seeded via app startup) before any
app import so settings/engine pick it up.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_FILE = BACKEND_DIR / "data" / "test_pytest.db"
if DB_FILE.exists():
    DB_FILE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.as_posix()}"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["SEED_DEMO_USERS"] = "true"
os.environ["APP_ENV"] = "test"

sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

DEMO_CREDENTIALS = {
    "admin": ("admin@demo.local", "Admin@12345"),
    "surveyor": ("surveyor@demo.local", "Survey@12345"),
    "viewer": ("viewer@demo.local", "Viewer@12345"),
}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    def _make(role: str):
        email, pw = DEMO_CREDENTIALS[role]
        r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make


@pytest.fixture(scope="session")
def admin_headers(auth_headers):
    return auth_headers("admin")


@pytest.fixture(scope="session")
def surveyor_headers(auth_headers):
    return auth_headers("surveyor")


@pytest.fixture(scope="session")
def viewer_headers(auth_headers):
    return auth_headers("viewer")
