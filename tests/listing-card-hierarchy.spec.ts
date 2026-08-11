import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test, type Page } from '@playwright/test'

const hierarchyCss = readFileSync(fileURLToPath(new URL('../src/listing-card-content-order.css', import.meta.url)), 'utf8')

async function finishMobileOnboarding(page: Page) {
  await page.goto('/')
  if (await page.getByTestId('open-location').isVisible().catch(() => false)) return
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

test('every supported listing-card variant has the approved restrictions-price-details ordering rule', () => {
  expect(hierarchyCss).toContain('.property-card .property-card__body-link > .badge-row')
  expect(hierarchyCss).toContain('.property-card .property-card__body-link > .card-topline')
  expect(hierarchyCss).toContain('.m2-result-card__content > .m2-result-card__badges')
  expect(hierarchyCss).toContain('.m2-result-card__content > .m2-result-card__price')
  expect(hierarchyCss).toContain('.m2-map-listing-preview__body > .m2-map-listing-preview__requirements')
  expect(hierarchyCss).toContain('.m2-map-listing-preview__body > strong')
  expect(hierarchyCss).toContain('.selected-listing-sheet__content > ul')
  expect(hierarchyCss).toContain('.selected-listing-sheet__content > strong')
})

test('all mobile result cards render restrictions above price and details', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await finishMobileOnboarding(page)
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByTestId('open-location').click()

  const cards = page.locator('.m2-result-card')
  await expect(cards.first()).toBeVisible()
  const count = await cards.count()
  expect(count).toBeGreaterThan(0)

  for (let index = 0; index < count; index += 1) {
    const card = cards.nth(index)
    const positions = await card.evaluate((element) => {
      const rectTop = (selector: string) => element.querySelector<HTMLElement>(selector)?.getBoundingClientRect().top ?? Number.POSITIVE_INFINITY
      return {
        restrictions: rectTop('.m2-result-card__badges'),
        price: rectTop('.m2-result-card__price'),
        location: rectTop('.m2-result-card__location'),
        title: rectTop('h2'),
        facts: rectTop('.m2-result-card__facts'),
      }
    })
    expect(positions.restrictions).toBeLessThan(positions.price)
    expect(positions.price).toBeLessThan(positions.location)
    expect(positions.price).toBeLessThan(positions.title)
    expect(positions.price).toBeLessThan(positions.facts)
  }
})

test('desktop full cards render restrictions first, price second and description afterwards', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')

  const card = page.locator('.property-card:not(.property-card--compact)').first()
  await expect(card).toBeVisible()
  const positions = await card.evaluate((element) => {
    const rectTop = (selector: string) => element.querySelector<HTMLElement>(selector)?.getBoundingClientRect().top ?? Number.POSITIVE_INFINITY
    return {
      restrictions: rectTop('.badge-row'),
      price: rectTop('.card-topline'),
      description: rectTop('.property-description'),
    }
  })

  expect(positions.restrictions).toBeLessThan(positions.price)
  expect(positions.price).toBeLessThan(positions.description)
})
