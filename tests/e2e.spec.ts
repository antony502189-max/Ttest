import { expect, test, type Page } from '@playwright/test'

const runtimeErrors = new WeakMap<Page, string[]>()

const reset = async (page: Page) => {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
}

const login = async (page: Page, role: 'tenant' | 'host' | 'admin' = 'tenant') => {
  const credentials = role === 'admin' ? ['admin@112233.es', 'admin112233'] : role === 'host' ? ['anfitrion@112233.es', 'demo112233'] : ['inquilina@112233.es', 'demo112233']
  await page.goto('/#/acceso')
  await page.getByLabel(/email/i).fill(credentials[0])
  await page.locator('#login-password').fill(credentials[1])
  await page.getByRole('button', { name: /^acceder$/i }).click()
  await expect(page).not.toHaveURL(/acceso/)
}

test.beforeEach(async ({ page }) => {
  const errors: string[] = []
  runtimeErrors.set(page, errors)
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('pageerror', (error) => errors.push(error.message))
  await reset(page)
})
test.afterEach(async ({ page }) => expect(runtimeErrors.get(page) ?? [], 'Errores de consola o runtime').toEqual([]))

test('01–03 inicio, navegación y dataset completo', async ({ page }) => {
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.getByRole('button', { name: /^buscar$/i }).click()
  await expect(page).toHaveURL(/buscar/)
  await expect(page.getByRole('heading', { name: /habitaciones en/i })).toContainText('23')
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('112233:listings:v2') || '[]').length)).toBe(32)
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

test('11–15 mapa Leaflet, кластер, выбор, границы и полигон', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await expect(page.locator('.leaflet-map-canvas')).toBeVisible()
  await expect(page.locator('.leaflet-tile')).not.toHaveCount(0)
  await expect(page.locator('.leaflet-marker-icon')).not.toHaveCount(0)
  await page.getByRole('button', { name: /dibujar zona/i }).click()
  await page.getByRole('button', { name: /añadir punto/i }).click()
  await page.getByRole('button', { name: /añadir punto/i }).click()
  await page.getByRole('button', { name: /añadir punto/i }).click()
  await page.getByRole('button', { name: /finalizar/i }).click()
  await expect(page).toHaveURL(/poligono=/)
  await page.getByRole('button', { name: /buscar en esta zona/i }).click()
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
  await page.getByRole('button', { name: /descartar/i }).click()
  await expect(page).toHaveURL(/buscar/)
})

test('20–22 login erróneo, demo y ruta protegida', async ({ page }) => {
  await page.goto('/#/perfil')
  await expect(page).toHaveURL(/acceso/)
  await page.getByLabel(/email/i).fill('nadie@example.es')
  await page.locator('#login-password').fill('incorrecta')
  await page.getByRole('button', { name: /^acceder$/i }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.getByLabel(/email/i).fill('inquilina@112233.es')
  await page.locator('#login-password').fill('demo112233')
  await page.getByRole('button', { name: /^acceder$/i }).click()
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
  await expect(page.getByRole('heading', { name: /ya está visible/i })).toBeVisible()
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
  await page.goto('/#/buscar?q=Tenerife')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await expect(page.locator('.bottom-nav')).toBeVisible()
  await page.getByRole('button', { name: /mostrar habitaciones en el mapa/i }).click()
  await expect(page.locator('.leaflet-map-canvas')).toBeVisible()
})
