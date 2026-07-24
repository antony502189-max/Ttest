import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: import('@playwright/test').Page) {
  await page.goto('/')
  await expect(page.getByText('Español', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByText('España (Tenerife)', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

test('location selection contains only the required Tenerife actions', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()

  await expect(page.getByTestId('location-screen')).toBeVisible()
  await expect(page.getByText('Búsqueda en Tenerife')).toBeVisible()
  await expect(page.getByPlaceholder('Municipio, zona o dirección')).toBeVisible()
  await expect(page.locator('.m2-location-action')).toHaveCount(2)
  await expect(page.getByText('Dibujar tu zona', { exact: true })).toBeVisible()
  await expect(page.getByText('Buscar en el mapa', { exact: true })).toBeVisible()
  await expect(page.getByText(/teléfono/i)).toHaveCount(0)
  await expect(page.getByText(/ubicación/i)).toHaveCount(0)

  await page.getByRole('button', { name: 'Cambiar' }).click()
  await expect(page.getByText('Selecciona la región en la que buscas o tienes una vivienda')).toBeVisible()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
})

test('draw and search map screens open without listing points or counts', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()

  await page.getByTestId('draw-zone').click()
  await expect(page.getByTestId('map-draw')).toBeVisible()
  await expect(page.getByTestId('google-map')).toBeVisible()
  await expect(page.getByText('Tu propia zona')).toBeVisible()
  await page.locator('.m2-back-header .m2-icon-button').click()

  await page.getByTestId('search-map').click()
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.getByTestId('google-map')).toBeVisible()
  await expect(page.getByText('Tenerife', { exact: true })).toBeVisible()
  await expect(page.getByText('Zona visible')).toBeVisible()
  await expect(page.locator('.m2-map-screen [data-listing-marker]')).toHaveCount(0)
  await expect(page.locator('.m2-map-results-header')).not.toContainText(/\d+\s+(viviendas|anuncios|resultados)/i)
})

test('housing modes start inactive and occupant selector supports multiple values', async ({ page }) => {
  await finishOnboarding(page)

  const housing = page.getByRole('button', { name: /Vivienda/ })
  const tourism = page.getByRole('button', { name: /Turismo/ })
  await expect(housing).toHaveAttribute('aria-pressed', 'false')
  await expect(tourism).toHaveAttribute('aria-pressed', 'false')
  await housing.click()
  await expect(housing).toHaveAttribute('aria-pressed', 'true')

  await page.getByRole('button', { name: /¿Quién vivirá\?/ }).click()
  const man = page.getByRole('checkbox', { name: 'Para quién: solo un hombre' })
  const woman = page.getByRole('checkbox', { name: 'Para quién: solo una mujer' })
  await man.click()
  await woman.click()
  await expect(man).toHaveAttribute('aria-checked', 'true')
  await expect(woman).toHaveAttribute('aria-checked', 'true')
  await page.getByRole('button', { name: 'Listo' }).click()
  await expect(page.getByRole('button', { name: /Para quién: solo un hombre, solo una mujer/ })).toBeVisible()
})
