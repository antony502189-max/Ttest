import asyncio
import os
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid5

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

PLACES = (
    ("Adeje", "Costa Adeje", 28.0902, -16.7260),
    ("Adeje", "Armeñime", 28.1272, -16.7390),
    ("Arona", "Playa de las Américas", 28.0640, -16.7310),
    ("Arona", "Los Cristianos", 28.0509, -16.7172),
    ("Granadilla de Abona", "San Isidro", 28.0770, -16.5580),
    ("Granadilla de Abona", "El Médano", 28.0477, -16.5363),
    ("Santa Cruz de Tenerife", "Santa Cruz de Tenerife", 28.4636, -16.2518),
    ("San Cristóbal de La Laguna", "La Laguna", 28.4874, -16.3159),
    ("Adeje", "Adeje", 28.1227, -16.7244),
    ("Arona", "Arona", 28.0996, -16.6809),
)
TITLES = (
    "Habitación luminosa con escritorio y gastos incluidos",
    "Habitación doble cerca de la playa y la guagua",
    "Habitación con baño privado para teletrabajo",
    "Habitación tranquila en piso compartido reformado",
    "Habitación amueblada junto a todos los servicios",
    "Estudio privado con cocina y terraza",
    "Habitación exterior con armario empotrado",
    "Habitación para curso universitario junto al tranvía",
    "Habitación amplia con balcón y Wi-Fi",
    "Habitación económica en vivienda organizada",
)
OWNERS = (
    ("Equipo Casa Norte", "CN"),
    ("Marina A.", "MA"),
    ("Daniel R.", "DR"),
    ("Vivienda Campus", "VC"),
    ("Isla Rooms", "IR"),
    ("Atlántico Estancias", "AE"),
    ("Nerea S.", "NS"),
    ("Clara M.", "CM"),
    ("Tenerife Hogar", "TH"),
    ("Raúl G.", "RG"),
)
AMENITIES = ("Wi-Fi", "Escritorio", "Balcón", "Ascensor", "Lavadora", "Aire acondicionado", "Terraza", "Aparcamiento")
PHOTOS = (
    "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1560185008-b033106af5c3?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1560185127-6ed189bf02f4?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1560448075-bb485b067938?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1615874959474-d609969a20ed?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?auto=format&fit=crop&w=1200&q=82",
    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=82",
)


async def demo_owner(session, index: int) -> User:
    name, initials = OWNERS[index % len(OWNERS)]
    email = f"demo-owner-{index % len(OWNERS)}@112233.local"
    owner = await session.scalar(select(User).where(User.email == email))
    if owner:
        return owner
    owner = User(
        email=email,
        name=name,
        initials=initials,
        role="host",
        password_hash=None,
        phone="+34 600 112 233",
        whatsapp="+34 611 223 344",
        show_phone=True,
        show_whatsapp=True,
        email_verified=index % 7 != 0,
    )
    session.add(owner)
    await session.flush()
    return owner


async def import_current_demo_listings(session) -> None:
    for index in range(32):
        listing_id = uuid5(NAMESPACE_URL, f"112233-demo-listing-{index}")
        existing = await session.get(Listing, listing_id)
        if existing:
            if not existing.external_image_urls:
                existing.external_image_urls = [PHOTOS[(index + offset * 2) % len(PHOTOS)] for offset in range(6)]
            continue
        city, area, latitude, longitude = PLACES[index % len(PLACES)]
        rental_mode = "holiday" if index % 5 == 2 or index % 7 == 5 else "long"
        price = 44 + (index % 8) * 7 if rental_mode == "holiday" else 350 + (index % 10) * 45
        tenant_requirement = (
            "single-woman"
            if index % 5 == 0
            else "single-man"
            if index % 7 == 0
            else "couple"
            if index % 3 == 0
            else "any"
        )
        room_capacity = 2 if tenant_requirement == "couple" or (tenant_requirement == "any" and index % 4 == 1) else 1
        bedroom_count = 1 if index % 9 == 5 else 1 + (index % 12)
        bills_included = index % 3 != 1
        owner = await demo_owner(session, index)
        session.add(
            Listing(
                id=listing_id,
                owner_user_id=owner.id,
                title=TITLES[index % len(TITLES)],
                city=city,
                area=area,
                street="",
                postcode="",
                approximate_address=(
                    "Zona centro",
                    "Cerca de la plaza",
                    "A 8 min de la costa",
                    "Junto a la parada principal",
                )[index % 4]
                + " · ubicación aproximada",
                rental_mode=rental_mode,
                monthly_price=price if rental_mode == "long" else price * 24,
                nightly_price=price if rental_mode == "holiday" else None,
                weekly_price=price * 6 if rental_mode == "holiday" else None,
                room_type="Estudio"
                if index % 9 == 5
                else "Habitación compartida"
                if index % 8 == 3
                else "Habitación individual",
                available_from=date(2026, 7 if index % 4 == 0 else 8, 1 + (index % 27)),
                available_until=date(2026, 12, 20) if rental_mode == "holiday" else None,
                minimum_stay_months=0 if rental_mode == "holiday" else (1, 2, 3, 6)[index % 4],
                minimum_nights=3 + (index % 5) if rental_mode == "holiday" else None,
                deposit_amount=0 if index % 6 == 0 else price,
                bills_included=bills_included,
                bathroom="Baño privado" if index % 4 == 2 else "Baño compartido",
                kitchen="Cocina privada" if index % 9 == 5 else "Cocina compartida",
                furnished=index % 11 != 0,
                room_size_m2=9 + (index % 10),
                bedroom_count=bedroom_count,
                current_residents=1 + (index % 6),
                room_capacity=room_capacity,
                shower="Ducha privada" if index % 4 == 2 else "Ducha compartida",
                tenant_requirement=tenant_requirement,
                smoking_allowed=index % 6 == 0,
                pets_allowed=index % 4 == 0,
                children_allowed=index % 6 == 1,
                empadronamiento_allowed=index % 2 == 0,
                restrictions=[
                    f"Requisito: {tenant_requirement}",
                    "Gastos incluidos" if bills_included else "Gastos aparte",
                ],
                amenities=[item for item_index, item in enumerate(AMENITIES) if (index + item_index) % 3 != 0][:5],
                external_image_urls=[PHOTOS[(index + offset * 2) % len(PHOTOS)] for offset in range(6)],
                status="published",
                location=ST_SetSRID(
                    ST_MakePoint(longitude + ((index % 4) - 1.5) * 0.004, latitude + ((index % 3) - 1) * 0.0045), 4326
                ),
                description="Habitación exterior y cuidada en una vivienda compartida con buena conexión. El anuncio detalla gastos, disponibilidad y normas para que puedas comparar antes de contactar.",
                home_description=f"Vivienda de {bedroom_count} dormitorio(s) con zonas comunes equipadas. La posición del mapa es aproximada para proteger la privacidad.",
                advertiser_type="Profesional" if index % 4 == 0 else "Particular",
                source="Anunciante profesional" if index % 4 == 0 else None,
                published_at=datetime(2026, 7, max(1, 20 - (index % 20)), 12 - (index % 8), tzinfo=UTC),
                expires_at=datetime(2026, 10, 1 + (index % 27), tzinfo=UTC),
                views=90 + index * 37,
            )
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
                    email=email,
                    name=name,
                    role=role,
                    password_hash=hash_password(password),
                    initials="".join(part[0] for part in name.split()[:2]).upper(),
                )
                session.add(user)
                await session.flush()
            users[email] = user
        if not await session.scalar(select(Listing.id).where(Listing.title == "Habitación luminosa en La Laguna")):
            session.add(
                Listing(
                    owner_user_id=users["anfitrion@112233.es"].id,
                    title="Habitación luminosa en La Laguna",
                    city="Tenerife",
                    area="La Laguna",
                    approximate_address="La Laguna",
                    rental_mode="long",
                    monthly_price=550,
                    nightly_price=None,
                    status="published",
                    description="Anuncio de desarrollo.",
                    location=ST_SetSRID(ST_MakePoint(-16.315, 28.487), 4326),
                )
            )
        await import_current_demo_listings(session)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
