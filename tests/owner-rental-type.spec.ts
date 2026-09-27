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
  const longBadge = cards.nth(0).getByTestId('owner-rental-type')
  const holidayBadge = cards.nth(2).getByTestId('owner-rental-type')
  await expect(longBadge).toHaveText('Larga estancia')
  await expect(longBadge).toHaveClass(/owner-rental-type--long/)
  await expect(holidayBadge).toHaveText('Alquiler vacacional')
  await expect(holidayBadge).toHaveClass(/owner-rental-type--holiday/)

  const priceLine = cards.nth(0).locator('.manage-card__main > p').first()
  const priceBox = await priceLine.boundingBox()
  const badgeBox = await longBadge.boundingBox()
  expect(priceBox).not.toBeNull()
  expect(badgeBox).not.toBeNull()
  expect(badgeBox!.y).toBeGreaterThan(priceBox!.y)

  const topCta = page.getByTestId('owner-top-cta')
  await expect(topCta).toBeVisible()
  await expect(cards.first().getByTestId('owner-top-status')).toHaveAttribute('data-top-active', 'false')
  await expect(cards.first().getByTestId('owner-top-status')).toContainText('No estás en TOP')

  const ctaBox = await topCta.boundingBox()
  const firstCardBox = await cards.first().boundingBox()
  expect(ctaBox).not.toBeNull()
  expect(firstCardBox).not.toBeNull()
  expect(ctaBox!.y).toBeLessThan(firstCardBox!.y)

  await topCta.getByRole('button').click()
  await expect(page.getByTestId('owner-top-option')).not.toHaveCount(0)
  await expect(page.getByTestId('owner-top-next-step')).toBeVisible()
  await page.keyboard.press('Escape')

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


test('owner card shows the real active TOP end date from listing data', async ({ page }) => {
  await page.goto('/')
  await page.waitForFunction(() => Boolean(localStorage.getItem('112233:listings:v3')))
  const seeded = await page.evaluate(() => {
    const stored = JSON.parse(localStorage.getItem('112233:listings:v3')!)
    const target = stored.data.find((item: { ownerUserId?: string; status?: string }) => item.ownerUserId === 'host-demo' && item.status === 'Publicado')
    if (!target) throw new Error('Missing published owner fixture')
    target.promoted = true
    target.promotionEndsAt = '2026-10-05T00:00:00.000Z'
    return { payload: JSON.stringify(stored), listingId: target.id as string }
  })
  await page.evaluate(({ payload }) => {
    localStorage.setItem('112233:listings:v3', payload)
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  }, seeded)

  await page.goto('/?owner-top-status=1#/mis-anuncios')
  const ownerCard = page.locator(`.manage-card[data-listing-id="${seeded.listingId}"]`)
  await expect(ownerCard).toBeVisible()
  const status = ownerCard.getByTestId('owner-top-status')
  await expect(status).toHaveAttribute('data-top-active', 'true')
  await expect(status).toContainText('Estás en TOP hasta')
  await expect(status).toContainText('2026')
  await expect(status).toContainText('👍')
})
