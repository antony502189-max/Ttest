"""Structured Spanish provinces and provider aliases (50 + Ceuta/Melilla)."""

from __future__ import annotations

from typing import Any

from .rental_classification import folded

PROVINCES = (
    "A Coruña",
    "Álava",
    "Albacete",
    "Alicante",
    "Almería",
    "Asturias",
    "Ávila",
    "Badajoz",
    "Barcelona",
    "Bizkaia",
    "Burgos",
    "Cáceres",
    "Cádiz",
    "Cantabria",
    "Castellón",
    "Ciudad Real",
    "Córdoba",
    "Cuenca",
    "Gipuzkoa",
    "Girona",
    "Granada",
    "Guadalajara",
    "Huelva",
    "Huesca",
    "Illes Balears",
    "Jaén",
    "La Rioja",
    "Las Palmas",
    "León",
    "Lleida",
    "Lugo",
    "Madrid",
    "Málaga",
    "Murcia",
    "Navarra",
    "Ourense",
    "Palencia",
    "Pontevedra",
    "Salamanca",
    "Santa Cruz de Tenerife",
    "Segovia",
    "Sevilla",
    "Soria",
    "Tarragona",
    "Teruel",
    "Toledo",
    "Valencia",
    "Valladolid",
    "Zamora",
    "Zaragoza",
    "Ceuta",
    "Melilla",
)


def province_token(value: Any) -> str:
    return " ".join(folded(value).replace("_", " ").replace("-", " ").split())


ALIASES = {province_token(value): value for value in PROVINCES}
ALIASES.update(
    {
        "araba": "Álava",
        "araba alava": "Álava",
        "alava araba": "Álava",
        "vizcaya": "Bizkaia",
        "bizkaia vizcaya": "Bizkaia",
        "vizcaya bizkaia": "Bizkaia",
        "guipuzcoa": "Gipuzkoa",
        "gipuzkoa guipuzcoa": "Gipuzkoa",
        "guipuzcoa gipuzkoa": "Gipuzkoa",
        "islas baleares": "Illes Balears",
        "baleares": "Illes Balears",
        "islas baleares illes balears": "Illes Balears",
        "navarra nafarroa": "Navarra",
        "castellon castello": "Castellón",
        "castello": "Castellón",
        "alacant": "Alicante",
        "alicante alacant": "Alicante",
        "valencia valencia": "Valencia",
        "valencia valencia provincia": "Valencia",
        "gerona": "Girona",
        "lerida": "Lleida",
        "orense": "Ourense",
        "la coruna": "A Coruña",
    }
)


def canonical_province(value: Any) -> str | None:
    return ALIASES.get(province_token(value))


def scope_province(scope_key: str) -> str | None:
    """Holiday slices share province evidence, but retain independent cursors."""
    if not scope_key.startswith("province:"):
        return None
    return canonical_province(scope_key.removeprefix("province:").removesuffix(":holiday"))


def spain_country(value: Any) -> bool:
    if isinstance(value, dict):
        value = value.get("name") or value.get("identifier")
    return folded(value).strip() in {"", "es", "esp", "espana", "spain"}


def coordinates_in_spain(latitude: float, longitude: float) -> bool:
    # Sanity only; province admission still needs structured provider evidence.
    return (
        (35.7 <= latitude <= 43.9 and -9.5 <= longitude <= 4.5)
        or (27.5 <= latitude <= 29.5 and -18.3 <= longitude <= -13.3)
        or (35.1 <= latitude <= 35.95 and -5.5 <= longitude <= -2.8)
    )
