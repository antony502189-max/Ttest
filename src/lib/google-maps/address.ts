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

const componentValueByPriority = (components: GoogleAddressComponent[], types: string[]) => {
  for (const type of types) {
    const value = componentValue(components, [type])
    if (value) return value
  }
  return undefined
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
  const city = componentValueByPriority(values, ['administrative_area_level_3', 'administrative_area_level_4', 'locality', 'postal_town'])
  const normalizedCity = city?.trim().toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  const area = [
    componentValue(values, ['neighborhood']),
    componentValue(values, ['sublocality_level_1']),
    componentValue(values, ['sublocality']),
    componentValue(values, ['postal_town']),
    componentValue(values, ['locality']),
  ].find((value) => {
    if (!value) return false
    const normalized = value.trim().toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    return !normalizedCity || normalized !== normalizedCity
  }) ?? city

  return {
    formattedAddress,
    coordinates,
    street,
    postcode: componentValue(values, ['postal_code']),
    // Google often lists the tourist/local place in postal_town/locality while
    // the municipality is carried by administrative_area_level_3/4.
    city,
    area,
  }
}
