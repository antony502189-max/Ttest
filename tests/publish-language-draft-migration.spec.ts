import { expect, test } from '@playwright/test'

test('localized legacy publication values hydrate back to canonical domain values', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:listing-draft:v3', JSON.stringify({
      version: 3,
      data: {
        bathroom: 'Собственная ванная',
        toilet: 'Собственный туалет',
        shower: 'Собственный душ',
        kitchen: 'Собственная кухня',
      },
    }))
  })

  await page.goto('/#/publicar')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')

  const migrated = await page.evaluate(() => {
    const raw = localStorage.getItem('112233:listing-draft:v3')
    return raw ? JSON.parse(raw).data : null
  })
  expect(migrated).toMatchObject({
    bathroom: 'Baño privado',
    toilet: 'Aseo privado',
    shower: 'Ducha privada',
    kitchen: 'Cocina privada',
  })

  const continueButton = page.getByRole('button', { name: 'Продолжить' })
  await continueButton.click()
  await continueButton.click()

  await expect(page.locator('#publish-bathroom')).toHaveValue('Baño privado')
  await expect(page.locator('#publish-toilet')).toHaveValue('Aseo privado')
  await expect(page.locator('#publish-shower')).toHaveValue('Ducha privada')
  await expect(page.locator('#publish-kitchen')).toHaveValue('Cocina privada')

  await expect(page.locator('#publish-bathroom option:checked')).toHaveText('Собственная ванная')
  await expect(page.locator('#publish-toilet option:checked')).toHaveText('Собственный туалет')
  await expect(page.locator('#publish-shower option:checked')).toHaveText('Собственный душ')
  await expect(page.locator('#publish-kitchen option:checked')).toHaveText('Собственная кухня')
})
