import { expect, test } from '@playwright/test'
import { buildDisplayMarkerPositions } from '../src/lib/map-marker-overlap'
import { distanceMeters } from '../src/lib/location-privacy'

type MarkerItem = { id: string; coordinates: { lat: number; lng: number } }

const origin = { lat: 28.1299668, lng: -16.7578612 }

test('coincident map listings get distinct deterministic display positions', () => {
  const items: MarkerItem[] = [
    { id: 'listing-b', coordinates: origin },
    { id: 'listing-a', coordinates: origin },
  ]
  const positions = buildDisplayMarkerPositions(items as never)
  const first = positions.get('listing-a')!
  const second = positions.get('listing-b')!

  expect(first.coincidentCount).toBe(2)
  expect(second.coincidentCount).toBe(2)
  expect(first.position).not.toEqual(second.position)
  expect(distanceMeters(first.position, second.position)).toBeGreaterThan(100)

  const reordered = buildDisplayMarkerPositions([...items].reverse() as never)
  expect(reordered.get('listing-a')?.position).toEqual(first.position)
  expect(reordered.get('listing-b')?.position).toEqual(second.position)
})

test('single marker keeps its real public map position', () => {
  const positions = buildDisplayMarkerPositions([{ id: 'only', coordinates: origin }] as never)
  expect(positions.get('only')).toEqual({ position: origin, coincidentCount: 1 })
})

test('large coincident groups are spread across multiple visible rings', () => {
  const items = Array.from({ length: 22 }, (_, index) => ({ id: `listing-${String(index).padStart(2, '0')}`, coordinates: origin }))
  const positions = buildDisplayMarkerPositions(items as never)
  const unique = new Set([...positions.values()].map(({ position }) => `${position.lat.toFixed(7)},${position.lng.toFixed(7)}`))
  expect(unique.size).toBe(22)
  expect([...positions.values()].every((value) => value.coincidentCount === 22)).toBe(true)
  expect(Math.max(...[...positions.values()].map(({ position }) => distanceMeters(origin, position)))).toBeLessThan(190)
})
