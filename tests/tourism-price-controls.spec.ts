import { expect, test } from '@playwright/test'

const priceParams = (pageUrl: string) => new URLSearchParams(new URL(pageUrl).hash.split('?', 2)[1] ?? '')

test('legacy saved long-term price filters are safely normalized to the inclusive EUR 1000 ceiling', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const controls = await page.evaluate(async () => {
    const module = await import('/src/lib/price-filter-controls.ts')
    const search = await import('/src/lib/search.ts')
    return {
      ceiling: module.LONG_STAY_PRICE_CEILING,
      defaultValues: module.priceControlValues({ minPrice: 0, maxPrice: 1000 }, 'long'),
      legacyValues: module.priceControlValues({ minPrice: 900, maxPrice: 1200 }, 'long'),
      saved: search.normalizeFilters({ minPrice: 900, maxPrice: 1200 }),
    }
  })
  expect(controls.ceiling).toBe(1000)
  expect(controls.defaultValues).toMatchObject({ minimum: 0, maximum: 1000, ceiling: 1000, unrestricted: true })
  expect(controls.legacyValues).toMatchObject({ minimum: 900, maximum: 1000, ceiling: 1000 })
  expect(controls.saved).toMatchObject({ minPrice: 900, maxPrice: 1000 })
})

test('legacy Tourism search URL redirects to long stay without a hidden maximum or tourism controls', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday&precioMax=5000')
  await expect(page).toHaveURL(/alquiler=long/)
  await expect(page.getByRole('radio', { name: /Turismo/ })).toHaveCount(0)
  expect(priceParams(page.url()).get('precioMax')).toBeNull()
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  const drawer = page.locator('.filter-drawer')
  await expect(drawer.getByLabel('Precio mínimo')).toHaveValue('0')
  await expect(drawer.getByLabel('Precio máximo')).toHaveValue('1000')
  await expect(drawer.getByLabel('Precio máximo')).toHaveAttribute('max', '1000')
})

test('user-selected residential price limit remains meaningful and never exceeds the policy ceiling', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&precioMin=900&precioMax=999')
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  const drawer = page.locator('.filter-drawer')
  await expect(drawer.getByLabel('Precio mínimo')).toHaveValue('900')
  await expect(drawer.getByLabel('Precio máximo')).toHaveValue('999')
  await expect(drawer.getByLabel('Precio máximo')).toHaveAttribute('max', '1000')
  await expect(page.getByRole('radio', { name: /Turismo/ })).toHaveCount(0)
})

test('unsupported holiday-mode search state normalizes without crossing monthly price units', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday&precioMin=700&precioMax=9999')
  await expect(page).toHaveURL(/alquiler=long/)
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  const drawer = page.locator('.filter-drawer')
  await expect(drawer.getByLabel('Precio mínimo')).toHaveValue('0')
  await expect(drawer.getByLabel('Precio máximo')).toHaveValue('1000')
})
