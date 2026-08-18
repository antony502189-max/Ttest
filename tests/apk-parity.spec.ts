import { expect, test, type Page } from '@playwright/test'

async function completeOnboarding(page: Page) {
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

async function finishOnboarding(page: Page) {
  await page.goto('/')
  if (await page.getByTestId('open-location').isVisible().catch(() => false)) return
  await completeOnboarding(page)
}

const homeModeButton = (page: Page, mode: 'housing' | 'tourism') =>
  page.locator('.m2-mode-switch > button').nth(mode === 'housing' ? 0 : 1)

test.describe('APK shell connected to the canonical web app', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('home refresh intentionally returns to onboarding', async ({ page }) => {
    await finishOnboarding(page)
    await page.reload()
    await expect(page.getByText('Selecciona el idioma de la aplicación')).toBeVisible()
    await expect(page.getByTestId('open-location')).toHaveCount(0)
    await completeOnboarding(page)
  })

  test('onboarding legal links open the real privacy and terms routes', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()

    const privacy = page.getByRole('link', { name: 'Política de privacidad' })
    const terms = page.getByRole('link', { name: 'Términos y condiciones' })
    await expect(privacy).toHaveAttribute('href', '#/privacidad')
    await expect(terms).toHaveAttribute('href', '#/terminos')

    await privacy.click()
    await expect(page).toHaveURL(/#\/privacidad$/)
    await expect(page.getByRole('heading', { name: 'Política de privacidad' })).toBeVisible()
  })

  test('location, search, back and reload use real URLs', async ({ page }) => {
    await finishOnboarding(page)
    await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
    await expect(page).toHaveURL(/panel=ubicacion/)
    await expect(page.getByTestId('location-screen')).toBeVisible()
    await page.getByRole('button', { name: 'Volver' }).click()
    await expect(page).toHaveURL(/#\/$/)

    await homeModeButton(page, 'housing').click()
    await page.getByTestId('open-location').click()
    await expect(page).toHaveURL(/#\/buscar\?q=Tenerife&alquiler=long/)
    await expect(page.getByTestId('mobile-results')).toBeVisible()
    await page.reload()
    await expect(page.getByTestId('mobile-results')).toBeVisible()
  })

  test('listing, account and publication actions open canonical routes', async ({ page }) => {
    await finishOnboarding(page)
    await page.getByTestId('open-location').click()
    const firstListing = page.locator('.m2-result-card__image-button').first()
    await firstListing.click()
    await expect(page).toHaveURL(/#\/habitacion\//)
    await expect(page.locator('.idealista-listing-page')).toBeVisible()

    await page.goto('/#/')
    await page.reload()
    await expect(page.getByText('Selecciona el idioma de la aplicación')).toBeVisible()
    await completeOnboarding(page)
    await page.getByRole('button', { name: 'Publicar anuncio' }).click()
    await expect(page).toHaveURL(/gate=publicar/)
    await expect(page.getByTestId('publication-gate')).toBeVisible()
    await page.getByTestId('publication-gate').getByRole('button', { name: 'Iniciar sesión' }).click()
    await expect(page).toHaveURL(/#\/acceso/)
  })

  test('bottom tabs are deep links and favorites display stored data', async ({ page }) => {
    await finishOnboarding(page)
    await page.getByTestId('open-location').click()
    await page.locator('.m2-result-card__favorite').first().click()
    await page.getByRole('button', { name: 'Volver' }).click()
    await expect(page.getByTestId('mobile-results')).toHaveCount(0)
    await page.getByRole('button', { name: 'Favoritos', exact: true }).click()
    await expect(page).toHaveURL(/#\/favoritos/)
    await expect(page.locator('.m2-collection__list > button')).toHaveCount(1)
    await page.evaluate(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.reload()
    await expect(page.locator('.m2-collection__list > button')).toHaveCount(1)
  })

  test('map and drawing screens are reflected in the URL', async ({ page }) => {
    await finishOnboarding(page)
    await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
    await page.getByTestId('draw-zone').click()
    await expect(page).toHaveURL(/vista=mapa.*dibujar=1/)
    await expect(page.getByTestId('map-draw')).toBeVisible()
    await page.getByRole('button', { name: 'Volver' }).click()
    await expect(page).toHaveURL(/panel=ubicacion/)
  })

  test('location actions keep nearby search connected', async ({ page, context }) => {
    await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:4173' })
    await context.setGeolocation({ latitude: 28.2916, longitude: -16.6291 })
    await finishOnboarding(page)
    await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
    await expect(page.locator('.m2-location-action')).toHaveCount(3)

    await page.getByTestId('search-nearby').click()
    await expect(page).toHaveURL(/vista=mapa.*cerca=1.*lat=28\.2916.*lng=-16\.6291/)
    await expect(page.getByTestId('map-search')).toBeVisible()

    await page.getByRole('button', { name: 'Volver' }).click()
    await expect(page.getByTestId('search-phone')).toHaveCount(0)
  })
})

test('desktop keeps the existing responsive route-based design', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Solo habitaciones' })).toBeVisible()
  await expect(page.locator('.m2-app')).toHaveCount(0)
})
