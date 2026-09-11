"""Bootstrap the first ADMIN user from environment variables, if none exists yet.

Grows in later phases (availability, scores, rules) into the full demo dataset
described in ARCHITECTURE.md; for Phase 1 it only needs to get one admin
logged in so they can start inviting people.
"""

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User


async def run() -> None:
    assert settings.admin_bootstrap_password is not None  # guaranteed by get_settings()

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.role == Role.ADMIN))
        existing_admin = result.scalars().first()
        if existing_admin is None:
            admin = User(
                email=settings.admin_bootstrap_email,
                password_hash=hash_password(settings.admin_bootstrap_password),
                full_name=settings.admin_bootstrap_full_name,
                role=Role.ADMIN,
                is_active=True,
            )
            db.add(admin)
            await db.commit()
            print(f"Created bootstrap admin: {admin.email}")
            print(f"Admin login -> email: {admin.email}")
            print(f"Admin login -> password: {settings.admin_bootstrap_password}")
        else:
            # Don't print settings.admin_bootstrap_password here: if this
            # admin's password was ever changed via PATCH /users/me, that
            # value is stale and would mislead rather than help.
            print(f"Admin already exists ({existing_admin.email}); skipping creation.")
            print(f"Admin login -> email: {existing_admin.email}")
            print("Admin login -> password: unchanged from whenever it was last set")


if __name__ == "__main__":
    asyncio.run(run())
