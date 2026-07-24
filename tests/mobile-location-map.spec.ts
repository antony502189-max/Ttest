import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await expect(page.getByText('Español', { exact: true })).toBeVisible()
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

test('onboarding starts on every launch and language names are never machine-translated', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Español', { exact: true })).toBeVisible()
  await expect(page.getByText('English', { exact: true })).toBeVisible()
  await expect(page.getByText('Русский', { exact: true })).toBeVisible()
  await expect(page.getByText('Испанский', { exact: true })).toHaveCount(0)
  await finishOnboarding(page)
  await page.reload()
  await expect(page.getByText('Selecciona el idioma de la aplicación')).toBeVisible()
})

test('country selection contains only Tenerife and returns correctly from location editing', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.m2-country')).toHaveCount(1)
  await expect(page.getByText('España (Tenerife)', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await page.getByTestId('open-location').click()
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

test('location screen contains only the required Tenerife actions and address submit opens map', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
  await expect(page.getByText('Búsqueda en Tenerife')).toBeVisible()
  await expect(page.locator('.m2-location-action')).toHaveCount(2)
  await expect(page.getByText('Dibujar tu zona', { exact: true })).toBeVisible()
  await expect(page.getByText('Buscar en el mapa', { exact: true })).toBeVisible()
  await expect(page.getByText(/teléfono/i)).toHaveCount(0)
  await expect(page.getByText(/cerca|proximidad|ubicación actual/i)).toHaveCount(0)

  const input = page.getByPlaceholder('Municipio, zona o dirección')
  await input.fill('Santa Cruz de Tenerife')
  await input.press('Enter')
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.getByText('Santa Cruz de Tenerife', { exact: true })).toBeVisible()
})

test('draw and search map interfaces contain no listing points or result count', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()
  await page.getByTestId('draw-zone').click()
  await expect(page.getByTestId('map-draw')).toBeVisible()
  await expect(page.getByTestId('google-map')).toBeVisible()
  await expect(page.getByText('Tu propia zona')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cambiar capas' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mi ubicación' })).toBeVisible()
  await page.getByRole('button', { name: 'Volver' }).click()

  await page.getByTestId('search-map').click()
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.getByText('Tenerife', { exact: true })).toBeVisible()
  await expect(page.getByText('Zona visible')).toBeVisible()
  await expect(page.locator('.m2-map-screen [data-listing-marker]')).toHaveCount(0)
  await expect(page.locator('.m2-map-results-header')).not.toContainText(/\d+\s+(viviendas|anuncios|resultados)/i)
  const save = page.getByRole('button', { name: 'Guardar' })
  await save.click()
  await expect(page.getByRole('button', { name: 'Guardado' })).toHaveAttribute('aria-pressed', 'true')
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

test('login opened from an app tab returns to that tab instead of privacy onboarding', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Favoritos' }).click()
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page.getByText('Inicia sesión o regístrate')).toBeVisible()
  await page.getByRole('button', { name: 'Volver' }).click()
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
    await page.getByRole('button', { name: 'Cerrar' }).click()
    await page.getByTestId('open-location').click()
    await expectNoHorizontalOverflow(page)
    await page.getByTestId('draw-zone').click()
    await expectNoHorizontalOverflow(page)
  })
}
