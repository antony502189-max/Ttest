import { expect, test } from '@playwright/test'
import { createProgressiveGalleryPage } from '../../src/lib/search'
import type { Listing } from '../../src/types'

const listing = (images = ['cover'], id = 'same-id') => ({ id, images } as Listing)

test('fast callback before cards commit is buffered without blocking the page', () => {
  let state: Listing[] | null = null
  const page = createProgressiveGalleryPage(() => true, update => { state = update(state) })
  page.recover(listing(['cover', 'two']))
  state = page.accept([listing()])
  expect(state[0].images).toEqual(['cover', 'two'])
})

test('queued recovery checks generation when the updater runs even if cancellation fails', () => {
  let active = true
  const queued: Array<(state: Listing[] | null) => Listing[] | null> = []
  const page = createProgressiveGalleryPage(() => active, update => queued.push(update))
  page.accept([listing()])
  page.recover(listing(['cover', 'old']))
  active = false
  const newest = [listing(['new-cover', 'new-two', 'new-three'])]
  expect(queued[0](newest)).toBe(newest)
})

test('same ID does not authorize an obsolete snapshot to replace a newer gallery', () => {
  let state: Listing[] | null = [listing()]
  const page = createProgressiveGalleryPage(() => true, update => { state = update(state) })
  page.accept(state)
  state = [listing(['new-cover', 'new-two', 'new-three'])]
  page.recover(listing(['old-cover', 'old-two']))
  expect(state[0].images).toEqual(['new-cover', 'new-two', 'new-three'])
})

test('current authoritative recovery can remove photos without a monotonic count rule', () => {
  let state: Listing[] | null = [listing(['cover', 'removed'])]
  const page = createProgressiveGalleryPage(() => true, update => { state = update(state) })
  page.accept(state)
  page.recover(listing(['cover']))
  expect(state[0].images).toEqual(['cover'])
})

test('recovery updates only its original gallery while preserving favorite-related metadata', () => {
  const initial = listing()
  let state: Listing[] | null = [initial]
  const page = createProgressiveGalleryPage(() => true, update => { state = update(state) })
  page.accept(state)
  state = [{ ...initial, title: 'Current title' }]
  page.recover(listing(['cover', 'two']))
  expect(state[0].images).toEqual(['cover', 'two'])
  expect(state[0].title).toBe('Current title')
})

test('separate page recoveries finish in any order without touching another snapshot', () => {
  let state: Listing[] | null = [listing(), listing(['cover-b'], 'b')]
  const update = (fn: (state: Listing[] | null) => Listing[] | null) => { state = fn(state) }
  const first = createProgressiveGalleryPage(() => true, update)
  const second = createProgressiveGalleryPage(() => true, update)
  first.accept([state[0]])
  second.accept([state[1]])
  second.recover(listing(['cover-b', 'b-two'], 'b'))
  first.recover(listing(['cover', 'a-two']))
  expect(state.map(item => item.images)).toEqual([['cover', 'a-two'], ['cover-b', 'b-two']])
})
