import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const adId = '00000000-0000-4000-8000-000000000731'
const assetId = '00000000-0000-4000-8000-000000000732'
const png = readFileSync('src/assets/mobile-hero.jpg')
const availability = (available = 7) => ({ total: 7, available, monthlyPriceCents: 3000, months: 1, currency: 'EUR', pushEnabled: false, pushPublicKey: null })
const ads = Array.from({ length: 8 }, (_, index) => ({ id: `${adId}-${index}`, title: `Service ${index + 1}`, description: 'A local service for our community.', imageUrl: `/api/v1/media/${assetId}?variant=card`, imageWidth: 800, imageHeight: 450, destinationType: 'website', destinationUrl: 'https://example.org/', placement: 'homepage_bottom' }))

test.beforeEach(async ({ page }) => {
  await page.route('https://images.unsplash.com/**', route => route.fulfill({ body: png, contentType: 'image/jpeg' }))
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability() }))
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: [] }))
  await page.route(`**/api/v1/media/${assetId}**`, (route) => route.fulfill({ body: png, contentType: 'image/jpeg' }))
  await page.route(`**/api/v1/payments/advertisements/${adId}/quote**`, (route) => route.fulfill({ json: { days: 30, amountCents: 3000, currency: 'EUR', available: true } }))
  await page.route('**/api/v1/advertisements/waitlist', route => route.fulfill({ json: { subscribed: false, channel: 'site' } }))
  await page.route('**/api/v1/payments/admin/review-required', route => route.fulfill({ json: [] }))
})

test('carousel preserves sponsored links, loops and caps an oversized response at seven', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: ads }))
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability(0) }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
  await expect(block.getByRole('heading', { name: 'Service 8' })).toHaveCount(0)
  await expect(block.locator('[data-testid="advertising-slot"][aria-hidden="false"]')).toHaveCount(1)
  await expect(block.getByRole('heading', { name: 'Service 1', exact: true })).toBeVisible()
  await block.getByRole('button', { name: 'Publicidad anterior' }).click()
  await expect(block.getByRole('heading', { name: 'Service 7' })).toBeVisible()
  await block.getByRole('button', { name: 'Publicidad siguiente' }).click()
  await expect(block.getByRole('heading', { name: 'Service 1', exact: true })).toBeVisible()
  await block.getByRole('button', { name: 'Publicidad 4', exact: true }).click()
  await expect(block.getByRole('heading', { name: 'Service 4' })).toBeVisible()
  await expect(block.getByRole('button', { name: 'Publicidad 4', exact: true })).toHaveAttribute('aria-current', 'true')
  await expect(block.getByRole('link', { name: 'Más información' }).first()).toHaveAttribute('rel', 'noopener noreferrer sponsored')
  await expect(block.getByText('30 € · 1 mes')).toHaveCount(0)
  await block.locator('img').evaluateAll((images) => images.forEach((img) => { (img as HTMLImageElement).loading = 'eager' }))
  await expect.poll(() => block.locator('img').evaluateAll((images) => images.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true)
  await block.screenshot({ path: 'output/advertising/seven-desktop.png', style: '.site-header, .skip-link { visibility: hidden !important; }' })
})

test('mobile carousel supports swiping and fits above fixed navigation at 320px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 })
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: ads.slice(0, 7) }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad--mobile')
  await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
  const track = block.locator('.commercial-ad__slides')
  await track.scrollIntoViewIfNeeded()
  const bounds = await track.boundingBox()
  expect(bounds).not.toBeNull()
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true })
  const x = bounds!.x + bounds!.width * .8
  const y = bounds!.y + 80
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] })
  for (let step = 1; step <= 6; step++) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x - step * bounds!.width * .1, y }] })
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await expect(block.locator('.commercial-ad__carousel-position')).toHaveText('2 / 7')
  await expect(block.getByRole('heading', { name: 'Service 2' })).toBeVisible()
  await expect(block.locator('[data-testid="advertising-slot"][aria-hidden="false"]')).toHaveCount(1)
  await block.getByRole('link', { name: 'Publicar publicidad' }).scrollIntoViewIfNeeded()
  await expect(block.getByRole('link', { name: 'Publicar publicidad' })).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await block.locator('img').evaluateAll((images) => images.forEach((img) => { (img as HTMLImageElement).loading = 'eager' }))
  await expect.poll(() => block.locator('img').evaluateAll((images) => images.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true)
  await block.screenshot({ path: 'output/advertising/seven-mobile.png', style: '.m2-bottom-nav, .skip-link { visibility: hidden !important; }' })
})

test('empty inventory shows one Russian placeholder without carousel controls', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:language:v1', 'ru'))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await expect(block.getByTestId('advertising-slot')).toHaveCount(1)
  await expect(block.getByRole('heading', { name: 'Здесь могла быть ваша реклама' })).toBeVisible()
  await expect(block.locator('.commercial-ad__carousel')).toHaveCount(0)
})

for (const width of [320, 390, 1280]) {
  test(`first banner and final placeholder are centered at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: ads.slice(0, 1) }))
    await page.goto('/#/')
    const block = page.locator('.commercial-ad')
    await block.scrollIntoViewIfNeeded()
    for (let index = 0; index < 2; index++) {
      await block.getByRole('button', { name: `Publicidad ${index + 1}`, exact: true }).click()
      await expect.poll(() => block.locator('.commercial-ad__slides').evaluate((element, position) => {
        const track = element.getBoundingClientRect()
        const card = element.children[position].getBoundingClientRect()
        return Math.abs((card.left + card.right) / 2 - (track.left + track.right) / 2)
      }, index)).toBeLessThanOrEqual(1)
    }
    await expect(block.getByRole('button', { name: /Pausar|Reanudar/ })).toHaveCount(0)
  })
}

test('visible carousel advances automatically and wraps without a pause button', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: ads.slice(0, 1) }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await block.scrollIntoViewIfNeeded()
  await page.mouse.move(0, 0)
  const position = block.locator('.commercial-ad__carousel-position')
  await expect(position).toHaveText('1 / 2')
  await expect(position).toHaveText('2 / 2', { timeout: 8000 })
  await expect(position).toHaveText('1 / 2', { timeout: 8000 })
  await expect(block.getByRole('button', { name: 'Pausar publicidad' })).toHaveCount(0)
})

test('reduced motion leaves manual navigation available without autoplay', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: ads.slice(0, 1) }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await block.scrollIntoViewIfNeeded()
  await page.mouse.move(0, 0)
  await page.waitForTimeout(5500)
  await expect(block.locator('.commercial-ad__carousel-position')).toHaveText('1 / 2')
  await expect(block.getByRole('button', { name: 'Pausar publicidad' })).toHaveCount(0)
  await block.getByRole('button', { name: 'Publicidad siguiente' }).click()
  await expect(block.locator('.commercial-ad__carousel-position')).toHaveText('2 / 2')
})

for (const count of [1, 2, 3, 6, 7]) {
  test(`${count} banners have exactly one vacancy slide until all seven places are filled`, async ({ page }) => {
    await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: ads.slice(0, count) }))
    await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: availability(7 - count) }))
    await page.goto('/#/')
    const block = page.locator('.commercial-ad')
    const total = Math.min(count + 1, 7)
    await expect(block.getByTestId('advertising-slot')).toHaveCount(total)
    await expect(block.locator('.commercial-ad__slot--empty')).toHaveCount(count < 7 ? 1 : 0)
    for (let index = 0; index < total; index++) {
      const visible = block.locator('[data-testid="advertising-slot"][aria-hidden="false"]')
      await expect(visible).toHaveCount(1)
      await expect(visible.getByRole('heading')).toHaveText(index < count ? `Service ${index + 1}` : 'Tu anuncio podría estar aquí')
      await expect(block.locator('.commercial-ad__carousel-position')).toHaveText(`${index + 1} / ${total}`)
      await block.getByRole('button', { name: 'Publicidad siguiente' }).click()
    }
    await expect(block.getByRole('heading', { name: 'Service 1', exact: true })).toBeVisible()
    await expect(block.getByRole('heading', { name: 'Tu anuncio podría estar aquí' })).toHaveCount(0)
  })
}

test('full inventory prevents upload and offers a cancellable persisted alert', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability(0) }))
  let subscriptions = 0
  let cancelled = false
  await page.route('**/api/v1/advertisements/waitlist', (route) => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { subscribed: false, channel: 'site' } })
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
  await expect(page.locator('.ad-flow__price')).toContainText('30,00')
  await expect(page.locator('.ad-flow__price')).toContainText('30 días')
  expect(checkouts).toBe(0)
  await page.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(page.getByText('No hay espacios publicitarios disponibles en este momento.')).toBeVisible()
  expect(checkouts).toBe(1)
  await expect(page.getByRole('button', { name: 'Avisarme cuando haya un espacio' })).toBeVisible()
})

test('saved push alert survives reload and can be cancelled', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: availability(0) }))
  let subscribed = true
  await page.route('**/api/v1/advertisements/waitlist', route => {
    if (route.request().method() === 'DELETE') { subscribed = false; return route.fulfill({ status: 204 }) }
    return route.fulfill({ json: { subscribed, channel: 'push' } })
  })
  await page.goto('/#/publicidad/nueva')
  await expect(page.getByText('Te enviaremos una notificación push cuando se libere un espacio.')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Cancelar aviso' })).toBeVisible()
  await page.getByRole('button', { name: 'Cancelar aviso' }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Avisarme cuando haya un espacio' })).toBeVisible()
})

test('Stripe cancellation return releases the reservation and allows a new attempt', async ({ page }) => {
  const item = { ...ads[0], id: adId, imageAssetId: assetId, packageId: 'homepage_1d', status: 'pending_payment', paymentStatus: 'unpaid' }
  await page.route('**/api/v1/advertisements/' + adId, route => route.fulfill({ json: item }))
  let cancelled = false
  await page.route('**/api/v1/payments/advertisements/*/checkout/cancel', route => {
    cancelled = true
    return route.fulfill({ json: { cancelled: true, paid: false } })
  })
  await page.goto('/#/publicidad/' + adId + '/checkout?payment=cancelled')
  await expect(page.getByText('Pago cancelado. El espacio reservado se ha liberado.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pagar con Stripe' })).toBeEnabled()
  expect(cancelled).toBe(true)
})

test('review-required paid order never offers another payment', async ({ page }) => {
  const item = { ...ads[0], id: adId, imageAssetId: assetId, packageId: 'homepage_1d', status: 'pending_payment', paymentStatus: 'unpaid' }
  await page.route('**/api/v1/advertisements/' + adId, route => route.fulfill({ json: item }))
  await page.route('**/api/v1/payments/advertisements/*/status', route => route.fulfill({ json: { status: 'pending_payment', paymentStatus: 'unpaid', orderStatus: 'paid', fulfillmentStatus: 'review_required' } }))
  await page.goto('/#/publicidad/' + adId + '/checkout?payment=return')
  await expect(page.getByText('El pago se ha recibido, pero necesita revisión. Contacta con soporte; no vuelvas a pagar.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pagar con Stripe' })).toHaveCount(0)
})

test('browser push permission denied keeps a truthful site-notification fallback', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'PushManager', { value: function PushManager() {} })
    Object.defineProperty(Notification, 'requestPermission', { value: async () => 'denied' })
  })
  await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: { ...availability(0), pushEnabled: true, pushPublicKey: 'test' } }))
  await page.route('**/api/v1/advertisements/waitlist', route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { subscribed: false, channel: 'site' } })
    expect(route.request().postDataJSON().subscription).toBeNull()
    return route.fulfill({ json: { subscribed: true, available: false } })
  })
  await page.goto('/#/publicidad/nueva')
  await page.getByRole('button', { name: 'Avisarme cuando haya un espacio' }).click()
  await expect(page.getByText('Te avisaremos en las notificaciones del sitio cuando se libere un espacio.')).toBeVisible()
})

test('sign-in for a vacancy alert returns to advertising instead of losing the intent', async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem('112233:session:v1'))
  await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: availability(0) }))
  await page.goto('/#/')
  await page.getByRole('link', { name: 'Inicia sesión para recibir un aviso' }).click()
  await expect(page).toHaveURL(/#\/acceso$/)
  await page.getByRole('button', { name: 'Continuar con Google' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva$/)
  await expect(page.getByRole('button', { name: 'Avisarme cuando haya un espacio' })).toBeVisible()
})

test('campaign list shows a received payment under review instead of another pay link', async ({ page }) => {
  await page.route('**/api/v1/advertisements/mine', route => route.fulfill({ json: [{ ...ads[0], id: adId, imageAssetId: assetId,
    destination: 'https://example.org/', packageId: 'homepage_1d', status: 'pending_payment', paymentStatus: 'unpaid',
    paymentReviewRequired: true, createdAt: new Date().toISOString(), startsAt: null, endsAt: null, moderationNote: null }] }))
  await page.goto('/#/mis-campanas')
  await expect(page.getByText('Pendiente de pago · Pago en revisión')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Pagar', exact: true })).toHaveCount(0)
  await expect(page.getByText('El pago se ha recibido, pero necesita revisión. Contacta con soporte; no vuelvas a pagar.')).toBeVisible()
})

test('banner image recovers after a transient failure on the next availability refresh', async ({ page }) => {
  await page.clock.install()
  await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: ads.slice(0, 1) }))
  let failing = true
  await page.route('**/api/v1/media/' + assetId + '**', route => failing ? route.abort() : route.fulfill({ body: png, contentType: 'image/jpeg' }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await block.scrollIntoViewIfNeeded()
  await expect(block.locator('.commercial-ad__visual > svg')).toBeVisible()
  failing = false
  await page.clock.runFor(60001)
  const image = block.locator('.commercial-ad__visual img')
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate(node => (node as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
})
