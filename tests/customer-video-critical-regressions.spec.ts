import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

async function signInAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
}

test('customer video fix keeps the owned-listing route behind authoritative hydration', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  const gate = readFileSync('src/components/owned-listings-hydration-gate.tsx', 'utf8')

  expect(app).toContain('<OwnedListingsHydrationGate><MyListingsPage /></OwnedListingsHydrationGate>')
  expect(gate).toContain("getOwnedListings(controller.signal)")
  expect(gate).toContain("type Snapshot = { userId: string; items: Listing[] }")
  expect(gate).toContain("snapshot?.userId === userId")
  expect(gate).toContain("window.dispatchEvent(new Event('catalog:updated'))")
  expect(gate).toContain('Tus anuncios no se han borrado')
  expect(gate).toContain('Объявления не удалены')
})

test('customer video fix removes the fake fresh-location claim and protects postcode input', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')

  expect(source).toContain("const AUTO_CITY_VALUE = '__112233_auto_municipality__'")
  expect(source).toContain("draft.city === 'Adeje'")
  expect(source).toContain("draft.area === 'Armeñime'")
  expect(source).toContain("draft.postcode === '38678'")
  expect(source).toContain("setNativeSelectValue(city, AUTO_CITY_VALUE, true)")
  expect(source).toContain("setNativeInputValue(area, '')")
  expect(source).toContain("setNativeInputValue(postcode, '')")
  expect(source).toContain("!/^\\d{5}$/.test(postcode.value.trim())")
  expect(source).toContain('selector.hidden = true')
})

test('customer video fix retries transient admin authorization without weakening the server route guard', () => {
  const app = readFileSync('src/App.tsx', 'utf8')

  expect(app).toContain('<ProtectedRoute admin><AdminPage /></ProtectedRoute>')
  expect(app).toContain("error.status === 401 || error.status === 403")
  expect(app).toContain('window.setTimeout(() => { void verifyAdmin(false) }, 450)')
  expect(app).toContain("setAdminAllowed('error')")
  expect(app).toContain('Сессия остаётся активной')
})

test('leaving a new publication does not make existing host listings disappear', async ({ page }) => {
  await signInAsHost(page)
  await page.goto('/#/mis-anuncios')

  const before = await page.locator('.manage-card').count()
  expect(before).toBeGreaterThan(0)

  await page.getByRole('link', { name: /nuevo anuncio/i }).click()
  await page.getByRole('button', { name: /continuar/i }).click()
  await expect(page.locator('#publish-city')).toBeVisible()

  await page.goBack()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await expect(page.locator('.manage-card')).toHaveCount(before)
  await expect(page.getByText('No hay anuncios en este estado')).toHaveCount(0)
})

test('owned-listing empty state follows the selected UI language', async ({ page }) => {
  await signInAsHost(page)
  await page.goto('/#/mis-anuncios')

  await page.getByLabel('Estado').selectOption('Borrador')
  await expect(page.locator('.account-empty')).toBeVisible()

  await page.getByRole('button', { name: 'Seleccionar idioma' }).click()
  await page.getByRole('menuitemradio', { name: /Русский/ }).click()

  await expect(page.locator('.account-empty h2')).toHaveText('Нет объявлений с таким статусом')
  await expect(page.locator('.account-empty p')).toHaveText('Выберите другой статус или создайте новое объявление.')
  await expect(page.locator('.account-empty')).not.toContainText('No hay anuncios en este estado')
})
