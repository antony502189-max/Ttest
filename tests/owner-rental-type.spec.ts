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


test('mobile owner card shows delete directly below edit', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/mis-anuncios')

  const card = page.locator('.manage-card').first()
  const edit = card.locator('a[href*="/editar"]')
  const remove = card.getByRole('button', { name: /^Eliminar / })

  await expect(edit).toBeVisible()
  await expect(remove).toBeVisible()

  const editBox = await edit.boundingBox()
  const removeBox = await remove.boundingBox()
  expect(editBox).not.toBeNull()
  expect(removeBox).not.toBeNull()
  expect(removeBox!.y).toBeGreaterThan(editBox!.y)
  const editCenter = editBox!.x + editBox!.width / 2
  const removeCenter = removeBox!.x + removeBox!.width / 2
  expect(Math.abs(removeCenter - editCenter)).toBeLessThanOrEqual(2)
})
