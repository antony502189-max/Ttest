export type RentalMode = 'long' | 'holiday'
export type ListingStatus = 'Borrador' | 'Pendiente' | 'Publicado' | 'Oculto' | 'Finalizado' | 'Rechazado'
export type UserRole = 'tenant' | 'host' | 'admin'
export type AdvertiserType = 'Particular' | 'Profesional'
export type GenderPreference = 'Cualquiera' | 'Solo hombre' | 'Solo mujer' | 'Sin preferencia de género'
export type YesNoAny = 'Cualquiera' | 'Sí' | 'No'
export type TenantRequirement = 'single-man' | 'single-woman' | 'single-person' | 'couple' | 'any'
export type ShowerType = 'Ducha privada' | 'Ducha compartida'

export interface Owner {
  name: string
  initials: string
  since: string
  response: string
  verified: boolean
}

export interface Coordinates {
  lat: number
  lng: number
}

export interface Listing {
  id: string
  title: string
  city: string
  area: string
  approximateAddress: string
  price: number
  cadence: 'mes' | 'noche'
  monthlyPrice?: number
  nightlyPrice?: number
  weeklyPrice?: number
  rentalMode: RentalMode
  roomType: 'Habitación individual' | 'Habitación compartida' | 'Estudio'
  available: string
  availableFrom: string
  availableUntil?: string
  minimumStay: string
  minimumStayMonths: number
  minimumNights?: number
  deposit: string
  depositAmount: number
  bills: string
  billsIncluded: boolean
  bathroom: 'Baño privado' | 'Baño compartido'
  kitchen: 'Cocina privada' | 'Cocina compartida'
  furnished: boolean
  occupants: number
  roomSizeM2: number
  currentResidents: number
  roomCapacity: 1 | 2
  shower: ShowerType
  coordinates: Coordinates
  genderPreference: GenderPreference
  tenantRequirement: TenantRequirement
  smokingAllowed: boolean
  petsAllowed: boolean
  couplesAllowed: boolean
  childrenAllowed: boolean
  empadronamientoAllowed: boolean
  restrictions: string[]
  amenities: string[]
  description: string
  homeDescription: string
  images: string[]
  owner: Owner
  advertiserType: AdvertiserType
  source?: string
  status: ListingStatus
  publishedAt: string
  views: number
  expiresAt: string
  userCreated?: boolean
  ownerUserId?: string
  contactPhone?: string
  contactWhatsapp?: string
  contactEmail?: string
  showPhone: boolean
  showWhatsApp: boolean
  allowContactForm: boolean
  closedReason?: 'expired' | 'owner'
}

export interface Filters {
  minPrice: number
  maxPrice: number
  areas: string[]
  roomType: string
  available: string
  minStay: string
  conditions: string[]
  gender: GenderPreference
  bathroom: string
  kitchen: string
  furnished: boolean
  billsIncluded: boolean
  deposit: string
  occupants: string
  roomSizeMin: number
  roomSizeMax: number
  shower: string
  currentResidents: string
  roomCapacity: string
  minimumNights: number
  availableUntil: string
  smoking: YesNoAny
  pets: YesNoAny
  couples: YesNoAny
  children: YesNoAny
  empadronamiento: YesNoAny
  publicationDate: string
  advertiserType: string
  amenities: string[]
  sort: string
}

export interface MapPolygonPoint extends Coordinates {}

export interface DemoUser {
  id: string
  name: string
  email: string
  password: string
  role: UserRole
  phone: string
  whatsapp: string
  telegram: string
  about: string
  initials: string
  showPhone: boolean
  showWhatsApp: boolean
  allowContactForm: boolean
  avatarRef?: string
  allowMessaging?: boolean
  blocked?: boolean
}

export interface ListingDraft {
  rentalMode: RentalMode
  city: string
  area: string
  street: string
  postcode: string
  coordinates: Coordinates
  roomType: Listing['roomType']
  roomSizeM2: number
  currentResidents: number
  roomCapacity: 1 | 2
  bathroom: Listing['bathroom']
  shower: ShowerType
  kitchen: Listing['kitchen']
  furnished: boolean
  amenities: string[]
  monthlyPrice: number
  nightlyPrice: number
  weeklyPrice?: number
  depositAmount: number
  billsIncluded: boolean
  billsNote: string
  availableFrom: string
  availableUntil?: string
  minimumStayMonths: number
  minimumNights: number
  expiresAt: string
  genderPreference: GenderPreference
  tenantRequirement: TenantRequirement
  smokingAllowed: boolean
  petsAllowed: boolean
  couplesAllowed: boolean
  childrenAllowed: boolean
  empadronamientoAllowed: boolean
  rules: string
  images: string[]
  title: string
  description: string
  contactName: string
  contactPhone: string
  contactWhatsapp: string
  contactEmail: string
  showPhone: boolean
  showWhatsApp: boolean
  allowContactForm: boolean
  status: ListingStatus
}

export interface ReportRecord {
  id: string
  listingId: string
  reason: string
  comment: string
  createdAt: string
  status: 'Abierta' | 'Resuelta'
}
