import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const phase = process.env.FINAL_DELTA_PHASE === 'before' ? 'before' : 'after'
const output = path.join(process.cwd(), 'artifacts', 'final-mobile-delta', phase)

async function settle(page: Page) {
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
}

async function screenshot(page: Page, name: string) {
  await writeFile(path.join(output, `${name}.png`), await page.screenshot({ animations: 'disabled' }))
}

async function capture(page: Page, name: string, route: string, width = 390, height = 844) {
  await page.setViewportSize({ width, height })
  await page.goto(route)
  await settle(page)
  const dimensions = await page.evaluate(() => ({
    documentWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
    viewportWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.documentWidth, `${name} overflow`).toBeLessThanOrEqual(dimensions.viewportWidth + 1)
  await screenshot(page, name)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('capture unmasked final mobile delta evidence', async ({ page }) => {
  test.setTimeout(180_000)
  await mkdir(output, { recursive: true })

  for (const [name, route, width, height] of [
    ['home-320x568', '/#/', 320, 568],
    ['home-360x800', '/#/', 360, 800],
    ['home-390x844', '/#/', 390, 844],
    ['home-412x915', '/#/', 412, 915],
    ['search-list-390x844', '/#/buscar?q=Tenerife&alquiler=long', 390, 844],
    ['search-map-390x844', '/#/buscar?q=Tenerife&alquiler=long&vista=mapa', 390, 844],
    ['listing-390x844', '/#/habitacion/arme%C3%B1ime-luminosa-01', 390, 844],
    ['menu-390x844', '/#/menu', 390, 844],
    ['messages-390x844', '/#/mensajes', 390, 844],
  ] as const) {
    await capture(page, name, route, width, height)
  }

  await page.setViewportSize({ width: 390, height: 700 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await page.getByTestId('mobile-results').getByRole('button', { name: 'Filtros' }).click()
  await expect(page.locator('.m2-results-filter')).toBeVisible()
  await screenshot(page, 'filters-390x700')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await page.locator('.m2-select-row').click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
  await screenshot(page, 'location-390x844')

  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await capture(page, 'profile-390x844', '/#/perfil')
  await capture(page, 'publish-390x844', '/#/publicar')

  await page.evaluate(() => localStorage.setItem('112233:language:v1', 'ru'))
  await capture(page, 'home-ru-390x844', '/#/')
  await capture(page, 'search-ru-390x844', '/#/buscar?q=Tenerife&alquiler=long')
})
