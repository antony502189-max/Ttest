import { expect, test } from '@playwright/test'

// The province selector is part of the existing location page: it does not
// navigate to a second suggestions screen, and counts come from the same
// geographic filter that is applied to the results.
test.describe('mobile Spain province search', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto('/#/')
  })

  test('home location starts unselected and location page has no Tenerife banner', async ({ page }) => {
    const pick = page.locator('.m2-select-row')
    await expect(pick).toContainText(/ubicación|location|локацию/i)
    await expect(pick).not.toContainText('Tenerife')
    await pick.click()
    await expect(page.getByTestId('location-screen')).toBeVisible()
    await expect(page.locator('.m2-location-region')).toHaveCount(0)
    await expect(page.getByTestId('draw-zone')).toBeVisible()
    await expect(page.getByTestId('search-map')).toBeVisible()
    await expect(page.getByTestId('search-nearby')).toBeVisible()
    await page.getByRole('searchbox').focus()
    await expect(page.getByTestId('province-suggestions')).toBeVisible()
    await expect(page.locator('.m2-community-option')).toHaveCount(52)
    await expect(page.getByTestId('location-screen')).toBeVisible()
  })

  test('typing Barcelona offers its province and opens provincial results', async ({ page }) => {
    await page.locator('.m2-select-row').click()
    const input = page.getByRole('searchbox')
    await input.fill('barce')
    const suggestions = page.getByTestId('province-suggestions')
    await expect(suggestions).toBeVisible()
    // Search offers the province itself, without selecting a municipality.
    await expect(page.locator('.m2-community-option').first()).toHaveAttribute('data-testid', 'province-option-08')
    await expect(page.getByTestId('province-option-08')).toContainText(/Barcelona/i)
    await expect(page.getByTestId('province-option-08')).toContainText(/anuncios|listings|объявлений/i)
    await page.getByTestId('province-option-08').click()
    await expect(page).toHaveURL(/provincia=08/)
    await expect(page).not.toHaveURL(/vista=mapa/)
    await expect(page.getByTestId('mobile-results')).toBeVisible()
    const header = page.locator('.m2-results__header')
    await expect(header).toContainText(/Barcelona/i)
    await expect(header).not.toContainText('Tenerife')
  })

  test('Madrid and Canary Islands choose distinct spatial searches', async ({ page }) => {
    await page.locator('.m2-select-row').click()
    await page.getByRole('searchbox').fill('madrid')
    await expect(page.getByTestId('province-option-28')).toBeVisible()
    await page.getByTestId('province-option-28').click()
    await expect(page).toHaveURL(/provincia=28/)
    await expect(page.locator('.m2-results__header')).toContainText(/Madrid|Мадрид/i)
    await page.goto('/#/?panel=ubicacion')
    await page.getByRole('searchbox').fill('Tenerife')
    await expect(page.getByTestId('province-option-38')).toBeVisible()
    await page.getByTestId('province-option-38').click()
    await expect(page).toHaveURL(/provincia=38/)
    await expect(page.locator('.m2-results__header')).toContainText(/Santa Cruz de Tenerife/i)
  })
})

test('Spanish autonomous communities have correct point-in-boundary assignments and 17 regions', async ({ page }) => {
  await page.goto('/#/')
  const result = await page.evaluate(async () => {
    const { SPANISH_COMMUNITIES, communityAtCoordinates, communitySuggestions, communityMapCamera } =
      await import('/src/lib/spain-communities.ts')
    const places = [
      [41.3874, 2.1686, '09'], // Barcelona
      [40.4168, -3.7038, '13'], // Madrid
      [37.3891, -5.9845, '01'], // Seville
      [39.4699, -0.3763, '10'], // Valencia
      [39.5696, 2.6502, '04'], // Palma
      [28.4636, -16.2518, '05'], // Santa Cruz de Tenerife
      [28.1235, -15.4363, '05'], // Las Palmas
      [42.8185, -1.644, '15'], // Pamplona
      [41.6488, -0.8891, '02'], // Zaragoza
    ] as const
    return {
      length: SPANISH_COMMUNITIES.length,
      matches: places.map(([lat, lng, expected]) => ({
        expected, actual: communityAtCoordinates(lat, lng)?.id,
      })),
      barcelona: communitySuggestions('barce').map((region) => region.id),
      tenerife: communitySuggestions('tenerife').map((region) => region.id),
      madrid: communityMapCamera('13', 390, 844),
      catalogNames: SPANISH_COMMUNITIES.map((item) => item.ru),
    }
  })
  expect(result.length).toBe(17)
  expect(result.matches.every((item) => item.actual === item.expected)).toBe(true)
  expect(result.barcelona[0]).toBe('09')
  expect(result.tenerife).toEqual(['05'])
  // Official INE municipality lookup, including towns absent from listings.
  const municipalitySuggestions = await page.evaluate(async () => {
    const { communitySuggestions } = await import('/src/lib/spain-communities.ts')
    return ['Ajalvir', 'Abáigar', 'Teguise', 'Pobla de Segur'].map((town) =>
      communitySuggestions(town).map((region) => region.id))
  })
  expect(municipalitySuggestions).toEqual([['13'], ['15'], ['05'], ['09']])
  expect(result.madrid?.zoom).toBeGreaterThan(5)
  expect(new Set(result.catalogNames).size).toBe(17)
})
