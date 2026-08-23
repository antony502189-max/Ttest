from __future__ import annotations

import json
import re
from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..db.session import get_session
from ..models import Listing
from ..repositories.listings import response_from, visible_query
from ..schemas.listings import ListingResponse

router = APIRouter(include_in_schema=False)


def _public_origin() -> str:
    return get_settings().frontend_app_url.rstrip("/")


def _absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    return f"{_public_origin()}/{value.lstrip('/')}"


def _compact_description(value: str, fallback: str) -> str:
    text = re.sub(r"\s+", " ", value).strip() or fallback
    if len(text) <= 180:
        return text
    return f"{text[:177].rstrip()}…"


def _safe_json(value: object) -> str:
    # JSON-LD is embedded in a script element. Escape HTML-significant
    # characters so user-authored listing text cannot terminate that element.
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _render_listing_page(listing: ListingResponse) -> str:
    origin = _public_origin()
    canonical = f"{origin}/habitacion/{listing.id}"
    spa_url = f"{origin}/#/habitacion/{listing.id}"
    location = " · ".join(part for part in (listing.city, listing.area) if part)
    fallback = f"{listing.roomType} en {location or 'Santa Cruz de Tenerife'}"
    description = _compact_description(listing.description, fallback)
    title = f"{listing.title} | 112233.es"
    image = _absolute_url(listing.coverImageUrl)
    currency = listing.priceCurrency or "EUR"
    price = listing.price
    price_label = f"{price} € / {listing.cadence}" if price is not None else "Consultar precio"

    structured: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Room",
        "name": listing.title,
        "description": description,
        "url": canonical,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": listing.city,
            "addressRegion": "Santa Cruz de Tenerife",
            "addressCountry": "ES",
        },
    }
    if image:
        structured["image"] = [image]
    if price is not None:
        structured["offers"] = {
            "@type": "Offer",
            "price": price,
            "priceCurrency": currency,
            "availability": "https://schema.org/InStock",
            "url": canonical,
        }

    image_meta = f'<meta property="og:image" content="{escape(image, quote=True)}">' if image else ""
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description, quote=True)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{escape(canonical, quote=True)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="112233.es">
  <meta property="og:title" content="{escape(listing.title, quote=True)}">
  <meta property="og:description" content="{escape(description, quote=True)}">
  <meta property="og:url" content="{escape(canonical, quote=True)}">
  {image_meta}
  <meta name="twitter:card" content="{'summary_large_image' if image else 'summary'}">
  <script type="application/ld+json">{_safe_json(structured)}</script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; color: #171717; background: #fff; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ font-size: clamp(1.7rem, 4vw, 2.5rem); line-height: 1.15; margin: 0 0 12px; }}
    .meta {{ color: #5f6368; margin-bottom: 20px; }}
    .price {{ font-size: 1.35rem; font-weight: 700; margin: 18px 0; }}
    img {{ width: 100%; max-height: 480px; object-fit: cover; border-radius: 14px; }}
    p {{ line-height: 1.6; }}
    a {{ display: inline-block; margin-top: 24px; padding: 12px 18px; border-radius: 10px;
         background: #111; color: #fff; text-decoration: none; font-weight: 650; }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(listing.title)}</h1>
    <div class="meta">{escape(location)}</div>
    {f'<img src="{escape(image, quote=True)}" alt="{escape(listing.title, quote=True)}">' if image else ''}
    <div class="price">{escape(price_label)}</div>
    <p>{escape(description)}</p>
    <a href="{escape(spa_url, quote=True)}">Ver anuncio interactivo</a>
  </main>
</body>
</html>"""


@router.get("/habitacion/{listing_id}", response_class=HTMLResponse)
async def public_listing_page(
    listing_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    row = (await session.execute(visible_query().where(Listing.id == listing_id))).one_or_none()
    if not row:
        raise HTTPException(404, "Listing not found")
    listing = response_from(row)
    return HTMLResponse(
        _render_listing_page(listing),
        headers={"Cache-Control": "public, max-age=60"},
    )


@router.get("/sitemap.xml")
async def public_sitemap(session: AsyncSession = Depends(get_session)) -> Response:
    rows = (
        await session.execute(
            visible_query().order_by(Listing.updated_at.desc(), Listing.id.desc()).limit(50_000)
        )
    ).all()
    origin = _public_origin()
    entries: list[str] = []
    for row in rows:
        listing = row[0]
        last_modified = listing.updated_at or listing.created_at
        entries.append(
            "<url>"
            f"<loc>{escape(f'{origin}/habitacion/{listing.id}')}</loc>"
            f"<lastmod>{last_modified.date().isoformat()}</lastmod>"
            "</url>"
        )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(entries)}"
        "</urlset>"
    )
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt() -> PlainTextResponse:
    origin = _public_origin()
    private_paths = (
        "/api/",
        "/acceso",
        "/registro",
        "/recuperar-contrasena",
        "/restablecer-contrasena",
        "/verificar-email",
        "/favoritos",
        "/busquedas-guardadas",
        "/mensajes",
        "/menu",
        "/perfil",
        "/mis-anuncios",
        "/publicar",
        "/admin",
    )
    lines = ["User-agent: *", "Allow: /"]
    lines.extend(f"Disallow: {path}" for path in private_paths)
    lines.extend((f"Sitemap: {origin}/sitemap.xml", ""))
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Cache-Control": "public, max-age=300"},
    )
