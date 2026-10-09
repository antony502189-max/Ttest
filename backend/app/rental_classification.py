"""Conservative rental admission using listing metadata, never page navigation.

Adapters translate their public fields into property_type, bedroom_count,
rental_category and price_period. Unknown structured types fail closed.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


def folded(value: Any) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(value or "").casefold()) if not unicodedata.combining(c)
    )


ROOM = "Habitación individual"
SHARED_ROOM = "Habitación compartida"
STUDIO = "Estudio"
ONE_BEDROOM = "Apartamento de 1 dormitorio"
ROOM_TYPES = {ROOM, SHARED_ROOM}

_BEDROOMS = re.compile(r"\b(\d+|un|una|dos|tres|cuatro|cinco)\s*(?:dormitorios?|bedrooms?|habitacion(?:es)?|hab\.?)\b")
_ROOM = re.compile(
    r"\b(?:se alquila(?:n)? habitacion(?:es)?|alquilo habitacion|alquiler (?:de )?habitacion|"
    r"habitacion (?:individual|privada|compartida|disponible|libre|en piso compartido)|"
    r"(?:private |shared )?room for rent|rooms available for rent|cuarto en alquiler)\b"
)
_WANTED = re.compile(r"\b(?:busco|buscamos|buscando|necesito|necesitamos|se busca|looking for|wanted)\b")
_UNITS = re.compile(
    r"\b(?:garaje|garage|parking|oficina|office|local comercial|parcela|terreno|trastero|"
    r"storage|plot|land|cama en habitacion|plaza en habitacion|bed space|bedspace|"
    r"bed(?:\s+\d+(?:[.-]\d+)*)?\s+in\s+(?:a\s+)?(?:shared\s+)?room)\b"
)
_SALES = re.compile(r"\b(?:venta|comprar|se vende|for sale|sale)\b")


def bedroom_count(data: dict[str, Any]) -> int | None:
    value = data.get("bedroom_count")
    if value is not None:
        try:
            number = int(str(value))
            return number if 0 <= number <= 100 else None
        except ValueError:
            return None
    corpus = folded(f"{data.get('title', '')} {data.get('description', '')}")
    counts = {
        int(x) if x.isdigit() else {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5}[x]
        for x in _BEDROOMS.findall(corpus)
    }
    return next(iter(counts)) if len(counts) == 1 else None


def property_type(data: dict[str, Any], source_name: str) -> str | None:
    title = folded(data.get("title"))
    category = folded(data.get("category"))
    description = folded(data.get("description"))
    operation = folded(data.get("operation"))
    # An amenity such as parking does not change the offered unit. Identity
    # negatives apply to title and provider type/category, not the whole page.
    structured = folded(data.get("property_type")).strip()
    unit_identity = re.sub(r"\b(?:con (?:parking|garaje)|parking incluido|garaje incluido)\b", "", title)
    if _SALES.search(f"{title} {category} {operation}") or _UNITS.search(f"{unit_identity} {structured}"):
        return None
    if _WANTED.search(title) or (
        _WANTED.search(description[:300])
        and not re.search(
            r"\b(?:se alquila|alquilo|ofrezco|disponible|en alquiler|available|for rent)\b", description[:300]
        )
    ):
        return None
    shared = "habitacion compartida" in f"{title} {description}" or "shared room" in f"{title} {description}"
    room = SHARED_ROOM if shared else ROOM
    count = bedroom_count(data)
    if structured:
        if structured in {"room", "private room", "shared room", "habitacion", "cuarto"}:
            return SHARED_ROOM if structured == "shared room" or shared else ROOM
        if data.get("bedroom_count") is not None and count is None:
            return None
        if structured in {"studio", "estudio", "studio apartment"}:
            return STUDIO if count in {None, 0} else None
        if structured in {"apartment", "apartamento", "flat", "piso", "loft"}:
            if count == 0:
                return STUDIO
            return ONE_BEDROOM if count == 1 else None
        return None
    path = folded(urlparse(str(data.get("url") or "")).path)
    room_route = (
        (source_name == "PisoCompartido" and path.startswith("/habitacion/"))
        or (source_name == "Pisos" and path.startswith("/alquilar/habitacion-"))
        or (source_name == "Fotocasa" and path.startswith("/es/compartir/vivienda/"))
        or (source_name == "Flatio" and path.startswith("/rent/room/"))
        or (source_name == "Milanuncios" and path.startswith("/pisos-compartidos-"))
    )
    corpus = f"{title} {description}"
    if room_route or _ROOM.search(title) or ("piso compartido" in corpus and _ROOM.search(corpus)):
        if re.search(r"\b(?:piso|apartamento|vivienda|casa|villa) (?:completo|completa|entero|entera)\b", title):
            return None
        return room
    if count is not None and count >= 2:
        return None
    if re.search(r"\b(?:casa|villa|chalet|townhouse|finca)\b", title):
        return None
    if re.search(r"\b(?:estudio|studio)\b", title):
        return STUDIO if count in {None, 0} else None
    if re.search(r"\b(?:piso|apartamento|apartment|flat)\b", title) and count == 1:
        return ONE_BEDROOM
    # Legacy room fixtures/categories remain valid only without a whole-unit
    # identity. Bare "1 habitación" on a property portal is not a room.
    if _ROOM.search(corpus) and not re.search(r"\b(?:piso|apartamento) (?:de|con)\b", title):
        return room
    if source_name in {"Idealista", "PisoCompartido", "Fotocasa", "Pisos", "AlquilerDocenteCanarias"} and (
        re.search(r"\bhabitacion\b", title) and "alquiler" in category
    ):
        return room
    return None


@dataclass(frozen=True)
class RentalPrice:
    mode: str
    amount: int
    period: str
    weekly_amount: int | None = None


def rental_price(data: dict[str, Any], source_name: str, amount: int | None, period: str | None) -> RentalPrice | None:
    if amount is None or amount <= 0:
        return None
    identity = folded(f"{data.get('title', '')} {data.get('category', '')} {data.get('operation', '')}")
    if _SALES.search(identity):
        return None
    # CUSTOMER POLICY: "long-term" means an explicitly advertised fixed
    # EUR/month rent, NOT a tenancy of six or more months. The normalized
    # price period is authoritative over words such as temporal, temporada,
    # holiday or vacacional. Currency and the EUR 1,000 cap are enforced by
    # the separate strict price parser and evaluate() admission gate.
    if period == "month":
        return RentalPrice("long", amount, "month")
    structured = folded(data.get("rental_category")).strip()
    long_categories = {"long", "long_stay", "long term", "residential", "residencial", "academic", "larga estancia"}
    holiday_categories = {"holiday", "vacacional", "holiday rental", "short stay", "tourist", "short_stay"}
    mode = "long" if structured in long_categories else "holiday" if structured in holiday_categories else None
    if structured and mode is None and structured not in {"temporada", "temporary", "seasonal"}:
        return None
    path = folded(urlparse(str(data.get("url") or "")).path)
    if mode is None:
        if source_name == "ThinkSpain" and path.startswith("/holiday-rentals/"):
            mode = "holiday"
        elif source_name == "ThinkSpain" and path.startswith("/property-to-rent-long-term/"):
            mode = "long"
        elif source_name == "Pisos" and path.startswith("/alquiler-vacacional/"):
            mode = "holiday"
    corpus = folded(f"{identity} {data.get('description', '')}")
    # A residential offer can explicitly prohibit tourist use. Such a
    # negation is not positive evidence of a holiday rental.
    corpus = re.sub(
        r"\b(?:no|sin)\s+(?:se admite\s+|para\s+|alquiler\s+)?(?:vacacional|turistico|holiday)\b", "", corpus
    )
    if mode is None:
        holiday = re.search(r"\b(?:vacacional|vacaciones|holiday|tourist|turistico|short stay|nightly)\b", corpus)
        residential = re.search(
            r"\b(?:larga estancia|larga duracion|larga temporada|residencial|curso academico|academic year)\b", corpus
        )
        if holiday and residential:
            return None
        mode = "holiday" if holiday else "long" if residential else None
    if mode is None:
        mode = "holiday" if period == "night" else "long" if period == "month" else None
    # Nightly and weekly rates remain classified for diagnostics only.
    # The authoritative public/import policy rejects both, regardless of
    # the category or any advertised minimum-stay duration.
    if mode == "holiday" and period == "night":
        return RentalPrice(mode, amount, period)
    if mode == "holiday" and period == "week":
        return RentalPrice(mode, (amount + 6) // 7, period, amount)
    return None
