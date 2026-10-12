import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const assetId = '00000000-0000-4000-8000-000000000732'
const picture = Buffer.alloc(300 * 1024, 97)

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
})

test('ad image upload has its own Nginx multipart limit without widening generic API requests', () => {
  const source = readFileSync('deploy/nginx.conf', 'utf-8')
  const route = source.match(/location = \/api\/v1\/advertisements\/uploads\s*\{([\s\S]*?)\n  \}/)?.[1]
  expect(route).toBeTruthy()
  expect(route).toContain('client_max_body_size 9m;')
  expect(route).toContain('limit_req zone=api_writes_per_ip')
  expect(route).toContain('proxy_pass http://backend:8000')
  expect(source).toContain('client_max_body_size 256k;')
})

test('300 KiB image upload succeeds via the commercial image endpoint', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  let uploadCalls = 0
  await page.route('**/api/v1/advertisements/uploads', async (route) => {
    uploadCalls += 1
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataBuffer()?.length).toBeGreaterThan(256 * 1024)
    await route.fulfill({ status: 201, json: { id: assetId, url: `/api/v1/media/${assetId}` } })
  })
  await page.goto('/#/publicidad/nueva')
  await page.locator('input[type="file"]').setInputFiles({
    name: 'imagen.jpg', mimeType: 'image/jpeg', buffer: picture,
  })
  await expect(page.getByRole('button', { name: 'Vista previa' })).toBeEnabled()
  await expect(page.locator('.ad-flow__error')).toHaveCount(0)
  expect(uploadCalls).toBe(1)
})

test('upload error 413 from Nginx HTML is explained, not a generic API error', async ({ page }) => {
  await page.route('**/api/v1/advertisements/uploads', (route) => route.fulfill({
    status: 413, contentType: 'text/html', body: '<h1>Request Entity Too Large</h1>',
  }))
  await page.goto('/#/publicidad/nueva')
  await page.locator('input[type="file"]').setInputFiles({
    name: 'foto.jpg', mimeType: 'image/jpeg', buffer: picture,
  })
  await expect(page.getByRole('alert')).toContainText('8 MB')
  await expect(page.getByRole('alert')).not.toContainText('No se pudo completar la solicitud')
})

test('file above backend 8 MiB limit is rejected locally before upload', async ({ page }) => {
  let uploadCalls = 0
  await page.route('**/api/v1/advertisements/uploads', (route) => {
    uploadCalls += 1
    return route.fulfill({ status: 201, json: { id: assetId, url: '' } })
  })
  await page.goto('/#/publicidad/nueva')
  await page.locator('input[type="file"]').setInputFiles({
    name: 'huge.jpg', mimeType: 'image/jpeg', buffer: Buffer.alloc(8 * 1024 * 1024 + 1),
  })
  await expect(page.getByRole('alert')).toContainText('8 MB')
  expect(uploadCalls).toBe(0)
})

test('My campaigns does not flash the empty-state while the owner request is loading', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  let send: (() => void) | undefined
  const pending = new Promise<void>((resolve) => { send = resolve })
  await page.route('**/api/v1/advertisements/mine', async (route) => {
    await pending
    await route.fulfill({ json: [] })
  })
  await page.goto('/#/mis-campanas')
  await expect(page.locator('.ad-flow [role="status"]')).toBeVisible()
  await expect(page.getByText('Todavía no tienes campañas publicitarias.')).toHaveCount(0)
  send?.()
  await expect(page.getByText('Todavía no tienes campañas publicitarias.')).toBeVisible()
  await expect(page.locator('.ad-flow [role="status"]')).toHaveCount(0)
})

test('campaign list exposes retry after a failed load', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/v1/advertisements/mine', async (route) => {
    attempts += 1
    await route.fulfill(attempts === 1 ? {
      status: 503, json: { detail: 'Service unavailable' },
    } : { json: [] })
  })
  await page.goto('/#/mis-campanas')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByText('Todavía no tienes campañas publicitarias.')).toHaveCount(0)
  await page.getByRole('button', { name: 'Reintentar' }).click()
  await expect(page.getByText('Todavía no tienes campañas publicitarias.')).toBeVisible()
  expect(attempts).toBe(2)
})
