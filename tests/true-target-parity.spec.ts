import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { expect, test } from '@playwright/test'

test('capture and gate the mandatory current Idealista-derived target states', async ({ page }) => {
  const output = path.join(process.cwd(), 'artifacts', 'true-target-parity')
  await mkdir(output, { recursive: true })
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.setViewportSize({ width: 390, height: 844 })

  const targets = [
    ['home', '/#/', '.m2-home'],
    ['location', '/#/?panel=ubicacion', '[data-testid="location-screen"]'],
    ['results', '/#/buscar?q=Tenerife', '[data-testid="mobile-results"]'],
    ['map', '/#/buscar?q=Tenerife&vista=mapa', '[data-testid="map-search"]'],
    ['phone', '/#/?panel=telefono', '[data-testid="phone-search-screen"]'],
    ['menu', '/#/menu', '.m2-menu'],
  ] as const

  for (const [name, route, selector] of targets) {
    await page.goto(route)
    await expect(page.locator(selector)).toBeVisible()
    await page.screenshot({ path: path.join(output, `${name}.png`), animations: 'disabled' })
  }
})
