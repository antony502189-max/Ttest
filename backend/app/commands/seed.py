import asyncio
import os

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import select

from ..core.config import get_settings
from ..core.security import hash_password
from ..db.session import SessionLocal
from ..models import Listing, User

DEMO_USERS = (
    ("inquilina@112233.es", "Lucía Demo", "tenant"),
    ("anfitrion@112233.es", "Carlos Anfitrión", "host"),
    ("admin@112233.es", "Ana Moderación", "admin"),
)


async def seed() -> None:
    if get_settings().app_env == "production":
        raise RuntimeError("Demo seed is disabled in production")
    password = os.getenv("SEED_PASSWORD", "demo112233")
    async with SessionLocal() as session:
        users: dict[str, User] = {}
        for email, name, role in DEMO_USERS:
            user = await session.scalar(select(User).where(User.email == email))
            if not user:
                user = User(
                    email=email, name=name, role=role, password_hash=hash_password(password),
                    initials="".join(part[0] for part in name.split()[:2]).upper(),
                )
                session.add(user)
                await session.flush()
            users[email] = user
        if not await session.scalar(select(Listing.id).where(Listing.title == "Habitación luminosa en La Laguna")):
            session.add(
                Listing(
                    owner_user_id=users["anfitrion@112233.es"].id, title="Habitación luminosa en La Laguna",
                    city="Tenerife", area="La Laguna", approximate_address="La Laguna", rental_mode="long",
                    monthly_price=550, nightly_price=None, status="published", description="Anuncio de desarrollo.",
                    location=ST_SetSRID(ST_MakePoint(-16.315, 28.487), 4326),
                )
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
