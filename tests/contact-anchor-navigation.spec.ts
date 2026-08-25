import { expect, test } from '@playwright/test'

const internalListingId = 'armeñime-luminosa-01'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('mobile Contactar opens, scrolls to and focuses the real contact panel', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const card = page.locator(`.m2-result-card[data-listing-id="${internalListingId}"]`)
  await expect(card).toBeVisible()
  await card.getByRole('button', { name: 'Contactar' }).click()

  await expect(page).toHaveURL(new RegExp(`#/habitacion/${encodeURIComponent(internalListingId)}#contacto$`))
  const contact = page.locator('#contacto')
  await expect(contact).toBeVisible()
  await expect.poll(async () => contact.evaluate((element) => document.activeElement === element)).toBe(true)
  const bounds = await contact.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.y).toBeLessThan(844)
  expect(bounds!.y + bounds!.height).toBeGreaterThan(0)
  await expect(contact.getByRole('button', { name: 'Chat' })).toHaveCount(0)
  await expect(contact.getByRole('button', { name: 'Enviar mensaje' })).toHaveCount(0)
})

test('direct contact hash is also restored after a hard reload', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}#contacto`)
  const contact = page.locator('#contacto')
  await expect(contact).toBeVisible()
  await expect.poll(async () => contact.evaluate((element) => document.activeElement === element)).toBe(true)
  await page.reload()
  await expect(contact).toBeVisible()
  await expect.poll(async () => contact.evaluate((element) => document.activeElement === element)).toBe(true)
})
