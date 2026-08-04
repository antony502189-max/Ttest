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
