export type RentalMode = 'long' | 'holiday'
export type ListingStatus = 'Borrador' | 'Pendiente' | 'Publicado' | 'Oculto' | 'Finalizado' | 'Rechazado'

export interface Owner {
  name: string
  initials: string
  since: string
  response: string
  verified: boolean
}

export interface Listing {
  id: string
  title: string
  city: string
  area: string
  approximateAddress: string
  price: number
  cadence: 'mes' | 'noche'
  rentalMode: RentalMode
  roomType: 'Habitación individual' | 'Habitación compartida' | 'Estudio'
  available: string
  minimumStay: string
  deposit: string
  bills: string
  bathroom: string
  kitchen: string
  furnished: boolean
  occupants: number
  coordinates: { lat: number; lng: number }
  restrictions: string[]
  amenities: string[]
  description: string
  homeDescription: string
  images: string[]
  owner: Owner
  source?: string
  status: ListingStatus
  publishedAt: string
  views: number
  expiresAt: string
}

export interface Filters {
  minPrice: number
  maxPrice: number
  areas: string[]
  roomType: string
  available: string
  minStay: string
  conditions: string[]
  bathroom: string
  kitchen: string
  furnished: boolean
  billsIncluded: boolean
  deposit: string
  occupants: string
  sort: string
}
