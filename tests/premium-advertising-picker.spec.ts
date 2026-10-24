import { expect, test } from '@playwright/test'

const availability = (premiumAvailable = 1, regularAvailable = 7) => ({
  total: 7, available: regularAvailable, monthlyPriceCents: 3000,
  premiumAvailable, premiumMonthlyPriceCents: 6000, months: 1, currency: 'EUR',
  pushEnabled: false, pushPublicKey: null,
})

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/advertisements/premium', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability() }))
})

test('premium and each regular empty slot show exactly one verified monthly price', async ({ page }) => {
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await expect(ads.getByTestId('premium-advertising-banner')).toBeVisible()
  await expect(ads.getByTestId('premium-advertising-price')).toContainText('60')
  await expect(ads.getByTestId('premium-advertising-price')).toContainText('30 días')
  const slots = ads.getByTestId('advertising-slot')
  await expect(slots).toHaveCount(7)
  await expect(ads.getByTestId('advertising-slot-price')).toHaveCount(7)
  for (const item of await ads.getByTestId('advertising-slot-price').all()) {
    await expect(item).toContainText('30')
    await expect(item).toContainText('30 días')
  }
  expect(await ads.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true)
})

test('click premium opens two server-priced choices, then forwards chosen plan before creating a charge', async ({ page }) => {
  let checkoutCount = 0
  await page.route('**/api/v1/payments/advertisements/*/checkout', (route) => { checkoutCount++; return route.fulfill({ status: 503, json: {} }) })
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await ads.locator('.commercial-ad__premium-action').click()
  const picker = page.getByTestId('advertising-package-picker')
  await expect(picker).toBeVisible()
  await expect(picker.getByRole('button', { name: /60\s*€/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(picker.getByRole('button', { name: /30\s*€/ })).toHaveAttribute('aria-pressed', 'false')

  await picker.getByRole('button', { name: /30\s*€/ }).click()
  await expect(picker.getByRole('button', { name: /30\s*€/ })).toHaveAttribute('aria-pressed', 'true')
  await picker.getByRole('button', { name: 'Continuar' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva\?plan=standard/)
  await expect(page.getByTestId('advertising-editor-package')).toContainText('Espacio publicitario')
  await expect(page.getByTestId('advertising-editor-package')).toContainText('30')
  expect(checkoutCount).toBe(0)

  await page.goto('/#/')
  await ads.locator('.commercial-ad__premium-action').click()
  await picker.getByRole('button', { name: 'Continuar' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva\?plan=premium/)
  await expect(page.getByTestId('advertising-editor-package')).toContainText('Banner Premium Principal')
  await expect(page.getByTestId('advertising-editor-package')).toContainText('60')
  expect(checkoutCount).toBe(0)
})

test('occupied premium slot cannot be purchased while ordinary advertising remains available', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability(0, 7) }))
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await expect(ads.locator('.commercial-ad__premium-action')).toBeDisabled()
  await ads.locator('.commercial-ad__slot--empty').first().click()
  const picker = page.getByTestId('advertising-package-picker')
  await expect(picker.getByRole('button', { name: /60\s*€/ })).toBeDisabled()
  await expect(picker.getByRole('button', { name: /30\s*€/ })).toBeEnabled()
  await picker.getByRole('button', { name: 'Continuar' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva\?plan=standard/)
})

test('when the backend tariff is unavailable the app does not invent or offer a charge', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await expect(ads.getByTestId('premium-advertising-price')).toHaveCount(0)
  await expect(ads.getByTestId('advertising-slot-price')).toHaveCount(0)
  await expect(ads.locator('.commercial-ad__premium-action')).toBeDisabled()
  await expect(ads.locator('.commercial-ad__slot--empty').first()).toBeDisabled()
})

test('premium editor persists package selection and shows verified €60 before explicit Stripe click', async ({ page }) => {
  const adId = '00000000-0000-4000-8000-000000000951'
  const assetId = '00000000-0000-4000-8000-000000000952'
  let submittedPackage: string | null = null
  let stripeClicks = 0
  await page.route('**/api/v1/advertisements/uploads', route => route.fulfill({ json: { id: assetId, url: '/api/v1/media/' + assetId } }))
  await page.route('**/api/v1/advertisements', route => {
    if (route.request().method() !== 'POST') return route.fulfill({ json: [] })
    const body = route.request().postDataJSON()
    submittedPackage = body.packageId
    return route.fulfill({ json: {
      ...body, id: adId, ownerUserId: 'host-demo', status: 'pending_payment', paymentStatus: 'unpaid',
      createdAt: new Date().toISOString(), startsAt: null, endsAt: null, moderationNote: null,
      imageUrl: '/api/v1/media/' + assetId, placement: 'homepage_premium',
    } })
  })
  await page.route('**/api/v1/advertisements/' + adId, route => route.fulfill({ json: {
    id: adId, ownerUserId: 'host-demo', imageAssetId: assetId, title: 'Premium banner',
    description: 'Local advertising for the community', destinationType: 'website',
    destination: 'https://example.org/', imageUrl: '/api/v1/media/' + assetId,
    packageId: 'homepage_premium_1m', placement: 'homepage_premium',
    status: 'pending_payment', paymentStatus: 'unpaid', startsAt: null, endsAt: null,
    createdAt: new Date().toISOString(), moderationNote: null,
  } }))
  await page.route('**/api/v1/payments/advertisements/' + adId + '/quote*', route => route.fulfill({ json: {
    days: 30, months: 1, packageId: 'homepage_premium_1m', amountCents: 6000,
    currency: 'EUR', available: true,
  } }))
  await page.route('**/api/v1/payments/advertisements/' + adId + '/checkout', route => {
    stripeClicks++
    return route.fulfill({ status: 503, json: { detail: 'Stripe unavailable in test' } })
  })

  await page.goto('/#/publicidad/nueva?plan=premium')
  await expect(page.getByTestId('advertising-editor-package')).toContainText('60')
  await page.locator('input[type=file]').setInputFiles('src/assets/mobile-hero.jpg')
  await page.getByLabel('Título').fill('Premium banner')
  await page.getByLabel('Descripción').fill('Local advertising for the community')
  await page.getByLabel('Enlace web').fill('https://example.org/')
  await page.getByRole('button', { name: 'Vista previa', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Vista previa' })).toBeVisible()
  await page.getByRole('button', { name: 'Continuar al pago' }).click()
  await expect(page).toHaveURL(new RegExp('/publicidad/' + adId + '/checkout'))
  expect(submittedPackage).toBe('homepage_premium_1m')
  await expect(page.locator('.ad-flow__price')).toContainText('60,00')
  expect(stripeClicks).toBe(0)
  await page.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  expect(stripeClicks).toBe(1)
})


test('unavailable price keeps ad editor editable but blocks payment until a fresh quote arrives', async ({ page }) => {
  let available = false
  let creates = 0
  await page.route('**/api/v1/advertisements/availability', route => {
    if (available) return route.fulfill({ json: availability() })
    return route.fulfill({ status: 503, json: { detail: 'Pricing unavailable' } })
  })
  await page.route('**/api/v1/advertisements', route => {
    if (route.request().method() === 'POST') creates += 1
    return route.fulfill({ status: 503, json: { detail: 'Unavailable' } })
  })
  await page.goto('/#/publicidad/nueva?plan=premium')
  await expect(page.locator('input[type=file]')).toBeVisible()
  await expect(page.getByTestId('advertising-editor-package')).toContainText('No se pudo comprobar')
  await page.getByLabel('Título').fill('A premium campaign')
  await page.getByLabel('Descripción').fill('A local premium campaign ready for upload')
  await page.getByLabel('Enlace web').fill('https://example.org/')
  await expect(page.getByRole('button', { name: 'Vista previa' })).toBeDisabled()
  expect(creates).toBe(0)
  available = true
  await page.getByRole('button', { name: 'Reintentar' }).click()
  await expect(page.getByTestId('advertising-editor-package')).toContainText('60')
  await expect(page.locator('input[type=file]')).toBeVisible()
  expect(creates).toBe(0)
})

test('all standard card children stay inside each card at 320px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 })
  await page.addInitScript(() => localStorage.setItem('112233:language:v1', 'ru'))
  await page.goto('/#/')
  const cards = page.locator('.commercial-ad--mobile .commercial-ad__slot--empty')
  await expect(cards).toHaveCount(7)
  for (const card of await cards.all()) {
    const measured = await card.evaluate(node => {
      const parent = node.getBoundingClientRect()
      const children = Array.from(node.children).map(child => child.getBoundingClientRect())
      return {
        within: children.every(child => child.left >= parent.left - 1 && child.right <= parent.right + 1),
        price: node.querySelector('[data-testid="advertising-slot-price"]')?.textContent,
        scrollWidth: node.scrollWidth,
        clientWidth: node.clientWidth,
      }
    })
    expect(measured.within).toBe(true)
    expect(measured.scrollWidth).toBeLessThanOrEqual(measured.clientWidth)
    expect(measured.price).toContain('30')
  }
})
