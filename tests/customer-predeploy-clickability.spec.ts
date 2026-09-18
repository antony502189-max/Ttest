import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const localListingId = 'armeñime-luminosa-01'

async function openAsHost(page: Page, path: string) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto(path)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('CUSTOMER-PREDEPLOY Calle autocomplete keeps the native field visible with an inline suggestion contract', async ({ page }) => {
  const css = readFileSync(resolve(process.cwd(), 'src/publish-location-enhancer.css'), 'utf8')
  expect(css).toContain('#publish-street[data-address-autocomplete="native"]')
  expect(css).toContain('.publish-address-predictions')
  expect(css).toContain('.publish-address-prediction')
  expect(css).toContain('.publish-address-predictions[hidden]')

  await page.setViewportSize({ width: 390, height: 844 })
  await openAsHost(page, '/#/publicar')
  if (await page.getByRole('button', { name: 'Continuar' }).count()) await page.getByRole('button', { name: 'Continuar' }).click()
  const street = page.locator('#publish-street[data-address-autocomplete="native"]')
  await expect(street).toBeVisible()
  const borders = await street.evaluate((element) => {
    const style = getComputedStyle(element)
    return [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth]
  })
  expect(borders.every((width) => Number.parseFloat(width) > 0)).toBe(true)
  await expect(page.locator('.publish-place-autocomplete')).toHaveCount(0)
})

test('CUSTOMER-PREDEPLOY desktop listing card opens from non-interactive card surface', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const card = page.locator(`.property-card[data-listing-id="${localListingId}"]`)
  await expect(card).toBeVisible()
  await card.evaluate((element) => element.dispatchEvent(new MouseEvent('click', { bubbles: true })))
  await expect(page).toHaveURL(new RegExp(`#/habitacion/${encodeURIComponent(localListingId)}`))
})

test('CUSTOMER-PREDEPLOY mobile listing card opens from non-interactive card surface', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const card = page.locator(`.m2-result-card[data-listing-id="${localListingId}"]`)
  await expect(card).toBeVisible()
  await card.evaluate((element) => element.dispatchEvent(new MouseEvent('click', { bubbles: true })))
  await expect(page).toHaveURL(new RegExp(`#/habitacion/${encodeURIComponent(localListingId)}`))
})

test('CUSTOMER-PREDEPLOY card controls stay independent from whole-card navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const card = page.locator(`.m2-result-card[data-listing-id="${localListingId}"]`)
  await expect(card).toBeVisible()
  const favorite = card.locator('.m2-result-card__favorite')
  const before = await favorite.getAttribute('aria-pressed')
  await favorite.click()
  await expect(page).toHaveURL(/#\/buscar/)
  await expect(favorite).toHaveAttribute('aria-pressed', before === 'true' ? 'false' : 'true')
})
