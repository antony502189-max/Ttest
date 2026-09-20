import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

const smartSource = readFileSync('src/components/publish-smart-address-autocomplete.tsx', 'utf8')
const enhancerCss = readFileSync('src/publish-location-enhancer.css', 'utf8')

const CUSTOMER_ADDRESS_REFERENCE = { lat: 28.12909, lng: -16.75657 }

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/publicar')
  await expect(page.locator('#publish-street[data-address-autocomplete="native"]')).toBeVisible()
}

async function openFirstListingEdit(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/mis-anuncios')
  const edit = page.locator('.manage-card').first().getByRole('link', { name: /Editar/i })
  const href = await edit.getAttribute('href')
  expect(href).toBeTruthy()
  await page.goto(href!.startsWith('#') ? `/${href}` : href!)
  await expect(page.locator('#publish-street[data-address-autocomplete="native"]')).toBeVisible()
}

test('publish address autocomplete uses the native field and resilient Google prediction fallbacks', () => {
  expect(smartSource).toContain('AutocompleteSuggestion.fetchAutocompleteSuggestions')
  expect(smartSource).toContain('new places.AutocompleteSessionToken()')
  expect(smartSource).toContain('new places.AutocompleteService()')
  expect(smartSource).toContain("google.maps.importLibrary('geocoding')")
  expect(smartSource).toContain("input.dataset.addressAutocomplete = 'native'")
  expect(smartSource).toContain("document.querySelectorAll('.publish-place-autocomplete').forEach((element) => element.remove())")
  expect(smartSource).toContain("includedRegionCodes: ['es']")
  expect(smartSource).toContain('locationRestriction: TENERIFE_BOUNDS')
  expect(smartSource).not.toContain('localStorage.setItem')
  expect(smartSource).not.toContain('sessionStorage.setItem')
})

test('native prediction dropdown is visible, touch-friendly and does not depend on Google widget shadow DOM', () => {
  expect(enhancerCss).toContain('#publish-street[data-address-autocomplete="native"]')
  expect(enhancerCss).toContain('.publish-address-predictions')
  expect(enhancerCss).toContain('.publish-address-prediction')
  expect(enhancerCss).toContain('.publish-address-predictions__attribution')
  expect(enhancerCss).toContain('max-height: min(18rem, 42dvh)')
})

test('Calle José Espronceda 20 shows a suggestion inline and selecting it fixes municipality, postcode and exact map point', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPublishLocation(page)

  await page.evaluate((coordinates) => {
    window.__112233TestAddressPredictions = async (query) => query.toLocaleLowerCase().includes('espronceda') ? [{
      label: 'Calle José Espronceda 20, 38678 Armeñime, Adeje, Santa Cruz de Tenerife, Spain',
      detail: {
        formattedAddress: 'Calle José Espronceda 20, 38678 Armeñime, Adeje, Santa Cruz de Tenerife, Spain',
        addressComponents: [
          { longText: 'Calle José Espronceda', types: ['route'] },
          { longText: '20', types: ['street_number'] },
          { longText: '38678', types: ['postal_code'] },
          { longText: 'Armeñime', types: ['sublocality_level_1'] },
          { longText: 'Adeje', types: ['administrative_area_level_3'] },
          { longText: 'Santa Cruz de Tenerife', types: ['administrative_area_level_2'] },
          { longText: 'Spain', types: ['country'] },
        ],
        coordinates,
      },
    }] : []
  }, CUSTOMER_ADDRESS_REFERENCE)

  const street = page.locator('#publish-street')
  await street.fill('Calle José Espronceda 20')

  const prediction = page.locator('.publish-address-prediction').first()
  await expect(prediction).toBeVisible()
  await expect(prediction).toContainText('Calle José Espronceda 20')
  await expect(page.locator('.publish-place-autocomplete')).toHaveCount(0)

  await prediction.click()

  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
  await expect(page.locator('#publish-street')).toHaveValue('Calle José Espronceda 20')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : null
  })).toEqual(CUSTOMER_ADDRESS_REFERENCE)
})

test('keyboard can choose an address prediction without opening a fullscreen mobile widget', async ({ page }) => {
  await openPublishLocation(page)
  await page.evaluate((coordinates) => {
    window.__112233TestAddressPredictions = async () => [{
      label: 'Calle José Espronceda 20, 38678 Armeñime, Adeje',
      detail: {
        formattedAddress: 'Calle José Espronceda 20, 38678 Armeñime, Adeje',
        addressComponents: [
          { longText: 'Calle José Espronceda', types: ['route'] },
          { longText: '20', types: ['street_number'] },
          { longText: '38678', types: ['postal_code'] },
          { longText: 'Armeñime', types: ['sublocality_level_1'] },
          { longText: 'Adeje', types: ['administrative_area_level_3'] },
        ],
        coordinates,
      },
    }]
  }, CUSTOMER_ADDRESS_REFERENCE)

  const street = page.locator('#publish-street')
  await street.fill('Calle José')
  await expect(page.locator('.publish-address-prediction')).toHaveCount(1)
  await street.press('ArrowDown')
  await street.press('Enter')

  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await expect(page.locator('.publish-address-predictions')).toBeHidden()
})

test('customer video: leading list prefix does not reject a valid Avenida V Centenario building and postal town replaces stale area', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPublishLocation(page)
  await page.getByLabel('Municipio').selectOption('Adeje')
  await page.getByLabel('Zona o barrio').fill('Armeñime')
  await page.getByLabel('Código postal').fill('38678')

  const exact = { lat: 28.0679, lng: -16.7270 }
  await page.evaluate((coordinates) => {
    window.__112233TestAddressPredictions = async () => [{
      label: 'Av. V Centenario, 1, 38660 Playa de las Américas, Santa Cruz de Tenerife',
      detail: {
        formattedAddress: 'Av. V Centenario, 1, 38660 Playa de las Américas, Santa Cruz de Tenerife',
        addressComponents: [
          { longText: 'Avenida V Centenario', types: ['route'] },
          { longText: '1', types: ['street_number'] },
          { longText: '38660', types: ['postal_code'] },
          { longText: 'Playa de las Américas', types: ['postal_town'] },
          { longText: 'Adeje', types: ['administrative_area_level_3'] },
          { longText: 'Santa Cruz de Tenerife', types: ['administrative_area_level_2'] },
        ],
        coordinates,
      },
    }]
  }, exact)

  const street = page.locator('#publish-street')
  await street.fill('0 Playa de las Américas, Santa Cruz de Tenerife')
  const prediction = page.locator('.publish-address-prediction').first()
  await expect(prediction).toBeVisible()
  await prediction.click()

  await expect(street).toHaveValue('Avenida V Centenario 1')
  await expect(page.getByLabel('Código postal')).toHaveValue('38660')
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Playa de las Américas')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(4)), lng: Number(center.lng().toFixed(4)) } : null
  })).toEqual(exact)
})

test('rejected address suggestion never overwrites the visible street while structured fields stay unchanged', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Municipio').selectOption('Adeje')
  await page.getByLabel('Zona o barrio').fill('Armeñime')
  await page.getByLabel('Código postal').fill('38678')

  await page.evaluate(() => {
    window.__112233TestAddressPredictions = async () => [{
      label: 'Calle Londres 7, 38660 Costa Adeje, Adeje',
      detail: {
        formattedAddress: 'Calle Londres 7, 38660 Costa Adeje, Adeje',
        addressComponents: [
          { longText: 'Calle Londres', types: ['route'] },
          { longText: '7', types: ['street_number'] },
          { longText: '38660', types: ['postal_code'] },
          { longText: 'Costa Adeje', types: ['sublocality_level_1'] },
          { longText: 'Adeje', types: ['administrative_area_level_3'] },
        ],
        coordinates: { lat: 28.0919, lng: -16.7364 },
      },
    }]
  })

  const street = page.locator('#publish-street')
  await street.fill('Calle Londres 5')
  const prediction = page.locator('.publish-address-prediction').first()
  await expect(prediction).toBeVisible()
  await prediction.click()

  await expect(street).toHaveValue('Calle Londres 5')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
  await expect(page.locator('.publish-address-assist')).toHaveAttribute('data-location-bias-source', 'error')
})

test('customer video: edit autocomplete searches the current area first for an ambiguous street', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openFirstListingEdit(page)
  await page.getByLabel('Municipio').selectOption('Adeje')
  await page.getByLabel('Zona o barrio').fill('Playa de las Américas')

  await page.evaluate(() => {
    const holder = window as Window & { __customerVideoPredictionQueries?: string[] }
    holder.__customerVideoPredictionQueries = []
    window.__112233TestAddressPredictions = async (query) => {
      holder.__customerVideoPredictionQueries?.push(query)
      if (!query.toLocaleLowerCase().includes('playa de las américas')) return []
      return [{
        label: 'Calle Poetas Españoles 3, Playa de las Américas, Adeje',
        detail: {
          formattedAddress: 'Calle Poetas Españoles 3, Playa de las Américas, Adeje',
          addressComponents: [
            { longText: 'Calle Poetas Españoles', types: ['route'] },
            { longText: '3', types: ['street_number'] },
            { longText: '38660', types: ['postal_code'] },
            { longText: 'Playa de las Américas', types: ['postal_town'] },
            { longText: 'Adeje', types: ['administrative_area_level_3'] },
          ],
          coordinates: { lat: 28.0668, lng: -16.7281 },
        },
      }]
    }
  })

  const shell = page.locator('.approximate-location-map-shell')
  await expect(shell).toHaveAttribute('data-location-lat', /.+/)
  await expect(shell).toHaveAttribute('data-location-lng', /.+/)

  await page.locator('#publish-street').fill('Calle Poetas Españoles 3')
  await expect(page.locator('.publish-address-prediction').first()).toBeVisible()
  await expect.poll(() => page.evaluate(() => (window as Window & { __customerVideoPredictionQueries?: string[] }).__customerVideoPredictionQueries ?? [])).toContain(
    'Calle Poetas Españoles 3, Playa de las Américas, Adeje',
  )
})

