import type { Filters, Listing, ListingDraft } from '@/types'

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
  'Habitación amplia con balcón y fibra',
  'Habitación económica en vivienda organizada',
]

const owners = [
  ['Equipo Casa Norte', 'CN'], ['Marina A.', 'MA'], ['Daniel R.', 'DR'], ['Vivienda Campus', 'VC'], ['Isla Rooms', 'IR'],
  ['Atlántico Estancias', 'AE'], ['Nerea S.', 'NS'], ['Clara M.', 'CM'], ['Tenerife Hogar', 'TH'], ['Raúl G.', 'RG'],
] as const

const legacyIds = ['armeñime-luminosa-01', 'cristianos-mar-02', 'medano-teletrabajo-03', 'laguna-estudiantes-04', 'santa-cruz-centro-05', 'americas-estudio-06', 'costa-adeje-terraza-07', 'san-isidro-economica-08']

const legacyPlaceIndices = [1, 3, 5, 7, 6, 2, 0, 4]

const rotatePhotos = (index: number) => Array.from({ length: 6 }, (_, offset) => photos[(index + offset * 2) % photos.length])

const buildRestrictions = (index: number, mode: Listing['rentalMode']) => {
  const gender = index % 5 === 0 ? 'Solo mujer' : index % 7 === 0 ? 'Solo hombre' : 'Sin preferencia de género'
  const restrictions = [gender]
  restrictions.push(index % 3 === 0 ? 'Parejas permitidas' : 'No parejas')
  restrictions.push(index % 4 === 0 ? 'Mascotas permitidas' : 'Sin mascotas')
  restrictions.push(index % 6 === 0 ? 'Se puede fumar' : 'No fumar')
  restrictions.push(index % 2 === 0 ? 'Empadronamiento posible' : 'Sin empadronamiento')
  restrictions.push(mode === 'holiday' ? 'Mínimo 3 noches' : `Mínimo ${[1, 2, 3, 6][index % 4]} meses`)
  if (index % 3 !== 1) restrictions.push('Gastos incluidos')
  return restrictions
}

export const areas = places.map((place) => place[1])
export const amenityOptions = ['Fibra', 'Escritorio', 'Balcón', 'Ascensor', 'Lavadora', 'Aire acondicionado', 'Terraza', 'Aparcamiento']

export const initialListings: Listing[] = Array.from({ length: 32 }, (_, index) => {
  const place = places[index < legacyPlaceIndices.length ? legacyPlaceIndices[index] : index % places.length]
  const rentalMode: Listing['rentalMode'] = index % 5 === 2 || index % 7 === 5 ? 'holiday' : 'long'
  const minimumStayMonths = rentalMode === 'holiday' ? 0 : [1, 2, 3, 6][index % 4]
  const price = rentalMode === 'holiday' ? 44 + (index % 8) * 7 : 350 + (index % 10) * 45
  const tenantRequirement: Listing['tenantRequirement'] = index % 5 === 0 ? 'single-woman' : index % 7 === 0 ? 'single-man' : index % 3 === 0 ? 'couple' : 'any'
  const roomCapacity: Listing['roomCapacity'] = tenantRequirement === 'couple' || (tenantRequirement === 'any' && index % 4 === 1) ? 2 : 1
  const publishedDate = new Date(Date.UTC(2026, 6, 20 - (index % 31), 12 - (index % 8)))
  const restrictions = buildRestrictions(index, rentalMode)
  const [ownerName, initials] = owners[index % owners.length]
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
    roomType: index % 9 === 5 ? 'Estudio' : index % 8 === 3 ? 'Habitación compartida' : 'Habitación individual',
    available: index % 4 === 0 ? 'Disponible ahora' : `Disponible desde ${1 + (index % 27)} agosto`,
    availableFrom: `2026-${index % 4 === 0 ? '07' : '08'}-${String(1 + (index % 27)).padStart(2, '0')}`,
    availableUntil: rentalMode === 'holiday' ? '2026-12-20' : undefined,
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
    occupants: 1 + (index % 6),
    roomSizeM2: 9 + (index % 10),
    currentResidents: 1 + (index % 6),
    roomCapacity,
    shower: index % 4 === 2 ? 'Ducha privada' : 'Ducha compartida',
    coordinates: { lat: place[2] + ((index % 3) - 1) * 0.0045, lng: place[3] + ((index % 4) - 1.5) * 0.004 },
    genderPreference: restrictions[0] as Listing['genderPreference'],
    tenantRequirement,
    smokingAllowed: restrictions.includes('Se puede fumar'),
    petsAllowed: restrictions.includes('Mascotas permitidas'),
    couplesAllowed: restrictions.includes('Parejas permitidas'),
    childrenAllowed: index % 6 === 1,
    empadronamientoAllowed: restrictions.includes('Empadronamiento posible'),
    restrictions,
    amenities: amenityOptions.filter((_, amenityIndex) => (index + amenityIndex) % 3 !== 0).slice(0, 5),
    description: 'Habitación exterior y cuidada en una vivienda compartida con buena conexión. El anuncio detalla gastos, disponibilidad y normas para que puedas comparar antes de contactar.',
    homeDescription: `Vivienda de ${2 + (index % 4)} dormitorios con zonas comunes equipadas. La posición del mapa es aproximada para proteger la privacidad.`,
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
    allowContactForm: true,
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
  gender: 'Cualquiera',
  bathroom: 'Cualquiera',
  kitchen: 'Cualquiera',
  furnished: false,
  billsIncluded: false,
  deposit: 'Cualquiera',
  occupants: 'Cualquiera',
  roomSizeMin: 0,
  roomSizeMax: 50,
  shower: 'Cualquiera',
  currentResidents: 'Cualquiera',
  roomCapacity: 'Cualquiera',
  minimumNights: 0,
  availableUntil: '',
  smoking: 'Cualquiera',
  pets: 'Cualquiera',
  couples: 'Cualquiera',
  children: 'Cualquiera',
  empadronamiento: 'Cualquiera',
  publicationDate: 'Cualquiera',
  advertiserType: 'Cualquiera',
  amenities: [],
  sort: 'Relevancia',
}

export const createDefaultDraft = (): ListingDraft => ({
  rentalMode: 'long', city: 'Adeje', area: 'Armeñime', street: '', postcode: '38678', coordinates: areaCenters['Armeñime'], roomType: 'Habitación individual', roomSizeM2: 12, currentResidents: 4, roomCapacity: 1,
  bathroom: 'Baño compartido', shower: 'Ducha compartida', kitchen: 'Cocina compartida', furnished: true, amenities: ['Fibra', 'Escritorio', 'Armario'], monthlyPrice: 450, nightlyPrice: 55, weeklyPrice: 330, depositAmount: 450,
  billsIncluded: true, billsNote: 'Todo incluido con uso responsable', availableFrom: '2026-08-01', availableUntil: '2026-12-20', minimumStayMonths: 3, minimumNights: 3, expiresAt: '2026-10-01',
  genderPreference: 'Sin preferencia de género', tenantRequirement: 'single-person', smokingAllowed: false, petsAllowed: false, couplesAllowed: false, childrenAllowed: false, empadronamientoAllowed: true,
  rules: 'Buscamos una convivencia tranquila. Se respetan los horarios de descanso y se organizan turnos de limpieza.', images: rotatePhotos(0),
  title: 'Habitación luminosa con escritorio y gastos incluidos', description: 'Habitación exterior y tranquila en una casa compartida bien cuidada. Dispone de cama, armario y zona de trabajo.',
  contactName: 'Equipo Casa Norte', contactPhone: '+34 600 112 233', contactWhatsapp: '+34 611 223 344', contactEmail: 'anuncios@example.es', showPhone: true, showWhatsApp: true, allowContactForm: true, status: 'Publicado',
})
