import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { expect, test } from '@playwright/test'

test('capture the current screenshot-locked live matrix', async ({ page }) => {
  const output = path.join(process.cwd(), 'artifacts', 'screenshot-locked', 'after-live')
  await mkdir(output, { recursive: true })
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))

  for (const [name, route, width, height] of [
    ['mobile-home', '/#/', 390, 844],
    ['mobile-results', '/#/buscar?q=Tenerife', 390, 844],
    ['mobile-location', '/#/?panel=ubicacion', 390, 844],
    ['mobile-map', '/#/buscar?q=Tenerife&vista=mapa', 390, 844],
    ['desktop-results', '/#/buscar?q=Tenerife', 1440, 900],
    ['listing', '/#/habitacion/arme%C3%B1ime-luminosa-01', 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height })
    await page.goto(route)
    await expect(page.locator('#root')).not.toBeEmpty()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true)
    await page.screenshot({ path: path.join(output, `${name}.png`), animations: 'disabled' })
  }
})
