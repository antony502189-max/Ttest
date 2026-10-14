import type { Page } from '@playwright/test'
import type { AdminListing, AdminUser } from '../../src/api/admin'

export const owner: AdminUser = {
  id: '00000000-0000-4000-8000-000000000001', email: 'owner@example.test', name: 'Ana García',
  role: 'host', blocked: false, phone: '', whatsapp: '', telegram: '', about: '', initials: 'AG',
  showPhone: false, showWhatsApp: false, avatarUrl: null, createdAt: '2026-09-01T12:00:00Z',
  deletedAt: null, lastLoginAt: null, listingCount: 9, activeRestriction: null, isAdmin: false,
}

export function listing(index: number): AdminListing {
  return {
    id: `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`, ownerUserId: owner.id,
    ownerName: owner.name, ownerEmail: owner.email, title: `Habitación ${String(index).padStart(5, '0')}`,
    city: 'Santa Cruz', area: 'Centro', status: ['published', 'pending', 'hidden'][index % 3],
    rentalMode: index % 2 ? 'holiday' : 'long', views: index, createdAt: new Date(Date.UTC(2026, 8, 30) - index * 1000).toISOString(),
    deletedAt: null, isExternal: index % 4 === 0, activeRestriction: null, promoted: false,
    boostedAt: index === 3 ? '2026-10-10T00:00:00Z' : null,
    promotionStartsAt: index === 3 ? '2026-10-10T00:00:00Z' : null,
    promotionEndsAt: index === 3 ? '2026-10-20T00:00:00Z' : null, promotionState: index === 3 ? 'active' : null,
    promotionDays: index === 3 ? 10 : null, promotionDailyPriceCents: index === 3 ? 100 : null,
    promotionTotalPriceCents: index === 3 ? 1000 : null,
  }
}

export async function mockAdmin(page: Page, count: number, delayMs = 100) {
  const rows = Array.from({ length: count }, (_, index) => listing(index))
  const requests: URL[] = []
  const errors: string[] = []
  const durations: number[] = []
  let payloadBytes = 0
  let failNext = false
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('requestfinished', (request) => {
    if (request.url().includes('/api/v1/admin/listings?')) durations.push(request.timing().responseEnd)
  })
  await page.addInitScript(() => {
    localStorage.setItem('112233:has-session', '1')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
    const metrics = { longTasks: [] as number[], reactCommits: [] as number[] }
    Object.assign(window, { adminMetrics: metrics })
    new PerformanceObserver((list) => metrics.longTasks.push(...list.getEntries().map((entry) => entry.duration))).observe({ type: 'longtask', buffered: true })
    Object.assign(window, { __REACT_DEVTOOLS_GLOBAL_HOOK__: {
      supportsFiber: true, renderers: new Map(), inject: () => 1, onCommitFiberUnmount: () => {},
      onCommitFiberRoot: (_id: number, root: { current: { actualDuration?: number } }) => {
        metrics.reactCommits.push(root.current.actualDuration ?? 0)
      },
    } })
  })
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace('/api/v1', '')
    let body: unknown = []
    if (path === '/auth/refresh') body = { accessToken: 'synthetic-test-session', user: { ...owner, role: 'admin', emailVerified: true } }
    else if (path === '/admin/access') body = { isAdmin: true, email: owner.email }
    else if (path === '/catalog/version') body = { version: 'synthetic' }
    else if (path === '/admin/homepage-hero') body = count ? { listingId: rows[0].id, startsAt: '2026-10-10T00:00:00Z', endsAt: '2026-10-20T00:00:00Z', state: 'active', days: 10 } : null
    else if (path === '/users/me/restriction') body = null
    else if (path === '/admin/users') body = [owner]
    else if (path === `/admin/users/${owner.id}`) body = { ...owner, restrictions: [] }
    else if (path === '/admin/listings') {
      requests.push(url)
      await new Promise((resolve) => setTimeout(resolve, delayMs))
      if (failNext) {
        failNext = false
        await route.fulfill({ status: 503, json: { detail: 'Synthetic temporary failure' } })
        return
      }
      let matching = rows
      const search = url.searchParams.get('displaySearch')
      const mode = url.searchParams.get('rentalMode')
      const ownerId = url.searchParams.get('ownerUserId')
      if (search?.trim()) matching = matching.filter((row) => `${row.title} ${row.ownerName ?? ''} ${row.area}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
      if (mode) matching = matching.filter((row) => row.rentalMode === mode)
      if (ownerId) matching = matching.filter((row) => row.ownerUserId === ownerId)
      const afterId = url.searchParams.get('afterId')
      const offset = afterId ? matching.findIndex((row) => row.id === afterId) + 1 : Number(url.searchParams.get('offset') || 0)
      body = matching.slice(offset, offset + Number(url.searchParams.get('limit') || 100))
      payloadBytes += Buffer.byteLength(JSON.stringify(body))
    } else if (/^\/admin\/listings\/.+\/status$/.test(path)) {
      const row = rows.find((item) => path.includes(item.id))!
      row.status = route.request().postDataJSON().status
      body = row
    } else if (path === '/notifications/unread-count') body = { count: 0 }
    else if (path === '/notifications') body = { items: [], unreadCount: 0 }
    else if (path === '/admin/admins') body = [{ email: owner.email, active: true, createdBy: null, createdAt: owner.createdAt }]
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  return { rows, requests, errors, durations, bytes: () => payloadBytes, fail: () => { failNext = true } }
}
