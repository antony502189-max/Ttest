import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'

const root = process.cwd()
const read = (file: string) => fs.readFileSync(path.join(root, file), 'utf8')

test('homepage hero promotion has an independent timed admin contract', () => {
  const admin = read('src/pages/AdminPage.tsx')
  const api = read('src/api/admin.ts')
  expect(admin).toContain('Publicidad en la portada')
  expect(admin).toContain('Poner en portada')
  expect(admin).toContain('promotionEndExclusiveIso(endDate)')
  expect(api).toContain("'/admin/homepage-hero'")
  expect(api).toContain('setAdminHomepageHero')
})

test('homepage falls back unless an active promoted listing is returned', () => {
  const desktop = read('src/pages/HomePage.tsx')
  const mobile = read('src/components/mobile-app-v2.tsx')
  const hook = read('src/hooks/use-homepage-hero-listing.ts')
  expect(desktop).toContain('promotedImage ?? homeHeroImage')
  expect(desktop).toContain('/habitacion/${heroListing.id}')
  expect(mobile).toContain('m2-hero__promotion-image')
  expect(mobile).toContain('m2-hero-ad__reveal')
  expect(hook).toContain('getHomepageHeroListing')
})

test('backend public hero endpoint is time bounded and uses visible listings', () => {
  const service = read('backend/app/services/homepage_hero.py')
  const routes = read('backend/app/api/v1/listings.py')
  expect(service).toContain('HomepageHeroPromotion.ends_at > now')
  expect(service).toContain('visible_query().where(Listing.id == promotion.listing_id)')
  expect(service).toContain('Homepage promotion requires at least one listing image')
  expect(routes).toContain('@router.get("/homepage-hero", response_model=ListingResponse | None)')
})