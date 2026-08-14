export type RentalMode = 'long' | 'holiday'
export type ListingStatus = 'Borrador' | 'Pendiente' | 'Publicado' | 'Oculto' | 'Finalizado' | 'Rechazado'
export type UserRole = 'tenant' | 'host' | 'admin' | 'pending'
export type AdvertiserType = 'Particular' | 'Profesional'
export type YesNoAny = 'Cualquiera' | 'Sí' | 'No'
export type TenantRequirement = 'single-man' | 'single-woman' | 'single-person' | 'couple' | 'any'
export type TenantRequirementFilter = TenantRequirement | 'Cualquiera'
export type ShowerType = 'Ducha privada' | 'Ducha compartida'
export type ToiletType = 'Aseo privado' | 'Aseo compartido'
export type RentalUnit = 'room' | 'bed'
export type BedType = 'single' | 'double'
export type HouseholdGender = 'men' | 'women' | 'mixed' | 'unknown'
export type HeatingType = 'individual' | 'central' | 'none' | 'unknown'
export type AcceptedTenantType = 'man' | 'woman' | 'couple' | 'family'

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
  street?: string
  postcode?: string
  exactCoordinates?: Coordinates
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
  minimumStayMonths: number | null
  minimumNights?: number
  deposit: string
  depositAmount: number | null
  bills: string
  billsIncluded: boolean | null
  bathroom: 'Baño privado' | 'Baño compartido' | null
  kitchen: 'Cocina privada' | 'Cocina compartida' | null
  furnished: boolean | null
  roomSizeM2: number | null
  bedroomCount?: number
  currentResidents: number
  roomCapacity: number | null
  shower: ShowerType
  homeSizeM2?: number | null
  bathroomCount?: number | null
  rentalUnit?: RentalUnit | null
  bedType?: BedType | null
  bedCount?: number | null
  currentRoomResidents?: number | null
  availableSpots?: number | null
  toilet?: ToiletType | null
  householdGender?: HouseholdGender | null
  householdHasChildren?: boolean | null
  heatingType?: HeatingType | null
  accessible?: boolean | null
  couplesAllowed?: boolean | null
  acceptedTenantTypes?: AcceptedTenantType[]
  coordinates: Coordinates
  tenantRequirement: TenantRequirement | null
  smokingAllowed: boolean | null
  petsAllowed: boolean | null
  childrenAllowed: boolean | null
  empadronamientoAllowed: boolean | null
  restrictions: string[]
  amenities: string[]
  description: string
  homeDescription: string
  images: string[]
  owner: Owner
  advertiserType: AdvertiserType
  source?: string
  isExternal?: boolean
  primarySource?: string
  sourceUrl?: string
  sourcePriceText?: string
  priceCurrency?: string
  pricePeriod?: 'month' | 'night' | 'week'
  priceIsFrom?: boolean
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
  closedReason?: 'expired' | 'owner' | 'deleted' | 'account_deleted'
}

export interface Filters {
  minPrice: number
  maxPrice: number
  areas: string[]
  roomType: string
  available: string
  minStay: string
  conditions: string[]
  tenantRequirement: TenantRequirementFilter
  tenantRequirements: TenantRequirement[]
  bathroom: string
  kitchen: string
  furnished: boolean
  billsIncluded: boolean
  deposit: string
  roomSizeMin: number
  roomSizeMax: number
  homeSizeMin: number
  homeSizeMax: number
  bathroomCountMin: number
  rentalUnit: 'Cualquiera' | RentalUnit
  bedType: 'Cualquiera' | BedType
  bedCountMin: number
  shower: string
  toilet: string
  currentResidents: string
  roomResidents: string
  roomCapacity: string
  availableSpotsMin: number
  minimumNights: number
  availableUntil: string
  smoking: YesNoAny
  pets: YesNoAny
  children: YesNoAny
  couplesAllowed: YesNoAny
  householdGender: 'Cualquiera' | HouseholdGender
  householdHasChildren: YesNoAny
  heatingType: 'Cualquiera' | HeatingType
  accessible: YesNoAny
  acceptedTenantTypes: AcceptedTenantType[]
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
  locationManuallyMoved: boolean
  roomType: Listing['roomType']
  roomSizeM2: number
  homeSizeM2: number
  bedroomCount: number
  bathroomCount: number
  currentResidents: number
  roomCapacity: number
  rentalUnit: RentalUnit
  bedType: BedType
  bedCount: number
  currentRoomResidents: number
  bathroom: NonNullable<Listing['bathroom']>
  toilet: ToiletType
  shower: ShowerType
  kitchen: NonNullable<Listing['kitchen']>
  heatingType: HeatingType
  accessible: boolean
  furnished: boolean
  amenities: string[]
  monthlyPrice: number
  nightlyPrice: number
  weeklyPrice?: number
  depositAmount: number
  billsIncluded: boolean
  billsNote: string
  availableFrom: string
  availableUntil: string
  minimumStayMonths: number
  minimumNights: number
  expiresAt: string
  tenantRequirement: TenantRequirement
  acceptedTenantTypes: AcceptedTenantType[]
  householdGender: HouseholdGender
  householdHasChildren: boolean
  couplesAllowed: boolean
  smokingAllowed: boolean
  petsAllowed: boolean
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

export interface LocalMessageThread {
  id: string
  listingId: string
  listingTitle: string
  imageRef: string
  contactName: string
  messagePreview: string
  createdAt: string
  status: 'Demo local' | 'Enviado'
}

export interface LocalListingComment {
  id: string
  userId: string
  listingId: string
  text: string
  createdAt: string
  updatedAt?: string
}
