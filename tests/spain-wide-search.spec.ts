import { expect, test } from '@playwright/test'

const searchParams = (url: string) => new URLSearchParams(new URL(url).hash.split('?')[1])

test('home search accepts a mainland municipality with the selected occupant profile', async ({ page }) => {
  await page.goto('/')
  const form = page.locator('.mandatory-home-search')
  await form.getByRole('button', { name: 'Sin restricción', exact: true }).click()
  await form.getByLabel('¿Dónde buscas habitación?').fill('Madrid')
  await form.getByRole('button', { name: 'Ver habitaciones' }).click()
  await expect(page).toHaveURL(/\/buscar\?q=Madrid/)
  expect(searchParams(page.url()).get('alquiler')).toBe('long')
})

test('results search accepts a village and clears stale Tenerife area filters', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&zonas=Arme%C3%B1ime&alquiler=long')
  await page.getByLabel('Ciudad, barrio o zona').fill('Albarracín')
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect.poll(() => searchParams(page.url()).get('q')).toBe('Albarracín')
  expect(searchParams(page.url()).get('zonas')).toBeNull()
  await expect(page.locator('#results-title')).toContainText('Albarracín')
})

test('mobile results name the actual mainland search location', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/buscar?q=A%20Coru%C3%B1a&alquiler=long')
  const header = page.locator('.m2-results__header strong')
  await expect(header).toContainText('A Coruña')
  await expect(header).not.toContainText('Tenerife')
})
