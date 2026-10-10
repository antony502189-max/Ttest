import { expect, test, type Page } from '@playwright/test'

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

test.describe('mobile history', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('fresh map starts between Spain and Tenerife before any listing is opened', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    const map = page.getByTestId('google-map')
    await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
    await expect(page.getByTestId('mobile-map-listing-preview')).toHaveCount(0)
    await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeGreaterThanOrEqual(5)
    await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeLessThanOrEqual(6)
    await expect(page).toHaveURL(/mapZoom=5\.25/)
    await expect(map).toHaveAttribute('data-map-center', '32.450000,-11.200000')
    // Simply opening the map never creates a remembered search area.
    expect(await page.evaluate(() => localStorage.getItem('112233:map-last-search-area:v2'))).toBeNull()
  })


  test('a new visit centers a 300 km search radius on the last explored point', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    const map = page.getByTestId('google-map')
    await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
    await map.dispatchEvent('pointerdown')
    await page.evaluate(() => {
      window.__googleMapsTestLastMap?.panTo({ lat: 28.12, lng: -16.72 })
      window.__googleMapsTestLastMap?.setZoom(11)
    })
    await expect(page).toHaveURL(/mapLat=28\.12000.*mapLng=-16\.72000.*mapZoom=11\.00/)
    await expect.poll(async () => page.evaluate(() => {
      const record = JSON.parse(localStorage.getItem('112233:map-last-search-area:v2') ?? '{}')
      return record.center
    })).toEqual({ lat: 28.12, lng: -16.72 })
    await page.goto('/#/')
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    await expect(map).toHaveAttribute('data-map-center', '28.120000,-16.720000')
    await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeGreaterThan(5)
    await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeLessThan(9)
    // The previous close-up (zoom 11) must not be restored.
    await expect(page).not.toHaveURL(/mapZoom=11\.00/)
  })

  test('after pan and zoom, reloading the same map URL recalls 300 km instead of the previous close-up', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    const map = page.getByTestId('google-map')
    await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
    await map.dispatchEvent('pointerdown')
    await page.evaluate(() => {
      window.__googleMapsTestLastMap?.panTo({ lat: 40.071, lng: -2.13 })
      window.__googleMapsTestLastMap?.setZoom(13)
    })
    await expect(page).toHaveURL(/mapAuto=1/)
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:map-last-search-area:v2') ?? '{}').center)).toEqual({ lat: 40.071, lng: -2.13 })
    await page.reload()
    await expect(map).toHaveAttribute('data-map-center', '40.071000,-2.130000')
    await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeGreaterThan(4)
    await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeLessThan(10)
  })

  test('the latest area replaces the previous one even when leaving without viewing a listing', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    const map = page.getByTestId('google-map')
    await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
    await map.dispatchEvent('pointerdown')
    await page.evaluate(() => {
      window.__googleMapsTestLastMap?.panTo({ lat: 27.99, lng: -15.59 })
      window.__googleMapsTestLastMap?.setZoom(11)
    })
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:map-last-search-area:v2') ?? '{}').center)).toEqual({ lat: 27.99, lng: -15.59 })
    await page.goto('/#/')
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    await expect(map).toHaveAttribute('data-map-center', '27.990000,-15.590000')
    await map.dispatchEvent('pointerdown')
    await page.evaluate(() => {
      window.__googleMapsTestLastMap?.panTo({ lat: 28.43, lng: -16.56 })
      window.__googleMapsTestLastMap?.setZoom(14)
    })
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:map-last-search-area:v2') ?? '{}').center)).toEqual({ lat: 28.43, lng: -16.56 })
    await page.goto('/#/favoritos')
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    await expect(map).toHaveAttribute('data-map-center', '28.430000,-16.560000')
    await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeLessThan(10)
    await expect(page.getByTestId('mobile-map-listing-preview')).toHaveCount(0)
  })

  test('opening a map marker saves its location even without moving the map first', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    const marker = page.locator('.m2-listing-marker').first()
    await expect(marker).toBeAttached({ timeout: 20_000 })
    await marker.evaluate((element) => element.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    await expect(page.getByTestId('mobile-map-listing-preview')).toBeVisible()
    const markerCenter = await page.getByTestId('google-map').getAttribute('data-map-center')
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:map-last-search-area:v2') ?? '{}').center)).not.toBeNull()
    await page.goto('/#/')
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('112233:map-last-search-area:v2') ?? '{}').center)
    await expect(page.getByTestId('google-map')).toHaveAttribute('data-map-center', `${saved.lat.toFixed(6)},${saved.lng.toFixed(6)}`)
    expect(markerCenter).not.toBeNull()
  })

  test('explicit map deep link wins over remembered viewport and a new city search wins over history', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:map-last-search-area:v2', JSON.stringify({
        center: { lat: 28.12, lng: -16.72 }, savedAt: Date.now(),
      }))
    })
    await page.goto('/#/buscar?q=Tenerife&vista=mapa&mapLat=28.46360&mapLng=-16.25180&mapZoom=13.00')
    const map = page.getByTestId('google-map')
    await expect(map).toHaveAttribute('data-map-center', '28.463600,-16.251800')
    await expect(map).toHaveAttribute('data-map-zoom', '13')
    await page.reload()
    await expect(map).toHaveAttribute('data-map-zoom', '13')
    await page.goto('/#/buscar?q=Adeje&vista=mapa')
    await expect(map).toHaveAttribute('data-map-center', '28.122700,-16.724400')
    await expect(map).toHaveAttribute('data-map-zoom', '12')
  })

  test('corrupt map history cannot displace the safe first-visit overview', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:map-last-search-area:v2', JSON.stringify({
        center: { lat: 999, lng: -16 }, savedAt: Date.now(),
      }))
    })
    await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    const map = page.getByTestId('google-map')
    await expect(map).toHaveAttribute('data-map-center', '32.450000,-11.200000')
    await expect(map).toHaveAttribute('data-map-zoom', '5.25')
  })

  test('Home → results → map → detail unwinds one visible screen at a time', async ({ page }) => {
    await finishOnboarding(page)
    await page.locator('.m2-mode-switch > button').first().click()
    await page.getByTestId('open-location').click()
    const results = page.getByTestId('mobile-results')
    await expect(results.locator('.m2-result-card').first()).toBeVisible()
    const resultsUrl = page.url()
    await results.getByRole('button', { name: 'Mapa' }).click()
    const map = page.getByTestId('google-map')
    await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
    const marker = page.locator('.m2-listing-marker').first()
    await expect(marker).toBeAttached()
    await marker.evaluate((element) => element.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    const preview = page.getByTestId('mobile-map-listing-preview')
    await expect(preview).toBeVisible()
    const listingId = await preview.getAttribute('data-listing-id')
    await expect(map).toHaveAttribute('data-map-center', /.+/)
    await expect(map).toHaveAttribute('data-map-zoom', /.+/)
    const cameraBeforeDetail = {
      center: await map.getAttribute('data-map-center'),
      zoom: await map.getAttribute('data-map-zoom'),
    }
    await preview.locator('.m2-map-listing-preview__open').click()
    await expect(page).toHaveURL(new RegExp(`#/habitacion/${encodeURIComponent(listingId!)}$`))
    await expect(page.locator('.listing-page h1')).toBeVisible()
    await page.getByRole('button', { name: 'Volver', exact: true }).click()
    await expect(map).toBeVisible()
    await expect(page).toHaveURL(/mapLat=.*mapLng=.*mapZoom=/)
    await expect.poll(() => map.getAttribute('data-map-center')).toBe(cameraBeforeDetail.center)
    await expect.poll(() => map.getAttribute('data-map-zoom')).toBe(cameraBeforeDetail.zoom)
    await expect(page.getByTestId('mobile-results')).toHaveCount(0)
    await page.goBack()
    await expect(page).toHaveURL(resultsUrl)
    await expect(results.locator('.m2-result-card').first()).toBeVisible()
    await page.goBack()
    await expect(page.getByTestId('open-location')).toBeVisible()
    await page.goForward()
    await expect(results.locator('.m2-result-card').first()).toBeVisible()
  })

  test('results scroll and filters survive detail Back, including the UI arrow', async ({ page }) => {
    await finishOnboarding(page)
    await page.locator('.m2-mode-switch > button').first().click()
    await page.getByTestId('open-location').click()
    const results = page.getByTestId('mobile-results')
    await expect(results.locator('.m2-result-card')).not.toHaveCount(0)
    await results.evaluate((element) => { element.scrollTop = 850 })
    const before = await results.evaluate((element) => element.scrollTop)
    expect(before).toBeGreaterThan(400)
    const url = page.url()
    await results.locator('.m2-result-card').nth(5).locator('.m2-result-card__image-button').click()
    await expect(page.locator('.listing-page h1')).toBeVisible()
    await page.goBack()
    await expect(page).toHaveURL(url)
    await expect(results.locator('.m2-result-card').first()).toBeAttached()
    await expect.poll(() => results.evaluate((element) => element.scrollTop)).toBeGreaterThan(before - 100)
    await results.locator('.m2-result-card').nth(5).locator('.m2-result-card__image-button').click()
    await page.getByRole('button', { name: 'Volver', exact: true }).click()
    await expect(results).toBeVisible()
  })

  test('menu → my listings → edit uses the actual history; direct detail has a fallback', async ({ page }) => {
    await finishOnboarding(page)
    await page.evaluate(() => {
      const key = '112233:listings:v3'
      const payload = JSON.parse(localStorage.getItem(key) ?? '{"version":3,"data":[]}')
      payload.data[0].ownerUserId = 'tenant-demo'
      payload.data[0].userCreated = true
      localStorage.setItem(key, JSON.stringify(payload))
      localStorage.setItem('112233:session:v1', JSON.stringify('tenant-demo'))
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    })
    await page.reload()
    await expect(page.getByTestId('open-location')).toBeVisible()
    await page.locator('.m2-bottom-nav button').last().click()
    await expect(page).toHaveURL(/#\/menu$/)
    await page.getByRole('button', { name: /ver y crear anuncios/i }).click()
    await expect(page.locator('.manage-card')).toHaveCount(1)
    await page.getByRole('link', { name: /editar/i }).click()
    await expect(page.getByRole('heading', { name: /editar habitación/i })).toBeVisible()
    const title = page.locator('#edit-title')
    await title.fill(`${await title.inputValue()} historial`)
    await page.locator('.listing-edit-back').click()
    await expect(page.locator('.manage-card')).toHaveCount(1)
    await page.locator('.owner-mobile-appbar button').click()
    await expect(page).toHaveURL(/#\/menu$/)

    const id = await page.evaluate(() => JSON.parse(localStorage.getItem('112233:listings:v3')!).data[0].id as string)
    const deepLink = await page.context().newPage()
    await deepLink.setViewportSize({ width: 390, height: 844 })
    await deepLink.goto(`/#/habitacion/${id}`)
    await expect(deepLink.locator('.listing-page h1')).toBeVisible()
    await deepLink.getByRole('button', { name: 'Volver', exact: true }).click()
    await expect(deepLink).toHaveURL(/#\/buscar/)
  })
})


test('desktop first map shows broad Spain and Tenerife before prior browsing', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  const map = page.locator('.google-map-canvas')
  await expect(map).toHaveAttribute('data-map-center', '32.450000,-11.200000')
  await expect(map).toHaveAttribute('data-map-zoom', '5.25')
})

test('desktop map saves a new area but reopens zoomed out to 300 km radius', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  const map = page.locator('.google-map-canvas')
  await expect(map).toHaveAttribute('data-map-zoom', '5.25')
  await map.dispatchEvent('wheel')
  await page.evaluate(() => {
    window.__googleMapsTestLastMap?.panTo({ lat: 28.12, lng: -16.72 })
    window.__googleMapsTestLastMap?.setZoom(11)
  })
  await expect.poll(() => page.evaluate(() => {
    const raw = localStorage.getItem('112233:map-last-search-area:v2')
    return raw ? JSON.parse(raw).center : null
  })).toEqual({ lat: 28.12, lng: -16.72 })
  await page.goto('/#/')
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await expect(map).toHaveAttribute('data-map-center', '28.120000,-16.720000')
  await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeGreaterThan(5)
  await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeLessThan(11)
})

test('desktop also saves a touch-style pointer pan when leaving directly', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  const map = page.locator('.google-map-canvas')
  await expect(map).toHaveAttribute('data-map-zoom', '5.25')
  await map.dispatchEvent('pointerdown')
  await page.evaluate(() => {
    window.__googleMapsTestLastMap?.panTo({ lat: 39.47, lng: -0.37 })
    window.__googleMapsTestLastMap?.setZoom(13)
  })
  await page.goto('/#/')
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:map-last-search-area:v2') ?? '{}').center)).toEqual({ lat: 39.47, lng: -0.37 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await expect(map).toHaveAttribute('data-map-center', '39.470000,-0.370000')
  await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeLessThan(10)
})

test('desktop remembered area fits on the current screen without altering filters', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:map-last-search-area:v2', JSON.stringify({
    center: { lat: 28.12, lng: -16.72 }, savedAt: Date.now(),
  })))
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  const map = page.locator('.google-map-canvas')
  await expect(map).toHaveAttribute('data-map-center', '28.120000,-16.720000')
  await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeGreaterThan(5)
  await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeLessThan(11)
  await expect(page).toHaveURL(/alquiler=long/)
})

test('desktop explicit named area wins over prior map history', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:map-last-search-area:v2', JSON.stringify({
    center: { lat: 28.12, lng: -16.72 }, savedAt: Date.now(),
  })))
  await page.goto('/#/buscar?q=Adeje&alquiler=long&vista=mapa')
  const map = page.locator('.google-map-canvas')
  await expect(map).toHaveAttribute('data-map-center', '28.122700,-16.724400')
  await expect(map).toHaveAttribute('data-map-zoom', '12')
})

test('desktop explicit bookmarked map camera wins over saved history', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:map-last-search-area:v2', JSON.stringify({
    center: { lat: 28.12, lng: -16.72 }, savedAt: Date.now(),
  })))
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa&mapLat=28.46360&mapLng=-16.25180&mapZoom=13.00')
  const map = page.locator('.google-map-canvas')
  await expect(map).toHaveAttribute('data-map-center', '28.463600,-16.251800')
  await expect(map).toHaveAttribute('data-map-zoom', '13')
})

test('desktop results → detail → browser Back restores the result route', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.locator('.search-page')).toBeVisible()
  const result = page.locator('.property-card a[href*="habitacion/"]').first()
  await expect(result).toBeVisible()
  const before = page.url()
  await result.click()
  await expect(page.locator('.listing-page h1')).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(before)
  await expect(page.locator('.property-card').first()).toBeVisible()
})

test('detail → related detail → Back restores the first detail', async ({ page }) => {
  await page.goto('/#/habitacion/arme%C3%B1ime-luminosa-01')
  await expect(page.locator('.listing-page h1')).toBeVisible()
  const firstUrl = page.url()
  const related = page.locator('.listing-similar .property-card a[href*="habitacion/"]').first()
  await expect(related).toBeVisible()
  await related.click()
  await expect(page.locator('.listing-page h1')).toBeVisible()
  expect(page.url()).not.toBe(firstUrl)
  await page.goBack()
  await expect(page).toHaveURL(firstUrl)
  await expect(page.locator('.listing-page h1')).toBeVisible()
})

test('search and map bookmarks survive reload', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/buscar?q=Arona&alquiler=long&precioMax=600')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await page.reload()
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page).toHaveURL(/q=Arona/)
  await page.goto('/#/buscar?q=Tenerife&vista=mapa&mapLat=28.29160&mapLng=-16.62910&mapZoom=11.00')
  await expect(page.getByTestId('google-map')).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
  await page.reload()
  await expect(page.getByTestId('google-map')).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
})


test('300 km recall fits the circle edge-to-edge without an extra zoom-out margin', async ({ page }) => {
  await page.goto('/#/')
  const result = await page.evaluate(async () => {
    const { viewportForRememberedArea, MAP_RECALL_RADIUS_KM } = await import('/src/lib/map-visit-history.ts')
    const radius = MAP_RECALL_RADIUS_KM / 6371.0088
    const latDelta = radius * 180 / Math.PI
    const y = (lat: number) => (1 - Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI) / 2
    return [
      { center: { lat: 28.12, lng: -16.72 }, width: 390, height: 844 }, // Tenerife, mobile
      { center: { lat: 28.1, lng: -15.59 }, width: 390, height: 844 }, // Gran Canaria, mobile
      { center: { lat: 40.07, lng: -2.13 }, width: 390, height: 844 }, // Cuenca, mobile
      { center: { lat: 28.12, lng: -16.72 }, width: 1000, height: 720 }, // desktop
      { center: { lat: 40.07, lng: -2.13 }, width: 1000, height: 720 },
      { center: { lat: 28.12, lng: -16.72 }, width: 844, height: 390 }, // landscape
    ].map(({ center, width, height }) => {
      const camera = viewportForRememberedArea(center, width, height)
      const longitudeDelta = Math.asin(Math.sin(radius) / Math.cos(center.lat * Math.PI / 180)) * 180 / Math.PI
      const diameterWidth = 256 * 2 ** camera.zoom * (2 * longitudeDelta / 360)
      const diameterHeight = 256 * 2 ** camera.zoom * (y(center.lat - latDelta) - y(center.lat + latDelta))
      const extent = Math.max(diameterWidth / width, diameterHeight / height)
      return { camera, extent, width, height }
    })
  })
  for (const { camera, extent } of result) {
    expect(camera.zoom).toBeGreaterThan(2)
    // At least one axis is filled exactly; the 300 km circle still fits both.
    expect(extent).toBeGreaterThan(0.9999)
    expect(extent).toBeLessThanOrEqual(1.000001)
  }
  expect(result[0].camera.zoom).toBeLessThan(result[3].camera.zoom)
})

test('mobile 300 km return uses the full map canvas rather than the old reduced dimensions', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:map-last-search-area:v2', JSON.stringify({
      center: { lat: 28.12, lng: -16.72 }, savedAt: Date.now(),
    }))
  })
  await page.goto('/#/buscar?q=Tenerife&vista=mapa')
  const map = page.getByTestId('google-map')
  await expect(map).toHaveAttribute('data-map-center', '28.120000,-16.720000')
  const expectedZoom = await page.evaluate(async () => {
    const { viewportForRememberedArea } = await import('/src/lib/map-visit-history.ts')
    return viewportForRememberedArea({ lat: 28.12, lng: -16.72 }, 390, 844).zoom
  })
  await expect.poll(async () => Number(await map.getAttribute('data-map-zoom'))).toBeCloseTo(expectedZoom, 5)
})
