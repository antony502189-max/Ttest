import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('https://**/*', route => route.abort())
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
})

for (const [city, postcode, province, lat, lng] of [
  ['Madrid', '28013', 'Madrid', 40.4168, -3.7038],
  ['Las Palmas de Gran Canaria', '35001', 'Las Palmas', 28.10, -15.42],
  ['Palma', '07001', 'Illes Balears', 39.57, 2.65],
  ['Ceuta', '51001', 'Ceuta', 35.89, -5.31],
  ['Melilla', '52001', 'Melilla', 35.29, -2.94],
] as const) {
  test(`real typing and prediction selection accepts ${city}`, async ({ page }) => {
    await page.goto('/#/publicar', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('#publish-street[data-address-autocomplete="native"]')).toBeVisible()
    await page.evaluate(({ city, postcode, lat, lng }) => {
      const fixture = { label: `Calle Mayor 1, ${postcode} ${city}, Spain`, detail: {
        formattedAddress: `Calle Mayor 1, ${postcode} ${city}, Spain`, coordinates: { lat, lng }, addressComponents: [
          { longText: 'Calle Mayor', types: ['route'] }, { longText: '1', types: ['street_number'] },
          { longText: postcode, types: ['postal_code'] }, { longText: city, types: ['locality'] },
          { longText: 'Centro', types: ['neighborhood'] }, { longText: 'Spain', shortText: 'ES', types: ['country'] },
        ],
      } }
      ;(window as unknown as { __112233TestAddressPredictions: () => Promise<unknown[]> }).__112233TestAddressPredictions = async () => [fixture]
    }, { city, postcode, lat, lng })
    await page.locator('#publish-street').fill(`Calle Mayor 1, ${city}`)
    await page.locator('.publish-address-prediction').first().click()
    await expect(page.locator('#publish-postcode')).toHaveValue(postcode)
    await expect(page.locator('#publish-city')).toHaveValue(city)
    await expect(page.getByLabel('Provincia', { exact: true })).toHaveValue(province)
  })
}

test('explicit Madrid province outranks remembered Tenerife camera', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:map-last-search-area:v2',
    JSON.stringify({ center: { lat: 28.2916, lng: -16.6291 }, savedAt: Date.now() })))
  await page.goto('/#/buscar?q=España&provincia=28&vista=mapa&alquiler=long', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-test-map-sdk="1"]')).toHaveCount(1)
  await expect.poll(() => page.evaluate(() => {
    const map = (window as unknown as { __googleMapsTestLastMap: { getCenter: () => { lat: () => number; lng: () => number } } }).__googleMapsTestLastMap
    return map.getCenter().lat()
  })).toBeGreaterThan(40)
  const lng = await page.evaluate(() => (window as unknown as { __googleMapsTestLastMap: { getCenter: () => { lng: () => number } } }).__googleMapsTestLastMap.getCenter().lng())
  expect(lng).toBeGreaterThan(-5)
  expect(lng).toBeLessThan(-2)
  await page.screenshot({ path: 'remediation-results/madrid-map.png' })
})

for (const width of [320, 768, 1280]) {
  test(`approved location shell and map alternatives at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    if (width < 768) {
      await page.goto('/#/?panel=ubicacion', { waitUntil: 'domcontentloaded' })
      await expect(page.getByTestId('search-nearby')).toBeVisible()
      await expect(page.getByTestId('search-map')).toBeVisible()
    } else {
      await page.goto('/#/', { waitUntil: 'domcontentloaded' })
      await page.locator('.location-selector-trigger').first().click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toHaveClass(/location-selector-dialog/)
      await expect(dialog.getByText('Seleccionar zonas en el mapa', { exact: true })).toBeVisible()
      await expect(dialog.getByText('Dibujar tu zona', { exact: true })).toBeVisible()
      await expect(dialog.getByText('Buscar en el mapa', { exact: true })).toBeVisible()
      await expect(dialog.getByText('Buscar alrededor de ti', { exact: true })).toBeVisible()
      expect((await dialog.boundingBox())!.width).toBeGreaterThan(width * .8)
      expect(await dialog.locator('.location-catalog-list').evaluate(el => getComputedStyle(el).backgroundColor)).not.toBe('rgb(32, 32, 32)')
    }
    await page.screenshot({ path: `remediation-results/location-${width}.png` })
  })
}

test('countdown zero waits for authoritative response, survives reload and clock skew', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-17T12:00:00Z') })
  let requests = 0
  let release = false
  await page.route('**/payments/listings/*/top/availability?*', route => {
    requests++
    return route.fulfill({ json: { municipality: 'Madrid', municipalityCode: '28079', capacity: 3,
      available: release, availableSlots: release ? 1 : 0,
      serverNow: '2026-10-17T12:00:00Z', availableAt: '2026-10-17T12:00:04Z' } })
  })
  const open = async () => {
    await page.getByTestId('owner-top-promote-button').first().click()
    await page.getByTestId('owner-promotion-choices').getByRole('button').last().click()
  }
  await page.goto('/#/mis-anuncios', { waitUntil: 'domcontentloaded' }); await open()
  await expect(page.getByRole('timer')).toHaveText('00:00:04')
  await page.clock.setSystemTime(new Date('2026-10-18T12:00:00Z'))
  await expect(page.getByRole('timer')).toHaveText('00:00:04')
  await page.reload({ waitUntil: 'domcontentloaded' }); await open()
  await expect(page.getByRole('timer')).toHaveText('00:00:04')
  const previous = requests
  release = true
  await page.clock.fastForward(5000)
  await expect.poll(() => requests).toBeGreaterThan(previous)
  await expect(page.getByRole('button', { name: 'Continuar', exact: true })).toBeEnabled()
})

test('unknown release, malformed time and transient failure never enable a purchase', async ({ page }) => {
  await page.clock.install()
  let mode = 'unknown'
  await page.route('**/payments/listings/*/top/availability?*', route => mode === 'error'
    ? route.fulfill({ status: 503, json: { detail: 'Temporary failure' } })
    : route.fulfill({ json: { municipality: 'Madrid', available: mode === 'released', availableSlots: mode === 'released' ? 1 : 0,
      serverNow: mode === 'malformed' ? 'invalid' : '2026-10-17T12:00:00Z', availableAt: mode === 'malformed' ? 'invalid' : null } }))
  await page.goto('/#/mis-anuncios', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('owner-top-promote-button').first().click()
  await page.getByTestId('owner-promotion-choices').getByRole('button').last().click()
  const next = page.getByRole('button', { name: 'Continuar', exact: true })
  await expect(next).toBeDisabled()
  await expect(page.getByRole('timer')).toHaveCount(0)
  mode = 'malformed'; await page.clock.fastForward(15001)
  await expect(page.getByRole('timer')).toHaveCount(0)
  await expect(next).toBeDisabled()
  mode = 'error'; await page.clock.fastForward(15001)
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(next).toBeDisabled()
  mode = 'released'; await page.clock.fastForward(15001)
  await expect(next).toBeEnabled()
})

test('saved code-only provincial scope round-trips and legacy city scope stays a city', async ({ page }) => {
  await page.goto('/#/buscar?q=España&provincia=28&alquiler=long', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Guardar búsqueda', exact: true }).first().click()
  await page.goto('/#/busquedas-guardadas', { waitUntil: 'domcontentloaded' })
  await page.getByRole('link', { name: 'Ver resultados', exact: true }).first().click()
  await expect(page).toHaveURL(/provincia=28/)
  await page.evaluate(() => {
    const key = '112233:saved-searches:v3'
    const stored = JSON.parse(localStorage.getItem(key)!)
    const rows = Object.values(stored.data).find((value: unknown) => Array.isArray(value) && value.length) as Array<Record<string, unknown>>
    rows.push({ ...rows[0], id: 'legacy-city', query: 'Madrid', provinceCode: null })
    localStorage.setItem(key, JSON.stringify(stored))
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.goto('/#/busquedas-guardadas', { waitUntil: 'domcontentloaded' })
  await page.locator('.saved-search-card').filter({ hasText: 'Habitaciones en Madrid' }).getByRole('link', { name: 'Ver resultados' }).click()
  await expect(page).toHaveURL(/ubicacion=ciudad/)
  expect(page.url()).not.toContain('provincia=')
})
