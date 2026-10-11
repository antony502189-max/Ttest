import { expect, test, type Page } from '@playwright/test'

async function openOwnedListings(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/mis-anuncios')
  await expect(page.locator('.manage-card').first()).toBeVisible()
}

test.describe('owner listing manager reference-inspired redesign', () => {
  for (const width of [320, 390, 430, 768, 1280]) {
    test(`usable layout, hierarchy and actions at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 })
      await openOwnedListings(page)
      const first = page.locator('.manage-card').first()
      await expect(first.locator('.manage-card__image img')).toBeVisible()
      await expect(first.locator('.manage-card__image-count')).toBeVisible()
      await expect(first.locator('.manage-card__main h2')).toBeVisible()
      await expect(first.getByTestId('owner-rental-type')).toBeVisible()
      await expect(first.locator('.manage-actions')).toBeVisible()
      const edit = first.locator('a[href*="/editar"]')
      const remove = first.getByRole('button', { name: /^Eliminar / })
      const more = first.getByRole('button', { name: /Más acciones para / })
      await expect(edit).toBeVisible()
      await expect(remove).toBeVisible()
      await expect(more).toBeVisible()
      for (const action of [edit, remove, more]) {
        const rect = await action.boundingBox()
        expect(rect, `missing tap target: ${width}`).not.toBeNull()
        expect(rect!.height).toBeGreaterThanOrEqual(44)
        expect(rect!.width).toBeGreaterThanOrEqual(width < 768 ? 65 : 115)
      }

      if (width < 768) {
        const [imageRect, detailsRect, promoRect, actionsRect] = await Promise.all([
          first.locator('.manage-card__image').boundingBox(),
          first.locator('.manage-card__main').boundingBox(),
          first.locator('.manage-card__promotion').boundingBox(),
          first.locator('.manage-actions').boundingBox(),
        ])
        expect(imageRect).not.toBeNull()
        expect(detailsRect).not.toBeNull()
        expect(promoRect).not.toBeNull()
        expect(actionsRect).not.toBeNull()
        expect(detailsRect!.x).toBeGreaterThan(imageRect!.x)
        expect(promoRect!.y).toBeGreaterThanOrEqual(imageRect!.y + imageRect!.height - 2)
        expect(actionsRect!.y).toBeGreaterThan(promoRect!.y + promoRect!.height - 2)
        const [editRect, deleteRect, moreRect] = await Promise.all([edit.boundingBox(), remove.boundingBox(), more.boundingBox()])
        expect(editRect!.x).toBeLessThan(deleteRect!.x)
        expect(deleteRect!.x).toBeLessThan(moreRect!.x)
      }
      const viewport = await page.evaluate(() => ({
        doc: document.documentElement.scrollWidth,
        width: document.documentElement.clientWidth,
      }))
      expect(viewport.doc).toBeLessThanOrEqual(viewport.width + 1)
    })
  }

  test('status filtering is available and preserves property-specific controls on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openOwnedListings(page)
    const selector = page.getByLabel('Estado')
    await expect(selector).toBeVisible()
    await expect(page.locator('.manage-card')).toHaveCount(3)
    await selector.selectOption('Publicado')
    await expect(page.locator('.manage-card')).toHaveCount(2)
    await selector.selectOption('Todos')
    await expect(page.locator('.manage-card')).toHaveCount(3)

    const card = page.locator('.manage-card').first()
    await card.getByRole('button', { name: /Más acciones para / }).click()
    await expect(page.getByRole('menuitem', { name: 'Cerrar anuncio' })).toBeVisible()
    await page.keyboard.press('Escape')
    await card.getByRole('button', { name: /^Eliminar / }).click()
    await expect(page.getByRole('alertdialog', { name: '¿Eliminar este anuncio?' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(card).toBeVisible()
  })

  test('TOP interaction selects the current listing, not a generic unrelated card', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openOwnedListings(page)
    const first = page.locator('.manage-card').first()
    const id = await first.getAttribute('data-listing-id')
    expect(id).toBeTruthy()
    await first.getByTestId('owner-top-promote-button').click()
    await expect(page.locator(`[data-testid="owner-top-option"][data-listing-id="${id}"]`)).toHaveClass(/is-selected/)
    await expect(page.getByTestId('owner-top-next-step')).toBeVisible()
  })
})
