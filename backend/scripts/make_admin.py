"""Promote an existing account to admin.

Registration always creates a student and there is no in-app promotion route, so
without this there is no way to reach the admin pages (class analytics, custom
agents) at all.

Run with: python -m scripts.make_admin <email>
"""

import asyncio
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.user import User


async def make_admin(email: str) -> int:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"No account found for {email!r}. Register it first, then re-run.")
            return 1

        if user.role == "admin":
            print(f"{email} is already an admin.")
            return 0

        user.role = "admin"
        await db.commit()
        print(f"{email} is now an admin. Sign out and back in to refresh the session.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.make_admin <email>")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(make_admin(sys.argv[1])))
