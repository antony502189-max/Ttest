import { expect, test, type Page } from '@playwright/test'

async function openOwnerPage(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/mis-anuncios')
  await expect(page.locator('.manage-card').first()).toBeVisible()
}

test.describe('classic owner cards with focused TOP controls', () => {
  for (const width of [320, 390, 430, 768, 1280]) {
    test('vertical right-side actions and readable TOP state at ' + width + 'px', async ({ page }) => {
      await page.setViewportSize({ width, height: 844 })
      await openOwnerPage(page)

      const card = page.locator('.manage-card').first()
      const edit = card.locator('.owner-manage-action--edit')
      const remove = card.locator('.owner-manage-action--delete')
      const more = card.locator('.owner-manage-action--more')
      const cardBox = await card.boundingBox()
      const editBox = await edit.boundingBox()
      const removeBox = await remove.boundingBox()
      const moreBox = await more.boundingBox()

      expect(cardBox).not.toBeNull()
      expect(editBox).not.toBeNull()
      expect(removeBox).not.toBeNull()
      expect(moreBox).not.toBeNull()
      for (const rect of [editBox!, removeBox!, moreBox!]) {
        expect(rect.width).toBeGreaterThanOrEqual(44)
        expect(rect.height).toBeGreaterThanOrEqual(44)
        expect(rect.x).toBeGreaterThan(cardBox!.x + cardBox!.width / 2)
        expect(rect.x + rect.width).toBeLessThanOrEqual(width + 1)
      }
      expect(removeBox!.y).toBeGreaterThanOrEqual(editBox!.y + editBox!.height)
      expect(moreBox!.y).toBeGreaterThanOrEqual(removeBox!.y + removeBox!.height)
      expect(Math.abs(editBox!.x - removeBox!.x)).toBeLessThanOrEqual(2)
      expect(Math.abs(removeBox!.x - moreBox!.x)).toBeLessThanOrEqual(2)

      await expect(edit).toContainText('Editar')
      await expect(remove).toContainText('Eliminar')
      await expect(more).toContainText('Más')
      await expect(card.getByTestId('owner-top-status')).toHaveAttribute('data-top-active', 'false')
      await expect(card.getByTestId('owner-top-status')).toContainText('No estás en TOP')
      await expect(card.getByTestId('owner-top-status').locator('svg.owner-top-state__face')).toBeVisible()
      const rocket = card.getByTestId('owner-top-promote-button')
      await expect(rocket).toBeVisible()
      await expect(rocket.locator('svg.owner-top-rocket')).toBeVisible()
    })
  }

  test('existing edit, delete confirm, More menu and TOP selection still work', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openOwnerPage(page)
    const card = page.locator('.manage-card').first()
    const listingId = await card.getAttribute('data-listing-id')
    expect(listingId).toBeTruthy()
    await expect(card.locator('.owner-manage-action--edit')).toHaveAttribute('href', new RegExp(listingId!.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))

    await card.locator('.owner-manage-action--delete').click()
    await expect(page.getByText('¿Eliminar este anuncio?')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(card).toBeVisible()

    await card.locator('.owner-manage-action--more').click()
    await expect(page.getByRole('menuitem', { name: 'Cerrar anuncio' })).toBeVisible()
    await page.keyboard.press('Escape')

    await card.getByTestId('owner-top-promote-button').click()
    await expect(page.locator('[data-testid="owner-top-option"][data-listing-id="' + listingId + '"]')).toHaveClass(/is-selected/)
    await page.keyboard.press('Escape')
    await expect(card.getByTestId('owner-top-status')).toHaveAttribute('data-top-active', 'false')
  })
})
