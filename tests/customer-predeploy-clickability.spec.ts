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

test('CUSTOMER-PREDEPLOY Calle autocomplete has a complete visible border contract', async ({ page }) => {
  const css = readFileSync(resolve(process.cwd(), 'src/publish-location-enhancer.css'), 'utf8')
  const rule = css.match(/\.publish-place-autocomplete\s*\{([^}]*)\}/s)?.[1] ?? ''
  expect(rule).toContain('border: 1px solid var(--border)')
  expect(rule).toContain('box-sizing: border-box')
  expect(rule).toContain('overflow: hidden')

  await page.setViewportSize({ width: 390, height: 844 })
  await openAsHost(page, '/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  const street = page.getByLabel('Calle')
  await expect(street).toBeVisible()
  const borders = await street.evaluate((element) => {
    const style = getComputedStyle(element)
    return [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth]
  })
  expect(borders.every((width) => Number.parseFloat(width) > 0)).toBe(true)
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
