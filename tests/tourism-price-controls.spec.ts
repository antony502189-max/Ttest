import { expect, test, type Locator, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const priceParams = (pageUrl: string) => new URLSearchParams(new URL(pageUrl).hash.split('?', 2)[1] ?? '')

async function openFilters(page: Page) {
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  const drawer = page.locator('.filter-drawer')
  await expect(drawer).toBeVisible()
  return drawer
}

async function setSliderValue(slider: Locator, value: number, step: number) {
  await slider.focus()
  await slider.press('Home')
  for (let current = 0; current < value; current += step) await slider.press('ArrowRight')
}

test('both desktop filter panels share valid Tourism control values without changing the unrestricted sentinel', async ({ page }) => {
  const panelSources = [
    '../src/components/marketplace.tsx',
    '../src/components/localized-search-filters.tsx',
  ].map((path) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8'))
  panelSources.forEach((source) => expect(source).toContain('priceControlValues'))

  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  const controls = await page.evaluate(async () => {
    const module = await import('/src/lib/price-filter-controls.ts')
    return {
      unrestricted: module.priceControlValues({ minPrice: 0, maxPrice: 1200 }, 'holiday'),
      staleLongStay: module.priceControlValues({ minPrice: 900, maxPrice: 1200 }, 'holiday'),
      normalized: module.filtersForRentalMode({ minPrice: 900, maxPrice: 1200 }, 'holiday'),
    }
  })

  expect(controls.unrestricted).toMatchObject({ minimum: 0, maximum: 350, ceiling: 350, unrestricted: true })
  expect(controls.staleLongStay).toMatchObject({ minimum: 350, maximum: 350, ceiling: 350, unrestricted: false })
  expect(controls.normalized).toMatchObject({ minPrice: 0, maxPrice: 1200 })
})

test('unrestricted Tourism renders valid price controls without serializing a hidden maximum', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await page.getByRole('radio', { name: /Turismo/ }).click()
  await expect(page).toHaveURL(/alquiler=holiday/)
  expect(priceParams(page.url()).get('precioMax')).toBeNull()

  const drawer = await openFilters(page)
  const minimum = drawer.getByLabel('Precio mínimo')
  const maximum = drawer.getByLabel('Precio máximo')
  await expect(minimum).toHaveValue('0')
  await expect(maximum).toHaveValue('350')
  await expect(minimum).toHaveAttribute('max', '350')
  await expect(maximum).toHaveAttribute('max', '350')
  await expect(drawer.locator('.range-values')).toContainText('0 €')
  await expect(drawer.locator('.range-values')).toContainText('350 €+')
})

test('Long Stay high price does not become an invalid or hidden Tourism restriction', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const longFilters = await openFilters(page)
  await setSliderValue(longFilters.getByRole('slider').first(), 900, 25)
  await longFilters.getByRole('button', { name: /Mostrar \d+ habitaciones/ }).click()
  expect(priceParams(page.url()).get('precioMin')).toBe('900')

  await page.getByRole('radio', { name: /Turismo/ }).click()
  await expect(page).toHaveURL(/alquiler=holiday/)
  const params = priceParams(page.url())
  expect(params.get('precioMin')).toBeNull()
  expect(params.get('precioMax')).toBeNull()

  const tourismFilters = await openFilters(page)
  const minimum = tourismFilters.getByLabel('Precio mínimo')
  const maximum = tourismFilters.getByLabel('Precio máximo')
  await expect(minimum).toHaveValue('0')
  await expect(maximum).toHaveValue('350')
  expect(Number(await minimum.inputValue())).toBeLessThanOrEqual(Number(await maximum.inputValue()))
})

test('explicit Tourism price changes serialize, and clearing restores the unrestricted sentinel', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  const drawer = await openFilters(page)
  const maximumSlider = drawer.getByRole('slider', { name: 'Maximum' })
  await maximumSlider.focus()
  for (let value = 350; value > 200; value -= 5) await maximumSlider.press('ArrowLeft')
  await drawer.getByRole('button', { name: /Mostrar \d+ habitaciones/ }).click()
  expect(priceParams(page.url()).get('precioMax')).toBe('200')

  const filteredDrawer = await openFilters(page)
  await filteredDrawer.getByRole('button', { name: 'Limpiar' }).click()
  await filteredDrawer.getByRole('button', { name: /Mostrar \d+ habitaciones/ }).click()
  const params = priceParams(page.url())
  expect(params.get('precioMin')).toBeNull()
  expect(params.get('precioMax')).toBeNull()

  const restoredDrawer = await openFilters(page)
  await expect(restoredDrawer.getByLabel('Precio mínimo')).toHaveValue('0')
  await expect(restoredDrawer.getByLabel('Precio máximo')).toHaveValue('350')
})
