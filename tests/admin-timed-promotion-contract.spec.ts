import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const adminPage = readFileSync('src/pages/AdminPage.tsx', 'utf8')
const adminApi = readFileSync('src/api/admin.ts', 'utf8')
const backendAdmin = readFileSync('backend/app/services/admin.py', 'utf8')
const listingRepository = readFileSync('backend/app/repositories/listings.py', 'utf8')
const migration = readFileSync('backend/alembic/versions/0042_timed_listing_promotions.py', 'utf8')

test('admin TOP scheduler exposes quick durations, calendar range and live day/price summary', () => {
  for (const days of [1, 7, 14, 21, 30]) {
    expect(adminPage).toContain(`${days}`)
  }
  expect(adminPage).toContain('PROMOTION_PRESETS = [1, 7, 14, 21, 30]')
  expect(adminPage).toContain('type="date" aria-label="TOP desde"')
  expect(adminPage).toContain('type="date" aria-label="TOP hasta"')
  expect(adminPage).toContain('promotionDayCount(startDate, endDate)')
  expect(adminPage).toContain("formatEuros(PROMOTION_DAILY_PRICE_CENTS)")
  expect(adminPage).toContain('Al terminar la fecha «Hasta», el anuncio dejará de estar en TOP automáticamente')
})

test('admin sends a dated promotion window and backend stores a fixed daily price snapshot', () => {
  expect(adminApi).toContain("payload: { startsAt: string; endsAt: string }")
  expect(adminApi).toContain("body: JSON.stringify(payload)")
  expect(backendAdmin).toContain('PROMOTION_DAILY_PRICE_CENTS = 100')
  expect(backendAdmin).toContain('daily_price_cents=PROMOTION_DAILY_PRICE_CENTS')
  expect(backendAdmin).toContain('total_price_cents=total_price_cents')
  expect(backendAdmin).toContain('"days": promotion_days')
})

test('scheduled and expired promotions cannot retain public TOP priority', () => {
  expect(listingRepository).toContain('ListingPromotion.starts_at <= func.now()')
  expect(listingRepository).toContain('ListingPromotion.ends_at > func.now()')
  expect(migration).toContain('sa.Column("starts_at"')
  expect(migration).toContain('sa.Column("ends_at"')
  expect(migration).toContain('sa.Column("daily_price_cents"')
  expect(migration).toContain('sa.Column("total_price_cents"')
})
