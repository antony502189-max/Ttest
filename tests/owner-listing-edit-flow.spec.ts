import { expect, test, type Page } from '@playwright/test'

async function fillMissingEquipment(page: Page) {
  for (const [selector, value] of [['#edit-bedding', 'included'], ['#edit-refrigerator', 'shared'], ['#edit-balcony', 'no'], ['#edit-washing', 'shared']] as const) {
    const field = page.locator(selector)
    if (await field.inputValue() === '') await field.selectOption(value)
  }
}

test('mobile owner can open, edit and save a listing even with tenant product role', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  const listingId = await page.evaluate(() => {
    const key = '112233:listings:v3'
    const payload = JSON.parse(localStorage.getItem(key) ?? '{"version":3,"data":[]}')
    const first = payload.data[0]
    first.ownerUserId = 'tenant-demo'
    first.userCreated = true
    localStorage.setItem(key, JSON.stringify(payload))
    localStorage.setItem('112233:session:v1', JSON.stringify('tenant-demo'))
    return first.id as string
  })
  await page.reload()
  await page.goto('/#/mis-anuncios')
  await expect(page.locator('.manage-card')).toHaveCount(1)
  await page.getByRole('link', { name: /editar/i }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios\/.+\/editar$/)
  await expect(page.getByRole('heading', { name: /editar habitación/i })).toBeVisible()
  await expect(page.locator('.stepper')).toHaveCount(0)

  await fillMissingEquipment(page)
  const title = `Mobile edit ${Date.now()}`
  await page.locator('#edit-title').fill(title)
  await page.getByRole('button', { name: /guardar cambios/i }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await expect(page.locator('.manage-card').filter({ hasText: title })).toBeVisible()
  expect(listingId).toBeTruthy()
})

test('a user still cannot edit a listing owned by another account', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  const listingId = await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{"data":[]}')
    localStorage.setItem('112233:session:v1', JSON.stringify('tenant-demo'))
    return payload.data[0].id as string
  })
  await page.reload()
  await page.goto(`/#/mis-anuncios/${encodeURIComponent(listingId)}/editar`)
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await expect(page.getByRole('heading', { name: /editar/i })).toHaveCount(0)
})
