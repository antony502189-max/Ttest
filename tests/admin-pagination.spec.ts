import { expect, test } from '@playwright/test'

type AdminUserDto = {
  id: string
  email: string
  name: string
  role: 'tenant' | 'host' | 'admin'
  blocked: boolean
  phone: string
  whatsapp: string
  telegram: string
  about: string
  initials: string
  showPhone: boolean
  showWhatsApp: boolean
  avatarUrl: string | null
  createdAt: string
  deletedAt: string | null
  lastLoginAt: string | null
  listingCount: number
  activeRestriction: null
  isAdmin: boolean
}

const userDto = (index: number, deleted = false): AdminUserDto => ({
  id: `user-${index}`,
  email: `user-${index}@example.com`,
  name: `User ${index}`,
  role: index % 2 ? 'tenant' : 'host',
  blocked: false,
  phone: '',
  whatsapp: '',
  telegram: '',
  about: '',
  initials: `U${index % 10}`,
  showPhone: false,
  showWhatsApp: false,
  avatarUrl: null,
  createdAt: new Date(Date.UTC(2026, 7, 9, 12, 0, 0) - index * 1000).toISOString(),
  deletedAt: deleted ? '2026-08-09T13:00:00.000Z' : null,
  lastLoginAt: null,
  listingCount: 0,
  activeRestriction: null,
  isAdmin: false,
})

const reportDto = (index: number) => ({
  id: `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
  publicReference: `R-${String(index).padStart(10, '0')}`,
  listingId: '00000000-0000-4000-8000-000000000001',
  targetType: 'listing' as const,
  targetUserId: null,
  reporterId: null,
  reason: `Reason ${index}`,
  comment: '',
  status: 'open' as const,
  handledBy: null,
  handledAt: null,
  createdAt: new Date(Date.UTC(2026, 7, 9, 12, 0, 0) - index * 1000).toISOString(),
})

test('admin user client switches to stable seek pagination after the first full page', async ({ page }) => {
  const requests: Array<{ offset: number; afterId: string | null; afterCreatedAt: string | null }> = []
  await page.route('**/api/v1/admin/users?*', async (route) => {
    const url = new URL(route.request().url())
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const afterId = url.searchParams.get('afterId')
    const afterCreatedAt = url.searchParams.get('afterCreatedAt')
    requests.push({ offset, afterId, afterCreatedAt })
    expect(url.searchParams.get('limit')).toBe('200')

    const rows = afterId
      ? Array.from({ length: 5 }, (_, index) => userDto(200 + index))
      : Array.from({ length: 200 }, (_, index) => userDto(index))
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(rows) })
  })

  await page.goto('/')
  const users = await page.evaluate(async () => {
    const admin = await import('/src/api/admin.ts')
    return admin.getAdminUserRows()
  })

  expect(users).toHaveLength(205)
  expect(requests).toHaveLength(2)
  expect(requests[0]).toEqual({ offset: 0, afterId: null, afterCreatedAt: null })
  expect(requests[1]).toEqual({
    offset: 0,
    afterId: 'user-199',
    afterCreatedAt: userDto(199).createdAt,
  })
})

test('admin report client switches to stable seek pagination after the first full page', async ({ page }) => {
  const requests: Array<{ offset: number; afterId: string | null; afterCreatedAt: string | null }> = []
  await page.route('**/api/v1/reports?*', async (route) => {
    const url = new URL(route.request().url())
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const afterId = url.searchParams.get('afterId')
    const afterCreatedAt = url.searchParams.get('afterCreatedAt')
    requests.push({ offset, afterId, afterCreatedAt })
    expect(url.searchParams.get('limit')).toBe('200')

    const rows = afterId
      ? Array.from({ length: 7 }, (_, index) => reportDto(200 + index))
      : Array.from({ length: 200 }, (_, index) => reportDto(index))
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(rows) })
  })

  await page.goto('/')
  const reports = await page.evaluate(async () => {
    const api = await import('/src/api/reports.ts')
    return api.getAdminReports()
  })

  expect(reports).toHaveLength(207)
  expect(requests).toHaveLength(2)
  expect(requests[0]).toEqual({ offset: 0, afterId: null, afterCreatedAt: null })
  expect(requests[1]).toEqual({
    offset: 0,
    afterId: reportDto(199).id,
    afterCreatedAt: reportDto(199).createdAt,
  })
})

test('admin row collection retains deleted users while legacy adapter excludes them', async ({ page }) => {
  await page.route('**/api/v1/admin/users?*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([userDto(1), userDto(2, true)]),
    })
  })

  await page.goto('/')
  const result = await page.evaluate(async () => {
    const admin = await import('/src/api/admin.ts')
    const rows = await admin.getAdminUserRows()
    const legacy = await admin.getAdminUsers()
    return {
      rowIds: rows.map((row) => row.id),
      legacyIds: legacy.map((row) => row.id),
    }
  })

  expect(result.rowIds).toEqual(['user-1', 'user-2'])
  expect(result.legacyIds).toEqual(['user-1'])
})
