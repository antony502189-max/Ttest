import { expect, test } from '@playwright/test'

const adId = '00000000-0000-4000-8000-000000000731'
const assetId = '00000000-0000-4000-8000-000000000732'
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64')

test.beforeEach(async ({ page }) => {
  await page.route('https://images.unsplash.com/**', route => route.fulfill({ body: png, contentType: 'image/png' }))
  await page.route('**/api/v1/payments/admin/review-required', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/advertisements/waitlist', route => route.fulfill({ json: { subscribed: false, channel: 'site' } }))
  await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: { total: 7, available: 7, monthlyPriceCents: 3000, months: 1, currency: 'EUR', pushEnabled: false, pushPublicKey: null } }))
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

async function expectDecodedImage(locator: import('@playwright/test').Locator) {
  await expect(locator).toBeVisible()
  await expect.poll(() => locator.evaluate((node) => {
    const image = node as HTMLImageElement
    return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0
  })).toBe(true)
}

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
  await expectDecodedImage(ad.locator('.commercial-ad__visual img'))
  const link = ad.getByRole('link', { name: 'Más información' })
  await expect(link).toHaveAttribute('href', 'https://example.org/moving')
  await expect(link).toHaveAttribute('target', '_blank')
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer sponsored')
  await test.info().attach('advertising-desktop', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
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
  expect(await advertising.evaluate((element) => Boolean(element.closest('.m2-menu-group') && element.closest('.m2-menu')))).toBe(true)
  await advertising.click()
  await expect(page).toHaveURL(/#\/mis-campanas$/)
})

test('campaign page back arrow returns directly to home in Russian on narrow mobile', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:language:v1', 'ru')
  })
  await page.route('**/api/v1/advertisements/mine', (route) => route.fulfill({ json: [] }))
  await page.goto('/#/mis-campanas')
  await expect(page.getByRole('heading', { name: 'Мои кампании' })).toBeVisible()

  const back = page.getByRole('link', { name: 'Вернуться на главную' })
  await expect(back).toBeVisible()
  await expect(back).toHaveAttribute('href', '#/')
  const bounds = await back.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.width).toBeGreaterThanOrEqual(44)
  expect(bounds!.height).toBeGreaterThanOrEqual(44)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(320)

  await back.click()
  await expect(page).toHaveURL(/#\/$/)
  await expect(page.getByRole('heading', { name: 'Мои кампании' })).toHaveCount(0)
})

test('mobile campaign page bottom navigation spans the viewport and every tab routes', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.route('**/api/v1/advertisements/mine', (route) => route.fulfill({ json: [] }))

  await page.goto('/#/mis-campanas')
  const nav = page.locator('.bottom-nav')
  await expect(nav).toBeVisible()
  const items = nav.locator('.bottom-nav__item')
  await expect(items).toHaveCount(4)

  const geometry = await nav.evaluate((element) => {
    const bounds = element.getBoundingClientRect()
    const itemBounds = Array.from(element.querySelectorAll<HTMLElement>('.bottom-nav__item')).map((item) => item.getBoundingClientRect())
    return {
      left: bounds.left,
      right: bounds.right,
      width: bounds.width,
      viewportWidth: window.innerWidth,
      itemWidths: itemBounds.map((item) => item.width),
      lastRight: itemBounds.at(-1)?.right ?? 0,
    }
  })
  expect(Math.abs(geometry.left)).toBeLessThanOrEqual(1)
  expect(Math.abs(geometry.right - geometry.viewportWidth)).toBeLessThanOrEqual(1)
  expect(geometry.width).toBeGreaterThanOrEqual(geometry.viewportWidth - 1)
  expect(Math.abs(geometry.lastRight - geometry.viewportWidth)).toBeLessThanOrEqual(1)
  for (const width of geometry.itemWidths) expect(width).toBeGreaterThanOrEqual(geometry.viewportWidth / 4 - 1)

  const destinations = [/#\/$/, /#\/favoritos$/, /#\/buscar$/, /#\/perfil$/]
  for (let index = 0; index < destinations.length; index += 1) {
    if (index > 0) {
      await page.goto('/#/mis-campanas')
      await expect(page.locator('.bottom-nav')).toBeVisible()
    }
    await page.locator('.bottom-nav__item').nth(index).click()
    await expect(page).toHaveURL(destinations[index])
  }
})

test('direct advertising moderation deeplink keeps the normal site footer and mobile nav out of the admin shell', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo')))
  await page.route('**/api/v1/admin/advertisements**', (route) => route.fulfill({ json: [] }))
  await page.goto('/#/admin/publicidad')
  await expect(page.getByRole('heading', { name: 'Moderación de publicidad' })).toBeVisible()
  await expect(page.locator('.site-footer')).toHaveCount(0)
  await expect(page.locator('.bottom-nav')).toHaveCount(0)
})

test('advertising API failure leaves homepage usable', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', (route) => route.abort())
  await page.goto('/#/')
  await expect(page.getByText('Tu anuncio podría estar aquí')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Solo habitaciones' })).toBeVisible()
})

test('advertiser previews, returns from Stripe and sees persisted review state', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  let ad: Record<string, unknown> | null = null
  await page.route('**/api/v1/payments/advertisements/*/status', route => route.fulfill({ json: { status: 'pending_review', paymentStatus: 'paid', orderStatus: 'paid', fulfillmentStatus: 'fulfilled' } }))
  await page.route('**/api/v1/payments/advertisements/*/quote**', route => route.fulfill({ json: { days: 30, amountCents: 3000, currency: 'EUR', available: true } }))
  await page.route('**/api/v1/payments/advertisements/*/checkout', route => {
    ad = { ...ad, status: 'pending_review', paymentStatus: 'paid' }
    expect(route.request().postDataJSON()).toEqual({ days: 30 })
    return route.fulfill({ json: { url: '/#/publicidad/' + adId + '/checkout?payment=return', amountCents: 3000, currency: 'EUR' } })
  })
  await page.route('**/api/v1/advertisements**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/homepage')) return route.fulfill({ json: [] })
    if (path.endsWith('/uploads') && request.method() === 'POST') return route.fulfill({ status: 201, json: { id: assetId, url: `/api/v1/media/${assetId}` } })
    if (path.endsWith('/checkout') && request.method() === 'POST') return route.fulfill({ json: { advertisementId: adId, packageId: 'homepage_1d', displayPrice: 'Pago de prueba — sin cargo', paymentMode: 'test' } })
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
  await expect(page.locator('.ad-flow')).not.toContainText('30 €')
  await page.locator('input[type=file]').setInputFiles({ name: 'banner.png', mimeType: 'image/png', buffer: png })
  await page.getByLabel('Título').fill('Local moving service')
  await page.getByLabel('Descripción').fill('A reliable moving service for local residents.')
  await page.getByLabel('Enlace web').fill('https://example.org/moving')
  await page.getByRole('button', { name: 'Vista previa' }).click()
  await expect(page.getByRole('heading', { name: 'Local moving service' })).toBeVisible()
  await expect(page.locator('.ad-flow')).not.toContainText('30 €')
  await page.getByRole('button', { name: 'Continuar al pago' }).click()
  await expect(page).toHaveURL(new RegExp(`#/publicidad/${adId}/checkout`))
  await expect(page.locator('.ad-flow__price')).toContainText('30,00')
  await expect(page.locator('.ad-flow__price')).toContainText('30 días')
  await expectDecodedImage(page.locator('.ad-flow__preview .commercial-ad__visual img'))
  await page.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(page.getByText('Pago confirmado · pendiente de revisión')).toBeVisible()
  await page.getByRole('link', { name: 'Mis campañas', exact: true }).click()
  await expect(page).toHaveURL(/#\/mis-campanas$/)
  await expect(page.getByText('Pendiente de revisión')).toBeVisible()
  await expectDecodedImage(page.locator('.ad-flow__row .commercial-ad__visual img'))
  await page.reload()
  await expect(page.getByText('Pendiente de revisión')).toBeVisible()
  await expectDecodedImage(page.locator('.ad-flow__row .commercial-ad__visual img'))
})

test('admin approves a paid campaign and the homepage displays it', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo')))
  let approved = false
  const detail = {
    id: adId, ownerUserId: 'host-demo', ownerEmail: 'advertiser@example.com', adminPriority: 0,
    title: 'Local moving service', description: 'Moving help across Spain.', imageAssetId: assetId,
    imageUrl: `/api/v1/media/${assetId}?variant=card`, destinationType: 'website',
    destination: 'https://example.org/moving', packageId: 'homepage_1d',
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
  await expectDecodedImage(page.locator('.ad-flow__row .commercial-ad__visual img'))
  await page.getByRole('button', { name: 'Aprobar' }).click()
  await expect(page.getByText('Activa · Pagado')).toBeVisible()
  await page.goto('/#/')
  const publicAd = page.locator('.commercial-ad')
  await expect(publicAd.getByRole('heading', { name: detail.title })).toBeVisible()
  await expectDecodedImage(publicAd.locator('.commercial-ad__visual img'))
})
