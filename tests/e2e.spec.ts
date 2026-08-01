import { expect, test, type Page } from '@playwright/test'
import { isExpectedHeadlessVectorFallback } from './helpers/google-maps-console'

const runtimeErrors = new WeakMap<Page, string[]>()

const reset = async (page: Page) => {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
}

const submitEmailLogin = async (page: Page, emailValue: string, passwordValue: string) => {
  const email = page.getByLabel(/^email$/i)
  if (!(await email.isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /iniciar sesión con email/i }).click()
  }
  await email.fill(emailValue)
  await page.locator('#login-password').or(page.getByLabel(/^contraseña$/i)).fill(passwordValue)
  const desktopSubmit = page.getByRole('button', { name: /^acceder$/i })
  if (await desktopSubmit.isVisible().catch(() => false)) await desktopSubmit.click()
  else await page.getByRole('button', { name: /iniciar sesión con email/i }).click()
}

const login = async (page: Page, role: 'tenant' | 'host' | 'admin' = 'tenant') => {
  const credentials = role === 'admin' ? ['admin@112233.es', 'admin112233'] : role === 'host' ? ['anfitrion@112233.es', 'demo112233'] : ['inquilina@112233.es', 'demo112233']
  await page.goto('/#/acceso')
  await submitEmailLogin(page, credentials[0], credentials[1])
  await expect(page).not.toHaveURL(/acceso/)
}

test.beforeEach(async ({ page }) => {
  const errors: string[] = []
  runtimeErrors.set(page, errors)
  page.on('console', (message) => {
    if (message.type() === 'error' && !isExpectedHeadlessVectorFallback(message.text())) errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(error.message))
  await reset(page)
})
test.afterEach(async ({ page }) => expect(runtimeErrors.get(page) ?? [], 'Errores de consola o runtime').toEqual([]))

test('01–03 inicio, navegación y dataset completo', async ({ page }) => {
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.getByRole('radio', { name: /Vivienda, larga estancia/i }).click()
  await page.getByRole('button', { name: 'Sin restricción' }).click()
  await page.getByRole('button', { name: /^ver habitaciones$/i }).click()
  await expect(page).toHaveURL(/buscar/)
  const resultsHeading = page.getByRole('heading', { name: /habitaciones en/i })
  const headingText = await resultsHeading.textContent()
  const resultCount = Number(headingText?.match(/^\d+/)?.[0])
  expect(Number.isFinite(resultCount)).toBeTruthy()
  expect(resultCount).toBeGreaterThan(0)
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('112233:listings:v3') || '{"data":[]}').data.length)).toBe(32)
})

test('04–07 filtros, chips, URL y restauración al recargar', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await page.getByRole('button', { name: /hasta 500/i }).click()
  await expect(page).toHaveURL(/precioMax=500/)
  await expect(page.locator('.applied-filters')).toContainText('500')
  const count = await page.locator('.property-card').count()
  await page.reload()
  await expect(page.locator('.property-card')).toHaveCount(count)
  await page.locator('.applied-filters button').first().click()
  await expect(page).not.toHaveURL(/precioMax=500/)
})

test('08–10 ordenación, paginación y back/forward', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await page.getByLabel('Ordenar resultados').selectOption('Precio más bajo')
  await expect(page.locator('.property-card .price-block strong').first()).toBeVisible()
  const prices = (await page.locator('.property-card .price-block strong').allTextContents()).map((value) => Number.parseInt(value.replace(/\D/g, '')))
  expect(prices[0]).toBeLessThanOrEqual(prices.at(-1) || 9999)
  await page.getByRole('button', { name: '2', exact: true }).click()
  await expect(page).toHaveURL(/pagina=2/)
  await page.goBack()
  await expect(page).not.toHaveURL(/pagina=2/)
  await page.goForward()
  await expect(page).toHaveURL(/pagina=2/)
})

test('11–15 Google Maps, кластер, выбор, границы и полигон', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await expect(page.locator('.google-map-canvas')).toBeVisible()
  await expect(page.locator('.gm-style[data-test-map-sdk="1"]')).toHaveCount(1)
  await expect(page.locator('.map-price-marker-shell, .map-cluster-marker-shell')).not.toHaveCount(0)
  await page.getByRole('button', { name: /dibujar zona/i }).click()
  const drawing = page.locator('.freehand-map-overlay')
  await expect(drawing).toBeVisible()
  const box = await drawing.boundingBox()
  expect(box).not.toBeNull()
  if (!box) return
  const left = box.x + box.width * .3
  const right = box.x + box.width * .7
  const top = box.y + box.height * .3
  const bottom = box.y + box.height * .7
  await page.mouse.move(left, top)
  await page.mouse.down()
  await page.mouse.move(right, top, { steps: 8 })
  await page.mouse.move(right, bottom, { steps: 8 })
  await page.mouse.move(left, bottom, { steps: 8 })
  await page.mouse.move(left, top, { steps: 8 })
  await page.mouse.up()
  await expect(drawing).toHaveCount(0)
  await expect(page).toHaveURL(/poligono=/)
  const searchArea = page.getByRole('button', { name: /buscar en esta zona/i })
  await expect(searchArea).toHaveCount(0)
  await page.locator('.google-map-canvas').hover()
  await page.mouse.wheel(0, -600)
  await expect(searchArea).toBeVisible()
  await expect(searchArea).toBeEnabled()
  await searchArea.click()
  await expect(page.getByRole('button', { name: /eliminar zona/i })).toBeVisible()
})

test('16–19 ficha: sin bloqueo, galería, favorito, descarte', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife')
  const href = await page.locator('.property-card a[href*="/habitacion/"]').first().getAttribute('href')
  await page.goto(`/${href}`)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('alertdialog')).toHaveCount(0)
  await page.getByRole('button', { name: /ver todas las fotos \(/i }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: /^guardar$/i }).click()
  await expect(page.getByRole('button', { name: /guardado/i })).toBeVisible()
  await page.getByRole('button', { name: /más acciones del anuncio/i }).click()
  await page.getByRole('menuitem', { name: /descartar/i }).click()
  await expect(page).toHaveURL(/buscar/)
})

test('20–22 login erróneo, demo y ruta protegida', async ({ page }) => {
  await page.goto('/#/perfil')
  await expect(page).toHaveURL(/acceso/)
  await submitEmailLogin(page, 'nadie@example.es', 'incorrecta')
  await expect(page.getByRole('alert')).toBeVisible()
  await submitEmailLogin(page, 'inquilina@112233.es', 'demo112233')
  await expect(page).toHaveURL(/perfil/)
})

test('23–26 registro y perfil persistente', async ({ page }) => {
  await page.goto('/#/registro')
  await page.getByLabel(/^nombre/i).fill('Persona Prueba')
  await page.getByLabel(/email/i).fill('persona@example.es')
  await page.getByLabel(/^contraseña/i).fill('segura112233')
  await page.getByLabel(/repite la contraseña/i).fill('segura112233')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: /crear cuenta/i }).click()
  await page.getByRole('link', { name: /abrir mi perfil/i }).click()
  await expect(page).toHaveURL(/perfil/)
  await page.getByRole('button', { name: /editar perfil/i }).click()
  await page.getByLabel(/^nombre$/i).fill('Persona Editada')
  await page.getByRole('button', { name: /guardar cambios/i }).click()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Persona Editada' })).toBeVisible()
})

test('27–29 publicación completa, CRUD y edición', async ({ page }) => {
  await login(page, 'host')
  await page.goto('/#/publicar')
  for (let index = 0; index < 9; index += 1) await page.getByRole('button', { name: /continuar/i }).click()
  await page.getByRole('button', { name: /publicar anuncio/i }).click()
  await expect(page.getByRole('heading', { name: /se ha enviado a revisión/i })).toBeVisible()
  await page.getByRole('link', { name: /mis anuncios/i }).click()
  await expect(page.locator('.manage-card')).toHaveCount(4)
  await page.locator('.manage-card').first().getByRole('link', { name: /editar/i }).click()
  await expect(page.getByRole('heading', { name: /editar habitación/i })).toBeVisible()
})

test('30 admin, búsqueda, moderación y exportación CSV', async ({ page }) => {
  await login(page, 'admin')
  await page.goto('/#/admin')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await page.getByRole('button', { name: /anuncios/i }).click()
  await page.getByLabel(/buscar en administración/i).fill('Armeñime')
  await expect(page.locator('tbody tr')).not.toHaveCount(0)
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: /exportar CSV/i }).click()
  expect((await downloadPromise).suggestedFilename()).toBe('112233-anuncios.csv')
})

test('31 responsive móvil sin desbordamiento y navegación inferior', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/buscar?q=Tenerife')
  await page.reload()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await expect(page.locator('.m2-bottom-nav')).toBeVisible()
  await page.locator('.m2-results__toolbar button').nth(2).click()
  await expect(page.locator('.m2-map-canvas')).toBeVisible()
})
