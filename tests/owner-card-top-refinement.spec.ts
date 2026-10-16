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

test.describe('owner edit label stays inside its button', () => {
  for (const width of [320, 360, 390, 430, 468]) {
    test(`all locales at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 })
      await openOwnerPage(page)

      for (const [language, expected] of [
        ['ru', 'Изменить'],
        ['es', 'Editar'],
        ['en', 'Edit'],
      ] as const) {
        await page.evaluate((next) => localStorage.setItem('112233:language:v1', next), language)
        await page.reload()
        await expect(page.locator('.manage-card').first()).toBeVisible()
        const edit = page.locator('.manage-card').first().locator('.owner-manage-action--edit')
        const label = edit.locator('.owner-manage-action__label')
        await expect(label).toHaveText(expected)
        await page.evaluate(async () => { await document.fonts.ready })
        const sizes = await edit.evaluate((button) => {
          const label = button.querySelector('.owner-manage-action__label') as HTMLElement
          const parent = button.getBoundingClientRect()
          const child = label.getBoundingClientRect()
          return {
            contained: child.left >= parent.left - 1 && child.right <= parent.right + 1,
            fullText: label.scrollWidth <= label.clientWidth + 1,
          }
        })
        expect(sizes.contained).toBe(true)
        expect(sizes.fullText).toBe(true)
      }
    })
  }
})

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
      const status = card.getByTestId('owner-top-status')
      await expect(status.locator('svg')).toHaveCount(0)
      await expect(status).toHaveCSS('background-color', 'rgb(243, 243, 243)')
      await expect(edit).toHaveCSS('background-color', 'rgb(218, 244, 244)')
      await expect(remove).toHaveCSS('background-color', 'rgb(255, 235, 236)')
      await expect(more).toHaveCSS('background-color', 'rgb(237, 237, 237)')
      const rocket = card.getByTestId('owner-top-promote-button')
      await expect(rocket).toBeVisible()
      await expect(rocket).toHaveCSS('background-color', 'rgb(255, 230, 233)')
      await expect(rocket.locator('svg.owner-top-action__face')).toBeVisible()
      await expect(rocket.locator('svg.owner-top-rocket')).toHaveAttribute('data-top-rocket-active', 'false')
      await expect(rocket.locator('svg.owner-top-rocket image')).toHaveAttribute('href', '/top-rocket-idle.svg')
      const idle = rocket.locator('svg.owner-top-rocket')
      await expect(idle).toHaveCSS('animation-name', 'none')
      const idleAngle = await idle.evaluate((element) => {
        const matrix = new DOMMatrix(getComputedStyle(element).transform)
        return Math.atan2(matrix.b, matrix.a) * (180 / Math.PI)
      })
      expect(idleAngle).toBeCloseTo(0, 1)
    })
  }

  test('active TOP uses reference green palette and smile/rocket in CTA', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    await page.waitForFunction(() => Boolean(localStorage.getItem('112233:listings:v3')))
    const listingId = await page.evaluate(() => {
      const stored = JSON.parse(localStorage.getItem('112233:listings:v3')!)
      const target = stored.data.find((item: { ownerUserId?: string; status?: string }) => item.ownerUserId === 'host-demo' && item.status === 'Publicado')
      if (!target) throw new Error('No owner fixture')
      target.promoted = true
      target.promotionEndsAt = '2026-11-04T00:00:00.000Z'
      localStorage.setItem('112233:listings:v3', JSON.stringify(stored))
      localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      return target.id as string
    })
    // Load a fresh document so the app hydrates the seeded owner and TOP state.
    await page.goto('/?owner-top-status=1#/mis-anuncios')
    const card = page.locator(`.manage-card[data-listing-id="${listingId}"]`)
    await expect(card).toBeVisible()
    const status = card.getByTestId('owner-top-status')
    const action = card.getByTestId('owner-top-manage-button')
    await expect(status).toHaveAttribute('data-top-active', 'true')
    await expect(status.locator('svg')).toHaveCount(0)
    await expect(status).toHaveCSS('background-color', 'rgb(225, 247, 225)')
    await expect(status).toContainText('Estás en TOP')
    await expect(action).toHaveCSS('background-color', 'rgb(209, 248, 205)')
    await expect(action.locator('svg.owner-top-action__face')).toBeVisible()
    await expect(action.locator('svg.owner-top-rocket')).toHaveAttribute('data-top-rocket-active', 'true')
    await expect(action.locator('svg.owner-top-rocket image')).toHaveAttribute('href', '/top-rocket-active.svg')
    const activeRocket = action.locator('svg.owner-top-rocket')
    await expect(activeRocket).toHaveCSS('animation-name', 'none')
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await expect(activeRocket).toHaveCSS('animation-name', 'none')
    const activeAngle = await activeRocket.evaluate((element) => {
      const matrix = new DOMMatrix(getComputedStyle(element).transform)
      return Math.atan2(matrix.b, matrix.a) * (180 / Math.PI)
    })
    expect(activeAngle).toBeCloseTo(0, 1)
    await expect(card.getByTestId('owner-top-promote-button')).toHaveCount(0)
    await action.click()
    await expect(page.locator(`[data-testid="owner-top-option"][data-listing-id="${listingId}"]`)).toHaveClass(/is-selected/)
  })

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
