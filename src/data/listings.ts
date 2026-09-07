import type { AcceptedTenantType, Filters, Listing, ListingDraft } from '@/types'

const photos = [
  'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1560185008-b033106af5c3?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1560185127-6ed189bf02f4?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1560448075-bb485b067938?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1615874959474-d609969a20ed?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?auto=format&fit=crop&w=1200&q=82',
  'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=82',
]

const places = [
  ['Adeje', 'Costa Adeje', 28.0902, -16.7260],
  ['Adeje', 'Armeñime', 28.12976, -16.75563],
  ['Arona', 'Playa de las Américas', 28.0640, -16.7310],
  ['Arona', 'Los Cristianos', 28.0509, -16.7172],
  ['Granadilla de Abona', 'San Isidro', 28.0770, -16.5580],
  ['Granadilla de Abona', 'El Médano', 28.0477, -16.5363],
  ['Santa Cruz de Tenerife', 'Santa Cruz de Tenerife', 28.4636, -16.2518],
  ['San Cristóbal de La Laguna', 'La Laguna', 28.4874, -16.3159],
  ['Adeje', 'Adeje', 28.1227, -16.7244],
  ['Arona', 'Arona', 28.0996, -16.6809],
] as const

export const areaCenters = Object.fromEntries(
  places.map((place) => [place[1], { lat: place[2], lng: place[3] }]),
) as Record<string, Listing['coordinates']>

const titles = [
  'Habitación luminosa con escritorio y gastos incluidos',
  'Habitación doble cerca de la playa y la guagua',
  'Habitación con baño privado para teletrabajo',
  'Habitación tranquila en piso compartido reformado',
  'Habitación amueblada junto a todos los servicios',
  'Estudio privado con cocina y terraza',
  'Habitación exterior con armario empotrado',
  'Habitación para curso universitario junto al tranvía',
  'Habitación amplia con balcón y Wi-Fi',
  'Habitación económica en vivienda organizada',
]

const owners = [
  ['Equipo Casa Norte', 'CN'], ['Marina A.', 'MA'], ['Daniel R.', 'DR'], ['Vivienda Campus', 'VC'], ['Isla Rooms', 'IR'],
  ['Atlántico Estancias', 'AE'], ['Nerea S.', 'NS'], ['Clara M.', 'CM'], ['Tenerife Hogar', 'TH'], ['Raúl G.', 'RG'],
] as const

const legacyIds = ['armeñime-luminosa-01', 'cristianos-mar-02', 'medano-teletrabajo-03', 'laguna-estudiantes-04', 'santa-cruz-centro-05', 'americas-estudio-06', 'costa-adeje-terraza-07', 'san-isidro-economica-08']
const legacyPlaceIndices = [1, 3, 5, 7, 6, 2, 0, 4]
const rotatePhotos = (index: number) => Array.from({ length: 6 }, (_, offset) => photos[(index + offset * 2) % photos.length])

const tenantLabels: Record<NonNullable<Listing['tenantRequirement']>, string> = {
  'single-man': 'Solo un hombre',
  'single-woman': 'Solo una mujer',
  'single-person': 'Una persona',
  couple: 'Solo pareja',
  any: 'Sin restricción',
}

const tenantRequirementCycle: NonNullable<Listing['tenantRequirement']>[] = [
  'single-woman',
  'single-man',
  'single-person',
  'couple',
  'any',
]
const compactSingleRoomSeedIndexes = new Set([0, 1, 10, 20, 21, 30])

const buildRestrictions = (index: number, mode: Listing['rentalMode'], tenantRequirement: NonNullable<Listing['tenantRequirement']>) => {
  const restrictions = [tenantLabels[tenantRequirement]]
  restrictions.push(index % 4 === 0 ? 'Mascotas permitidas' : 'Sin mascotas')
  restrictions.push(index % 6 === 0 ? 'Se puede fumar' : 'No fumar')
  restrictions.push(index % 2 === 0 ? 'Empadronamiento posible' : 'Sin empadronamiento')
  restrictions.push(mode === 'holiday' ? 'Mínimo 3 noches' : `Mínimo ${[1, 2, 3, 6][index % 4]} meses`)
  if (index % 3 !== 1) restrictions.push('Gastos incluidos')
  return restrictions
}

const buildListing = (index: number, mode: Listing['rentalMode']): Listing => {
  const placeIndex = index < legacyPlaceIndices.length ? legacyPlaceIndices[index] : index % places.length
  const place = places[placeIndex]
  const owner = owners[index % owners.length]
  const roomCapacity = compactSingleRoomSeedIndexes.has(index) ? 1 : (index % 3) + 1
  const tenantRequirement = compactSingleRoomSeedIndexes.has(index)
    ? 'single-man'
    : tenantRequirementCycle[index % tenantRequirementCycle.length]
  const monthlyPrice = mode === 'holiday' ? 0 : 380 + (index % 8) * 45
  const nightlyPrice = mode === 'holiday' ? 38 + (index % 9) * 7 : 0
  const imageSet = rotatePhotos(index)
  return {
    id: legacyIds[index] ?? `${mode}-${place[1].toLocaleLowerCase('es-ES').replace(/[^a-z0-9áéíóúüñ]+/g, '-')}-${String(index + 1).padStart(2, '0')}`,
    rentalMode: mode,
    title: titles[index % titles.length],
    city: place[0],
    area: place[1],
    approximateAddress: index % 2 === 0 ? `Cerca de ${place[1]} · ubicación aproximada` : 'Zona centro · ubicación aproximada',
    coordinates: { lat: place[2] + ((index % 3) - 1) * 0.0025, lng: place[3] + ((index % 4) - 1.5) * 0.0025 },
    price: monthlyPrice,
    nightlyPrice,
    bills: mode === 'holiday' ? 'Limpieza incluida' : index % 3 === 1 ? '+ gastos' : 'Gastos incluidos',
    deposit: mode === 'holiday' ? 'Sin fianza' : `${monthlyPrice || 450} € de fianza`,
    roomType: roomCapacity === 1 ? 'Habitación individual' : 'Habitación doble',
    roomSizeM2: 10 + (index % 8),
    homeSizeM2: 68 + (index % 7) * 11,
    bedroomCount: 2 + (index % 5),
    bathroomCount: 1 + (index % 3),
    currentResidents: 1 + (index % 5),
    roomCapacity,
    rentalUnit: index % 9 === 5 ? 'studio' : 'room',
    bedType: index % 4 === 0 ? 'double' : 'single',
    bedCount: index % 7 === 2 ? 2 : 1,
    currentRoomResidents: index % 3 === 0 ? 0 : 1,
    bathroom: index % 5 === 0 ? 'Baño privado' : 'Baño compartido',
    toilet: index % 4 === 0 ? 'Aseo privado' : 'Aseo compartido',
    shower: index % 5 === 0 ? 'Ducha privada' : 'Ducha compartida',
    kitchen: index % 6 === 0 ? 'Cocina privada' : 'Cocina compartida',
    heatingType: index % 5 === 0 ? 'heat-pump' : 'none',
    accessible: index % 8 === 0,
    floor: String(index % 5),
    elevator: index % 3 !== 0,
    furnished: true,
    terrace: index % 4 === 0,
    balcony: index % 5 === 0,
    exterior: index % 3 !== 0,
    restrictions: buildRestrictions(index, mode, tenantRequirement),
    amenities: ['Wi-Fi', 'Lavadora', 'Cocina equipada', index % 2 === 0 ? 'Escritorio' : 'Balcón'],
    tenantRequirement,
    available: index % 4 === 0 ? 'Disponible ahora' : 'Disponible pronto',
    availableFrom: `2026-${String(9 + (index % 3)).padStart(2, '0')}-${String(1 + (index % 24)).padStart(2, '0')}`,
    availableUntil: index % 5 === 0 ? `2027-0${1 + (index % 4)}-15` : '',
    minStayMonths: mode === 'long' ? [1, 2, 3, 6][index % 4] : 0,
    minStayNights: mode === 'holiday' ? [2, 3, 5, 7][index % 4] : 0,
    maxStayNights: mode === 'holiday' && index % 5 === 0 ? 28 : 0,
    description: `Habitación cómoda en ${place[1]}, ${place[0]}. Vivienda organizada, bien comunicada y pensada para una convivencia tranquila.`,
    ownerName: owner[0],
    ownerInitials: owner[1],
    advertiserType: index % 6 === 0 ? 'Profesional' : 'Particular',
    images: imageSet,
    publishedAt: new Date(Date.UTC(2026, 7, 1 + (index % 30), 10 + (index % 8), 0, 0)).toISOString(),
    status: 'published',
    ownerId: index < 4 ? 'host-demo' : `owner-${index % 9}`,
    contactPhone: `+34 6${String(10000000 + index * 1731).slice(-8)}`,
  }
}

export const initialListings: Listing[] = [
  ...Array.from({ length: 35 }, (_, index) => buildListing(index, 'long')),
  ...Array.from({ length: 35 }, (_, index) => buildListing(index + 35, 'holiday')),
]

export const amenityOptions = ['Wi-Fi', 'Lavadora', 'Cocina equipada', 'Escritorio', 'Balcón', 'Terraza', 'Aire acondicionado', 'Lavavajillas']
export const areas = [...new Set(places.map((place) => place[1]))]

export const defaultFilters: Filters = {
  minPrice: 0,
  maxPrice: 1200,
  areas: [],
  roomType: 'Cualquiera',
  tenantRequirement: 'Cualquiera',
  minRoomSize: 0,
  minHomeSize: 0,
  minBedrooms: 0,
  minBathrooms: 0,
  maxResidents: 0,
  minRoomCapacity: 0,
  bedType: 'Cualquiera',
  rentalUnit: 'Cualquiera',
  currentRoomResidents: 'Cualquiera',
  bathroom: 'Cualquiera',
  toilet: 'Cualquiera',
  shower: 'Cualquiera',
  kitchen: 'Cualquiera',
  heatingType: 'Cualquiera',
  accessible: 'Cualquiera',
  available: '',
  restrictions: [],
  amenities: [],
}

export const createDefaultDraft = (): ListingDraft => ({
  publicationKey: crypto.randomUUID(),
  rentalMode: 'long', city: 'Adeje', area: 'Armeñime', street: '', postcode: '38678', coordinates: areaCenters['Armeñime'], locationManuallyMoved: false,
  roomType: 'Habitación individual', roomSizeM2: 14, homeSizeM2: 85, bedroomCount: 5, bathroomCount: 2, currentResidents: 4, roomCapacity: 1,
  rentalUnit: 'room', bedType: 'single', bedCount: 1, currentRoomResidents: 0,
  bathroom: 'Baño compartido', toilet: 'Aseo privado', shower: 'Ducha compartida', kitchen: 'Cocina privada', heatingType: 'none', accessible: false, floor: '1', elevator: false, furnished: true, terrace: false, balcony: false, exterior: true,
  tenantRequirement: 'single-man', restrictions: ['Solo un hombre', 'Sin mascotas', 'No fumar', 'Sin empadronamiento', 'Mínimo 3 meses'], amenities: ['Wi-Fi', 'Lavadora', 'Cocina equipada'],
  price: 650, nightlyPrice: 0, bills: 'Gastos incluidos', deposit: '300 € de fianza', available: 'Disponible ahora', availableFrom: '2026-08-15', availableUntil: '', minStayMonths: 3, minStayNights: 0, maxStayNights: 0,
  description: 'Buscamos una convivencia tranquila. Se respetan los horarios de descanso y se organizan turnos de limpieza.', images: [],
})
