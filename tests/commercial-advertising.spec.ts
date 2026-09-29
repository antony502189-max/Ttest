import { expect, test } from '@playwright/test'

const adId = '00000000-0000-4000-8000-000000000731'
const assetId = '00000000-0000-4000-8000-000000000732'
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64')

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('house advertisement is visible and signed-out CTA keeps the intended route', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: [] }))
  await page.goto('/#/')
  await expect(page.getByText('Tu anuncio podría estar aquí')).toBeVisible()
  await page.getByRole('link', { name: 'Publicar publicidad' }).click()
  await expect(page).toHaveURL(/#\/acceso$/)
})

test('mobile house advertisement scrolls above fixed navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: [] }))
  await page.goto('/#/')
  const ad = page.locator('.commercial-ad--mobile')
  await ad.scrollIntoViewIfNeeded()
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await page.waitForFunction(() => document.querySelector('.commercial-ad--mobile')!.getBoundingClientRect().bottom <= document.querySelector('.m2-bottom-nav')!.getBoundingClientRect().top)
  await test.info().attach('advertising-mobile', { body: await page.screenshot(), contentType: 'image/png' })
  await expect(ad).toBeVisible()
  const bounds = await page.evaluate(() => {
    const ad = document.querySelector('.commercial-ad--mobile')!.getBoundingClientRect()
    const nav = document.querySelector('.m2-bottom-nav')!.getBoundingClientRect()
    return { adBottom: ad.bottom, navTop: nav.top, overflow: document.documentElement.scrollWidth > window.innerWidth }
  })
  expect(bounds.overflow).toBe(false)
  expect(bounds.adBottom).toBeLessThanOrEqual(bounds.navTop)
})

test('approved advertisement has a visible disclosure and safe sponsored link', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: [{
    id: adId, title: 'Local moving service', description: 'Moving help across Spain.',
    imageUrl: `/api/v1/media/${assetId}?variant=card`, imageWidth: 800, imageHeight: 450,
    destinationType: 'website', destinationUrl: 'https://example.org/moving', placement: 'homepage_bottom',
  }] }))
  await page.route(`**/api/v1/media/${assetId}**`, (route) => route.fulfill({ body: png, contentType: 'image/png' }))
  await page.goto('/#/')
  const ad = page.locator('.commercial-ad')
  await expect(ad.getByText('Publicidad', { exact: true })).toBeVisible()
  await expect(ad.getByRole('heading', { name: 'Local moving service' })).toBeVisible()
  const link = ad.getByRole('link', { name: 'Más información' })
  await expect(link).toHaveAttribute('href', 'https://example.org/moving')
  await expect(link).toHaveAttribute('target', '_blank')
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer sponsored')
  await test.info().attach('advertising-desktop', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
})

test('homepage carousel exposes at most twelve campaigns and rotates without redesigning the card', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const ads = Array.from({ length: 13 }, (_, index) => ({
    id: `00000000-0000-4000-8000-${String(800 + index).padStart(12, '0')}`,
    title: `Campaign ${index + 1}`,
    description: `Commercial campaign number ${index + 1} for carousel verification.`,
    imageUrl: `/api/v1/media/${assetId}?variant=card`,
    imageWidth: 800,
    imageHeight: 450,
    destinationType: 'website',
    destinationUrl: `https://example.org/campaign-${index + 1}`,
    placement: 'homepage_bottom',
  }))
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: ads }))
  await page.route(`**/api/v1/media/${assetId}**`, (route) => route.fulfill({ body: png, contentType: 'image/png' }))
  await page.goto('/#/')

  const placement = page.locator('.commercial-ad')
  const slide = placement.getByTestId('commercial-ad-slide')
  await expect(slide).toHaveAttribute('data-ad-id', ads[0].id)
  await expect(placement.getByText('1 / 12')).toBeVisible()
  await expect(placement.locator('.commercial-ad__carousel-dots button')).toHaveCount(12)
  await expect(placement.getByRole('heading', { name: 'Campaign 13' })).toHaveCount(0)
  await placement.scrollIntoViewIfNeeded()
  expect(await placement.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  await test.info().attach('advertising-carousel-mobile-12', { body: await page.screenshot(), contentType: 'image/png' })

  await placement.getByRole('button', { name: 'Publicidad siguiente' }).click()
  await expect(slide).toHaveAttribute('data-ad-id', ads[1].id)
  await expect(placement.getByText('2 / 12')).toBeVisible()
  await expect(placement.getByRole('heading', { name: 'Campaign 2' })).toBeVisible()

  await placement.getByRole('button', { name: 'Publicidad anterior' }).click()
  await expect(slide).toHaveAttribute('data-ad-id', ads[0].id)
  await expect(placement.getByText('1 / 12')).toBeVisible()
})

test('authenticated mobile advertising entry stays inside the existing menu row design', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.goto('/#/menu')
  const menu = page.locator('.m2-menu')
  await expect(menu).toBeVisible()
  const advertising = menu.getByRole('button', { name: /Mis campañas publicitarias/ })
  await expect(advertising).toBeVisible()
  await expect(advertising).toHaveClass(/m2-menu-row/)
  await expect(advertising.locator('svg')).toHaveCount(2)
  expect(await advertising.evaluate((element) => element.parentElement?.classList.contains('m2-menu') ?? false)).toBe(true)
  await advertising.click()
  await expect(page).toHaveURL(/#\/mis-campanas$/)
})

test('advertising API failure leaves homepage usable', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', (route) => route.abort())
  await page.goto('/#/')
  await expect(page.getByText('Tu anuncio podría estar aquí')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Solo habitaciones' })).toBeVisible()
})

test('advertiser previews, completes test checkout and sees persisted review state', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  let ad: Record<string, unknown> | null = null
  await page.route('**/api/v1/advertisements**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/homepage')) return route.fulfill({ json: [] })
    if (path.endsWith('/uploads') && request.method() === 'POST') return route.fulfill({ status: 201, json: { id: assetId, url: `/api/v1/media/${assetId}` } })
    if (path.endsWith('/checkout') && request.method() === 'POST') return route.fulfill({ json: { advertisementId: adId, packageId: 'test_homepage_30d', displayPrice: 'Pago de prueba — sin cargo', paymentMode: 'test' } })
    if (path.endsWith('/fake-payment/complete') && request.method() === 'POST') {
      ad = { ...ad, status: 'pending_review', paymentStatus: 'paid' }
      return route.fulfill({ json: ad })
    }
    if (path.endsWith('/mine')) return route.fulfill({ json: ad ? [ad] : [] })
    if (path.endsWith(adId) && request.method() === 'GET') return route.fulfill({ json: ad })
    if (path.endsWith('/advertisements') && request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      ad = { ...body, id: adId, ownerUserId: 'host-demo', imageUrl: `/api/v1/media/${assetId}?variant=card`, status: 'pending_payment', paymentStatus: 'unpaid', placement: 'homepage_bottom', createdAt: new Date().toISOString(), startsAt: null, endsAt: null, moderationNote: null }
      return route.fulfill({ status: 201, json: ad })
    }
    return route.continue()
  })
  await page.route(`**/api/v1/media/${assetId}**`, (route) => route.fulfill({ body: png, contentType: 'image/png' }))
  await page.goto('/#/publicidad/nueva')
  await page.locator('input[type=file]').setInputFiles({ name: 'banner.png', mimeType: 'image/png', buffer: png })
  await page.getByLabel('Título').fill('Local moving service')
  await page.getByLabel('Descripción').fill('A reliable moving service for local residents.')
  await page.getByLabel('Enlace web').fill('https://example.org/moving')
  await page.getByRole('button', { name: 'Vista previa' }).click()
  await expect(page.getByRole('heading', { name: 'Local moving service' })).toBeVisible()
  await page.getByRole('button', { name: 'Continuar al pago de prueba' }).click()
  await expect(page).toHaveURL(new RegExp(`#/publicidad/${adId}/checkout`))
  await expect(page.getByText('Pago de prueba — sin cargo')).toBeVisible()
  await page.getByRole('button', { name: 'Simular pago' }).click()
  await expect(page).toHaveURL(/#\/mis-campanas$/)
  await expect(page.getByText('Pendiente de revisión')).toBeVisible()
  await page.reload()
  await expect(page.getByText('Pendiente de revisión')).toBeVisible()
})

test('admin approves a paid campaign and the homepage displays it', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo')))
  let approved = false
  const detail = {
    id: adId, ownerUserId: 'host-demo', ownerEmail: 'advertiser@example.com', adminPriority: 0,
    title: 'Local moving service', description: 'Moving help across Spain.', imageAssetId: assetId,
    imageUrl: `/api/v1/media/${assetId}?variant=card`, destinationType: 'website',
    destination: 'https://example.org/moving', packageId: 'test_homepage_30d',
    placement: 'homepage_bottom', status: 'pending_review', paymentStatus: 'paid',
    createdAt: new Date().toISOString(), startsAt: null, endsAt: null, moderationNote: null,
  }
  await page.route('**/api/v1/admin/advertisements**', (route) => {
    if (route.request().method() === 'POST') {
      approved = true
      return route.fulfill({ json: { ...detail, status: 'active' } })
    }
    return route.fulfill({ json: [{ ...detail, status: approved ? 'active' : 'pending_review' }] })
  })
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: approved ? [{
    id: adId, title: detail.title, description: detail.description,
    imageUrl: detail.imageUrl, imageWidth: 800, imageHeight: 450,
    destinationType: 'website', destinationUrl: detail.destination, placement: 'homepage_bottom',
  }] : [] }))
  await page.route(`**/api/v1/media/${assetId}**`, (route) => route.fulfill({ body: png, contentType: 'image/png' }))
  await page.goto('/#/admin/publicidad')
  await expect(page.getByRole('heading', { name: 'Moderación de publicidad' })).toBeVisible()
  await expect(page.getByRole('heading', { name: detail.title })).toBeVisible()
  await page.getByRole('button', { name: 'Aprobar' }).click()
  await expect(page.getByText('active · paid')).toBeVisible()
  await page.goto('/#/')
  await expect(page.locator('.commercial-ad').getByRole('heading', { name: detail.title })).toBeVisible()
})
