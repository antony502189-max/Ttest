import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { expect, test, type Page, type Request } from '@playwright/test'

test.skip(process.env.V4_EVIDENCE !== '1', 'Run explicitly with V4_EVIDENCE=1')

const phase = process.env.V4_PHASE === 'after' ? 'after' : 'before'
const root = path.join(process.cwd(), 'artifacts', 'v4-exact-design')
const output = path.join(root, phase)
const geometryOutput = path.join(root, 'reports', 'geometry', phase)

const diagnostics = {
  consoleErrors: [] as string[],
  pageErrors: [] as string[],
  failedRequests: [] as string[],
}

const geometrySelectors = [
  'body',
  '.mobile-header',
  '.bottom-nav',
  '.promoted-listing',
  '.market-search-panel',
  '.home-publish-action',
  '.mobile-results-topbar',
  '.idealista-results-toolbar',
  '.property-card',
  '.filter-drawer',
  '.filter-footer',
  '.mobile-map-screen__header',
  '.mobile-map-screen__footer',
  '.map-selected-card',
  '.listing-actionbar',
  '.property-gallery',
  '.listing-title',
  '.listing-comments',
  '.mobile-contact-bar',
  '.menu-page',
  '.owner-mobile-appbar',
  '.manage-card',
  '.publish-header',
  '.wizard-actions',
]

async function settle(page: Page, map = false) {
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
  await page.locator('img').evaluateAll((images) => Promise.race([
    Promise.all(images.filter((node) => (node as HTMLElement).offsetParent !== null).slice(0, 4).map((node) => {
      const image = node as HTMLImageElement
      if (image.complete) return Promise.resolve()
      return new Promise<void>((resolve) => {
        image.addEventListener('load', () => resolve(), { once: true })
        image.addEventListener('error', () => resolve(), { once: true })
      })
    })),
    new Promise<void>((resolve) => window.setTimeout(resolve, 4_000)),
  ])).catch(() => undefined)
  if (map) await expect(page.locator('.google-map-canvas')).toBeVisible({ timeout: 15_000 })
  await page.waitForTimeout(180)
}

async function reset(page: Page, session: string | null = null, language: 'es' | 'en' | 'ru' = 'es') {
  await page.goto('/#/')
  await page.evaluate(({ session: nextSession, language: nextLanguage }) => {
    localStorage.clear()
    localStorage.setItem('112233:session:v1', JSON.stringify(nextSession))
    localStorage.setItem('112233:language:v1', nextLanguage)
  }, { session, language })
  await page.reload()
  await settle(page)
}

async function open(page: Page, route: string, map = false) {
  await page.goto(route)
  await settle(page, map)
}

async function capture(page: Page, index: number, label: string, options: { preserveToasts?: boolean } = {}) {
  const name = `${String(index).padStart(3, '0')}-${label}`
  await settle(page)
  if (!options.preserveToasts) {
    for (let attempt = 0; attempt < 3 && await page.locator('[data-sonner-toast]').count(); attempt += 1) {
      const close = page.locator('[data-sonner-toast] [data-close-button]').first()
      if (await close.count()) await close.click({ force: true }).catch(() => undefined)
      else await page.locator('[data-sonner-toast]').first().waitFor({ state: 'detached', timeout: 6_000 }).catch(() => undefined)
    }
  }
  let snapshot: { overflow: { viewportWidth: number; documentWidth: number; viewportHeight: number; documentHeight: number }; geometry: Record<string, unknown> } | undefined
  for (let attempt = 0; attempt < 3 && !snapshot; attempt += 1) {
    try {
      snapshot = await page.evaluate((selectors) => ({
        overflow: {
          viewportWidth: document.documentElement.clientWidth,
          documentWidth: document.documentElement.scrollWidth,
          viewportHeight: document.documentElement.clientHeight,
          documentHeight: document.documentElement.scrollHeight,
        },
        geometry: Object.fromEntries(selectors.map((selector) => {
          const element = document.querySelector<HTMLElement>(selector)
          if (!element || element.offsetParent === null) return [selector, null]
          const box = element.getBoundingClientRect()
          const style = getComputedStyle(element)
          return [selector, {
            x: Math.round(box.x * 100) / 100,
            y: Math.round(box.y * 100) / 100,
            width: Math.round(box.width * 100) / 100,
            height: Math.round(box.height * 100) / 100,
            position: style.position,
            display: style.display,
          }]
        })),
      }), geometrySelectors)
    } catch (error) {
      if (!String(error).includes('Execution context was destroyed') || attempt === 2) throw error
      await page.waitForLoadState('domcontentloaded')
      await settle(page)
    }
  }
  if (!snapshot) throw new Error(`Unable to capture stable geometry for ${name}`)
  const { overflow, geometry } = snapshot
  expect(overflow.documentWidth, `${name} horizontal overflow`).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  await page.screenshot({ path: path.join(output, `${name}.png`), animations: 'disabled', caret: 'hide' })
  await writeFile(path.join(geometryOutput, `${name}.json`), JSON.stringify({ name, url: page.url(), overflow, geometry }, null, 2), 'utf8')
}

async function scrollFilter(page: Page, ratio: number) {
  const panel = page.locator('.filter-drawer .filter-panel')
  await panel.evaluate((node, nextRatio) => { node.scrollTop = (node.scrollHeight - node.clientHeight) * nextRatio }, ratio)
  await page.waitForTimeout(100)
}

async function selectMapListing(page: Page) {
  for (let attempt = 0; attempt < 5 && await page.locator('.price-marker-shell').count() === 0; attempt += 1) {
    const cluster = page.locator('.room-cluster-shell').first()
    if (await cluster.count()) await cluster.click({ timeout: 15_000 })
    await page.waitForTimeout(300)
  }
  const price = page.locator('.price-marker-shell').first()
  if (await price.count()) await price.click({ timeout: 15_000 })
  await expect(page.locator('.map-selected-card')).toBeVisible({ timeout: 15_000 })
}

test('capture V4 golden-indexed live evidence', async ({ page }) => {
  test.setTimeout(600_000)
  await Promise.all([mkdir(output, { recursive: true }), mkdir(geometryOutput, { recursive: true })])
  page.on('console', (message) => { if (message.type() === 'error') diagnostics.consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error.message))
  page.on('requestfailed', (request: Request) => diagnostics.failedRequests.push(`${request.method()} ${request.url()} :: ${request.failure()?.errorText ?? 'failed'}`))
  await page.setViewportSize({ width: 390, height: 844 })
  await reset(page)

  await capture(page, 19, 'home-default')
  await page.locator('#home-tenant-requirement').scrollIntoViewIfNeeded()
  await capture(page, 24, 'home-property-control')
  await capture(page, 32, 'home-search')

  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await capture(page, 35, 'location-entry')
  await page.keyboard.press('Escape')

  await open(page, '/#/buscar?q=Tenerife&vista=mapa&dibujar=1', true)
  await capture(page, 37, 'map-draw-instruction')
  const addPoint = page.getByRole('button', { name: 'Añadir punto' })
  for (let point = 0; point < 3; point += 1) await addPoint.click()
  await capture(page, 42, 'map-drawing')
  await page.getByRole('button', { name: /Finalizar/ }).click()
  await capture(page, 43, 'map-polygon')
  await page.getByRole('button', { name: /Mostrar .* habitaciones/ }).click()
  await settle(page)
  await capture(page, 45, 'selected-zone-list')

  await open(page, '/#/buscar?q=Tenerife')
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  await expect(page.locator('.filter-drawer')).toBeVisible()
  await capture(page, 46, 'filters-top')
  await page.locator('.filter-drawer').getByLabel('Precio máximo').fill('550')
  await scrollFilter(page, 0.38)
  await capture(page, 49, 'filters-middle')
  await scrollFilter(page, 0.72)
  await capture(page, 53, 'filters-lower')
  await scrollFilter(page, 1)
  await capture(page, 55, 'filters-bottom')
  await page.getByRole('button', { name: /Mostrar .* habitaciones/ }).click()
  await settle(page)

  await capture(page, 57, 'results-list')
  await open(page, '/#/buscar?q=Tenerife&vista=mapa', true)
  await capture(page, 60, 'results-map-overview')
  await capture(page, 63, 'results-map-zoomed')
  await selectMapListing(page)
  await capture(page, 66, 'results-map-preview')
  await page.getByRole('button', { name: /Mostrar .* habitaciones/ }).click()
  await open(page, '/#/habitacion/arme%C3%B1ime-luminosa-01')
  await capture(page, 68, 'listing-entry')

  await page.locator('.listing-comments').evaluate((node) => node.scrollIntoView({ block: 'start' }))
  await capture(page, 69, 'listing-comments')
  await open(page, '/#/habitacion/arme%C3%B1ime-luminosa-01')
  await capture(page, 73, 'listing-top')
  await capture(page, 76, 'listing-actions')
  await page.locator('.listing-comments').evaluate((node) => node.scrollIntoView({ block: 'start' }))
  await capture(page, 80, 'listing-comment-entry')
  await capture(page, 83, 'listing-advertiser-comment')
  await page.getByRole('button', { name: /Guardar|Guardado/ }).first().click()
  await page.waitForTimeout(120)
  await capture(page, 84, 'listing-favorite-feedback', { preserveToasts: true })
  await capture(page, 86, 'listing-favorite-selected')

  await open(page, '/#/buscar?q=Tenerife&vista=mapa', true)
  await selectMapListing(page)
  await capture(page, 90, 'map-selected-card')
  await open(page, '/#/')
  await capture(page, 92, 'home-return')
  await open(page, '/#/menu')
  await capture(page, 96, 'menu')

  await reset(page, 'host-demo')
  await open(page, '/#/mis-anuncios/arme%C3%B1ime-luminosa-01/editar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await capture(page, 100, 'owner-edit-room')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await capture(page, 105, 'owner-edit-fields')
  await open(page, '/#/mis-anuncios')
  await capture(page, 109, 'owner-listings')

  await reset(page)
  await open(page, '/#/buscar?q=Adeje')
  await page.getByRole('button', { name: 'Guardar búsqueda' }).click()
  await open(page, '/#/')
  await capture(page, 112, 'home-saved-search')
  await capture(page, 114, 'home-saved-location')

  await writeFile(path.join(root, 'reports', `diagnostics-${phase}.json`), JSON.stringify(diagnostics, null, 2), 'utf8')
})
