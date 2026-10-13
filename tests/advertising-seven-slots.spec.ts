import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const adId = '00000000-0000-4000-8000-000000000731'
const assetId = '00000000-0000-4000-8000-000000000732'
const png = readFileSync('src/assets/mobile-hero.jpg')
const availability = (available = 7) => ({ total: 7, available, dailyPriceCents: 100, currency: 'EUR', pushEnabled: false, pushPublicKey: null })
const ads = Array.from({ length: 8 }, (_, index) => ({ id: `${adId}-${index}`, title: `Service ${index + 1}`, description: 'A local service for our community.', imageUrl: `/api/v1/media/${assetId}?variant=card`, imageWidth: 800, imageHeight: 450, destinationType: 'website', destinationUrl: 'https://example.org/', placement: 'homepage_bottom' }))

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability() }))
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: [] }))
  await page.route(`**/api/v1/media/${assetId}**`, (route) => route.fulfill({ body: png, contentType: 'image/jpeg' }))
  await page.route(`**/api/v1/payments/advertisements/${adId}/quote`, (route) => route.fulfill({ json: { days: 1, amountCents: 100, currency: 'EUR', available: true } }))
})

test('seven cards preserve sponsored links and cap even an oversized response', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: ads }))
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability(0) }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
  await expect(block.getByRole('heading', { name: 'Service 8' })).toHaveCount(0)
  await expect(block.getByRole('heading', { name: 'Service 7' })).toBeVisible()
  await expect(block.getByRole('link', { name: 'Más información' }).first()).toHaveAttribute('rel', 'noopener noreferrer sponsored')
  await expect(block.getByText('1 € · 1 día')).toBeVisible()
  await block.locator('img').evaluateAll((images) => images.forEach((img) => { (img as HTMLImageElement).loading = 'eager' }))
  await expect.poll(() => block.locator('img').evaluateAll((images) => images.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true)
  await block.screenshot({ path: 'output/advertising/seven-desktop.png', style: '.site-header, .skip-link { visibility: hidden !important; }' })
})

test('mobile seven slots scroll above the fixed navigation without overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: ads.slice(0, 7) }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad--mobile')
  await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
  await block.getByRole('link', { name: 'Publicar publicidad' }).scrollIntoViewIfNeeded()
  await expect(block.getByRole('link', { name: 'Publicar publicidad' })).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await block.locator('img').evaluateAll((images) => images.forEach((img) => { (img as HTMLImageElement).loading = 'eager' }))
  await expect.poll(() => block.locator('img').evaluateAll((images) => images.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true)
  await block.screenshot({ path: 'output/advertising/seven-mobile.png', style: '.m2-bottom-nav, .skip-link { visibility: hidden !important; }' })
})

test('full inventory prevents upload and offers a cancellable persisted alert', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability(0) }))
  let subscriptions = 0
  let cancelled = false
  await page.route('**/api/v1/advertisements/waitlist', (route) => {
    if (route.request().method() === 'DELETE') { cancelled = true; return route.fulfill({ status: 204 }) }
    expect(route.request().postDataJSON()).toEqual({ language: 'es', subscription: null })
    subscriptions++
    return route.fulfill({ json: { subscribed: true, available: false } })
  })
  await page.goto('/#/publicidad/nueva')
  await expect(page.getByText('No hay espacios publicitarios disponibles en este momento.')).toBeVisible()
  await expect(page.locator('input[type=file]')).toHaveCount(0)
  await page.getByRole('button', { name: 'Avisarme cuando haya un espacio' }).click()
  await expect(page.getByText('Te avisaremos en las notificaciones del sitio cuando se libere un espacio.')).toBeVisible()
  expect(subscriptions).toBe(1)
  await page.getByRole('button', { name: 'Cancelar aviso' }).click()
  await expect(page.getByRole('button', { name: 'Avisarme cuando haya un espacio' })).toBeVisible()
  expect(cancelled).toBe(true)
})

test('vacancy detected while subscribing sends the user back to purchase', async ({ page }) => {
  let freed = false
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability(freed ? 1 : 0) }))
  await page.goto('/#/publicidad/nueva')
  await expect(page.getByRole('button', { name: 'Avisarme cuando haya un espacio' })).toBeVisible()
  freed = true
  await page.getByRole('button', { name: 'Avisarme cuando haya un espacio' }).click()
  await expect(page.getByText('Ya hay un espacio disponible.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Crear publicidad' })).toHaveAttribute('href', '#/publicidad/nueva')
  await page.getByRole('link', { name: 'Crear publicidad' }).click()
  await expect(page.locator('input[type=file]')).toBeVisible()
})

test('checkout starts only after an explicit payment click and handles the last slot race', async ({ page }) => {
  const item = { ...ads[0], id: adId, imageAssetId: assetId, destination: 'https://example.org/', packageId: 'homepage_1d', status: 'pending_payment', paymentStatus: 'unpaid', startsAt: null, endsAt: null, moderationNote: null, createdAt: new Date().toISOString(), ownerUserId: 'host-demo' }
  await page.route(`**/api/v1/advertisements/${adId}`, (route) => route.fulfill({ json: item }))
  let checkouts = 0
  await page.route(`**/api/v1/payments/advertisements/${adId}/checkout`, (route) => {
    checkouts++
    return route.fulfill({ status: 409, json: { detail: 'No advertising slots available' } })
  })
  await page.goto(`/#/publicidad/${adId}/checkout`)
  await expect(page.getByText('Publicidad · 1 día · 1 €')).toBeVisible()
  expect(checkouts).toBe(0)
  await page.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(page.getByText('No hay espacios publicitarios disponibles en este momento.')).toBeVisible()
  expect(checkouts).toBe(1)
  await expect(page.getByRole('button', { name: 'Avisarme cuando haya un espacio' })).toBeVisible()
})
