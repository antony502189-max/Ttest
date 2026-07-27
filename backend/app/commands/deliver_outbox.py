import asyncio

from ..db.session import SessionLocal
from ..services.mail import deliver_pending_mail


async def main() -> None:
    async with SessionLocal() as session:
        delivered = await deliver_pending_mail(session)
    print(f"Delivered {delivered} mail item(s)")


if __name__ == "__main__":
    asyncio.run(main())
