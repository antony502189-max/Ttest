import { expect, test } from '@playwright/test'
import { buildDisplayMarkerPositions, coincidentListingIdsFor, exactCoincidentListingIds } from '../src/lib/map-marker-overlap'

type MarkerItem = { id: string; coordinates: { lat: number; lng: number } }

const origin = { lat: 28.1299668, lng: -16.7578612 }

test('coincident map listings keep the same truthful geographic position', () => {
  const items: MarkerItem[] = [
    { id: 'listing-b', coordinates: origin },
    { id: 'listing-a', coordinates: origin },
  ]
  const positions = buildDisplayMarkerPositions(items as never)
  expect(positions.get('listing-a')).toEqual({ position: origin, coincidentCount: 2 })
  expect(positions.get('listing-b')).toEqual({ position: origin, coincidentCount: 2 })
})

test('single marker keeps its real public map position', () => {
  const positions = buildDisplayMarkerPositions([{ id: 'only', coordinates: origin }] as never)
  expect(positions.get('only')).toEqual({ position: origin, coincidentCount: 1 })
})

test('large coincident groups stay on one point for clustering', () => {
  const items = Array.from({ length: 22 }, (_, index) => ({ id: `listing-${String(index).padStart(2, '0')}`, coordinates: origin }))
  const positions = buildDisplayMarkerPositions(items as never)
  expect([...positions.values()].every((value) => value.coincidentCount === 22)).toBe(true)
  expect([...positions.values()].every((value) => value.position.lat === origin.lat && value.position.lng === origin.lng)).toBe(true)
})


test('only a cluster whose listings share the exact real point is expanded into listing choices', () => {
  const items: MarkerItem[] = [
    { id: 'room-a', coordinates: origin },
    { id: 'room-b', coordinates: origin },
    { id: 'nearby-room', coordinates: { lat: origin.lat + 0.0001, lng: origin.lng } },
  ]

  expect(exactCoincidentListingIds(items as never, ['room-a', 'room-b'])).toEqual(['room-a', 'room-b'])
  expect(exactCoincidentListingIds(items as never, ['room-a', 'nearby-room'])).toEqual([])
})


test('four listings at one address remain on one truthful point and are all selectable candidates', () => {
  const items: MarkerItem[] = Array.from({ length: 4 }, (_, index) => ({
    id: `room-${index + 1}`,
    coordinates: origin,
  }))

  const positions = buildDisplayMarkerPositions(items as never)
  expect([...positions.values()]).toHaveLength(4)
  expect([...positions.values()].every((value) => value.coincidentCount === 4)).toBe(true)
  expect([...positions.values()].every((value) => value.position.lat === origin.lat && value.position.lng === origin.lng)).toBe(true)
  expect(exactCoincidentListingIds(items as never, items.map((item) => item.id))).toEqual([
    'room-1',
    'room-2',
    'room-3',
    'room-4',
  ])
})

test('twenty rooms at one address are all available to the carousel', () => {
  const items: MarkerItem[] = Array.from({ length: 20 }, (_, index) => ({
    id: `room-${index + 1}`,
    coordinates: origin,
  }))

  expect(coincidentListingIdsFor(items as never, 'room-1')).toEqual(items.map((item) => item.id))
})
