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

test('seven banner positions are a grid with genuine sponsored links and bounded provider inventory', async ({ page }) => {
  await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: ads }))
  await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: availability(0) }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
  await expect(block.getByRole('heading', { name: 'Service 8' })).toHaveCount(0)
  await expect(block.locator('.commercial-ad__slot--empty')).toHaveCount(0)
  await expect(block.getByRole('heading', { name: 'Service 1', exact: true })).toBeVisible()
  await expect(block.getByRole('heading', { name: 'Service 7', exact: true })).toBeVisible()
  await expect(block.locator('.commercial-ad__carousel')).toHaveCount(0)
  const firstLink = block.getByRole('link', { name: 'Más información' }).first()
  await expect(firstLink).toHaveAttribute('rel', 'noopener noreferrer sponsored')
  await expect(firstLink).toHaveAttribute('href', 'https://example.org/')
  await expect(block.getByTestId('advertising-monthly-price')).toContainText(/30[.,]00/)
  await expect(block.getByTestId('advertising-monthly-price')).toContainText('/ mes')
  await block.locator('img').evaluateAll(images => images.forEach(img => { (img as HTMLImageElement).loading = 'eager' }))
  await expect.poll(() => block.locator('img').evaluateAll(images => images.every(img => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true)
  await block.screenshot({ path: 'output/advertising/seven-desktop.png', style: '.site-header, .skip-link { visibility: hidden !important; }' })
})

for (const width of [320, 390, 480, 768, 1280]) {
  test(`paid banner images stay inside their column at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => localStorage.setItem('112233:language:v1', 'ru'))
    const shapes = [[800, 800], [1600, 400], [400, 1600]]
    await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: shapes.map(([imageWidth, imageHeight], index) => ({
      ...ads[index], title: index === 0 ? 'ChatGPT' : 'ОченьДлинноеНазваниеРекламодателяБезПробелов',
      description: 'Ваш интеллектуальный помощник. Помогаем с работой, учёбой и повседневными задачами.',
      imageUrl: `/api/v1/media/${assetId}?shape=${index}`, imageWidth, imageHeight,
    })) }))
    await page.route(`**/api/v1/media/${assetId}**`, route => {
      const [w, h] = shapes[Number(new URL(route.request().url()).searchParams.get('shape'))]
      return route.fulfill({ contentType: 'image/svg+xml', body: `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="${w}" height="${h}" fill="#173d32"/><circle cx="${w / 2}" cy="${h / 2}" r="${Math.min(w, h) * .3}" fill="#d8ff4b"/></svg>` })
    })
    await page.goto('/#/')
    const cards = page.locator('.commercial-ad article[data-ad-id]')
    await expect(cards).toHaveCount(3)
    for (const card of await cards.all()) {
      await card.scrollIntoViewIfNeeded()
      await expect.poll(() => card.locator('img').evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true)
      const bounds = await card.evaluate(element => {
        const rect = (selector: string) => {
          const { x, y, width, height, right, bottom } = element.querySelector(selector)!.getBoundingClientRect()
          return { x, y, width, height, right, bottom }
        }
        return { card: element.getBoundingClientRect().toJSON(), visual: rect('.commercial-ad__visual'), image: rect('img'), copy: rect('.commercial-ad__copy'), link: rect('a') }
      })
      expect(bounds.image.right).toBeLessThanOrEqual(bounds.visual.right + 1)
      expect(bounds.image.bottom).toBeLessThanOrEqual(bounds.visual.bottom + 1)
      expect(bounds.visual.right + 8).toBeLessThanOrEqual(bounds.copy.x)
      expect(bounds.copy.right).toBeLessThanOrEqual(bounds.card.right)
      expect(bounds.link.right).toBeLessThanOrEqual(bounds.card.right)
      expect(bounds.link.bottom).toBeLessThanOrEqual(bounds.card.bottom)
    }
    expect(await page.locator('.commercial-ad').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await cards.first().screenshot({ path: `output/advertising/paid-banner-${width}.png` })
  })
}

for (const width of [320, 390, 480]) {
  test(`empty mobile advertising positions match restored vertical reference at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.addInitScript(() => localStorage.setItem('112233:language:v1', 'ru'))
    await page.goto('/#/')
    const block = page.locator('.commercial-ad--mobile')
    await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
    await expect(block.getByTestId('advertising-monthly-price')).toContainText(/30[.,]00/)
    await expect(block.getByTestId('advertising-monthly-price')).toContainText('/ месяц')
    const slots = block.locator('.commercial-ad__slot--empty')
    await expect(slots).toHaveCount(7)
    await expect(slots.first()).toContainText('Рекламное место')
    await expect(slots.nth(6)).toContainText('Рекламное место')
    await expect(block.getByRole('heading', { name: 'Здесь могла быть ваша реклама' })).toBeVisible()
    await expect(block.getByText('Расскажите о своём бизнесе пользователям 112233.es.')).toBeVisible()
    const cta = block.getByRole('link', { name: 'Разместить рекламу' })
    await expect(cta).toHaveAttribute('href', '#/publicidad/nueva')
    await cta.scrollIntoViewIfNeeded()
    await expect(cta).toBeInViewport()
    for (const index of [1, 3, 6]) {
      const prev = await slots.nth(index - 1).boundingBox()
      const cur = await slots.nth(index).boundingBox()
      expect(prev).not.toBeNull()
      expect(cur).not.toBeNull()
      expect(cur!.y).toBeGreaterThanOrEqual(prev!.y + prev!.height)
      expect(Math.abs(cur!.x - prev!.x)).toBeLessThan(2)
      expect(Math.abs(cur!.width - prev!.width)).toBeLessThan(2)
    }
    const sample = await slots.first().boundingBox()
    expect(sample).not.toBeNull()
    expect(sample!.height).toBeGreaterThanOrEqual(120)
    // The existing mobile shell is capped at 430px; do not widen unrelated screens.
    expect(sample!.width).toBeGreaterThanOrEqual(Math.min(width, 430) - 40)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await block.screenshot({ path: `output/advertising/reference-mobile-${width}.png`, style: '.m2-bottom-nav, .skip-link { visibility: hidden !important; }' })
  })
}

test('advertising price is taken from server availability, not a hardcoded client amount', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: { ...availability(4), monthlyPriceCents: 4500 } }))
  await page.goto('/#/')
  const price = page.locator('.commercial-ad').getByTestId('advertising-monthly-price')
  await expect(price).toContainText('45,00')
  await expect(price).toContainText('/ mes')
})

test('no public price is invented when the pricing endpoint is unavailable', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  await expect(block.getByTestId('advertising-monthly-price')).toHaveCount(0)
  await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
})

test('desktop advertising uses two columns and keeps the original CTA', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 960 })
  await page.goto('/#/')
  const block = page.locator('.commercial-ad')
  const cards = block.locator('.commercial-ad__slot--empty')
  await expect(cards).toHaveCount(7)
  const first = await cards.nth(0).boundingBox()
  const second = await cards.nth(1).boundingBox()
  const third = await cards.nth(2).boundingBox()
  expect(first).not.toBeNull()
  expect(second).not.toBeNull()
  expect(third).not.toBeNull()
  expect(Math.abs(second!.y - first!.y)).toBeLessThanOrEqual(2)
  expect(second!.x).toBeGreaterThan(first!.x + first!.width)
  expect(third!.y).toBeGreaterThanOrEqual(first!.y + first!.height)
  await expect(block.getByRole('link', { name: 'Publicar publicidad' })).toBeVisible()
})

for (const count of [0, 1, 2, 3, 6, 7]) {
  test(`${count} paid banners occupy exactly ${count} of seven grid slots`, async ({ page }) => {
    await page.route('**/api/v1/advertisements/homepage', route => route.fulfill({ json: ads.slice(0, count) }))
    await page.route('**/api/v1/advertisements/availability', route => route.fulfill({ json: availability(7 - count) }))
    await page.goto('/#/')
    const block = page.locator('.commercial-ad')
    await expect(block.getByTestId('advertising-slot')).toHaveCount(7)
    await expect(block.locator('article[data-ad-id]')).toHaveCount(count)
    await expect(block.locator('.commercial-ad__slot--empty')).toHaveCount(7 - count)
    if (count === 7) {
      await expect(block.getByRole('link', { name: 'Publicar publicidad' })).toHaveCount(0)
    } else {
      await expect(block.getByRole('link', { name: 'Publicar publicidad' })).toBeVisible()
    }
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
  await expect(page.locator('.ad-flow__price')).toContainText('1 mes')
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
