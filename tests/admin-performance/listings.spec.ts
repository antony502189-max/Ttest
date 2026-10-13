import { expect, test } from '@playwright/test'
import { mockAdmin } from './fixtures'

test.skip(process.env.ADMIN_BENCHMARK_PHASE === 'before', 'Baseline implementation predates incremental loading')

async function openListings(page: import('@playwright/test').Page) {
  await page.goto('/#/admin')
  await expect(page.locator('.admin-user-row')).toHaveCount(1)
  await page.getByRole('button', { name: 'Anuncios', exact: true }).click()
}

test('first results use one bounded page and scrolling reaches the complete ordered dataset', async ({ page }) => {
  const fixture = await mockAdmin(page, 205, 10)
  await openListings(page)
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  expect(fixture.requests).toHaveLength(1)
  for (const expected of [100, 150, 200, 205]) {
    await page.locator('.admin-listing-row').last().scrollIntoViewIfNeeded()
    await expect(page.locator('.admin-listing-row')).toHaveCount(expected)
  }
  expect(fixture.requests).toHaveLength(5)
  expect(fixture.requests.map((url) => url.searchParams.get('afterId'))).toEqual([null, ...[49, 99, 149, 199].map((i) => fixture.rows[i].id)])
  const titles = await page.locator('.admin-listing-row strong').allTextContents()
  expect(titles).toEqual(fixture.rows.map((row) => row.title))
  expect(new Set(titles).size).toBe(205)
  expect(fixture.errors).toEqual([])
})

test('search and rental filters find records beyond the first page without downloading the dataset', async ({ page }) => {
  const fixture = await mockAdmin(page, 1000, 10)
  await openListings(page)
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  const input = page.getByPlaceholder('Título, usuario, zona o Ref.…')
  await input.fill('Habitación 00999')
  await expect(page.locator('.admin-listing-row')).toHaveCount(1)
  await expect(page.locator('.admin-listing-row strong')).toHaveText('Habitación 00999')
  await expect(input).toBeFocused()
  await page.getByLabel('Tipo de alquiler').selectOption('long')
  await expect(page.getByText('No hay anuncios que coincidan con la búsqueda.')).toBeVisible()
  await page.getByLabel('Tipo de alquiler').selectOption('holiday')
  await expect(page.locator('.admin-listing-row strong')).toHaveText('Habitación 00999')
  expect(fixture.requests).toHaveLength(4)
})

test('superseded searches and navigation do not apply stale pages or duplicate requests', async ({ page }) => {
  const fixture = await mockAdmin(page, 1000, 350)
  await openListings(page)
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  const input = page.getByPlaceholder('Título, usuario, zona o Ref.…')
  await input.fill('Habitación 00999')
  await expect.poll(() => fixture.requests.length).toBe(2)
  await input.fill('Habitación 00500')
  await expect(page.locator('.admin-listing-row strong')).toHaveText('Habitación 00500')
  await page.getByRole('button', { name: 'Ajustes', exact: true }).click()
  await expect(page.locator('.admin-main h1')).toHaveText('Ajustes')
  expect(fixture.requests).toHaveLength(3)
  expect(fixture.errors).toEqual([])
})

test('failed initial and continuation pages retry the same cursor without losing records', async ({ page }) => {
  const fixture = await mockAdmin(page, 75, 20)
  fixture.fail()
  await openListings(page)
  await expect(page.locator('.admin-load-error')).toBeVisible()
  await page.getByRole('button', { name: 'Reintentar' }).click()
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  fixture.fail()
  await page.locator('.admin-listing-row').last().scrollIntoViewIfNeeded()
  await expect(page.locator('.admin-load-error')).toBeVisible()
  // A failed continuation must not hide listings already fetched, the search
  // input, or existing moderation actions while the retry is available.
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  await expect(page.getByPlaceholder('Título, usuario, zona o Ref.…')).toBeVisible()
  await expect(page.locator('.admin-listing-row').first().getByRole('button', { name: 'Ocultar' })).toBeVisible()
  await page.getByRole('button', { name: 'Reintentar' }).click()
  await expect(page.locator('.admin-listing-row')).toHaveCount(75)
  expect(fixture.requests[2].searchParams.get('afterId')).toBe(fixture.requests[3].searchParams.get('afterId'))
})

test('moderation survives a filtered page reload and user context retains every associated listing', async ({ page }) => {
  const fixture = await mockAdmin(page, 205, 0)
  await openListings(page)
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  page.on('dialog', (dialog) => { void dialog.accept() })
  const row = page.locator('.admin-listing-row').nth(1)
  await row.getByRole('button', { name: 'Aprobar', exact: true }).click()
  await expect(row.getByRole('button', { name: 'Ocultar', exact: true })).toBeVisible()
  await page.getByPlaceholder('Título, usuario, zona o Ref.…').fill('Habitación 00001')
  await expect(page.locator('.admin-listing-row')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Ocultar', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Usuario', exact: true }).click()
  await expect(page.locator('.admin-user-detail .admin-compact-list').first().locator(':scope > div')).toHaveCount(205)
  await page.getByRole('button', { name: 'Volver a usuarios' }).click()
  await expect(page.getByRole('button', { name: 'Ocultar', exact: true })).toBeVisible()
  // A later request must accept fresh server state (including another admin's
  // changes) rather than preserving a permanent local mutation overlay.
  fixture.rows[1].status = 'pending'
  await page.getByPlaceholder('Título, usuario, zona o Ref.…').fill('Habitación 0000')
  await expect(page.locator('.admin-listing-row').nth(1).getByRole('button', { name: 'Aprobar', exact: true })).toBeVisible()
})

test('an in-flight continuation cannot resurrect a listing deleted during the request', async ({ page }) => {
  const fixture = await mockAdmin(page, 100, 0)
  let continuing = false
  let release = () => {}
  const gate = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/v1/admin/listings?*', async (route) => {
    const url = new URL(route.request().url())
    if (!url.searchParams.has('afterId')) return route.fallback()
    continuing = true
    const stalePage = JSON.stringify(fixture.rows.slice(49, 99))
    await gate
    await route.fulfill({ contentType: 'application/json', body: stalePage })
  })
  await page.route(`**/api/v1/listings/${fixture.rows[49].id}`, (route) => route.fulfill({ status: 204 }))
  await openListings(page)
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  const target = page.locator('.admin-listing-row').nth(49)
  await target.scrollIntoViewIfNeeded()
  await expect.poll(() => continuing).toBe(true)
  await target.getByRole('button', { name: 'Eliminar', exact: true }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Eliminar', exact: true }).click()
  await expect(page.locator('.admin-listing-row strong').filter({ hasText: 'Habitación 00049' })).toHaveCount(0)
  release()
  await expect(page.locator('.admin-listing-row')).toHaveCount(98)
  await expect(page.locator('.admin-listing-row strong').filter({ hasText: 'Habitación 00049' })).toHaveCount(0)
})

test('a non-advancing server cursor shows the existing retry error instead of looping', async ({ page }) => {
  const fixture = await mockAdmin(page, 50, 0)
  await page.route('**/api/v1/admin/listings?*', (route) => route.fulfill({ json: fixture.rows }))
  await openListings(page)
  await expect(page.locator('.admin-listing-row')).toHaveCount(50)
  await page.locator('.admin-listing-row').last().scrollIntoViewIfNeeded()
  await expect(page.locator('.admin-load-error')).toContainText('La paginación de anuncios no avanzó.')
})

test('an external abort signal preserves the API timeout budget', async ({ page }) => {
  await mockAdmin(page, 0)
  await page.route('**/api/v1/timeout-probe', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500))
    await route.fulfill({ json: [] })
  })
  await page.goto('/#/admin')
  const code = await page.evaluate(async () => {
    const { api, ApiError } = await import('/src/api/client.ts')
    try { await api('/timeout-probe', { timeoutMs: 30, signal: new AbortController().signal }) }
    catch (error) { return error instanceof ApiError ? error.code : 'unexpected' }
  })
  expect(code).toBe('REQUEST_TIMEOUT')
})
