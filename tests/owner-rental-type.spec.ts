import { expect, test } from '@playwright/test'

test('owner cards show the existing rental labels without adding them to public cards', async ({ page }) => {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/mis-anuncios')

  const cards = page.locator('.manage-card')
  await expect(cards).toHaveCount(3)
  await expect(cards.nth(0).getByTestId('owner-rental-type')).toHaveText('Larga estancia')
  await expect(cards.nth(2).getByTestId('owner-rental-type')).toHaveText('Alquiler vacacional')

  await page.goto('/#/buscar')
  await expect(page.locator('[data-testid="owner-rental-type"]')).toHaveCount(0)
})
