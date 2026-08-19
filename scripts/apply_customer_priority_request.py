from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    text = read(path)
    actual = text.count(old)
    if actual < count:
        raise RuntimeError(f"{path}: expected at least {count} occurrence(s), found {actual}: {old[:120]!r}")
    write(path, text.replace(old, new, count))


def replace_between(path: str, start_marker: str, end_marker: str, replacement: str) -> None:
    text = read(path)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{path}: start marker not found")
    end_start = text.find(end_marker, start)
    if end_start < 0:
        raise RuntimeError(f"{path}: end marker not found")
    end = end_start + len(end_marker)
    write(path, text[:start] + replacement + text[end:])


# ---------------------------------------------------------------------------
# Frontend domain model and defaults: structured floor + requested amenities.
# ---------------------------------------------------------------------------
replace(
    "src/types.ts",
    "export type HeatingType = 'individual' | 'central' | 'none' | 'unknown'\n",
    "export type HeatingType = 'individual' | 'central' | 'none' | 'unknown'\nexport type FloorLevel = 'basement' | '1' | '2' | '3' | '4+' | 'top'\n",
)
replace(
    "src/types.ts",
    "  accessible?: boolean | null\n  couplesAllowed?: boolean | null\n",
    "  accessible?: boolean | null\n  floor?: FloorLevel | null\n  couplesAllowed?: boolean | null\n",
)
replace(
    "src/types.ts",
    "  accessible: YesNoAny\n  acceptedTenantTypes: AcceptedTenantType[]\n",
    "  accessible: YesNoAny\n  floor: 'Cualquiera' | FloorLevel\n  acceptedTenantTypes: AcceptedTenantType[]\n",
)
replace(
    "src/types.ts",
    "  accessible: boolean\n  furnished: boolean\n",
    "  accessible: boolean\n  floor: FloorLevel\n  furnished: boolean\n",
)

replace(
    "src/data/listings.ts",
    "export const amenityOptions = ['Wi-Fi', 'Escritorio', 'Balcón', 'Ascensor', 'Lavadora', 'Aire acondicionado', 'Terraza', 'Aparcamiento', 'Cocina equipada']",
    "export const amenityOptions = ['Wi-Fi', 'Escritorio', 'Balcón', 'Ascensor', 'Lavadora', 'Aire acondicionado', 'Terraza', 'Piscina', 'Jardín', 'Limpieza incluida', 'Ventana a la calle', 'Aparcamiento', 'Cocina equipada']",
)
replace(
    "src/data/listings.ts",
    "  accessible: 'Cualquiera',\n  acceptedTenantTypes: [],\n",
    "  accessible: 'Cualquiera',\n  floor: 'Cualquiera',\n  acceptedTenantTypes: [],\n",
)
replace(
    "src/data/listings.ts",
    "  bathroom: 'Baño compartido', toilet: 'Aseo privado', shower: 'Ducha compartida', kitchen: 'Cocina privada', heatingType: 'none', accessible: false,\n",
    "  bathroom: 'Baño compartido', toilet: 'Aseo privado', shower: 'Ducha compartida', kitchen: 'Cocina privada', heatingType: 'none', accessible: false, floor: '1',\n",
)
# Mock/local listings get deterministic floors so the new filter is testable in demo/CI.
replace(
    "src/data/listings.ts",
    "    accessible: index % 5 === 0,\n",
    "    accessible: index % 5 === 0,\n    floor: (['basement', '1', '2', '3', '4+', 'top'] as const)[index % 6],\n",
)

# ---------------------------------------------------------------------------
# Local filtering + URL persistence.
# ---------------------------------------------------------------------------
replace(
    "src/lib/search.ts",
    "    if (!boolMatches(listing.accessible, filters.accessible)) return false\n    if (filters.acceptedTenantTypes.length) {\n",
    "    if (!boolMatches(listing.accessible, filters.accessible)) return false\n    if (filters.floor !== 'Cualquiera' && listing.floor !== filters.floor) return false\n    if (filters.acceptedTenantTypes.length) {\n",
)
replace(
    "src/lib/search.ts",
    "  if (filters.accessible !== defaultFilters.accessible) keys.push('accessible')\n  if (filters.acceptedTenantTypes.length) keys.push('acceptedTenantTypes')\n",
    "  if (filters.accessible !== defaultFilters.accessible) keys.push('accessible')\n  if (filters.floor !== defaultFilters.floor) keys.push('floor')\n  if (filters.acceptedTenantTypes.length) keys.push('acceptedTenantTypes')\n",
)
replace(
    "src/lib/search.ts",
    "  children: 'ninos', couplesAllowed: 'parejasOk', householdGender: 'convivenciaGenero', householdHasChildren: 'convivenciaNinos', heatingType: 'calefaccion', accessible: 'adaptada', acceptedTenantTypes: 'acepta',\n",
    "  children: 'ninos', couplesAllowed: 'parejasOk', householdGender: 'convivenciaGenero', householdHasChildren: 'convivenciaNinos', heatingType: 'calefaccion', accessible: 'adaptada', floor: 'planta', acceptedTenantTypes: 'acepta',\n",
)

# ---------------------------------------------------------------------------
# API DTO/payload/search round-trip for floor.
# ---------------------------------------------------------------------------
replace(
    "src/api/listings.ts",
    "  accessible: boolean | null\n  couplesAllowed: boolean | null\n",
    "  accessible: boolean | null\n  floor: Listing['floor'] | null\n  couplesAllowed: boolean | null\n",
)
replace(
    "src/api/listings.ts",
    "    accessible: dto.accessible,\n    couplesAllowed: dto.couplesAllowed,\n",
    "    accessible: dto.accessible,\n    floor: dto.floor,\n    couplesAllowed: dto.couplesAllowed,\n",
)
replace(
    "src/api/listings.ts",
    "    ...(yesNo(filters.accessible) !== undefined ? { accessible: yesNo(filters.accessible) } : {}),\n    ...(filters.acceptedTenantTypes.length ? { acceptedTenantTypes: filters.acceptedTenantTypes } : {}),\n",
    "    ...(yesNo(filters.accessible) !== undefined ? { accessible: yesNo(filters.accessible) } : {}),\n    ...(filters.floor !== 'Cualquiera' ? { floor: filters.floor } : {}),\n    ...(filters.acceptedTenantTypes.length ? { acceptedTenantTypes: filters.acceptedTenantTypes } : {}),\n",
)
replace(
    "src/api/listings.ts",
    "    heatingType: listing.heatingType ?? null, accessible: listing.accessible ?? null, couplesAllowed: listing.couplesAllowed ?? null,\n",
    "    heatingType: listing.heatingType ?? null, accessible: listing.accessible ?? null, floor: listing.floor ?? null, couplesAllowed: listing.couplesAllowed ?? null,\n",
)

# ---------------------------------------------------------------------------
# Publication: persist floor, clearer room wording, complete Tenerife cities.
# ---------------------------------------------------------------------------
replace(
    "src/pages/PublishPage.tsx",
    "    accessible: listing.accessible ?? false,\n    furnished: listing.furnished ?? true,\n",
    "    accessible: listing.accessible ?? false,\n    floor: listing.floor ?? '1',\n    furnished: listing.furnished ?? true,\n",
)
replace(
    "src/pages/PublishPage.tsx",
    "    accessible: draft.accessible,\n    couplesAllowed: draft.couplesAllowed,\n",
    "    accessible: draft.accessible,\n    floor: draft.floor,\n    couplesAllowed: draft.couplesAllowed,\n",
)
replace(
    "src/pages/PublishPage.tsx",
    "<FormField label=\"Municipio\" htmlFor=\"publish-city\"><select id=\"publish-city\" value={draft.city} onChange={(event) => set(\"city\", event.target.value)}><option>Adeje</option><option>Arona</option><option>Granadilla de Abona</option><option>Santa Cruz de Tenerife</option><option>San Cristóbal de La Laguna</option></select></FormField>",
    "<FormField label=\"Municipio\" htmlFor=\"publish-city\"><select id=\"publish-city\" value={draft.city} onChange={(event) => set(\"city\", event.target.value)}>{['Adeje','Arafo','Arico','Arona','Buenavista del Norte','Candelaria','El Rosario','El Sauzal','El Tanque','Fasnia','Garachico','Granadilla de Abona','Guía de Isora','Güímar','Icod de los Vinos','La Guancha','La Matanza de Acentejo','La Orotava','La Victoria de Acentejo','Los Realejos','Los Silos','Puerto de la Cruz','San Cristóbal de La Laguna','San Juan de la Rambla','San Miguel de Abona','Santa Cruz de Tenerife','Santa Úrsula','Santiago del Teide','Tacoronte','Tegueste','Vilaflor de Chasna'].map((city) => <option key={city}>{city}</option>)}</select></FormField>",
)
replace(
    "src/pages/PublishPage.tsx",
    "<FormField label=\"Aseo / WC\" htmlFor=\"publish-toilet\"><select id=\"publish-toilet\" value={draft.toilet} onChange={(e) => set(\"toilet\", e.target.value as ListingDraft[\"toilet\"])}><option>Aseo compartido</option><option>Aseo privado</option></select></FormField>\n            <FormField label=\"Ducha\" htmlFor=\"publish-shower\"><select id=\"publish-shower\" value={draft.shower} onChange={(e) => set(\"shower\", e.target.value as ListingDraft[\"shower\"])}><option>Ducha compartida</option><option>Ducha privada</option></select></FormField>\n            <FormField label=\"Cocina\" htmlFor=\"publish-kitchen\"><select id=\"publish-kitchen\" value={draft.kitchen} onChange={(e) => set(\"kitchen\", e.target.value as ListingDraft[\"kitchen\"])}><option>Cocina compartida</option><option>Cocina privada</option></select></FormField>\n            <FormField label=\"Calefacción\" htmlFor=\"publish-heating\"><select id=\"publish-heating\" value={draft.heatingType} onChange={(e) => set(\"heatingType\", e.target.value as ListingDraft[\"heatingType\"])}><option value=\"none\">Sin calefacción</option><option value=\"individual\">Calefacción individual</option><option value=\"central\">Calefacción central</option><option value=\"unknown\">No especificado</option></select></FormField>",
    "<FormField label=\"Aseo / WC en la habitación\" htmlFor=\"publish-toilet\"><select id=\"publish-toilet\" value={draft.toilet} onChange={(e) => set(\"toilet\", e.target.value as ListingDraft[\"toilet\"])}><option>Aseo compartido</option><option>Aseo privado</option></select></FormField>\n            <FormField label=\"Ducha / baño en la habitación\" htmlFor=\"publish-shower\"><select id=\"publish-shower\" value={draft.shower} onChange={(e) => set(\"shower\", e.target.value as ListingDraft[\"shower\"])}><option>Ducha compartida</option><option>Ducha privada</option></select></FormField>\n            <FormField label=\"Cocina / mini-cocina en la habitación\" htmlFor=\"publish-kitchen\"><select id=\"publish-kitchen\" value={draft.kitchen} onChange={(e) => set(\"kitchen\", e.target.value as ListingDraft[\"kitchen\"])}><option>Cocina compartida</option><option>Cocina privada</option></select></FormField>\n            <FormField label=\"Planta\" htmlFor=\"publish-floor\"><select id=\"publish-floor\" value={draft.floor} onChange={(e) => set(\"floor\", e.target.value as ListingDraft[\"floor\"])}><option value=\"basement\">Sótano / semisótano</option><option value=\"1\">1</option><option value=\"2\">2</option><option value=\"3\">3</option><option value=\"4+\">4+</option><option value=\"top\">Última planta</option></select></FormField>\n            <FormField label=\"Calefacción\" htmlFor=\"publish-heating\"><select id=\"publish-heating\" value={draft.heatingType} onChange={(e) => set(\"heatingType\", e.target.value as ListingDraft[\"heatingType\"])}><option value=\"none\">Sin calefacción</option><option value=\"individual\">Calefacción individual</option><option value=\"central\">Calefacción central</option><option value=\"unknown\">No especificado</option></select></FormField>",
)

# Desktop advanced filter retains all prior controls and gains structured floor.
replace(
    "src/components/localized-search-filters.tsx",
    "        {selectRow(t('Accesibilidad'), filters.accessible, yesNoOptions, (value) => set('accessible', value as Filters['accessible']))}\n",
    "        {selectRow(t('Accesibilidad'), filters.accessible, yesNoOptions, (value) => set('accessible', value as Filters['accessible']))}\n        {selectRow(t('Planta'), filters.floor, ['Cualquiera', 'basement', '1', '2', '3', '4+', 'top'], (value) => set('floor', value as Filters['floor']))}\n",
)
replace(
    "src/components/localized-search-filters.tsx",
    "{selectRow(t('Cocina'), filters.kitchen, ['Cualquiera', 'Cocina privada', 'Cocina compartida'], (value) => set('kitchen', value))}",
    "{selectRow(t('Cocina / mini-cocina en la habitación'), filters.kitchen, ['Cualquiera', 'Cocina privada', 'Cocina compartida'], (value) => set('kitchen', value))}",
)

# ---------------------------------------------------------------------------
# Mobile filter state and priority ordering requested by customer.
# ---------------------------------------------------------------------------
replace(
    "src/components/mobile-search-results-v2.tsx",
    "import type { Listing, RentalMode } from '@/types'",
    "import type { Filters, Listing, RentalMode } from '@/types'",
)
text = read("src/components/mobile-search-results-v2.tsx")
text = re.sub(
    r"type ResultsFilters = \{\n.*?\n\}",
    """type ResultsFilters = {
  rentalMode: RentalMode | null
  minPrice: number
  maxPrice: number
  minArea: number
  maxArea: number
  roomTypes: Listing['roomType'][]
  roomCounts: RoomCountFilter[]
  available: string
  availableUntil: string
  shower: Filters['shower']
  toilet: Filters['toilet']
  kitchen: Filters['kitchen']
  bedType: Filters['bedType']
  smoking: Filters['smoking']
  accessible: Filters['accessible']
  floor: Filters['floor']
  amenities: string[]
}""",
    text,
    count=1,
    flags=re.S,
)
text = re.sub(
    r"const createDefaultFilters = \(rentalMode: RentalMode \| null = null\): ResultsFilters => \(\{\n.*?\n\}\)",
    """const createDefaultFilters = (rentalMode: RentalMode | null = null): ResultsFilters => ({
  rentalMode,
  minPrice: defaultFilters.minPrice,
  maxPrice: defaultFilters.maxPrice,
  minArea: defaultFilters.roomSizeMin,
  maxArea: defaultFilters.roomSizeMax,
  roomTypes: [],
  roomCounts: [],
  available: defaultFilters.available,
  availableUntil: defaultFilters.availableUntil,
  shower: defaultFilters.shower,
  toilet: defaultFilters.toilet,
  kitchen: defaultFilters.kitchen,
  bedType: defaultFilters.bedType,
  smoking: defaultFilters.smoking,
  accessible: defaultFilters.accessible,
  floor: defaultFilters.floor,
  amenities: [],
})""",
    text,
    count=1,
    flags=re.S,
)
write("src/components/mobile-search-results-v2.tsx", text)

# Copy additions in all languages. Keys mirror Spanish so ResultsCopy stays structural.
replace(
    "src/components/mobile-search-results-v2.tsx",
    "    individual: 'Habitaciones individuales', shared: 'Habitaciones compartidas', studio: 'Estudios', showListings: 'Ver anuncios', residents: 'residentes',\n",
    "    moveIn: 'Fecha de entrada', moveOut: 'Fecha de salida (opcional)', priority: 'Características principales', privateShower: 'Ducha / baño privado en la habitación', privateToilet: 'Aseo / WC privado en la habitación', privateKitchen: 'Cocina / mini-cocina privada en la habitación', fullyPrivate: 'Zona totalmente privada: cocina + aseo + ducha', airConditioning: 'Aire acondicionado', bed: 'Tipo de cama', any: 'Cualquiera', singleBed: 'Individual', doubleBed: 'Doble', streetWindow: 'Ventana a la calle', smokingAllowed: 'Se permite fumar', bathroomType: 'Tipo de baño / aseo', bathroomPrivate: 'Ducha + aseo privados', toiletPrivateShowerShared: 'Aseo privado, ducha compartida', bathroomShared: 'Ducha + aseo compartidos', customBathroom: 'Configuración personalizada', additional: 'Filtros adicionales', terrace: 'Terraza', pool: 'Piscina', garden: 'Jardín', elevator: 'Ascensor', cleaning: 'Limpieza incluida', accessibleLabel: 'Adaptado para movilidad reducida', floor: 'Planta', basement: 'Sótano / semisótano', topFloor: 'Última planta',\n    individual: 'Habitaciones individuales', shared: 'Habitaciones compartidas', studio: 'Estudios', showListings: 'Ver anuncios', residents: 'residentes',\n",
)
replace(
    "src/components/mobile-search-results-v2.tsx",
    "    individual: 'Individual rooms', shared: 'Shared rooms', studio: 'Studios', showListings: 'View listings', residents: 'residents',\n",
    "    moveIn: 'Move-in date', moveOut: 'Move-out date (optional)', priority: 'Main features', privateShower: 'Private shower / bathroom in the room', privateToilet: 'Private toilet in the room', privateKitchen: 'Private kitchen / kitchenette in the room', fullyPrivate: 'Fully private zone: kitchen + toilet + shower', airConditioning: 'Air conditioning', bed: 'Bed type', any: 'Any', singleBed: 'Single', doubleBed: 'Double', streetWindow: 'Street-facing window', smokingAllowed: 'Smoking allowed', bathroomType: 'Bathroom / toilet type', bathroomPrivate: 'Private shower + toilet', toiletPrivateShowerShared: 'Private toilet, shared shower', bathroomShared: 'Shared shower + toilet', customBathroom: 'Custom configuration', additional: 'Additional filters', terrace: 'Terrace', pool: 'Pool', garden: 'Garden', elevator: 'Elevator', cleaning: 'Cleaning included', accessibleLabel: 'Accessible for reduced mobility', floor: 'Floor', basement: 'Basement', topFloor: 'Top floor',\n    individual: 'Individual rooms', shared: 'Shared rooms', studio: 'Studios', showListings: 'View listings', residents: 'residents',\n",
)
replace(
    "src/components/mobile-search-results-v2.tsx",
    "    individual: 'Отдельные комнаты', shared: 'Общие комнаты', studio: 'Студии', showListings: 'Перейти к объявлениям', residents: 'жильцов',\n",
    "    moveIn: 'Дата заезда', moveOut: 'Дата выезда (необязательно)', priority: 'Основные параметры', privateShower: 'Личный душ / ванная в комнате', privateToilet: 'Личный туалет в комнате', privateKitchen: 'Личная кухня / мини-кухня в комнате', fullyPrivate: 'Полностью приватная зона: кухня + туалет + душ', airConditioning: 'Кондиционер', bed: 'Кровать', any: 'Любой', singleBed: 'Односпальная', doubleBed: 'Двуспальная', streetWindow: 'Окно на улицу', smokingAllowed: 'Курение разрешено', bathroomType: 'Тип санузла', bathroomPrivate: 'Личный душ + туалет', toiletPrivateShowerShared: 'Личный туалет, общий душ', bathroomShared: 'Полностью общий санузел', customBathroom: 'Своя комбинация', additional: 'Дополнительные фильтры', terrace: 'Терраса', pool: 'Бассейн', garden: 'Сад', elevator: 'Лифт', cleaning: 'Уборка включена', accessibleLabel: 'Для людей с ограниченной мобильностью', floor: 'Этаж', basement: 'Цокольный', topFloor: 'Последний этаж',\n    individual: 'Отдельные комнаты', shared: 'Общие комнаты', studio: 'Студии', showListings: 'Перейти к объявлениям', residents: 'жильцов',\n",
)

# Route state now includes every requested customer filter.
replace(
    "src/components/mobile-search-results-v2.tsx",
    "    const routeFilters = { rentalMode: routeMode, minPrice: parsed.minPrice, maxPrice: parsed.maxPrice, minArea: parsed.roomSizeMin, maxArea: parsed.roomSizeMax, roomTypes, roomCounts }\n",
    "    const routeFilters: ResultsFilters = { rentalMode: routeMode, minPrice: parsed.minPrice, maxPrice: parsed.maxPrice, minArea: parsed.roomSizeMin, maxArea: parsed.roomSizeMax, roomTypes, roomCounts, available: parsed.available, availableUntil: parsed.availableUntil, shower: parsed.shower, toilet: parsed.toilet, kitchen: parsed.kitchen, bedType: parsed.bedType, smoking: parsed.smoking, accessible: parsed.accessible, floor: parsed.floor, amenities: [...parsed.amenities] }\n",
)

old_canonical = """    const canonicalFilters = {
      ...appFilters,
      minPrice: Math.min(filters.minPrice, filters.maxPrice),
      maxPrice: Math.max(filters.minPrice, filters.maxPrice),
      roomSizeMin: Math.min(filters.minArea, filters.maxArea),
      roomSizeMax: Math.max(filters.minArea, filters.maxArea),
      roomType: 'Cualquiera',
    }
"""
new_canonical = """    const canonicalFilters = {
      ...appFilters,
      minPrice: Math.min(filters.minPrice, filters.maxPrice),
      maxPrice: Math.max(filters.minPrice, filters.maxPrice),
      roomSizeMin: Math.min(filters.minArea, filters.maxArea),
      roomSizeMax: Math.max(filters.minArea, filters.maxArea),
      roomType: 'Cualquiera',
      available: filters.available,
      availableUntil: filters.availableUntil,
      shower: filters.shower,
      toilet: filters.toilet,
      kitchen: filters.kitchen,
      bedType: filters.bedType,
      smoking: filters.smoking,
      accessible: filters.accessible,
      floor: filters.floor,
      amenities: filters.amenities,
    }
"""
replace("src/components/mobile-search-results-v2.tsx", old_canonical, new_canonical)
old_preview = old_canonical.replace("filters.min", "draftFilters.min").replace("filters.max", "draftFilters.max").replace("filters.available", "draftFilters.available").replace("filters.shower", "draftFilters.shower").replace("filters.toilet", "draftFilters.toilet").replace("filters.kitchen", "draftFilters.kitchen").replace("filters.bedType", "draftFilters.bedType").replace("filters.smoking", "draftFilters.smoking").replace("filters.accessible", "draftFilters.accessible").replace("filters.floor", "draftFilters.floor").replace("filters.amenities", "draftFilters.amenities")
# The original preview block did not yet contain the added fields, so replace its original form explicitly.
old_preview = """    const canonicalFilters = {
      ...appFilters,
      minPrice: Math.min(draftFilters.minPrice, draftFilters.maxPrice),
      maxPrice: Math.max(draftFilters.minPrice, draftFilters.maxPrice),
      roomSizeMin: Math.min(draftFilters.minArea, draftFilters.maxArea),
      roomSizeMax: Math.max(draftFilters.minArea, draftFilters.maxArea),
      roomType: 'Cualquiera',
    }
"""
new_preview = new_canonical.replace("filters.", "draftFilters.")
replace("src/components/mobile-search-results-v2.tsx", old_preview, new_preview)

replace(
    "src/components/mobile-search-results-v2.tsx",
    """    const nextFilters = {
      ...appFilters,
      minPrice: Math.min(draftFilters.minPrice, draftFilters.maxPrice),
      maxPrice: Math.max(draftFilters.minPrice, draftFilters.maxPrice),
      roomSizeMin: Math.min(draftFilters.minArea, draftFilters.maxArea),
      roomSizeMax: Math.max(draftFilters.minArea, draftFilters.maxArea),
      roomType: 'Cualquiera',
    }
""",
    """    const nextFilters = {
      ...appFilters,
      minPrice: Math.min(draftFilters.minPrice, draftFilters.maxPrice),
      maxPrice: Math.max(draftFilters.minPrice, draftFilters.maxPrice),
      roomSizeMin: Math.min(draftFilters.minArea, draftFilters.maxArea),
      roomSizeMax: Math.max(draftFilters.minArea, draftFilters.maxArea),
      roomType: 'Cualquiera',
      available: draftFilters.available,
      availableUntil: draftFilters.availableUntil,
      shower: draftFilters.shower,
      toilet: draftFilters.toilet,
      kitchen: draftFilters.kitchen,
      bedType: draftFilters.bedType,
      smoking: draftFilters.smoking,
      accessible: draftFilters.accessible,
      floor: draftFilters.floor,
      amenities: draftFilters.amenities,
    }
""",
)

replace(
    "src/components/mobile-search-results-v2.tsx",
    "  const t = resultsCopy[language] as ResultsCopy\n  const contact = () => { if (!currentUser) navigate('/acceso') }\n",
    """  const t = resultsCopy[language] as ResultsCopy
  const hasDraftAmenity = (amenity: string) => draftFilters.amenities.includes(amenity)
  const setDraftAmenity = (amenity: string, enabled: boolean) => setDraftFilters((current) => ({ ...current, amenities: enabled ? Array.from(new Set([...current.amenities, amenity])) : current.amenities.filter((item) => item !== amenity) }))
  const fullyPrivate = draftFilters.shower === 'Ducha privada' && draftFilters.toilet === 'Aseo privado' && draftFilters.kitchen === 'Cocina privada'
  const bathroomProfile = draftFilters.shower === 'Ducha privada' && draftFilters.toilet === 'Aseo privado'
    ? 'private'
    : draftFilters.shower === 'Ducha compartida' && draftFilters.toilet === 'Aseo privado'
      ? 'private-toilet'
      : draftFilters.shower === 'Ducha compartida' && draftFilters.toilet === 'Aseo compartido'
        ? 'shared'
        : draftFilters.shower === 'Cualquiera' && draftFilters.toilet === 'Cualquiera' ? 'any' : 'custom'
  const contact = () => { if (!currentUser) navigate('/acceso') }
""",
)

old_ui_start = "      <fieldset><legend>{t.price}</legend>"
old_ui_end = "      <fieldset><legend>{t.housingType}</legend><div className=\"m2-results-filter__checks\">{([['Habitación individual', t.individual], ['Habitación compartida', t.shared], ['Estudio', t.studio]] as const).map(([value, label]) => <label key={value}><input type=\"checkbox\" checked={draftFilters.roomTypes.includes(value)} onChange={() => setDraftFilters((current) => ({ ...current, roomTypes: toggleValue(current.roomTypes, value) }))} /><span>{label}</span></label>)}</div></fieldset>\n"
new_ui = """      <fieldset><legend>{t.price}</legend><div className="m2-results-filter__pair"><label><span>{t.min}</span><input aria-label={`${t.price} ${t.min}`} type="number" min="0" step="25" value={draftFilters.minPrice} onChange={(event) => setDraftFilters((current) => ({ ...current, minPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{t.max}</span><input aria-label={`${t.price} ${t.max}`} type="number" min="0" step="25" value={draftFilters.maxPrice} onChange={(event) => setDraftFilters((current) => ({ ...current, maxPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
      <fieldset><legend>{t.moveIn}</legend><div className="m2-results-filter__pair m2-results-filter__pair--dates"><label><span>{t.moveIn}</span><input aria-label={t.moveIn} type="date" value={draftFilters.available} onChange={(event) => setDraftFilters((current) => ({ ...current, available: event.target.value }))} /></label><label><span>{t.moveOut}</span><input aria-label={t.moveOut} type="date" min={draftFilters.available || undefined} value={draftFilters.availableUntil} onChange={(event) => setDraftFilters((current) => ({ ...current, availableUntil: event.target.value }))} /></label></div></fieldset>
      <fieldset><legend>{t.priority}</legend><div className="m2-results-filter__checks m2-results-filter__checks--priority">
        <label><input type="checkbox" checked={draftFilters.shower === 'Ducha privada'} onChange={(event) => setDraftFilters((current) => ({ ...current, shower: event.target.checked ? 'Ducha privada' : 'Cualquiera' }))} /><span>{t.privateShower}</span></label>
        <label><input type="checkbox" checked={draftFilters.toilet === 'Aseo privado'} onChange={(event) => setDraftFilters((current) => ({ ...current, toilet: event.target.checked ? 'Aseo privado' : 'Cualquiera' }))} /><span>{t.privateToilet}</span></label>
        <label><input type="checkbox" checked={draftFilters.kitchen === 'Cocina privada'} onChange={(event) => setDraftFilters((current) => ({ ...current, kitchen: event.target.checked ? 'Cocina privada' : 'Cualquiera' }))} /><span>{t.privateKitchen}</span></label>
        <label><input type="checkbox" checked={fullyPrivate} onChange={(event) => setDraftFilters((current) => ({ ...current, shower: event.target.checked ? 'Ducha privada' : 'Cualquiera', toilet: event.target.checked ? 'Aseo privado' : 'Cualquiera', kitchen: event.target.checked ? 'Cocina privada' : 'Cualquiera' }))} /><span>{t.fullyPrivate}</span></label>
        <label><input type="checkbox" checked={hasDraftAmenity('Aire acondicionado')} onChange={(event) => setDraftAmenity('Aire acondicionado', event.target.checked)} /><span>{t.airConditioning}</span></label>
      </div>
      <label className="m2-results-filter__select"><span>{t.bed}</span><select aria-label={t.bed} value={draftFilters.bedType} onChange={(event) => setDraftFilters((current) => ({ ...current, bedType: event.target.value as Filters['bedType'] }))}><option value="Cualquiera">{t.any}</option><option value="single">{t.singleBed}</option><option value="double">{t.doubleBed}</option></select></label>
      <div className="m2-results-filter__checks m2-results-filter__checks--priority"><label><input type="checkbox" checked={hasDraftAmenity('Ventana a la calle')} onChange={(event) => setDraftAmenity('Ventana a la calle', event.target.checked)} /><span>{t.streetWindow}</span></label><label><input type="checkbox" checked={draftFilters.smoking === 'Sí'} onChange={(event) => setDraftFilters((current) => ({ ...current, smoking: event.target.checked ? 'Sí' : 'Cualquiera' }))} /><span>{t.smokingAllowed}</span></label></div></fieldset>
      <fieldset><legend>{t.bathroomType}</legend><label className="m2-results-filter__select"><span>{t.bathroomType}</span><select aria-label={t.bathroomType} value={bathroomProfile} onChange={(event) => { const value = event.target.value; setDraftFilters((current) => value === 'private' ? { ...current, shower: 'Ducha privada', toilet: 'Aseo privado' } : value === 'private-toilet' ? { ...current, shower: 'Ducha compartida', toilet: 'Aseo privado' } : value === 'shared' ? { ...current, shower: 'Ducha compartida', toilet: 'Aseo compartido' } : value === 'any' ? { ...current, shower: 'Cualquiera', toilet: 'Cualquiera' } : current) }}><option value="any">{t.any}</option><option value="private">{t.bathroomPrivate}</option><option value="private-toilet">{t.toiletPrivateShowerShared}</option><option value="shared">{t.bathroomShared}</option>{bathroomProfile === 'custom' ? <option value="custom">{t.customBathroom}</option> : null}</select></label></fieldset>
      <fieldset><legend>{t.additional}</legend><div className="m2-results-filter__checks"><label><input type="checkbox" checked={hasDraftAmenity('Terraza')} onChange={(event) => setDraftAmenity('Terraza', event.target.checked)} /><span>{t.terrace}</span></label><label><input type="checkbox" checked={hasDraftAmenity('Piscina')} onChange={(event) => setDraftAmenity('Piscina', event.target.checked)} /><span>{t.pool}</span></label><label><input type="checkbox" checked={hasDraftAmenity('Jardín')} onChange={(event) => setDraftAmenity('Jardín', event.target.checked)} /><span>{t.garden}</span></label><label><input type="checkbox" checked={hasDraftAmenity('Ascensor')} onChange={(event) => setDraftAmenity('Ascensor', event.target.checked)} /><span>{t.elevator}</span></label><label><input type="checkbox" checked={hasDraftAmenity('Limpieza incluida')} onChange={(event) => setDraftAmenity('Limpieza incluida', event.target.checked)} /><span>{t.cleaning}</span></label><label><input type="checkbox" checked={draftFilters.accessible === 'Sí'} onChange={(event) => setDraftFilters((current) => ({ ...current, accessible: event.target.checked ? 'Sí' : 'Cualquiera' }))} /><span>{t.accessibleLabel}</span></label></div><label className="m2-results-filter__select"><span>{t.floor}</span><select aria-label={t.floor} value={draftFilters.floor} onChange={(event) => setDraftFilters((current) => ({ ...current, floor: event.target.value as Filters['floor'] }))}><option value="Cualquiera">{t.any}</option><option value="basement">{t.basement}</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4+">4+</option><option value="top">{t.topFloor}</option></select></label></fieldset>
      <fieldset><legend>{t.area}</legend><div className="m2-results-filter__pair"><label><span>{t.min}</span><input aria-label={`${t.area} ${t.min}`} type="number" min="0" value={draftFilters.minArea} onChange={(event) => setDraftFilters((current) => ({ ...current, minArea: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{t.max}</span><input aria-label={`${t.area} ${t.max}`} type="number" min="0" value={draftFilters.maxArea} onChange={(event) => setDraftFilters((current) => ({ ...current, maxArea: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
      <fieldset><legend>{t.rooms}</legend><div className="m2-results-filter__checks m2-results-filter__checks--rooms">{roomCountOptions.map((value) => { const label = value === '10+' ? t.moreThanTenRooms : t.roomCount(value); return <label key={String(value)}><input type="checkbox" checked={draftFilters.roomCounts.includes(value)} onChange={() => setDraftFilters((current) => ({ ...current, roomCounts: toggleValue(current.roomCounts, value) }))} /><span>{label}</span></label> })}</div></fieldset>
      <fieldset><legend>{t.housingType}</legend><div className="m2-results-filter__checks">{([['Habitación individual', t.individual], ['Habitación compartida', t.shared], ['Estudio', t.studio]] as const).map(([value, label]) => <label key={value}><input type="checkbox" checked={draftFilters.roomTypes.includes(value)} onChange={() => setDraftFilters((current) => ({ ...current, roomTypes: toggleValue(current.roomTypes, value) }))} /><span>{label}</span></label>)}</div></fieldset>
"""
replace_between("src/components/mobile-search-results-v2.tsx", old_ui_start, old_ui_end, new_ui)

# Small mobile style additions; keep the approved visual language.
with (ROOT / "src/mobile-search-results.css").open("a", encoding="utf-8") as handle:
    handle.write("""

/* Customer-priority filter controls */
.m2-results-filter__pair--dates input { min-width: 0; padding-inline: .45rem; font-size: .72rem; text-align: left; }
.m2-results-filter__checks--priority { gap: .2rem; margin-bottom: .75rem; }
.m2-results-filter__checks--priority > label { min-height: 2.8rem; padding: .3rem 0; border-bottom: 1px solid #303030; }
.m2-results-filter__checks--priority > label:last-child { border-bottom: 0; }
""")

# ---------------------------------------------------------------------------
# Google Maps: map drag places marker, reverse-geocodes, shows detected address.
# ---------------------------------------------------------------------------
map_file = r'''import { useEffect, useRef, useState } from 'react'
import { useI18n } from '@/contexts/i18n-context'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, TENERIFE_CENTER, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'

const DOUBLE_TAP_DELAY_MS = 360
const DOUBLE_TAP_DISTANCE_PX = 28
const TAP_MOVE_TOLERANCE_PX = 14

type AddressResolvedDetail = {
  formattedAddress: string
  addressComponents: google.maps.GeocoderAddressComponent[]
  coordinates: Coordinates
}

type LocationSelectedDetail = { coordinates?: Coordinates }

export function ApproximateLocationMap({ coordinates, onChange }: { coordinates: Coordinates; onChange: (coordinates: Coordinates) => void }) {
  const { language } = useI18n()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null)
  const onChangeRef = useRef(onChange)
  const initialCoordinatesRef = useRef(coordinates)
  const internalChangeRef = useRef(false)
  const [error, setError] = useState('')
  const [detectedAddress, setDetectedAddress] = useState('')
  const guidance = language === 'ru'
    ? 'Перемещайте карту: после отпускания маркер встанет в центр, а адрес определится автоматически. Маркер также можно перетаскивать.'
    : language === 'en'
      ? 'Move the map: when you release it, the marker is placed in the centre and the address is detected automatically. You can also drag the marker.'
      : 'Mueve el mapa: al soltarlo, el marcador se coloca en el centro y la dirección se detecta automáticamente. También puedes arrastrar el marcador.'
  const mapLabel = language === 'ru'
    ? `Google Maps для выбора местоположения. ${guidance}`
    : language === 'en'
      ? `Google Maps for choosing a location. ${guidance}`
      : `Google Maps para elegir una ubicación. ${guidance}`
  const detectedLabel = language === 'ru' ? 'Определённый адрес' : language === 'en' ? 'Detected address' : 'Dirección detectada'

  useEffect(() => { onChangeRef.current = onChange }, [onChange])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    let dragListener: google.maps.MapsEventListener | null = null
    let mapDragEndListener: google.maps.MapsEventListener | null = null
    let mapDoubleClickListener: google.maps.MapsEventListener | null = null
    let removePointerListeners: (() => void) | null = null
    let pointerStart: { id: number; x: number; y: number } | null = null
    let lastTap: { at: number; x: number; y: number } | null = null
    let geocoder: google.maps.Geocoder | null = null
    const handleAuthFailure = () => setError(googleMapsAuthErrorMessage)
    window.addEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)

    loadGoogleMaps().then(async ({ maps, marker }) => {
      if (cancelled || !containerRef.current) return
      if (!googleMapsConfig.mapId) throw new GoogleMapsSetupError('missing-map-id')
      const requestedInitial = initialCoordinatesRef.current
      const initial = isInsideTenerife(requestedInitial) ? requestedInitial : TENERIFE_CENTER
      const mapInstance = new maps.Map(containerRef.current, {
        center: initial,
        zoom: 16,
        minZoom: 10,
        maxZoom: 20,
        mapId: googleMapsConfig.mapId,
        mapTypeId: 'roadmap',
        disableDefaultUI: true,
        zoomControl: true,
        clickableIcons: false,
        gestureHandling: 'greedy',
        disableDoubleClickZoom: true,
        restriction: { latLngBounds: TENERIFE_BOUNDS, strictBounds: true },
      })
      const pin = new marker.PinElement({ background: '#dff34f', borderColor: '#344500', glyphColor: '#344500', scale: 1.15 })
      const publicMarker = new marker.AdvancedMarkerElement({ map: mapInstance, position: initial, content: pin, gmpDraggable: true, title: 'Ubicación seleccionada' })

      if (!googleMapsTestSdkEnabled) {
        try {
          const geocoding = await google.maps.importLibrary('geocoding') as google.maps.GeocodingLibrary
          geocoder = new geocoding.Geocoder()
        } catch {
          // The map remains fully usable if geocoding is temporarily unavailable.
        }
      }

      const resolveAddress = async (point: Coordinates) => {
        if (!geocoder || cancelled) return
        try {
          const response = await geocoder.geocode({ location: point })
          const result = response.results[0]
          if (!result || cancelled) return
          setDetectedAddress(result.formatted_address)
          window.dispatchEvent(new CustomEvent<AddressResolvedDetail>('112233:map-address-resolved', { detail: { formattedAddress: result.formatted_address, addressComponents: result.address_components, coordinates: point } }))
        } catch {
          if (!cancelled) setDetectedAddress('')
        }
      }

      const commitPoint = (point: Coordinates, detectAddress = true) => {
        if (!isInsideTenerife(point)) return
        publicMarker.position = point
        internalChangeRef.current = true
        onChangeRef.current(point)
        if (detectAddress) void resolveAddress(point)
      }

      const pointFromClientPosition = (clientX: number, clientY: number): Coordinates | null => {
        const projection = mapInstance.getProjection()
        const center = mapInstance.getCenter()
        const zoom = mapInstance.getZoom()
        if (!projection || !center || zoom == null) return null
        const centerWorld = projection.fromLatLngToPoint(center)
        if (!centerWorld) return null
        const rect = container.getBoundingClientRect()
        if (!rect.width || !rect.height) return null
        const scale = 2 ** zoom
        const worldPoint = new google.maps.Point(centerWorld.x + (clientX - rect.left - rect.width / 2) / scale, centerWorld.y + (clientY - rect.top - rect.height / 2) / scale)
        const latLng = projection.fromPointToLatLng(worldPoint)
        return latLng ? { lat: latLng.lat(), lng: latLng.lng() } : null
      }

      const placeFromClientPosition = (clientX: number, clientY: number) => {
        const point = pointFromClientPosition(clientX, clientY)
        if (point) commitPoint(point)
      }

      dragListener = publicMarker.addListener('dragend', () => {
        const position = publicMarker.position
        if (!position) return
        const point = position instanceof google.maps.LatLng ? { lat: position.lat(), lng: position.lng() } : { lat: position.lat, lng: position.lng }
        mapInstance.panTo(point)
        commitPoint(point)
      })
      mapDragEndListener = mapInstance.addListener('dragend', () => {
        const center = mapInstance.getCenter()
        if (center) commitPoint({ lat: center.lat(), lng: center.lng() })
      })
      mapDoubleClickListener = mapInstance.addListener('dblclick', (event: google.maps.MapMouseEvent) => {
        const latLng = event.latLng
        if (latLng) commitPoint({ lat: latLng.lat(), lng: latLng.lng() })
      })

      const handleSelectedLocation = (event: Event) => {
        const point = (event as CustomEvent<LocationSelectedDetail>).detail?.coordinates
        if (!point || !isInsideTenerife(point)) return
        mapInstance.panTo(point)
        mapInstance.setZoom(Math.max(mapInstance.getZoom() ?? 16, 17))
        commitPoint(point, false)
      }
      window.addEventListener('112233:publish-location-selected', handleSelectedLocation)

      const handleDoubleClick = (event: MouseEvent) => { event.preventDefault(); placeFromClientPosition(event.clientX, event.clientY) }
      const handlePointerDown = (event: PointerEvent) => { if (event.pointerType !== 'mouse') pointerStart = { id: event.pointerId, x: event.clientX, y: event.clientY } }
      const handlePointerUp = (event: PointerEvent) => {
        if (event.pointerType === 'mouse' || !pointerStart || pointerStart.id !== event.pointerId) return
        const moved = Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y)
        pointerStart = null
        if (moved > TAP_MOVE_TOLERANCE_PX) { lastTap = null; return }
        const now = performance.now()
        if (lastTap && now - lastTap.at <= DOUBLE_TAP_DELAY_MS && Math.hypot(event.clientX - lastTap.x, event.clientY - lastTap.y) <= DOUBLE_TAP_DISTANCE_PX) {
          event.preventDefault(); placeFromClientPosition(event.clientX, event.clientY); lastTap = null; return
        }
        lastTap = { at: now, x: event.clientX, y: event.clientY }
      }
      const handlePointerCancel = () => { pointerStart = null; lastTap = null }

      container.addEventListener('dblclick', handleDoubleClick, true)
      container.addEventListener('pointerdown', handlePointerDown, true)
      container.addEventListener('pointerup', handlePointerUp, true)
      container.addEventListener('pointercancel', handlePointerCancel, true)
      removePointerListeners = () => {
        container.removeEventListener('dblclick', handleDoubleClick, true)
        container.removeEventListener('pointerdown', handlePointerDown, true)
        container.removeEventListener('pointerup', handlePointerUp, true)
        container.removeEventListener('pointercancel', handlePointerCancel, true)
        window.removeEventListener('112233:publish-location-selected', handleSelectedLocation)
      }

      mapRef.current = mapInstance
      markerRef.current = publicMarker
      resizeObserver = new ResizeObserver(() => { const center = mapInstance.getCenter(); google.maps.event.trigger(mapInstance, 'resize'); if (center) mapInstance.setCenter(center) })
      resizeObserver.observe(containerRef.current)
    }).catch((loadError) => { if (!cancelled) setError(googleMapsErrorMessage(loadError)) })

    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      dragListener?.remove()
      mapDragEndListener?.remove()
      mapDoubleClickListener?.remove()
      removePointerListeners?.()
      window.removeEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)
      if (markerRef.current) markerRef.current.map = null
      if (mapRef.current) google.maps.event.clearInstanceListeners(mapRef.current)
      mapRef.current = null
      markerRef.current = null
      container.replaceChildren()
    }
  }, [])

  useEffect(() => {
    if (!isInsideTenerife(coordinates)) return
    if (markerRef.current) markerRef.current.position = coordinates
    if (internalChangeRef.current) { internalChangeRef.current = false; return }
    mapRef.current?.panTo(coordinates)
  }, [coordinates.lat, coordinates.lng, coordinates])

  return <div className="approximate-location-map-shell google-map-shell" data-provider="google-maps">
    <div ref={containerRef} className="approximate-location-map google-map-canvas" role="application" aria-label={mapLabel} />
    <p className="approximate-location-map-hint">{guidance}</p>
    {detectedAddress ? <p className="approximate-location-map-address" aria-live="polite"><strong>{detectedLabel}:</strong> {detectedAddress}</p> : null}
    {error ? <p className="map-inline-error" role="alert">{error}</p> : null}
  </div>
}
'''
write("src/components/map/approximate-location-map.tsx", map_file)

# New Places (New) autocomplete enhancer. In CI test SDK it keeps the native input
# and still handles custom address events, so deterministic tests do not call Google.
enhancer = r'''import { useEffect } from 'react'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'
import '@/publish-location-enhancer.css'

type AddressComponent = { longText?: string; long_name?: string; types: string[] }
type AddressDetail = { formattedAddress?: string; addressComponents?: AddressComponent[]; coordinates?: Coordinates }

function component(components: AddressComponent[], type: string) {
  const item = components.find((entry) => entry.types.includes(type))
  return item?.longText ?? item?.long_name ?? ''
}

function setNativeValue(element: HTMLInputElement | HTMLSelectElement | null, value: string) {
  if (!element || !value) return
  if (element instanceof HTMLSelectElement && !Array.from(element.options).some((option) => option.value === value)) return
  const prototype = element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set
  setter?.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
  element.dispatchEvent(new Event('change', { bubbles: true }))
}

function applyAddress(detail: AddressDetail) {
  const components = detail.addressComponents ?? []
  const route = component(components, 'route')
  const number = component(components, 'street_number')
  const postcode = component(components, 'postal_code')
  const city = component(components, 'locality') || component(components, 'administrative_area_level_3')
  const area = component(components, 'sublocality_level_1') || component(components, 'sublocality') || component(components, 'neighborhood')
  const street = [route, number].filter(Boolean).join(' ').trim() || detail.formattedAddress?.split(',')[0]?.trim() || ''
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-street'), street)
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-postcode'), postcode)
  setNativeValue(document.querySelector<HTMLSelectElement>('#publish-city'), city)
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-area'), area)
}

export function PublishLocationEnhancer() {
  useEffect(() => {
    let cancelled = false
    const widgets = new Set<HTMLElement>()

    const handleResolved = (event: Event) => applyAddress((event as CustomEvent<AddressDetail>).detail ?? {})
    window.addEventListener('112233:map-address-resolved', handleResolved)

    const setup = async () => {
      const input = document.querySelector<HTMLInputElement>('#publish-street')
      if (!input || input.dataset.addressAutocomplete) return
      input.dataset.addressAutocomplete = 'pending'
      input.placeholder = 'Empieza a escribir Calle, número…'
      input.autocomplete = 'street-address'
      if (googleMapsTestSdkEnabled) { input.dataset.addressAutocomplete = 'test'; return }
      try {
        await loadGoogleMaps()
        const places = await google.maps.importLibrary('places') as google.maps.PlacesLibrary
        if (cancelled || !input.isConnected) return
        const autocomplete = new places.PlaceAutocompleteElement({})
        autocomplete.classList.add('publish-place-autocomplete')
        autocomplete.placeholder = 'Empieza a escribir Calle, número…'
        autocomplete.includedRegionCodes = ['es']
        autocomplete.locationRestriction = TENERIFE_BOUNDS
        autocomplete.setAttribute('aria-label', 'Calle y número')
        autocomplete.addEventListener('gmp-select', async (rawEvent) => {
          const event = rawEvent as google.maps.places.PlacePredictionSelectEvent
          const place = event.placePrediction.toPlace()
          await place.fetchFields({ fields: ['formattedAddress', 'location', 'addressComponents'] })
          if (!place.location) return
          const coordinates = { lat: place.location.lat(), lng: place.location.lng() }
          if (!isInsideTenerife(coordinates)) return
          const detail: AddressDetail = { formattedAddress: place.formattedAddress ?? '', addressComponents: (place.addressComponents ?? []) as AddressComponent[], coordinates }
          applyAddress(detail)
          window.dispatchEvent(new CustomEvent('112233:publish-location-selected', { detail: { coordinates } }))
        })
        input.insertAdjacentElement('beforebegin', autocomplete)
        input.classList.add('publish-street-source-input')
        input.dataset.addressAutocomplete = 'ready'
        widgets.add(autocomplete)
      } catch {
        input.dataset.addressAutocomplete = 'fallback'
        input.classList.remove('publish-street-source-input')
      }
    }

    const observer = new MutationObserver(() => { void setup() })
    observer.observe(document.body, { childList: true, subtree: true })
    void setup()
    return () => {
      cancelled = true
      observer.disconnect()
      window.removeEventListener('112233:map-address-resolved', handleResolved)
      widgets.forEach((widget) => widget.remove())
    }
  }, [])
  return null
}
'''
write("src/components/publish-location-enhancer.tsx", enhancer)
write("src/publish-location-enhancer.css", """.publish-place-autocomplete { width: 100%; min-height: 2.75rem; color-scheme: light; }\n.publish-street-source-input { position: absolute !important; width: 1px !important; height: 1px !important; padding: 0 !important; margin: -1px !important; overflow: hidden !important; clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important; }\n.approximate-location-map-address { margin: .45rem 0 0; padding: .55rem .7rem; border: 1px solid var(--border); border-radius: .45rem; background: var(--muted); font-size: .82rem; line-height: 1.35; }\n""")
replace(
    "src/components/layout.tsx",
    "import { MobileSearchResults } from '@/components/mobile-search-results-v2'\n",
    "import { MobileSearchResults } from '@/components/mobile-search-results-v2'\nimport { PublishLocationEnhancer } from '@/components/publish-location-enhancer'\n",
)
replace(
    "src/components/layout.tsx",
    "<main id=\"main-content\" tabIndex={-1}><MobileAppV2 />",
    "<main id=\"main-content\" tabIndex={-1}><PublishLocationEnhancer /><MobileAppV2 />",
)

# ---------------------------------------------------------------------------
# Backend: structured floor is a nullable, expand-only room-detail attribute.
# ---------------------------------------------------------------------------
replace(
    "backend/app/models/room_details.py",
    "    accessible: Mapped[bool | None] = mapped_column(Boolean)\n    couples_allowed: Mapped[bool | None] = mapped_column(Boolean)\n",
    "    accessible: Mapped[bool | None] = mapped_column(Boolean)\n    floor: Mapped[str | None] = mapped_column(String(16))\n    couples_allowed: Mapped[bool | None] = mapped_column(Boolean)\n",
)

schema = "backend/app/schemas/listings.py"
replace(schema, "ALLOWED_HEATING_TYPES = {\"individual\", \"central\", \"none\", \"unknown\"}\n", "ALLOWED_HEATING_TYPES = {\"individual\", \"central\", \"none\", \"unknown\"}\nALLOWED_FLOORS = {\"basement\", \"1\", \"2\", \"3\", \"4+\", \"top\"}\n")
replace(schema, "    accessible: bool | None = None\n    couplesAllowed: bool | None = None\n", "    accessible: bool | None = None\n    floor: str | None = Field(default=None, max_length=16)\n    couplesAllowed: bool | None = None\n", count=2)
replace(schema, "        if self.heatingType is not None and self.heatingType not in ALLOWED_HEATING_TYPES:\n            raise ValueError(\"heatingType contains an unsupported value\")\n", "        if self.heatingType is not None and self.heatingType not in ALLOWED_HEATING_TYPES:\n            raise ValueError(\"heatingType contains an unsupported value\")\n        if self.floor is not None and self.floor not in ALLOWED_FLOORS:\n            raise ValueError(\"floor contains an unsupported value\")\n", count=2)
replace(schema, "            \"accessible\",\n            \"couplesAllowed\",\n", "            \"accessible\",\n            \"floor\",\n            \"couplesAllowed\",\n")
replace(schema, "    accessible: bool | None = None\n    couplesAllowed: bool | None = None\n    acceptedTenantTypes: list[str] = Field(default_factory=list)\n", "    accessible: bool | None = None\n    floor: str | None = None\n    couplesAllowed: bool | None = None\n    acceptedTenantTypes: list[str] = Field(default_factory=list)\n")
replace(schema, "    accessible: bool | None = None\n    couplesAllowed: bool | None = None\n    acceptedTenantTypes: list[str] = Field(default_factory=list, max_length=4)\n", "    accessible: bool | None = None\n    floor: str | None = Field(default=None, max_length=16)\n    couplesAllowed: bool | None = None\n    acceptedTenantTypes: list[str] = Field(default_factory=list, max_length=4)\n")
# Search request validator has its own validation tail.
replace(schema, "        if self.heatingType not in {None, *ALLOWED_HEATING_TYPES}:\n            raise ValueError(\"heatingType contains an unsupported value\")\n", "        if self.heatingType not in {None, *ALLOWED_HEATING_TYPES}:\n            raise ValueError(\"heatingType contains an unsupported value\")\n        if self.floor not in {None, *ALLOWED_FLOORS}:\n            raise ValueError(\"floor contains an unsupported value\")\n")

replace(
    "backend/app/services/listings.py",
    "    \"accessible\": \"accessible\",\n    \"couplesAllowed\": \"couples_allowed\",\n",
    "    \"accessible\": \"accessible\",\n    \"floor\": \"floor\",\n    \"couplesAllowed\": \"couples_allowed\",\n",
)
replace(
    "backend/app/repositories/listings.py",
    "        accessible=room_details.accessible if room_details else None,\n        couplesAllowed=room_details.couples_allowed if room_details else None,\n",
    "        accessible=room_details.accessible if room_details else None,\n        floor=room_details.floor if room_details else None,\n        couplesAllowed=room_details.couples_allowed if room_details else None,\n",
)
replace(
    "backend/app/repositories/listings.py",
    "    if payload.accessible is not None:\n        query = query.where(ListingRoomDetails.accessible == payload.accessible)\n    if payload.couplesAllowed is not None:\n",
    "    if payload.accessible is not None:\n        query = query.where(ListingRoomDetails.accessible == payload.accessible)\n    if payload.floor:\n        query = query.where(ListingRoomDetails.floor == payload.floor)\n    if payload.couplesAllowed is not None:\n",
)

write("backend/alembic/versions/0035_room_floor.py", '''"""Add a structured floor value to room details.\n\nRevision ID: 0035_room_floor\nRevises: 0034_room_first_listing_details\n"""\n\nfrom collections.abc import Sequence\n\nfrom alembic import op\nimport sqlalchemy as sa\n\nrevision: str = "0035_room_floor"\ndown_revision: str | None = "0034_room_first_listing_details"\nbranch_labels: str | Sequence[str] | None = None\ndepends_on: str | Sequence[str] | None = None\n\n\ndef upgrade() -> None:\n    op.add_column("listing_room_details", sa.Column("floor", sa.String(length=16), nullable=True))\n    op.create_check_constraint("ck_room_details_floor", "listing_room_details", "floor IS NULL OR floor IN ('basement', '1', '2', '3', '4+', 'top')")\n\n\ndef downgrade() -> None:\n    op.drop_constraint("ck_room_details_floor", "listing_room_details", type_="check")\n    op.drop_column("listing_room_details", "floor")\n''')

# ---------------------------------------------------------------------------
# Regression coverage.
# ---------------------------------------------------------------------------
write("backend/tests/test_customer_priority_filter_contract.py", '''import pytest\nfrom pydantic import ValidationError\n\nfrom app.schemas.listings import ListingSearchRequest\nfrom app.services.listings import ROOM_DETAIL_MAPPING\n\n\ndef test_floor_filter_contract_is_structured_and_validated():\n    assert ListingSearchRequest(floor="basement").floor == "basement"\n    assert ListingSearchRequest(floor="top").floor == "top"\n    assert ListingSearchRequest(floor="4+").floor == "4+"\n    assert ROOM_DETAIL_MAPPING["floor"] == "floor"\n\n    with pytest.raises(ValidationError):\n        ListingSearchRequest(floor="between floors")\n''')

write("tests/customer-priority-filters-location.spec.ts", r'''import { expect, test, type Page } from '@playwright/test'

async function openAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('CUSTOMER-PRIORITY mobile filters follow the requested decision order and persist to URL', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&panel=filtros')
  const panel = page.locator('.m2-results-filter')
  await expect(panel).toBeVisible()
  const text = await panel.locator('.m2-results-filter__scroll').innerText()
  const ordered = ['Precio', 'Fecha de entrada', 'Ducha / baño privado en la habitación', 'Aseo / WC privado en la habitación', 'Cocina / mini-cocina privada en la habitación', 'Zona totalmente privada', 'Aire acondicionado', 'Tipo de cama', 'Ventana a la calle', 'Se permite fumar']
  for (let index = 1; index < ordered.length; index += 1) expect(text.indexOf(ordered[index - 1])).toBeLessThan(text.indexOf(ordered[index]))

  await panel.getByText('Zona totalmente privada', { exact: false }).click()
  await panel.getByText('Aire acondicionado', { exact: true }).click()
  await panel.getByLabel('Tipo de cama').selectOption('double')
  await panel.getByText('Ventana a la calle', { exact: true }).click()
  await panel.getByText('Se permite fumar', { exact: true }).click()
  await panel.getByText('Ascensor', { exact: true }).click()
  await panel.getByLabel('Planta').selectOption('top')
  await panel.getByRole('button', { name: /Ver anuncios/ }).click()

  await expect(page).toHaveURL(/ducha=Ducha(?:\+|%20)privada/)
  await expect(page).toHaveURL(/aseo=Aseo(?:\+|%20)privado/)
  await expect(page).toHaveURL(/cocina=Cocina(?:\+|%20)privada/)
  await expect(page).toHaveURL(/cama=double/)
  await expect(page).toHaveURL(/fumar=S%C3%AD/)
  await expect(page).toHaveURL(/planta=top/)
  await expect(page).toHaveURL(/servicios=/)
})

test('CUSTOMER-PRIORITY bathroom profile supports private toilet with shared shower', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&panel=filtros')
  const panel = page.locator('.m2-results-filter')
  await panel.getByLabel('Tipo de baño / aseo').selectOption('private-toilet')
  await expect(panel.getByText('Ducha / baño privado en la habitación', { exact: true }).locator('..').locator('input')).not.toBeChecked()
  await expect(panel.getByText('Aseo / WC privado en la habitación', { exact: true }).locator('..').locator('input')).toBeChecked()
  await panel.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(page).toHaveURL(/ducha=Ducha(?:\+|%20)compartida/)
  await expect(page).toHaveURL(/aseo=Aseo(?:\+|%20)privado/)
})

test('CUSTOMER-LOCATION map/geocoder event updates address fields and floor is in publication data', async ({ page }) => {
  await openAsHost(page)
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByLabel('Calle')).toBeVisible()
  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail: {
      formattedAddress: 'Calle Londres 4, 38660 Costa Adeje, España',
      coordinates: { lat: 28.092, lng: -16.733 },
      addressComponents: [
        { long_name: 'Calle Londres', types: ['route'] },
        { long_name: '4', types: ['street_number'] },
        { long_name: '38660', types: ['postal_code'] },
        { long_name: 'Adeje', types: ['locality'] },
        { long_name: 'Costa Adeje', types: ['sublocality_level_1'] },
      ],
    } }))
  })
  await expect(page.getByLabel('Calle')).toHaveValue('Calle Londres 4')
  await expect(page.getByLabel('Código postal')).toHaveValue('38660')
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Costa Adeje')

  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByLabel('Planta').selectOption('top')
  await expect(page.getByText('Piscina', { exact: true })).toBeVisible()
  await expect(page.getByText('Jardín', { exact: true })).toBeVisible()
  await expect(page.getByText('Limpieza incluida', { exact: true })).toBeVisible()
  await expect(page.getByText('Ventana a la calle', { exact: true })).toBeVisible()
  const draft = await page.evaluate(() => JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}').data)
  expect(draft.floor).toBe('top')
})
''')

print("customer priority request patch applied")
