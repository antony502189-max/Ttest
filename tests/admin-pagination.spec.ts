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
  allowContactForm: boolean
  avatarUrl: string | null
  createdAt: string
}

const userDto = (index: number): AdminUserDto => ({
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
  allowContactForm: true,
  avatarUrl: null,
  createdAt: new Date(Date.UTC(2026, 7, 9, 12, 0, 0) - index * 1000).toISOString(),
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

test('admin user client drains every server page before rendering', async ({ page }) => {
  const requestedOffsets: number[] = []
  await page.route('**/api/v1/admin/users?*', async (route) => {
    const url = new URL(route.request().url())
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const limit = Number(url.searchParams.get('limit') ?? '0')
    requestedOffsets.push(offset)
    expect(limit).toBe(200)
    const count = offset === 0 ? 200 : offset === 200 ? 5 : 0
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(Array.from({ length: count }, (_, index) => userDto(offset + index))),
    })
  })

  await page.goto('/')
  const users = await page.evaluate(async () => {
    const admin = await import('/src/api/admin.ts')
    return admin.getAdminUsers()
  })

  expect(requestedOffsets).toEqual([0, 200])
  expect(users).toHaveLength(205)
  expect(users.at(-1)?.email).toBe('user-204@example.com')
})

test('admin report client drains every server page', async ({ page }) => {
  const requestedOffsets: number[] = []
  await page.route('**/api/v1/reports?*', async (route) => {
    const url = new URL(route.request().url())
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const limit = Number(url.searchParams.get('limit') ?? '0')
    requestedOffsets.push(offset)
    expect(limit).toBe(200)
    const count = offset === 0 ? 200 : offset === 200 ? 7 : 0
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(Array.from({ length: count }, (_, index) => reportDto(offset + index))),
    })
  })

  await page.goto('/')
  const reports = await page.evaluate(async () => {
    const api = await import('/src/api/reports.ts')
    return api.getAdminReports()
  })

  expect(requestedOffsets).toEqual([0, 200])
  expect(reports).toHaveLength(207)
  expect(reports.at(-1)?.publicReference).toBe('R-0000000206')
})

test('admin user pagination switches to cursor instead of exceeding offset 10000', async ({ page }) => {
  const requestedOffsets: number[] = []
  let cursorRequests = 0
  await page.route('**/api/v1/admin/users?*', async (route) => {
    const url = new URL(route.request().url())
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const afterId = url.searchParams.get('afterId')
    const afterCreatedAt = url.searchParams.get('afterCreatedAt')
    requestedOffsets.push(offset)

    if (afterId || afterCreatedAt) {
      cursorRequests += 1
      expect(afterId).toBeTruthy()
      expect(afterCreatedAt).toBeTruthy()
      expect(offset).toBe(0)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([userDto(10_200), userDto(10_201), userDto(10_202)]),
      })
      return
    }

    expect(offset).toBeLessThanOrEqual(10_000)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(Array.from({ length: 200 }, (_, index) => userDto(offset + index))),
    })
  })

  await page.goto('/')
  const users = await page.evaluate(async () => {
    const admin = await import('/src/api/admin.ts')
    return admin.getAdminUserRows()
  })

  expect(Math.max(...requestedOffsets)).toBe(10_000)
  expect(cursorRequests).toBe(1)
  expect(users).toHaveLength(10_203)
})

test('admin report pagination switches to cursor instead of exceeding offset 10000', async ({ page }) => {
  const requestedOffsets: number[] = []
  let cursorRequests = 0
  await page.route('**/api/v1/reports?*', async (route) => {
    const url = new URL(route.request().url())
    const offset = Number(url.searchParams.get('offset') ?? '0')
    const afterId = url.searchParams.get('afterId')
    const afterCreatedAt = url.searchParams.get('afterCreatedAt')
    requestedOffsets.push(offset)

    if (afterId || afterCreatedAt) {
      cursorRequests += 1
      expect(afterId).toBeTruthy()
      expect(afterCreatedAt).toBeTruthy()
      expect(offset).toBe(0)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([reportDto(10_200), reportDto(10_201)]),
      })
      return
    }

    expect(offset).toBeLessThanOrEqual(10_000)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(Array.from({ length: 200 }, (_, index) => reportDto(offset + index))),
    })
  })

  await page.goto('/')
  const reports = await page.evaluate(async () => {
    const api = await import('/src/api/reports.ts')
    return api.getAdminReports()
  })

  expect(Math.max(...requestedOffsets)).toBe(10_000)
  expect(cursorRequests).toBe(1)
  expect(reports).toHaveLength(10_202)
})
