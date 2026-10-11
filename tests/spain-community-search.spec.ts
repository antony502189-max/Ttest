import { expect, test } from '@playwright/test'

// The community selector is part of the existing location page: it does not
// navigate to a second suggestions screen, and counts come from the same
// geographic filter that is applied to the results.
test.describe('mobile Spain community search', () => {
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
    await expect(page.getByTestId('community-suggestions')).toHaveCount(0)
    await page.getByTestId('community-search-input').focus()
    await expect(page.getByTestId('community-suggestions')).toBeVisible()
    await expect(page.locator('.m2-community-option')).toHaveCount(17)
    await expect(page.getByTestId('location-screen')).toBeVisible()
  })

  test('typing Barcelona offers Cataluña inline then opens region-specific scrolling results', async ({ page }) => {
    await page.locator('.m2-select-row').click()
    const input = page.getByTestId('community-search-input')
    await input.fill('barce')
    const suggestions = page.getByTestId('community-suggestions')
    await expect(suggestions).toBeVisible()
    await expect(page.locator('.m2-community-option')).toHaveCount(1)
    await expect(page.getByTestId('community-option-09')).toContainText(/Catalu|Каталон/i)
    await expect(page.getByTestId('community-option-09')).toContainText(/anuncios|listings|объявлений/i)
    await page.getByTestId('community-option-09').click()
    await expect(page).toHaveURL(/comunidad=09/)
    await expect(page).not.toHaveURL(/vista=mapa/)
    await expect(page.getByTestId('mobile-results')).toBeVisible()
    const header = page.locator('.m2-results__header')
    await expect(header).toContainText(/Catalu|Каталон/i)
    await expect(header).not.toContainText('Tenerife')
  })

  test('Madrid and Canary Islands choose distinct spatial searches', async ({ page }) => {
    await page.locator('.m2-select-row').click()
    await page.getByTestId('community-search-input').fill('madrid')
    await expect(page.getByTestId('community-option-13')).toBeVisible()
    await page.getByTestId('community-option-13').click()
    await expect(page).toHaveURL(/comunidad=13/)
    await expect(page.locator('.m2-results__header')).toContainText(/Madrid|Мадрид/i)
    await page.goto('/#/?panel=ubicacion')
    await page.getByTestId('community-search-input').fill('Tenerife')
    await expect(page.getByTestId('community-option-05')).toBeVisible()
    await page.getByTestId('community-option-05').click()
    await expect(page).toHaveURL(/comunidad=05/)
    await expect(page.locator('.m2-results__header')).toContainText(/Canarias|Canary|Канар/i)
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
  expect(result.barcelona).toEqual(['09'])
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
