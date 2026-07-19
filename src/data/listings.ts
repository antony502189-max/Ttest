import type { Listing } from '@/types'

const photos = [
  'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1560185008-b033106af5c3?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1560185127-6ed189bf02f4?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1560448075-bb485b067938?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1615874959474-d609969a20ed?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?auto=format&fit=crop&w=1200&q=85',
  'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=85',
]

const owner = (name: string, initials: string, verified = true) => ({
  name,
  initials,
  since: 'Publica desde 2023',
  response: 'Suele responder en menos de 1 hora',
  verified,
})

export const listings: Listing[] = [
  {
    id: 'armeñime-luminosa-01', title: 'Habitación luminosa con escritorio y gastos incluidos', city: 'Adeje', area: 'Armeñime',
    approximateAddress: 'Cerca de la plaza de Armeñime · ubicación aproximada', price: 450, cadence: 'mes', rentalMode: 'long', roomType: 'Habitación individual',
    available: 'Disponible ahora', minimumStay: 'Mínimo 3 meses', deposit: '1 mes de fianza', bills: 'Gastos incluidos', bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, occupants: 4,
    coordinates: { x: 34, y: 64, lat: 28.1272, lng: -16.739 }, restrictions: ['Solo hombre', 'Sin mascotas', 'No fumar', 'Sin empadronamiento', 'Mínimo 3 meses', 'Gastos incluidos'],
    amenities: ['Fibra 600 Mb', 'Lavadora', 'Escritorio', 'Armario', 'Limpieza zonas comunes'],
    description: 'Habitación exterior y tranquila en una casa compartida bien cuidada. Dispone de cama individual, armario amplio y zona de trabajo. Buscamos una convivencia respetuosa y estable.',
    homeDescription: 'Casa de 4 dormitorios con cocina equipada, patio interior y dos baños. A pocos minutos de supermercado y paradas de guagua.', images: [photos[0], photos[4], photos[8], photos[9]], owner: owner('Equipo Casa Norte', 'CN'), source: 'Anunciante profesional', status: 'Publicado', publishedAt: 'Publicado hace 2 días', views: 318, expiresAt: '19 sep 2026',
  },
  {
    id: 'cristianos-mar-02', title: 'Habitación doble a 8 min de Playa de Las Vistas', city: 'Arona', area: 'Los Cristianos',
    approximateAddress: 'Zona centro · ubicación aproximada', price: 620, cadence: 'mes', rentalMode: 'long', roomType: 'Habitación individual',
    available: 'Disponible desde 1 agosto', minimumStay: 'Mínimo 6 meses', deposit: '620 €', bills: 'Agua e internet incluidos', bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, occupants: 3,
    coordinates: { x: 62, y: 77, lat: 28.0509, lng: -16.7172 }, restrictions: ['Parejas permitidas', 'Sin mascotas', 'No fumar', 'Empadronamiento posible', 'Mínimo 6 meses'],
    amenities: ['Balcón', 'Ascensor', 'Ventilador de techo', 'Cama doble', 'Cerca de la playa'], description: 'Dormitorio amplio con balcón lateral y mucha luz natural. La vivienda tiene un ambiente tranquilo, ideal para una persona trabajadora o una pareja.',
    homeDescription: 'Piso en tercera planta con ascensor, salón con balcón, cocina independiente y un baño compartido entre tres habitaciones.', images: [photos[1], photos[5], photos[10], photos[3]], owner: owner('Marina A.', 'MA'), status: 'Publicado', publishedAt: 'Publicado hoy', views: 526, expiresAt: '1 oct 2026',
  },
  {
    id: 'medano-teletrabajo-03', title: 'Habitación con baño privado para teletrabajo', city: 'Granadilla de Abona', area: 'El Médano',
    approximateAddress: 'Avenida principal · ubicación aproximada', price: 690, cadence: 'mes', rentalMode: 'long', roomType: 'Habitación individual',
    available: 'Disponible desde 15 agosto', minimumStay: 'Mínimo 2 meses', deposit: '1 mes de fianza', bills: 'Gastos incluidos hasta 60 €', bathroom: 'Baño privado', kitchen: 'Cocina compartida', furnished: true, occupants: 2,
    coordinates: { x: 55, y: 88, lat: 28.0477, lng: -16.5363 }, restrictions: ['Sin preferencia de género', 'Sin mascotas', 'No fumar', 'Empadronamiento posible', 'Gastos incluidos'],
    amenities: ['Baño privado', 'Fibra 1 Gb', 'Escritorio grande', 'Terraza', 'Lavavajillas'], description: 'Suite privada preparada para trabajar desde casa, con baño propio y escritorio de 140 cm. Ambiente sereno y mucha ventilación.',
    homeDescription: 'Apartamento moderno de dos dormitorios con terraza común orientada al sur, cocina abierta y acceso sin escalones.', images: [photos[2], photos[6], photos[11], photos[7]], owner: owner('Daniel R.', 'DR'), status: 'Publicado', publishedAt: 'Publicado hace 4 días', views: 441, expiresAt: '25 sep 2026',
  },
  {
    id: 'laguna-estudiantes-04', title: 'Habitación para curso universitario junto al tranvía', city: 'San Cristóbal de La Laguna', area: 'La Laguna',
    approximateAddress: 'Casco histórico · ubicación aproximada', price: 390, cadence: 'mes', rentalMode: 'long', roomType: 'Habitación individual',
    available: 'Disponible desde 1 septiembre', minimumStay: 'Septiembre a junio', deposit: '390 €', bills: 'Gastos aparte: aprox. 35 €', bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, occupants: 4,
    coordinates: { x: 47, y: 22, lat: 28.4874, lng: -16.3159 }, restrictions: ['Solo estudiante', 'Sin mascotas', 'No fumar', 'Empadronamiento posible', 'Septiembre a junio'],
    amenities: ['Tranvía a 3 min', 'Mesa de estudio', 'Patio', 'Lavadora', 'Cerradura privada'], description: 'Habitación equipada para estudiante en piso compartido de ambiente organizado. Contrato por curso académico y zonas comunes amplias.',
    homeDescription: 'Vivienda de 105 m² con cuatro dormitorios, dos baños, cocina independiente y patio interior.', images: [photos[3], photos[7], photos[9], photos[4]], owner: owner('Vivienda Campus', 'VC'), source: 'Anunciante profesional', status: 'Publicado', publishedAt: 'Publicado ayer', views: 239, expiresAt: '30 sep 2026',
  },
  {
    id: 'santa-cruz-centro-05', title: 'Habitación exterior en piso reformado del centro', city: 'Santa Cruz de Tenerife', area: 'Santa Cruz de Tenerife',
    approximateAddress: 'Zona La Salle · ubicación aproximada', price: 520, cadence: 'mes', rentalMode: 'long', roomType: 'Habitación individual',
    available: 'Disponible ahora', minimumStay: 'Mínimo 4 meses', deposit: '1 mes de fianza', bills: 'Gastos incluidos', bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, occupants: 3,
    coordinates: { x: 70, y: 27, lat: 28.4636, lng: -16.2518 }, restrictions: ['Solo mujer', 'Sin mascotas', 'No fumar', 'Sin empadronamiento', 'Gastos incluidos'],
    amenities: ['Ascensor', 'Cama doble', 'Smart TV', 'Fibra', 'Limpieza quincenal'], description: 'Habitación exterior en una vivienda reformada y silenciosa. Bien conectada con intercambiador, tranvía y zona comercial.',
    homeDescription: 'Piso de tres dormitorios, salón comedor, cocina equipada y baño renovado. Convivencia tranquila entre profesionales.', images: [photos[4], photos[8], photos[0], photos[10]], owner: owner('Isla Rooms', 'IR'), source: 'Anunciante profesional', status: 'Publicado', publishedAt: 'Publicado hace 6 horas', views: 610, expiresAt: '20 oct 2026',
  },
  {
    id: 'americas-estudio-06', title: 'Estudio privado cerca de la playa y zona comercial', city: 'Arona', area: 'Playa de las Américas',
    approximateAddress: 'Cerca de Av. Rafael Puig · ubicación aproximada', price: 78, cadence: 'noche', rentalMode: 'holiday', roomType: 'Estudio',
    available: 'Disponible del 5 al 24 agosto', minimumStay: 'Mínimo 5 noches', deposit: 'Sin fianza', bills: 'Todo incluido', bathroom: 'Baño privado', kitchen: 'Cocina privada', furnished: true, occupants: 2,
    coordinates: { x: 58, y: 72, lat: 28.064, lng: -16.731 }, restrictions: ['Parejas permitidas', 'Sin mascotas', 'No fumar', 'Máximo 2 personas', 'Gastos incluidos'],
    amenities: ['Aire acondicionado', 'Cocina equipada', 'Piscina comunitaria', 'Wi‑Fi', 'Caja de seguridad'], description: 'Estudio independiente, compacto y bien resuelto para una estancia corta en el sur de Tenerife. Check-in autónomo.',
    homeDescription: 'Unidad privada en complejo residencial con piscina. La posición del mapa es aproximada hasta confirmar la reserva.', images: [photos[5], photos[9], photos[1], photos[11]], owner: owner('Atlántico Estancias', 'AE'), status: 'Publicado', publishedAt: 'Actualizado hoy', views: 802, expiresAt: '31 ago 2026',
  },
  {
    id: 'costa-adeje-terraza-07', title: 'Habitación amplia con terraza en Costa Adeje', city: 'Adeje', area: 'Costa Adeje',
    approximateAddress: 'Torviscas Alto · ubicación aproximada', price: 590, cadence: 'mes', rentalMode: 'long', roomType: 'Habitación individual',
    available: 'Disponible desde 20 julio', minimumStay: 'Mínimo 3 meses', deposit: '590 €', bills: 'Luz aparte', bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, occupants: 3,
    coordinates: { x: 40, y: 70, lat: 28.0902, lng: -16.726 }, restrictions: ['Sin preferencia de género', 'Mascota pequeña valorable', 'No fumar', 'Sin empadronamiento', 'Mínimo 3 meses'],
    amenities: ['Terraza', 'Piscina', 'Armario empotrado', 'Aparcamiento fácil', 'Guagua cercana'], description: 'Habitación amplia con acceso directo a terraza compartida y vistas parciales al mar. Zona residencial con servicios próximos.',
    homeDescription: 'Piso de tres dormitorios en urbanización con piscina. Cocina renovada y amplio salón compartido.', images: [photos[6], photos[10], photos[2], photos[8]], owner: owner('Nerea S.', 'NS', false), status: 'Publicado', publishedAt: 'Publicado hace 5 días', views: 352, expiresAt: '10 oct 2026',
  },
  {
    id: 'san-isidro-economica-08', title: 'Habitación amueblada cerca de todos los servicios', city: 'Granadilla de Abona', area: 'San Isidro',
    approximateAddress: 'Zona Mercado · ubicación aproximada', price: 420, cadence: 'mes', rentalMode: 'long', roomType: 'Habitación individual',
    available: 'Disponible ahora', minimumStay: 'Mínimo 3 meses', deposit: '420 €', bills: 'Gastos incluidos', bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, occupants: 4,
    coordinates: { x: 52, y: 79, lat: 28.077, lng: -16.558 }, restrictions: ['Solo mujer', 'Sin mascotas', 'No fumar', 'Empadronamiento posible', 'Gastos incluidos'],
    amenities: ['Fibra', 'Ventana exterior', 'Cerradura', 'Lavadora', 'Guaguas 24 h'], description: 'Dormitorio funcional y luminoso en el centro de San Isidro. Ideal para una persona trabajadora que valore el orden y la buena comunicación.',
    homeDescription: 'Vivienda de cuatro dormitorios con dos baños, cocina comedor y azotea comunitaria.', images: [photos[7], photos[11], photos[3], photos[9]], owner: owner('Clara M.', 'CM'), status: 'Publicado', publishedAt: 'Publicado ayer', views: 191, expiresAt: '28 sep 2026',
  },
]

export const areas = ['Costa Adeje', 'Armeñime', 'Playa de las Américas', 'Los Cristianos', 'San Isidro', 'El Médano', 'Santa Cruz de Tenerife', 'La Laguna']

export const defaultFilters = {
  minPrice: 0, maxPrice: 1000, areas: [] as string[], roomType: 'Cualquiera', available: '', minStay: 'Cualquiera', conditions: [] as string[],
  bathroom: 'Cualquiera', kitchen: 'Cualquiera', furnished: false, billsIncluded: false, deposit: 'Cualquiera', occupants: 'Cualquiera', sort: 'Relevancia',
}
