import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const adminPage = readFileSync('src/pages/AdminPage.tsx', 'utf8')
const adminListings = readFileSync('backend/app/services/admin_listings.py', 'utf8')

test('customer-video admin listing search matches the visible search promise', () => {
  expect(adminPage).toContain('placeholder="Título, usuario, zona o Ref.…"')
  expect(adminPage).toContain('Ref. {listing.id.slice(0, 8).toUpperCase()}')
  expect(adminListings).toContain('Listing.title.ilike(term)')
  expect(adminListings).toContain('User.name.ilike(term)')
  expect(adminListings).toContain('User.email.ilike(term)')
  expect(adminListings).toContain('Listing.area.ilike(term)')
  expect(adminListings).toContain('Listing.city.ilike(term)')
  expect(adminListings).toContain('cast(Listing.id, String).ilike(term)')
})

test('customer-video unpublished rows do not render misleading disabled promotion controls', () => {
  expect(adminPage).toContain("listing.status === 'published' ? <Button")
  expect(adminPage).toContain('Publica el anuncio para gestionar portada y TOP.')
  expect(adminPage).not.toContain('disabled={listing.status !== \'published\'} onClick={() => setListingPromotion(listing)}')
})
