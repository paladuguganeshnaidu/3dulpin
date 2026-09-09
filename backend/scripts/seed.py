"""Seed / initialize the backend database for local development.

From backend/:
    ..\\.venv\\Scripts\\python.exe scripts/seed.py            # schema + demo users + demo data
    ..\\.venv\\Scripts\\python.exe scripts/seed.py --users-only

Development-only demo accounts (NEVER use in production):
    admin@demo.local     / Admin@12345      (admin)
    surveyor@demo.local  / Survey@12345     (surveyor)
    viewer@demo.local    / Viewer@12345     (viewer)

Uses DATABASE_URL from the environment (default: sqlite ./data/3dulpin.db).
Set DATABASE_URL=postgresql+psycopg://... for a PostGIS deployment.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    ap = argparse.ArgumentParser(description="Initialize and seed the 3D ULPIN database.")
    ap.add_argument("--users-only", action="store_true", help="Only create the demo users.")
    ap.add_argument("--no-users", action="store_true", help="Only seed demo geometry data.")
    args = ap.parse_args()

    from app.db.session import SessionLocal, create_schema
    from app.services.seed import seed_all, seed_demo_dataset, seed_users

    print("Creating schema ...")
    create_schema()
    db = SessionLocal()
    try:
        if args.users_only:
            print(seed_users(db))
        elif args.no_users:
            print("Seeding demo geometry ...")
            from app.services.seed import seed_demo_dataset

            print(seed_demo_dataset(db))
        else:
            print("Seeding demo users + geometry ...")
            result = seed_all(db)
            print(f"users: {result['users']}")
            print(f"parcels: {result['data']['parcels_created']}, properties: {result['data']['properties_created']}")
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
