import { expect, test, type BrowserContext, type Page } from '@playwright/test'

const origin = 'http://127.0.0.1:4173'

for (const target of ['area', 'list', 'filters'] as const) {
  test(`delayed camera idle cannot overwrite ${target} navigation`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      const push = history.pushState.bind(history)
      let injected = false
      history.pushState = (...args) => {
        const answer = push(...args)
        if (!injected && String(args[2]).includes('poligono=') && !String(args[2]).includes('dibujar=1')) {
          injected = true
          queueMicrotask(() => window.__googleMapsTestLastMap?.setCenter({ lat: 28.15, lng: -16.62 }))
        }
        return answer
      }
    })
    const polygon = '28.00000,-16.79000;28.00000,-16.50000;28.17000,-16.50000;28.17000,-16.79000'
    await page.goto(`/#/buscar?q=Tenerife&alquiler=long&vista=mapa&${target === 'area' ? 'dibujar=1&' : ''}poligono=${encodeURIComponent(polygon)}`)
    await expect(page).toHaveURL(/mapZoom=/)
    if (target === 'area') await page.getByTestId('search-this-area').click()
    else await page.getByRole('button', { name: target === 'list' ? 'Listado' : 'Filtros', exact: true }).click()
    await expect(page).not.toHaveURL(/dibujar=1/)
    await expect(page).toHaveURL(/poligono=/)
    if (target === 'area') await expect(page).toHaveURL(/vista=mapa/)
    else {
      await expect(page).not.toHaveURL(/vista=mapa|mapLat=|mapLng=|mapZoom=/)
      if (target === 'filters') await expect(page).toHaveURL(/panel=filtros/)
      else await expect(page.locator('.m2-result-card').first()).toBeVisible()
    }
  })
}

test('delayed camera idle cannot undo same-query map Back', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    window.addEventListener('popstate', () => {
      if (document.documentElement.dataset.backIdle !== 'armed') return
      delete document.documentElement.dataset.backIdle
      queueMicrotask(() => window.__googleMapsTestLastMap?.setCenter({ lat: 28.15, lng: -16.62 }))
    })
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.locator('.m2-result-card').first()).toBeVisible()
  await page.getByRole('button', { name: 'Mapa', exact: true }).click()
  await expect(page).toHaveURL(/vista=mapa.*mapZoom=/)
  await page.evaluate(() => { document.documentElement.dataset.backIdle = 'armed' })
  await page.goBack()
  await expect(page).not.toHaveURL(/vista=mapa|mapLat=|mapLng=|mapZoom=/)
  await expect(page.locator('.m2-result-card').first()).toBeVisible()
})

test('delayed camera idle cannot undo map Back fallback', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    const replace = history.replaceState.bind(history)
    let injected = false
    history.replaceState = (...args) => {
      const answer = replace(...args)
      if (!injected && String(args[2]).includes('/buscar?') && !String(args[2]).includes('vista=mapa')) {
        injected = true
        queueMicrotask(() => window.__googleMapsTestLastMap?.setCenter({ lat: 28.15, lng: -16.62 }))
      }
      return answer
    }
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await expect(page).toHaveURL(/mapZoom=/)
  await page.getByRole('button', { name: 'Volver', exact: true }).click()
  await expect(page).not.toHaveURL(/vista=mapa|mapLat=|mapLng=|mapZoom=/)
  await expect(page.locator('.m2-result-card').first()).toBeVisible()
})

async function openLocation(page: Page) {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/?panel=ubicacion')
  await expect(page.getByTestId('location-screen')).toBeVisible()
}

async function allowTenerifeLocation(context: BrowserContext) {
  await context.grantPermissions(['geolocation'], { origin })
  await context.setGeolocation({ latitude: 28.2916, longitude: -16.6291 })
}

test.describe('PR43 regression recovery', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('location keeps the approved three actions and hides phone lookup', async ({ page }) => {
    await openLocation(page)
    await expect(page.locator('.m2-location-action')).toHaveCount(3)
    await expect(page.getByTestId('search-phone')).toHaveCount(0)
  })

  test('nearby success stores coordinates and radius in the URL', async ({ page, context }) => {
    await allowTenerifeLocation(context)
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page).toHaveURL(/cerca=1/)
    await expect(page).toHaveURL(/radio=30/)
    await expect(page).toHaveURL(/lat=28\.2916/)
    await expect(page).toHaveURL(/lng=-16\.6291/)
    await expect(page.getByTestId('map-search')).toBeVisible()
  })

  test('nearby works from Madrid, not only from Tenerife', async ({ page, context }) => {
    await context.grantPermissions(['geolocation'], { origin })
    await context.setGeolocation({ latitude: 40.4168, longitude: -3.7038 })
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page).toHaveURL(/vista=mapa/)
    await expect(page).toHaveURL(/lat=40\.4168/)
    await expect(page).toHaveURL(/lng=-3\.7038/)
    await expect(page.getByTestId('map-search')).toBeVisible()
  })

  test('nearby rejects coordinates outside Spain without pretending success', async ({ page, context }) => {
    await context.grantPermissions(['geolocation'], { origin })
    await context.setGeolocation({ latitude: 48.8566, longitude: 2.3522 })
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page.getByRole('alert')).toContainText('fuera de España')
    await expect(page).toHaveURL(/panel=ubicacion/)
  })

  test('nearby handles denied permission', async ({ page, context }) => {
    await context.clearPermissions()
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page.getByRole('alert')).toContainText('No has permitido')
    await expect(page).toHaveURL(/panel=ubicacion/)
  })

  for (const failure of [
    { code: 2, text: 'no está disponible', name: 'unavailable' },
    { code: 3, text: 'tardado demasiado', name: 'timeout' },
  ]) {
    test(`nearby handles ${failure.name}`, async ({ page }) => {
      await page.addInitScript((code) => {
        Object.defineProperty(navigator, 'geolocation', {
          configurable: true,
          value: {
            getCurrentPosition: (_success: PositionCallback, error: PositionErrorCallback) => error({
              code,
              message: 'mock failure',
              PERMISSION_DENIED: 1,
              POSITION_UNAVAILABLE: 2,
              TIMEOUT: 3,
            } as GeolocationPositionError),
          },
        })
      }, failure.code)
      await openLocation(page)
      await page.getByTestId('search-nearby').click()
      await expect(page.getByRole('alert')).toContainText(failure.text)
    })
  }

  test('nearby handles an unavailable Geolocation API', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined })
    })
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page.getByRole('alert')).toContainText('no ofrece geolocalización')
  })

  test('polygon exposes Search this area and survives map-list-reload', async ({ page }) => {
    const polygon = '28.00000,-16.79000;28.00000,-16.50000;28.17000,-16.50000;28.17000,-16.79000'
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto(`/#/buscar?q=Tenerife&alquiler=long&vista=mapa&dibujar=1&poligono=${encodeURIComponent(polygon)}`)

    const searchArea = page.getByTestId('search-this-area')
    await expect(searchArea).toBeVisible()
    await searchArea.click()
    await expect(page).toHaveURL(/vista=mapa/)
    await expect(page).not.toHaveURL(/dibujar=1/)
    await expect(page).toHaveURL(/poligono=/)

    await page.getByRole('button', { name: 'Listado' }).click()
    const cards = page.locator('.m2-result-card')
    await expect.poll(() => cards.count()).toBeGreaterThan(0)
    const beforeReload = await cards.count()
    expect(beforeReload).toBeLessThan(23)
    await page.reload()
    await expect(cards).toHaveCount(beforeReload)
    await expect(page).toHaveURL(/poligono=/)
  })
})
