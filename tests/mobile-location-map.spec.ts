import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await expect(page.getByText('Español', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Español', exact: true }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByText('España (Tenerife)', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({ viewport: window.innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport)
}

test('onboarding restarts after every full page reload and language names are never machine-translated', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Español', { exact: true })).toBeVisible()
  await expect(page.getByText('English', { exact: true })).toBeVisible()
  await expect(page.getByText('Русский', { exact: true })).toBeVisible()
  await expect(page.getByText('Испанский', { exact: true })).toHaveCount(0)
  await finishOnboarding(page)
  await page.reload()
  await expect(page.getByText('Selecciona el idioma de la aplicación')).toBeVisible()
  await expect(page.getByText('Español', { exact: true })).toBeVisible()
})

test('country selection contains only Tenerife and returns correctly from location editing', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.m2-country')).toHaveCount(1)
  await expect(page.getByText('España (Tenerife)', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
  await page.getByRole('button', { name: 'Cambiar' }).click()
  await expect(page.getByText('Selecciona la región en la que buscas o tienes una vivienda')).toBeVisible()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
})

test('housing modes start inactive and occupant selector supports safe multi-select', async ({ page }) => {
  await finishOnboarding(page)
  const housing = page.getByRole('button', { name: /Vivienda/ })
  const tourism = page.getByRole('button', { name: /Turismo/ })
  await expect(housing).toHaveAttribute('aria-pressed', 'false')
  await expect(tourism).toHaveAttribute('aria-pressed', 'false')
  await housing.click()
  await expect(housing).toHaveAttribute('aria-pressed', 'true')
  await expect(tourism).toHaveAttribute('aria-pressed', 'false')
  await tourism.click()
  await expect(tourism).toHaveAttribute('aria-pressed', 'true')

  await page.getByRole('button', { name: /¿Quién vivirá\?/ }).click()
  const man = page.getByRole('checkbox', { name: 'Para quién: solo un hombre' })
  const woman = page.getByRole('checkbox', { name: 'Para quién: solo una mujer' })
  await man.click(); await woman.click()
  await expect(man).toHaveAttribute('aria-checked', 'true')
  await expect(woman).toHaveAttribute('aria-checked', 'true')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Para quién: solo un hombre, solo una mujer/ })).toBeVisible()

  await page.getByRole('button', { name: /¿Quién vivirá\?/ }).click()
  await page.getByRole('checkbox', { name: 'Para quién: sin restricción' }).click()
  await expect(man).toHaveAttribute('aria-checked', 'false')
  await expect(woman).toHaveAttribute('aria-checked', 'false')
  await expect(page.getByRole('checkbox', { name: 'Para quién: sin restricción' })).toHaveAttribute('aria-checked', 'true')
})

test('location screen contains the approved actions and address submit opens map', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
  await expect(page.getByText('Búsqueda en Tenerife')).toBeVisible()
  await expect(page.locator('.m2-location-action')).toHaveCount(3)
  await expect(page.getByText('Dibujar tu zona', { exact: true })).toBeVisible()
  await expect(page.getByText('Buscar en el mapa', { exact: true })).toBeVisible()
  await expect(page.getByText('Buscar alrededor de ti', { exact: true })).toBeVisible()
  await expect(page.getByTestId('search-phone')).toHaveCount(0)

  const input = page.getByPlaceholder('Municipio, zona o dirección')
  await input.fill('Santa Cruz de Tenerife')
  await input.press('Enter')
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.getByText('Santa Cruz de Tenerife', { exact: true })).toBeVisible()
})

test('current location opens the map and keeps the user coordinates even when no nearby listing is required', async ({ page, context }) => {
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:4173' })
  await context.setGeolocation({ latitude: 28.2916, longitude: -16.6291 })
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
  await page.getByTestId('search-nearby').click()
  await expect(page).toHaveURL(/vista=mapa/)
  await expect(page).toHaveURL(/cerca=1/)
  await expect(page).toHaveURL(/lat=28\.2916/)
  await expect(page).toHaveURL(/lng=-16\.6291/)
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.locator('.m2-user-location-marker')).toHaveCount(1)
})

test('map current-location control centers the map and renders the user marker', async ({ page, context }) => {
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:4173' })
  await context.setGeolocation({ latitude: 28.2916, longitude: -16.6291 })
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
  await page.getByTestId('search-map').click()
  await page.getByRole('button', { name: 'Mi ubicación' }).click()
  await expect(page.getByText('Ubicación encontrada')).toBeVisible()
  await expect(page.locator('.m2-user-location-marker')).toHaveCount(1)
})

test('draw and search map interfaces expose the connected listing layer without a result-count redesign', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
  await page.getByTestId('draw-zone').click()
  await expect(page.getByTestId('map-draw')).toBeVisible()
  await expect(page.getByTestId('google-map')).toBeVisible()
  await expect(page.getByText('Tu propia zona')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cambiar capas' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mi ubicación' })).toBeVisible()
  await page.getByRole('button', { name: 'Volver' }).click()

  await page.getByTestId('search-map').click()
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.locator('.m2-map-results-header')).toContainText('Tenerife')
  await expect.poll(async () => page.locator('.m2-listing-marker').count()).toBeGreaterThan(0)
  await expect(page.locator('.m2-map-results-header')).not.toContainText(/\d+\s+(viviendas|anuncios|resultados)/i)
})

test('menu keeps deleted sections absent and settings rows work without restarting registration', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Menú' }).click()
  await expect(page.getByText('Servicios para ti')).toHaveCount(0)
  await expect(page.getByText(/valora|evalúa|оцените/i)).toHaveCount(0)
  await expect(page.getByText('Buscar agencias para vender')).toBeVisible()
  await expect(page.getByText('Publica tu anuncio')).toBeVisible()

  await page.getByRole('button', { name: /Idioma Español/ }).click()
  await page.getByRole('button', { name: 'English' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByText('Settings', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /Language English/ })).toBeVisible()

  await page.getByRole('button', { name: /Search region España \(Tenerife\)/ }).click()
  await expect(page.getByText('Select the region where you are looking for or own a property')).toBeVisible()
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByText('Settings', { exact: true })).toBeVisible()
})

test('login opened from an app tab uses the canonical account route', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Favoritos' }).click()
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page).toHaveURL(/#\/acceso/)
  await expect(page.getByRole('heading', { name: 'Bienvenido de nuevo' })).toBeVisible()
  await page.goBack()
  await expect(page.getByText('No tienes viviendas en favoritos')).toBeVisible()
  await expect(page.getByText('Gracias por instalar nuestra aplicación')).toHaveCount(0)
})

for (const viewport of [
  { width: 320, height: 700 }, { width: 360, height: 800 }, { width: 390, height: 844 }, { width: 430, height: 932 },
]) {
  test(`main, location, modal and map do not overflow at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await finishOnboarding(page)
    await expectNoHorizontalOverflow(page)
    await page.getByRole('button', { name: /¿Quién vivirá\?/ }).click()
    await expectNoHorizontalOverflow(page)
    await page.getByRole('button', { name: /Cerrar|Close/ }).click()
    await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
    await expectNoHorizontalOverflow(page)
    await page.getByTestId('draw-zone').click()
    await expectNoHorizontalOverflow(page)
  })
}
