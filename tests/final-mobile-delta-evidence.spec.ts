import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const phase = process.env.FINAL_DELTA_PHASE === 'before' ? 'before' : 'after'
const output = path.join(process.cwd(), 'artifacts', 'final-mobile-delta', phase)

async function screenshot(page: Page, destination: string) {
  const image = await page.screenshot({ animations: 'disabled' })
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try { await writeFile(destination, image); return } catch (error) {
      if (attempt === 4) throw error
      await page.waitForTimeout(200 * (attempt + 1))
    }
  }
}

async function settle(page: Page) {
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.waitForLoadState('domcontentloaded')
  await page.evaluate(async () => { await document.fonts.ready })
}

async function capture(page: Page, name: string, route: string, width = 390, height = 844) {
  await page.setViewportSize({ width, height })
  await page.goto(route)
  await settle(page)
  const overflow = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
    elements: [...document.querySelectorAll<HTMLElement>('body *')]
      .filter((element) => { const box = element.getBoundingClientRect(); return box.right > document.documentElement.scrollWidth + 1 || box.left < -1 })
      .slice(0, 8)
      .map((element) => ({ tag: element.tagName, className: String(element.className), right: element.getBoundingClientRect().right })),
  }))
  expect(overflow.documentWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.viewportWidth + 1)
  await screenshot(page, path.join(output, `${name}.png`))
}

async function setLocalState(page: Page, state: { language?: 'es' | 'en' | 'ru'; session?: string | null }) {
  await page.goto('/#/')
  await page.evaluate(({ language, session }) => {
    if (language) localStorage.setItem('112233:language:v1', language)
    else localStorage.removeItem('112233:language:v1')
    localStorage.setItem('112233:session:v1', JSON.stringify(session ?? null))
  }, state)
}

test('capture unmasked final mobile delta evidence', async ({ page }) => {
  test.setTimeout(180_000)
  await mkdir(output, { recursive: true })

  await capture(page, 'home-320x568', '/#/', 320, 568)
  await capture(page, 'home-360x800', '/#/', 360, 800)
  await capture(page, 'home-390x844', '/#/', 390, 844)
  await capture(page, 'home-412x915', '/#/', 412, 915)
  await capture(page, 'search-list-390x844', '/#/buscar?q=Tenerife&alquiler=long')
  await capture(page, 'search-map-390x844', '/#/buscar?q=Tenerife&alquiler=long&vista=mapa')

  await page.setViewportSize({ width: 390, height: 700 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await settle(page)
  await page.getByRole('button', { name: /Todos los filtros/ }).click()
  await expect(page.getByRole('heading', { name: 'Filtros' })).toBeVisible()
  await screenshot(page, path.join(output, 'filters-390x700.png'))

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await settle(page)
  await page.getByRole('button', { name: /Abrir selección de ubicación/ }).first().click()
  await expect(page.getByRole('heading', { name: '¿Dónde buscas?' })).toBeVisible()
  await screenshot(page, path.join(output, 'location-390x844.png'))

  await capture(page, 'listing-390x844', '/#/habitacion/arme%C3%B1ime-luminosa-01')
  await capture(page, 'menu-390x844', '/#/menu')
  await capture(page, 'messages-390x844', '/#/mensajes')

  await setLocalState(page, { session: 'host-demo' })
  await capture(page, 'profile-390x844', '/#/perfil')
  await capture(page, 'publish-390x844', '/#/publicar')

  await setLocalState(page, { language: 'ru' })
  await capture(page, 'home-ru-390x844', '/#/')
  await capture(page, 'search-ru-390x844', '/#/buscar?q=Tenerife&alquiler=long')
})
