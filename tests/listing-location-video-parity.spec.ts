import { expect, test, type Page } from '@playwright/test'

const internalListingId = 'armeñime-luminosa-01'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

async function patchInternalListingContacts(page: Page, patch: Record<string, unknown>) {
  await page.goto('/#/')
  await page.evaluate(({ id, contactPatch }) => {
    const raw = localStorage.getItem('112233:listings:v3')
    if (!raw) throw new Error('Mock listing storage was not initialized')
    const payload = JSON.parse(raw)
    payload.data = payload.data.map((listing: { id: string }) => listing.id === id ? { ...listing, ...contactPatch } : listing)
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
  }, { id: internalListingId, contactPatch: patch })
  await page.reload()
}

test('listing location follows the customer street-map interaction without exposing an exact address', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)

  const location = page.locator('.listing-location-section')
  await expect(location).toBeVisible()
  await expect(location.getByRole('heading', { name: 'Ubicación aproximada' })).toBeVisible()
  await expect(location).toContainText('calles y referencias de la zona')
  await expect(location.getByRole('link', { name: 'Calcular ruta' })).toHaveAttribute('href', /google\.com\/maps\/dir\/\?api=1&destination=/)
  await expect(location.getByRole('link', { name: 'Street View' })).toHaveAttribute('href', /map_action=pano&viewpoint=/)
  await expect(location.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' })).toBeVisible()
  await expect(location.locator('.listing-location-google-map')).toHaveAttribute('aria-label', 'Mapa de la ubicación aproximada del anuncio')
  await expect(location).not.toContainText(/386\d{2}/)
  await expect(location).not.toContainText(/Calle\s+\S+\s+\d+/i)
})

test('listing map opens a true full-screen zoomable Google roadmap with a back control', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)
  await page.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' }).click()

  const dialog = page.getByRole('dialog', { name: 'Ubicación' })
  const mapCanvas = dialog.locator('.listing-location-dialog__map .listing-location-google-map')
  const back = dialog.getByRole('button', { name: 'Volver al anuncio' })
  await expect(dialog).toBeVisible()
  await expect(mapCanvas).toBeVisible()
  await expect(back).toBeVisible()
  await expect(back).toBeFocused()

  const options = await page.evaluate(() => {
    const map = window.__googleMapsTestLastMap
    return map ? {
      zoom: map.get('zoom'),
      minZoom: map.get('minZoom'),
      maxZoom: map.get('maxZoom'),
      mapTypeId: map.get('mapTypeId'),
      zoomControl: map.get('zoomControl'),
      streetViewControl: map.get('streetViewControl'),
      gestureHandling: map.get('gestureHandling'),
    } : null
  })
  expect(options).toEqual({
    zoom: 18,
    minZoom: 11,
    maxZoom: 20,
    mapTypeId: 'roadmap',
    zoomControl: true,
    streetViewControl: true,
    gestureHandling: 'greedy',
  })

  const beforeZoom = await page.evaluate(() => window.__googleMapsTestLastMap?.getZoom() ?? 0)
  await mapCanvas.dispatchEvent('wheel', { deltaY: -100 })
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom() ?? 0)).toBeGreaterThan(beforeZoom)

  const box = await dialog.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.x).toBeLessThanOrEqual(1)
  expect(box!.y).toBeLessThanOrEqual(1)
  expect(box!.width).toBeGreaterThanOrEqual(388)
  expect(box!.height).toBeGreaterThanOrEqual(842)

  await back.click()
  await expect(dialog).toHaveCount(0)
})

test('customer Android recording viewport keeps the portaled map edge-to-edge', async ({ page }) => {
  await page.setViewportSize({ width: 588, height: 1280 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)
  await page.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' }).click()

  const dialog = page.getByRole('dialog', { name: 'Ubicación' })
  const mapShell = dialog.locator('.listing-location-dialog__map .listing-location-google-map-shell')
  await expect(dialog).toBeVisible()
  await expect(mapShell).toBeVisible()

  const dialogBox = await dialog.boundingBox()
  const mapBox = await mapShell.boundingBox()
  expect(dialogBox).not.toBeNull()
  expect(mapBox).not.toBeNull()
  expect(dialogBox!.x).toBeLessThanOrEqual(1)
  expect(dialogBox!.y).toBeLessThanOrEqual(1)
  expect(dialogBox!.width).toBeGreaterThanOrEqual(586)
  expect(dialogBox!.height).toBeGreaterThanOrEqual(1278)
  expect(mapBox!.x).toBeLessThanOrEqual(1)
  expect(mapBox!.y).toBeLessThanOrEqual(1)
  expect(mapBox!.width).toBeGreaterThanOrEqual(586)
  expect(mapBox!.height).toBeGreaterThanOrEqual(1278)

  const layout = await dialog.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      position: style.position,
      left: style.left,
      right: style.right,
      width: style.width,
      maxWidth: style.maxWidth,
      transform: style.transform,
    }
  })
  expect(layout.position).toBe('fixed')
  expect(layout.left).toBe('0px')
  expect(layout.right).toBe('0px')
  expect(layout.width).toBe('588px')
  expect(layout.maxWidth).toBe('none')
  expect(layout.transform).toBe('none')
})

test('preview keeps Android Google tile rows contiguous and outside responsive image resets', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)

  const preview = page.locator('.listing-location-preview')
  const open = preview.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' })
  const previewBox = await preview.boundingBox()
  const buttonBox = await open.boundingBox()
  expect(previewBox).not.toBeNull()
  expect(buttonBox).not.toBeNull()
  expect(buttonBox!.width).toBeLessThan(previewBox!.width * 0.6)
  expect(buttonBox!.height).toBeLessThan(previewBox!.height * 0.3)

  const tileStyles = await page.evaluate(() => {
    const preview = document.querySelector('.listing-location-preview')
    const map = preview?.querySelector('.listing-location-google-map')
    if (!preview || !map) return null
    const gm = document.createElement('div')
    gm.className = 'gm-style'
    const tileLayer = document.createElement('div')
    const image = document.createElement('img')
    image.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='
    tileLayer.appendChild(image)
    gm.appendChild(tileLayer)
    map.appendChild(gm)
    const imageStyle = getComputedStyle(image)
    const value = {
      previewContain: getComputedStyle(preview).contain,
      maxWidth: imageStyle.maxWidth,
      maxHeight: imageStyle.maxHeight,
      position: imageStyle.position,
    }
    gm.remove()
    return value
  })
  expect(tileStyles).toEqual({
    previewContain: 'none',
    maxWidth: 'none',
    maxHeight: 'none',
    position: 'absolute',
  })
})

test('mobile WhatsApp-only listing exposes confirmation instead of a blank fixed strip', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await patchInternalListingContacts(page, {
    showPhone: false,
    showWhatsApp: true,
    contactPhone: '+34 699 999 999',
    contactWhatsapp: '+34 688 888 888',
  })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)

  const bar = page.locator('.mobile-contact-bar')
  const confirmation = bar.locator('.condition-confirm')
  await expect(bar).toBeVisible()
  await expect(bar).toHaveCSS('position', 'fixed')
  await expect(confirmation).toBeVisible()
  await expect(bar.locator('a[href^="https://wa.me/"]')).toHaveCount(0)

  await confirmation.locator('[data-slot="checkbox"]').click()

  const whatsapp = bar.locator('a[href^="https://wa.me/"]')
  await expect(whatsapp).toBeVisible()
  await expect(whatsapp).toHaveAttribute('href', /34688888888/)
  await expect(confirmation).toBeHidden()
})

test('mobile listing with no contact action does not paint an orphan fixed white shell', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await patchInternalListingContacts(page, {
    showPhone: false,
    showWhatsApp: false,
    contactPhone: '+34 699 999 999',
    contactWhatsapp: '+34 688 888 888',
  })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)

  const bar = page.locator('.mobile-contact-bar')
  await expect(bar).toBeHidden()
  await expect(bar).toHaveCSS('display', 'none')

  const fixedWhiteBands = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>('.mobile-contact-bar')]
    .filter((element) => {
      const style = getComputedStyle(element)
      const box = element.getBoundingClientRect()
      return style.position === 'fixed'
        && style.display !== 'none'
        && box.width >= window.innerWidth * 0.9
        && box.height > 0
        && (style.backgroundColor === 'rgb(255, 255, 255)' || style.backgroundColor === 'rgba(255, 255, 255, 1)')
    }).length)
  expect(fixedWhiteBands).toBe(0)
})

test('customer location controls are fully localized in English and Russian', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)
  const location = page.locator('.listing-location-section')
  const languageSwitcher = page.locator('.language-switcher:visible')

  await languageSwitcher.click()
  await page.getByRole('menuitemradio', { name: /English/ }).click()
  await expect(location.getByRole('heading', { name: 'Approximate location' })).toBeVisible()
  await expect(location).toContainText('nearby streets and landmarks')
  await expect(location.getByRole('link', { name: 'Get directions' })).toBeVisible()
  await expect(location.getByRole('button', { name: 'Open the location map full screen' })).toBeVisible()
  await expect(location.locator('.listing-location-google-map')).toHaveAttribute('aria-label', 'Map of the listing’s approximate location')

  await languageSwitcher.click()
  await page.getByRole('menuitemradio', { name: /Русский/ }).click()
  await expect(location.getByRole('heading', { name: 'Примерное местоположение' })).toBeVisible()
  await expect(location).toContainText('улицы и ориентиры района')
  await expect(location.getByRole('link', { name: 'Построить маршрут' })).toBeVisible()
  await expect(location.getByRole('button', { name: 'Открыть карту местоположения на весь экран' })).toBeVisible()
  await expect(location.locator('.listing-location-google-map')).toHaveAttribute('aria-label', 'Карта примерного местоположения объявления')
})
