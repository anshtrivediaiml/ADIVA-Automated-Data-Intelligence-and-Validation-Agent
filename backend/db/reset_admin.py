"""
Reset admin user in the database.

Requires:
  ADMIN_EMAIL, ADMIN_PASSWORD
Optional:
  ADMIN_NAME, ADMIN_USERNAME, ADMIN_ROLE
  ADMIN_DELETE_EMAILS (comma-separated list of emails to delete before seeding)
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


def reset_admin() -> None:
    if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
        raise SystemExit("ADMIN_EMAIL and ADMIN_PASSWORD must be set to reset admin.")

    delete_emails = [
        e.strip().lower()
        for e in (config.ADMIN_DELETE_EMAILS or "").split(",")
        if e.strip()
    ]

    db: Session = SessionLocal()
    try:
        if delete_emails:
            db.query(models.User).filter(models.User.email.in_(delete_emails)).delete(
                synchronize_session=False
            )

        existing = (
            db.query(models.User)
            .filter(models.User.email == config.ADMIN_EMAIL)
            .first()
        )

        if existing:
            existing.name = config.ADMIN_NAME
            existing.username = config.ADMIN_USERNAME
            existing.role = config.ADMIN_ROLE
            existing.hashed_password = hash_password(config.ADMIN_PASSWORD)
            existing.status = "active"
        else:
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
        print("Admin reset complete.")
    finally:
        db.close()


if __name__ == "__main__":
    reset_admin()
