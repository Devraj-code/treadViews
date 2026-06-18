"""Database initialisation: create tables and seed the first admin user."""
from __future__ import annotations

import logging

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import User, UserRole  # noqa: F401 — ensures models are registered

logger = logging.getLogger(__name__)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.FIRST_ADMIN_EMAIL).first()
        if not existing:
            admin = User(
                email=settings.FIRST_ADMIN_EMAIL,
                password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD),
                full_name="Administrator",
                role=UserRole.admin,
            )
            db.add(admin)
            db.commit()
            logger.info("Seeded admin user %s", settings.FIRST_ADMIN_EMAIL)
    finally:
        db.close()
