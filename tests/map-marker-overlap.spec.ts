import { expect, test } from '@playwright/test'
import { buildDisplayMarkerPositions } from '../src/lib/map-marker-overlap'

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
