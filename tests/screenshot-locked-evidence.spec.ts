import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const v4Matrix = process.env.V4_MATRIX === '1'
const output = v4Matrix
  ? path.join(process.cwd(), 'artifacts', 'v4-exact-design', 'reports', 'supplemental')
  : path.join(process.cwd(), 'artifacts', 'screenshot-locked', 'after-live')

async function screenshot(page: Page, destination: string) {
  const image = await page.screenshot({ animations: 'disabled', caret: 'hide' })
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try { await writeFile(destination, image); return } catch (error) {
      if (attempt === 4) throw error
      await page.waitForTimeout(200 * (attempt + 1))
    }
  }
}

async function settle(page: Page, options: { map?: boolean } = {}) {
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
  await page.locator('img').evaluateAll((images) => Promise.race([
    Promise.all(images
      .filter((node) => (node as HTMLElement).offsetParent !== null)
      .slice(0, 3)
      .map((node) => {
        const image = node as HTMLImageElement
        if (image.complete) return Promise.resolve()
        return new Promise<void>((resolve) => {
          image.addEventListener('load', () => resolve(), { once: true })
          image.addEventListener('error', () => resolve(), { once: true })
        })
      })),
    new Promise<void>((resolve) => window.setTimeout(resolve, 4_000)),
  ])).catch(() => undefined)
  if (options.map) {
    await expect(page.locator('.google-map-canvas')).toBeVisible({ timeout: 15_000 })
    await expect.poll(() => page.locator('.map-price-marker-shell, .map-cluster-marker-shell').count(), { timeout: 15_000 }).toBeGreaterThan(0)
  }
  await page.waitForTimeout(180)
}

async function capture(page: Page, name: string, route: string, width = 390, height = 844, options: { map?: boolean } = {}) {
  await page.setViewportSize({ width, height })
  await page.goto(route)
  await settle(page, options)
  const overflow = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth }))
  expect(overflow.width, `${name} overflowed by ${overflow.width - overflow.viewport}px`).toBeLessThanOrEqual(overflow.viewport + 1)
  await screenshot(page, path.join(output, `${name}.png`))
}

async function setState(page: Page, state: { session?: string | null; language?: 'es' | 'en' | 'ru' }) {
  await page.goto('/#/')
  await page.evaluate(({ session, language }) => {
    localStorage.setItem('112233:session:v1', JSON.stringify(session ?? null))
    if (language) localStorage.setItem('112233:language:v1', language)
    else localStorage.removeItem('112233:language:v1')
  }, state)
  await page.reload()
}

test('capture unmasked screenshot-locked AFTER-LIVE matrix', async ({ page }) => {
  test.setTimeout(600_000)
  await mkdir(output, { recursive: true })
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())

  for (const [name, width, height] of [
    ['home-320x568', 320, 568],
    ['home-360x800', 360, 800],
    ['home-390x844', 390, 844],
    ['home-412x915', 412, 915],
  ] as const) await capture(page, name, '/#/', width, height)

  await capture(page, 'search-list-390x844', '/#/buscar?q=Tenerife')
  await capture(page, 'selected-zone-results-390x844', '/#/buscar?q=Adeje')
  await capture(page, 'search-list-844x390', '/#/buscar?q=Tenerife', 844, 390)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await settle(page)
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await screenshot(page, path.join(output, 'location-390x844.png'))
  await page.getByRole('button', { name: 'Seleccionar municipios y barrios' }).click()
  await screenshot(page, path.join(output, 'location-zones-390x844.png'))

  await page.goto('/#/buscar?q=Tenerife')
  await settle(page)
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  const filter = page.locator('.filter-drawer')
  await expect(filter).toBeVisible()
  await screenshot(page, path.join(output, 'filters-top-390x844.png'))
  const filterScroller = filter.locator('.filter-panel')
  await filterScroller.evaluate((node) => { node.scrollTop = node.scrollHeight * 0.48 })
  await page.waitForTimeout(120)
  await screenshot(page, path.join(output, 'filters-middle-390x844.png'))
  await filterScroller.evaluate((node) => { node.scrollTop = node.scrollHeight })
  await page.waitForTimeout(120)
  await screenshot(page, path.join(output, 'filters-bottom-390x844.png'))
  await page.keyboard.press('Escape')
  await page.locator('.mobile-sort-control').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await screenshot(page, path.join(output, 'sort-390x844.png'))

  await capture(page, 'search-map-390x844', '/#/buscar?q=Tenerife&vista=mapa', 390, 844, { map: true })
  for (let attempt = 0; attempt < 4 && await page.locator('.price-marker-shell').count() === 0; attempt += 1) {
    await page.locator('.room-cluster-shell').first().click({ timeout: 15_000 })
    await page.waitForTimeout(450)
  }
  await page.locator('.price-marker-shell').first().click({ timeout: 15_000 })
  await expect(page.locator('.map-selected-card')).toBeVisible()
  await screenshot(page, path.join(output, 'map-selected-listing-390x844.png'))
  await capture(page, 'map-draw-instruction-390x844', '/#/buscar?q=Tenerife&vista=mapa&dibujar=1', 390, 844, { map: true })
  await capture(page, 'search-map-667x375', '/#/buscar?q=Tenerife&vista=mapa', 667, 375, { map: true })
  if (v4Matrix) await capture(page, 'search-map-844x390', '/#/buscar?q=Tenerife&vista=mapa', 844, 390, { map: true })

  await capture(page, 'listing-390x844', '/#/habitacion/arme%C3%B1ime-luminosa-01')
  if (v4Matrix) {
    await page.getByRole('button', { name: 'Enviar mensaje' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await screenshot(page, path.join(output, 'contact-dialog-390x844.png'))
    await page.keyboard.press('Escape')
  }
  await page.getByRole('button', { name: 'Añadir comentario' }).click()
  await page.getByLabel('Comentario personal').fill('Me interesa: revisar gastos, convivencia y transporte.')
  await page.getByRole('button', { name: 'Guardar comentario' }).click()
  await page.locator('.listing-comments').scrollIntoViewIfNeeded()
  await page.waitForTimeout(120)
  await screenshot(page, path.join(output, 'listing-comments-390x844.png'))
  if (v4Matrix) {
    await page.locator('.listing-section').nth(2).scrollIntoViewIfNeeded()
    await screenshot(page, path.join(output, 'listing-lower-390x844.png'))
  }

  await capture(page, 'menu-390x844', '/#/menu')
  await capture(page, 'messages-390x844', '/#/mensajes')
  if (v4Matrix) {
    await capture(page, 'favorites-390x844', '/#/favoritos')
    await capture(page, 'saved-searches-390x844', '/#/busquedas-guardadas')
  }

  await setState(page, { session: 'host-demo' })
  await capture(page, 'profile-390x844', '/#/perfil')
  await capture(page, 'owner-listings-390x844', '/#/mis-anuncios')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/mis-anuncios/arme%C3%B1ime-luminosa-01/editar')
  await settle(page)
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await screenshot(page, path.join(output, 'owner-edit-390x844.png'))
  await capture(page, 'publish-start-390x844', '/#/publicar')
  const next = page.getByRole('button', { name: 'Continuar' })
  for (let index = 0; index < 2; index += 1) await next.click()
  if (v4Matrix) await screenshot(page, path.join(output, 'publish-room-390x844.png'))
  for (let index = 0; index < 3; index += 1) await next.click()
  await screenshot(page, path.join(output, 'publish-restrictions-390x844.png'))
  await next.click()
  await screenshot(page, path.join(output, 'publish-cover-390x844.png'))
  for (let index = 0; index < 3; index += 1) await next.click()
  await settle(page)
  await screenshot(page, path.join(output, 'publish-preview-390x844.png'))

  await setState(page, { session: null, language: 'es' })
  await page.goto('/#/buscar?q=Adeje')
  await settle(page)
  await page.getByRole('button', { name: 'Guardar búsqueda' }).click()
  await capture(page, 'home-saved-search-390x844', '/#/')

  await setState(page, { language: 'ru' })
  await capture(page, 'home-ru-390x844', '/#/')
  await capture(page, 'search-ru-390x844', '/#/buscar?q=Tenerife')
  await capture(page, 'menu-ru-390x844', '/#/menu')

  if (v4Matrix) {
    await setState(page, { session: null, language: 'es' })
    for (const [label, width, height] of [
      ['tablet-portrait', 768, 1024],
      ['tablet-landscape', 1024, 768],
      ['desktop', 1440, 900],
      ['desktop-wide', 1920, 1080],
    ] as const) {
      await capture(page, `home-${label}`, '/#/', width, height)
      await capture(page, `search-${label}`, '/#/buscar?q=Tenerife', width, height)
      await capture(page, `listing-${label}`, '/#/habitacion/arme%C3%B1ime-luminosa-01', width, height)
    }
  }
})
