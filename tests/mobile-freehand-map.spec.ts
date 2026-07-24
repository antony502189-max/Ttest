import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

test('freehand gesture creates and preserves a selected map area', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()
  await page.getByTestId('draw-zone').click()

  const cancelDrawing = page.getByRole('button', { name: 'Cancelar dibujo' })
  await expect(cancelDrawing).toBeEnabled({ timeout: 20_000 })

  const overlay = page.getByTestId('freehand-overlay')
  await expect(overlay).toBeVisible()
  const box = await overlay.boundingBox()
  expect(box).not.toBeNull()
  if (!box) return

  const left = box.x + box.width * 0.25
  const right = box.x + box.width * 0.72
  const top = box.y + box.height * 0.32
  const bottom = box.y + box.height * 0.68

  await page.mouse.move(left, top)
  await page.mouse.down()
  await page.mouse.move(right, top, { steps: 12 })
  await page.mouse.move(right, bottom, { steps: 10 })
  await page.mouse.move(left, bottom, { steps: 12 })
  await page.mouse.move(left, top, { steps: 10 })
  await page.mouse.up()

  await expect(overlay).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Volver a dibujar' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Eliminar zona' })).toBeVisible()
  await expect(page.locator('.m2-map-screen')).toHaveClass(/has-drawn-zone/)

  await page.getByRole('button', { name: 'Volver', exact: true }).click()
  await page.getByTestId('search-map').click()
  await expect(page.getByRole('button', { name: 'Volver a dibujar' })).toBeEnabled({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Eliminar zona' })).toBeVisible()

  await page.getByRole('button', { name: 'Eliminar zona' }).click()
  await expect(page.getByRole('button', { name: 'Dibujar tu zona' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Eliminar zona' })).toHaveCount(0)
})
