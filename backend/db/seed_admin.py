"""
Seed a default admin user into the database.

Requires:
  ADMIN_EMAIL, ADMIN_PASSWORD
Optional:
  ADMIN_NAME, ADMIN_USERNAME, ADMIN_ROLE
"""

import sys
from pathlib import Path

from sqlalchemy.orm import Session

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.session import SessionLocal
from db import models
from api.auth.jwt_handler import hash_password
import config


def seed_admin() -> None:
    if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
        raise SystemExit("ADMIN_EMAIL and ADMIN_PASSWORD must be set to seed admin.")

    db: Session = SessionLocal()
    try:
        existing = (
            db.query(models.User)
            .filter(models.User.email == config.ADMIN_EMAIL)
            .first()
        )
        if existing:
            print("Admin user already exists.")
            return

        user = models.User(
            email=config.ADMIN_EMAIL,
            name=config.ADMIN_NAME,
            username=config.ADMIN_USERNAME,
            role=config.ADMIN_ROLE,
            hashed_password=hash_password(config.ADMIN_PASSWORD),
            status="active",
        )
        db.add(user)
        db.commit()
        print("Admin user created.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
