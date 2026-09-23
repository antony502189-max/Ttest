import type { Listing } from '@/types'

const normalizeAddressPart = (value: string | undefined) =>
  (value ?? '').trim().toLocaleLowerCase('es-ES').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ')

export function privateAddressGroupKey(listing: Pick<Listing, 'street' | 'postcode'>) {
  const street = normalizeAddressPart(listing.street)
  const postcode = normalizeAddressPart(listing.postcode).replace(/\s+/g, '')
  return street && postcode ? `${street}|${postcode}` : null
}

export function sharesPrivateAddressGroup(
  left: Pick<Listing, 'street' | 'postcode'>,
  right: Pick<Listing, 'street' | 'postcode'>,
) {
  const leftKey = privateAddressGroupKey(left)
  return Boolean(leftKey && leftKey === privateAddressGroupKey(right))
}

const coordinatesEqual = (left: Listing['exactCoordinates'], right: Listing['exactCoordinates']) => {
  if (!left || !right) return left === right
  return Math.abs(left.lat - right.lat) < 1e-6 && Math.abs(left.lng - right.lng) < 1e-6
}

export function ownerListingLocationChanged(next: Listing, previous: Listing) {
  return normalizeAddressPart(next.city) !== normalizeAddressPart(previous.city)
    || normalizeAddressPart(next.area) !== normalizeAddressPart(previous.area)
    || normalizeAddressPart(next.street) !== normalizeAddressPart(previous.street)
    || normalizeAddressPart(next.postcode) !== normalizeAddressPart(previous.postcode)
    || !coordinatesEqual(next.exactCoordinates, previous.exactCoordinates)
}

export function applySharedListingLocation(target: Listing, source: Listing): Listing {
  return {
    ...target,
    city: source.city,
    area: source.area,
    street: source.street,
    postcode: source.postcode,
    approximateAddress: source.approximateAddress,
    coordinates: source.coordinates,
    exactCoordinates: source.exactCoordinates,
  }
}
