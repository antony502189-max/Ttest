import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
})

for (const width of [390, 1440]) {
  test(`only residential rentals and monthly price controls at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/')
    await expect(page.getByRole('button', { name: /Turismo/i })).toHaveCount(0)
    await expect(page.getByRole('radio', { name: /Turismo/i })).toHaveCount(0)
    await page.goto('/#/buscar?q=Tenerife&alquiler=holiday&precioMax=5000')
    await expect(page).toHaveURL(/alquiler=long/)
    await expect(page.getByRole('radio', { name: /Turismo/i })).toHaveCount(0)
    if (width < 768) {
      const results = page.getByTestId('mobile-results')
      await results.getByRole('button', { name: 'Filtros', exact: true }).click()
      const input = results.getByLabel('Precio Máx')
      await expect(input).toHaveValue('1000')
      await expect(input).toHaveAttribute('max', '1000')
      await expect(results.getByRole('button', { name: 'Turismo', exact: true })).toHaveCount(0)
    } else {
      await expect(page.locator('.filter-sidebar').getByLabel('Precio máximo', { exact: true })).toHaveAttribute('max', '1000')
    }
  })
}

test('legacy filters and draft admission retain exact boundary semantics', async ({ page }) => {
  await page.goto('/#/')
  const result = await page.evaluate(async () => {
    const policy = await import('/src/lib/rental-policy.ts')
    const search = await import('/src/lib/search.ts')
    const base = { rentalMode: 'long', monthlyPrice: 1000, billsIncluded: true, billsNote: '' }
    return {
      limit: policy.MAX_MONTHLY_RENT_EUR,
      atLimit: policy.eligibleDraftPrice(base),
      aboveLimit: policy.eligibleDraftPrice({ ...base, monthlyPrice: 1001 }),
      holiday: policy.eligibleDraftPrice({ ...base, rentalMode: 'holiday' }),
      fees: policy.eligibleDraftPrice({ ...base, monthlyPrice: 950, billsIncluded: false, billsNote: '51' }),
      normalized: search.normalizeFilters({ minPrice: 1200, maxPrice: 5000 }),
      translations: ['es', 'en', 'ru'].map(policy.rentalPriceError),
    }
  })
  expect(result).toMatchObject({ limit: 1000, atLimit: true, aboveLimit: false, holiday: false, fees: false,
    normalized: { minPrice: 1000, maxPrice: 1000 } })
  expect(new Set(result.translations).size).toBe(3)
})

test('restored out-of-policy draft remains editable and is never silently clamped', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:listing-draft:v2', JSON.stringify({ monthlyPrice: 1001, rentalMode: 'long' }))
  })
  await page.goto('/#/publicar')
  await expect(page.getByText('Alquiler vacacional', { exact: true })).toHaveCount(0)
  // Desktop publish uses a long form, not the mobile multi-step wizard.
  const price = page.locator('#publish-price')
  await expect(price).toBeVisible()
  await expect(price).toHaveValue('1001')
  await expect(price).toHaveAttribute('max', '1000')
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(price).toHaveAttribute('aria-invalid', 'true')
  await price.fill('1000')
  await expect(price).toHaveValue('1000')
  await expect(page.getByText('Alquiler vacacional', { exact: true })).toHaveCount(0)
})
