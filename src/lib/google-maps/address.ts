import type { Coordinates } from '@/types'

export type GoogleAddressComponent = {
  long_name?: string
  short_name?: string
  longText?: string
  types: string[]
}

export type ResolvedGoogleAddress = {
  formattedAddress: string
  coordinates: Coordinates
  street?: string
  postcode?: string
  city?: string
  area?: string
}

/** A lightweight guard for APIs that cannot cancel an in-flight geocoding request. */
export function createRequestVersionGate() {
  let current = 0
  return {
    next: () => ++current,
    isCurrent: (version: number) => version === current,
  }
}

const componentValue = (components: GoogleAddressComponent[], types: string[]) => {
  const component = components.find((candidate) => types.some((type) => candidate.types.includes(type)))
  return component?.longText?.trim() || component?.long_name?.trim() || undefined
}

/** Extract only address data Google explicitly returned; callers retain all other draft fields. */
export function parseGoogleAddress(
  components: GoogleAddressComponent[] | undefined,
  formattedAddress: string,
  coordinates: Coordinates,
): ResolvedGoogleAddress {
  const values = components ?? []
  const route = componentValue(values, ['route'])
  const streetNumber = componentValue(values, ['street_number'])
  const street = [route, streetNumber].filter(Boolean).join(' ') || undefined

  return {
    formattedAddress,
    coordinates,
    street,
    postcode: componentValue(values, ['postal_code']),
    city: componentValue(values, ['locality', 'postal_town', 'administrative_area_level_3', 'administrative_area_level_4', 'administrative_area_level_2']),
    area: componentValue(values, ['neighborhood', 'sublocality_level_1', 'sublocality']),
  }
}
