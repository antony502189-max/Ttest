import { expect, test, type Page } from '@playwright/test'

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
}

async function typeExactAddress(page: Page, streetValue = 'Calle Londres 5', postcodeValue = '38660') {
  const street = page.getByLabel('Calle')
  await street.click()
  await page.keyboard.type(streetValue)
  const postcode = page.getByLabel('Código postal')
  await postcode.click()
  await page.keyboard.type(postcodeValue)
}

function geocoderResult({
  route,
  number = '',
  postcode,
  area = 'Costa Adeje',
  municipality = 'Adeje',
  coordinates,
  types = number ? ['street_address'] : ['route'],
}: {
  route: string
  number?: string
  postcode: string
  area?: string
  municipality?: string
  coordinates: { lat: number; lng: number }
  types?: string[]
}) {
  return ({
    formatted_address: `${route}${number ? ` ${number}` : ''}, ${postcode} ${area}, Santa Cruz de Tenerife, Spain`,
    types,
    address_components: [
      { long_name: route, short_name: route, types: ['route'] },
      ...(number ? [{ long_name: number, short_name: number, types: ['street_number'] }] : []),
      { long_name: postcode, short_name: postcode, types: ['postal_code'] },
      { long_name: area, short_name: area, types: ['sublocality_level_1'] },
      { long_name: municipality, short_name: municipality, types: ['administrative_area_level_3'] },
    ],
    geometry: {
      location: { lat: () => coordinates.lat, lng: () => coordinates.lng },
      location_type: number ? 'ROOFTOP' : 'GEOMETRIC_CENTER',
      viewport: {},
    },
  } as unknown as google.maps.GeocoderResult)
}

test('typing street, building number and postcode moves the owner marker to the exact building at street zoom', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Costa Adeje')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  const exact = { lat: 28.09123, lng: -16.73561 }
  await page.evaluate(({ coordinates }) => {
    window.__112233TestAddressGeocode = async () => [({
      formatted_address: 'Calle Londres 5, 38660 Costa Adeje, Santa Cruz de Tenerife, Spain',
      types: ['street_address'],
      address_components: [
        { long_name: 'Calle Londres', short_name: 'C. Londres', types: ['route'] },
        { long_name: '5', short_name: '5', types: ['street_number'] },
        { long_name: '38660', short_name: '38660', types: ['postal_code'] },
        { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['sublocality_level_1'] },
        { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
      ],
      geometry: {
        location: { lat: () => coordinates.lat, lng: () => coordinates.lng },
        location_type: 'ROOFTOP',
        viewport: {},
      },
    } as unknown as google.maps.GeocoderResult)]
  }, { coordinates: exact })

  await typeExactAddress(page)

  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })).toEqual(exact)
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect(page.locator('.approximate-location-selector output')).toContainText('28.0912, -16.7356')
})

test('customer address Calle José Espronceda 20 in Armeñime sends the complete hierarchy and recenters to the matched rooftop', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Municipio').selectOption('Adeje')
  await page.getByLabel('Zona o barrio').fill('Armeñime')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  const mockRooftop = { lat: 28.12746, lng: -16.73872 }
  const result = geocoderResult({ route: 'Calle José Espronceda', number: '20', postcode: '38678', area: 'Armeñime', coordinates: mockRooftop })
  await page.evaluate(({ geocodeResult }) => {
    const holder = window as Window & { __lastExactAddressQuery?: string }
    window.__112233TestAddressGeocode = async (query) => {
      holder.__lastExactAddressQuery = query
      return [geocodeResult]
    }
  }, { geocodeResult: result })

  await typeExactAddress(page, 'Calle José Espronceda 20', '38678')

  await expect.poll(() => page.evaluate(() => (window as Window & { __lastExactAddressQuery?: string }).__lastExactAddressQuery ?? '')).toBe(
    'Calle José Espronceda 20, 38678, Armeñime, Adeje, Tenerife, Spain',
  )
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })).toEqual(mockRooftop)
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect(page.getByLabel('Calle')).toHaveValue('Calle José Espronceda 20')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
})

test('nearby Google correction with a different house number is rejected instead of moving to the wrong building', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Costa Adeje')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  const before = await page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : null
  })
  const wrongBuilding = { lat: 28.09199, lng: -16.73642 }
  await page.evaluate(({ coordinates }) => {
    window.__112233TestAddressGeocode = async () => [({
      formatted_address: 'Calle Londres 7, 38660 Costa Adeje, Santa Cruz de Tenerife, Spain',
      types: ['street_address'],
      address_components: [
        { long_name: 'Calle Londres', short_name: 'C. Londres', types: ['route'] },
        { long_name: '7', short_name: '7', types: ['street_number'] },
        { long_name: '38660', short_name: '38660', types: ['postal_code'] },
        { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['sublocality_level_1'] },
        { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
      ],
      geometry: { location: { lat: () => coordinates.lat, lng: () => coordinates.lng }, location_type: 'ROOFTOP', viewport: {} },
    } as unknown as google.maps.GeocoderResult)]
  }, { coordinates: wrongBuilding })

  await typeExactAddress(page)
  await expect(page.locator('.map-inline-error')).toContainText('No se pudo ubicar esta dirección con precisión')
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : null
  })).toEqual(before)
})

test('same house number and postcode on a different Google route is rejected', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Armeñime')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  const before = await page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : null
  })
  const wrongRoute = geocoderResult({ route: 'Calle Poetas Españoles', number: '20', postcode: '38678', area: 'Armeñime', coordinates: { lat: 28.1282, lng: -16.7378 } })
  await page.evaluate((result) => { window.__112233TestAddressGeocode = async () => [result] }, wrongRoute)

  await typeExactAddress(page, 'Calle José Espronceda 20', '38678')
  await expect(page.locator('.map-inline-error')).toContainText('No se pudo ubicar esta dirección con precisión')
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : null
  })).toEqual(before)
})

test('house number is taken from the final numeric token rather than a number inside the street name', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Costa Adeje')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  const exact = { lat: 28.09211, lng: -16.73112 }
  const result = geocoderResult({ route: 'Avenida 25 de Abril', number: '20', postcode: '38660', coordinates: exact })
  await page.evaluate((geocodeResult) => { window.__112233TestAddressGeocode = async () => [geocodeResult] }, result)
  await typeExactAddress(page, 'Avenida 25 de Abril 20', '38660')

  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })).toEqual(exact)
})

test('street plus postcode without a building number recenters at street zoom instead of pretending rooftop precision', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Armeñime')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  const streetPoint = { lat: 28.1273, lng: -16.7391 }
  const result = geocoderResult({ route: 'Calle José Espronceda', postcode: '38678', area: 'Armeñime', coordinates: streetPoint })
  await page.evaluate((geocodeResult) => { window.__112233TestAddressGeocode = async () => [geocodeResult] }, result)
  await typeExactAddress(page, 'Calle José Espronceda', '38678')

  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(16)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })).toEqual(streetPoint)
})

test('manual marker controls cancel an in-flight exact-address lookup', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Costa Adeje')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  await page.evaluate(() => {
    const holder = window as Window & { __addressGeocodeStarted?: boolean }
    window.__112233TestAddressGeocode = () => new Promise((resolve) => {
      holder.__addressGeocodeStarted = true
      window.setTimeout(() => resolve([({
        formatted_address: 'Calle Londres 5, 38660 Costa Adeje, Santa Cruz de Tenerife, Spain',
        types: ['street_address'],
        address_components: [
          { long_name: 'Calle Londres', short_name: 'C. Londres', types: ['route'] },
          { long_name: '5', short_name: '5', types: ['street_number'] },
          { long_name: '38660', short_name: '38660', types: ['postal_code'] },
          { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['sublocality_level_1'] },
          { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
        ],
        geometry: { location: { lat: () => 28.09123, lng: () => -16.73561 }, location_type: 'ROOFTOP', viewport: {} },
      } as unknown as google.maps.GeocoderResult)]), 300)
    })
  })

  await typeExactAddress(page)
  await expect.poll(() => page.evaluate(() => Boolean((window as Window & { __addressGeocodeStarted?: boolean }).__addressGeocodeStarted))).toBe(true)

  await page.locator('.approximate-location-selector__grid button').first().dispatchEvent('click')
  const manualCenter = await page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })
  await page.waitForTimeout(450)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })).toEqual(manualCenter)
})

test('publication map is substantially larger on a customer-size mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPublishLocation(page)

  const shell = page.locator('.approximate-location-map-shell')
  const box = await shell.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.height).toBeGreaterThanOrEqual(350)
  expect(box!.width).toBeGreaterThanOrEqual(330)
})
