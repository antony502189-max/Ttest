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
  ['Adeje', 'Armeñime', 28.1272, -16.7390],
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

function acceptedTenants(requirement: NonNullable<Listing['tenantRequirement']>): AcceptedTenantType[] {
  if (requirement === 'single-man') return ['man']
  if (requirement === 'single-woman') return ['woman']
  if (requirement === 'couple') return ['couple']
  return requirement === 'single-person' ? ['man', 'woman'] : ['man', 'woman', 'couple', 'family']
}

export const areas = places.map((place) => place[1])
export const amenityOptions = ['Wi-Fi', 'Escritorio', 'Balcón', 'Ascensor', 'Lavadora', 'Aire acondicionado', 'Terraza', 'Piscina', 'Jardín', 'Limpieza incluida', 'Ventana a la calle', 'Aparcamiento', 'Cocina equipada']

export const initialListings: Listing[] = Array.from({ length: 32 }, (_, index) => {
  const place = places[index < legacyPlaceIndices.length ? legacyPlaceIndices[index] : index % places.length]
  const rentalMode: Listing['rentalMode'] = index % 5 === 2 || index % 7 === 5 ? 'holiday' : 'long'
  const minimumStayMonths = rentalMode === 'holiday' ? 0 : [1, 2, 3, 6][index % 4]
  const price = rentalMode === 'holiday' ? 44 + (index % 8) * 7 : 350 + (index % 10) * 45
  const tenantRequirement = tenantRequirementCycle[index % tenantRequirementCycle.length]
  const roomCapacity: Listing['roomCapacity'] = tenantRequirement === 'couple' || (tenantRequirement === 'any' && index % 4 === 1) ? 2 : 1
  const bedroomCount = compactSingleRoomSeedIndexes.has(index) || index % 9 === 5 ? 1 : 1 + (index % 12)
  const publishedDate = new Date(Date.UTC(2026, 6, 20 - (index % 31), 12 - (index % 8)))
  const restrictions = buildRestrictions(index, rentalMode, tenantRequirement)
  const [ownerName, initials] = owners[index % owners.length]
  const roomType: Listing['roomType'] = index % 9 === 5 ? 'Estudio' : index % 8 === 3 ? 'Habitación compartida' : 'Habitación individual'
  const shared = roomType === 'Habitación compartida'
  const bedType: Listing['bedType'] = shared ? 'single' : index % 3 === 0 ? 'double' : 'single'
  const currentRoomResidents = shared ? Math.min(Math.max(0, (roomCapacity ?? 1) - 1), 1) : 0
  return {
    id: legacyIds[index] ?? `${place[1].toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-')}-${String(index + 1).padStart(2, '0')}`,
    title: titles[index % titles.length],
    city: place[0],
    area: place[1],
    approximateAddress: `${['Zona centro', 'Cerca de la plaza', 'A 8 min de la costa', 'Junto a la parada principal'][index % 4]} · ubicación aproximada`,
    price,
    cadence: rentalMode === 'holiday' ? 'noche' : 'mes',
    monthlyPrice: rentalMode === 'long' ? price : price * 24,
    nightlyPrice: rentalMode === 'holiday' ? price : undefined,
    weeklyPrice: rentalMode === 'holiday' ? price * 6 : undefined,
    rentalMode,
    roomType,
    available: index % 4 === 0 ? 'Disponible ahora' : `Disponible desde ${1 + (index % 27)} agosto`,
    availableFrom: `2026-${index % 4 === 0 ? '07' : '08'}-${String(1 + (index % 27)).padStart(2, '0')}`,
    availableUntil: '2026-12-20',
    minimumStay: rentalMode === 'holiday' ? `Mínimo ${3 + (index % 5)} noches` : `Mínimo ${minimumStayMonths} ${minimumStayMonths === 1 ? 'mes' : 'meses'}`,
    minimumStayMonths,
    minimumNights: rentalMode === 'holiday' ? 3 + (index % 5) : undefined,
    deposit: index % 6 === 0 ? 'Sin fianza' : `${price} €`,
    depositAmount: index % 6 === 0 ? 0 : price,
    bills: index % 3 === 1 ? 'Gastos aparte: aprox. 45 €' : 'Gastos incluidos',
    billsIncluded: index % 3 !== 1,
    bathroom: index % 4 === 2 ? 'Baño privado' : 'Baño compartido',
    kitchen: index % 9 === 5 ? 'Cocina privada' : 'Cocina compartida',
    furnished: index % 11 !== 0,
    roomSizeM2: 9 + (index % 10),
    homeSizeM2: 60 + (index % 8) * 8,
    bedroomCount,
    bathroomCount: 1 + (index % 2),
    currentResidents: 1 + (index % 6),
    roomCapacity,
    rentalUnit: shared ? 'bed' : 'room',
    bedType,
    bedCount: shared ? Math.max(2, roomCapacity ?? 2) : 1,
    currentRoomResidents,
    availableSpots: roomCapacity == null ? null : Math.max(0, roomCapacity - currentRoomResidents),
    toilet: index % 5 === 0 ? 'Aseo privado' : 'Aseo compartido',
    shower: index % 4 === 2 ? 'Ducha privada' : 'Ducha compartida',
    householdGender: index % 3 === 0 ? 'men' : index % 3 === 1 ? 'women' : 'mixed',
    householdHasChildren: index % 6 === 1,
    heatingType: index % 4 === 0 ? 'individual' : index % 7 === 0 ? 'central' : 'none',
    accessible: index % 8 === 0,
    floor: (['basement', '1', '2', '3', '4+', 'top'] as const)[index % 6],
    couplesAllowed: tenantRequirement === 'couple' || tenantRequirement === 'any',
    acceptedTenantTypes: acceptedTenants(tenantRequirement),
    coordinates: { lat: place[2] + ((index % 3) - 1) * 0.0045, lng: place[3] + ((index % 4) - 1.5) * 0.004 },
    tenantRequirement,
    smokingAllowed: restrictions.includes('Se puede fumar'),
    petsAllowed: restrictions.includes('Mascotas permitidas'),
    childrenAllowed: index % 6 === 1,
    empadronamientoAllowed: restrictions.includes('Empadronamiento posible'),
    restrictions,
    amenities: amenityOptions.filter((_, amenityIndex) => (index + amenityIndex) % 3 !== 0).slice(0, 5),
    description: 'Habitación exterior y cuidada en una vivienda compartida con buena conexión. El anuncio detalla gastos, disponibilidad y normas para que puedas comparar antes de contactar.',
    homeDescription: `Vivienda de ${bedroomCount} ${bedroomCount === 1 ? 'dormitorio' : 'dormitorios'} con zonas comunes equipadas. La posición del mapa es aproximada para proteger la privacidad.`,
    images: rotatePhotos(index),
    owner: { name: ownerName, initials, since: `Publica desde ${2021 + (index % 5)}`, response: index % 3 === 0 ? 'Suele responder en menos de 1 hora' : 'Suele responder en el mismo día', verified: index % 7 !== 0 },
    advertiserType: index % 4 === 0 ? 'Profesional' : 'Particular',
    source: index % 4 === 0 ? 'Anunciante profesional' : undefined,
    status: 'Publicado',
    publishedAt: publishedDate.toISOString(),
    views: 90 + index * 37,
    expiresAt: `2026-10-${String(1 + (index % 27)).padStart(2, '0')}`,
    userCreated: index < 3,
    ownerUserId: index < 3 ? 'host-demo' : undefined,
    contactPhone: '+34 600 112 233',
    contactWhatsapp: '+34 611 223 344',
    contactEmail: 'anuncios@example.es',
    showPhone: true,
    showWhatsApp: true,
  }
})

export const listings = initialListings

export const defaultFilters: Filters = {
  minPrice: 0,
  maxPrice: 1200,
  areas: [],
  roomType: 'Cualquiera',
  available: '',
  minStay: 'Cualquiera',
  conditions: [],
  tenantRequirement: 'Cualquiera',
  tenantRequirements: [],
  bathroom: 'Cualquiera',
  kitchen: 'Cualquiera',
  furnished: false,
  billsIncluded: false,
  deposit: 'Cualquiera',
  roomSizeMin: 0,
  roomSizeMax: 50,
  homeSizeMin: 0,
  homeSizeMax: 250,
  bathroomCountMin: 0,
  rentalUnit: 'Cualquiera',
  bedType: 'Cualquiera',
  bedCountMin: 0,
  shower: 'Cualquiera',
  toilet: 'Cualquiera',
  currentResidents: 'Cualquiera',
  roomResidents: 'Cualquiera',
  roomCapacity: 'Cualquiera',
  availableSpotsMin: 0,
  minimumNights: 0,
  availableUntil: '',
  smoking: 'Cualquiera',
  pets: 'Cualquiera',
  children: 'Cualquiera',
  couplesAllowed: 'Cualquiera',
  householdGender: 'Cualquiera',
  householdHasChildren: 'Cualquiera',
  heatingType: 'Cualquiera',
  accessible: 'Cualquiera',
  floor: 'Cualquiera',
  acceptedTenantTypes: [],
  empadronamiento: 'Cualquiera',
  publicationDate: 'Cualquiera',
  advertiserType: 'Cualquiera',
  amenities: [],
  sort: 'Relevancia',
}

export const createDefaultDraft = (): ListingDraft => ({
  publicationKey: crypto.randomUUID(),
  rentalMode: 'long', city: 'Adeje', area: 'Armeñime', street: '', postcode: '38678', coordinates: areaCenters['Armeñime'], locationManuallyMoved: false,
  roomType: 'Habitación individual', roomSizeM2: 14, homeSizeM2: 85, bedroomCount: 5, bathroomCount: 2, currentResidents: 4, roomCapacity: 1,
  rentalUnit: 'room', bedType: 'single', bedCount: 1, currentRoomResidents: 0,
  bathroom: 'Baño compartido', toilet: 'Aseo privado', shower: 'Ducha compartida', kitchen: 'Cocina privada', heatingType: 'none', accessible: false, floor: '1',
  furnished: true, amenities: ['Wi-Fi', 'Escritorio', 'Armario', 'Lavadora', 'Cocina equipada'], monthlyPrice: 450, nightlyPrice: 55, weeklyPrice: 330, depositAmount: 100,
  billsIncluded: true, billsNote: '', availableFrom: '2026-08-15', availableUntil: '', minimumStayMonths: 3, minimumNights: 3, expiresAt: '2026-10-01',
  tenantRequirement: 'single-man', acceptedTenantTypes: ['man'], householdGender: 'men', householdHasChildren: false, couplesAllowed: false,
  smokingAllowed: false, petsAllowed: false, childrenAllowed: false, empadronamientoAllowed: true,
  rules: 'Buscamos una convivencia tranquila. Se respetan los horarios de descanso y se organizan turnos de limpieza.', images: rotatePhotos(0),
  title: 'Habitación privada con cocina y aseo propios', description: 'Habitación exterior y tranquila en una casa compartida bien cuidada. Dispone de cama, armario, cocina privada y aseo privado; la ducha es compartida.',
  contactName: 'Equipo Casa Norte', contactPhone: '+34 600 112 233', contactWhatsapp: '+34 611 223 344', contactEmail: 'anuncios@example.es', showPhone: true, showWhatsApp: true, status: 'Publicado',
})
