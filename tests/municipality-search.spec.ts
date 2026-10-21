import { expect, test } from '@playwright/test'
import catalog from '../src/data/spain-municipalities.json' with { type: 'json' }

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
})

test('suggestions appear from the first letter and narrow with each letter', async ({ page }) => {
  await page.goto('/#/?panel=ubicacion')
  const input = page.getByRole('searchbox')
  await input.fill('a')
  for (const id of ['38001', '38004', '38005', '38006']) await expect(page.getByTestId(`municipality-option-${id}`)).toBeAttached()
  const initialCount = await page.locator('[data-testid^="municipality-option-"]').count()
  await input.fill('ar')
  await expect(page.getByTestId('municipality-option-38004')).toBeAttached()
  await expect(page.getByTestId('municipality-option-38001')).toHaveCount(0)
  expect(await page.locator('[data-testid^="municipality-option-"]').count()).toBeLessThan(initialCount)
  await input.fill('Arafo')
  await expect(page.getByTestId('municipality-option-38004')).toContainText('Santa Cruz de Tenerife')
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: 'output/municipality-search/arafo-mobile.png' })
  await input.press('ArrowDown')
  await input.press('Enter')
  await expect(page).toHaveURL(/municipio=38004/)
  await expect(page.locator('.m2-results__header')).toContainText('Arafo')
  await page.reload()
  await expect(page.locator('.m2-results__header')).toContainText('Arafo')
})

test('Adeje search excludes other municipalities and remembers the last selection', async ({ page }) => {
  await page.goto('/#/?panel=ubicacion')
  await page.getByRole('searchbox').fill('Adeje')
  await page.getByTestId('municipality-option-38001').click()
  await expect(page).toHaveURL(/municipio=38001/)
  await expect(page.locator('.m2-results__header')).toContainText('Adeje')
  const cards = page.locator('.m2-result-card')
  await expect(cards.first()).toBeVisible()
  for (const text of await cards.allTextContents()) expect(text).not.toContain('Arona')
  await page.goto('/#/?panel=ubicacion')
  await page.getByRole('searchbox').focus()
  await expect(page.locator('.m2-community-option').first()).toContainText('Adeje')
  await page.getByRole('searchbox').fill('a')
  await expect(page.locator('.m2-community-option').first()).toContainText('Adeje')
  await expect(page.getByTestId('municipality-option-38004')).toBeAttached()
})

test('all 31 Tenerife municipalities are searchable and official article forms resolve', async ({ page }) => {
  await page.goto('/#/?panel=ubicacion')
  const ids = ['Adeje', 'Arafo', 'Arico', 'Arona', 'Buenavista del Norte', 'Candelaria', 'El Rosario',
    'El Sauzal', 'El Tanque', 'Fasnia', 'Garachico', 'Granadilla de Abona', 'Guía de Isora', 'Güímar',
    'Icod de los Vinos', 'La Guancha', 'La Matanza de Acentejo', 'La Orotava', 'La Victoria de Acentejo',
    'Los Realejos', 'Los Silos', 'Puerto de la Cruz', 'San Cristóbal de La Laguna', 'San Juan de la Rambla',
    'San Miguel de Abona', 'Santa Cruz de Tenerife', 'Santa Úrsula', 'Santiago del Teide', 'Tacoronte',
    'Tegueste', 'Vilaflor de Chasna']
  expect(ids).toHaveLength(31)
  expect(Object.keys(catalog.municipalities)).toHaveLength(8132)
  for (const name of ids) {
    await page.getByRole('searchbox').fill(name)
    await expect(page.locator('[data-testid^="municipality-option-"] strong').filter({ hasText: name })).toHaveCount(1)
  }
  await page.getByRole('searchbox').fill('guimar')
  await expect(page.getByTestId('municipality-option-38020')).toContainText('Güímar')
  await page.getByRole('searchbox').fill('zzzzzzzz')
  await expect(page.locator('.m2-community-empty')).toContainText('No se encontró ninguna ubicación')
  await page.getByRole('searchbox').fill('Albarracin')
  await expect(page.getByTestId('municipality-option-44009')).toContainText('Albarracín')
  await page.getByRole('searchbox').fill('La Laguna')
  await expect(page.getByTestId('municipality-option-38023')).toBeVisible()
})

test('desktop location picker keeps municipality identity separate from its province', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/#/buscar?q=Espa%C3%B1a')
  await page.locator('.location-selector-trigger:visible').click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('searchbox').fill('Arafo')
  await dialog.getByTestId('municipality-option-38004').click()
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page).toHaveURL(/municipio=38004/)
  await expect(page.locator('#results-title')).toContainText('Arafo')
})

test('saved city searches retain their code when city and province have the same name', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.goto('/#/buscar?q=Santa%20Cruz%20de%20Tenerife&provincia=38&municipio=38038')
  await page.getByRole('complementary', { name: 'Filtros de búsqueda' }).getByRole('button', { name: 'Guardar búsqueda', exact: true }).click()
  await expect.poll(() => page.evaluate(() => {
    const value = JSON.parse(localStorage.getItem('112233:saved-searches:v3') ?? '{}')
    return JSON.stringify(value).includes('38038')
  })).toBe(true)
  await page.goto('/#/busquedas-guardadas')
  const result = page.getByRole('link', { name: 'Ver resultados', exact: true }).first()
  await expect(result).toHaveAttribute('href', /municipio=38038/)
  await result.click()
  await expect(page).toHaveURL(/municipio=38038/)
})
