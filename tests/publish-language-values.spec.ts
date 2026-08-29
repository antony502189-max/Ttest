import { expect, test, type Page } from '@playwright/test'

async function chooseLanguage(page: Page, code: 'ES' | 'RU') {
  const trigger = page.locator('.site-header .language-switcher')
  await expect(trigger).toHaveAttribute('data-state', 'closed')
  await trigger.click()
  await expect(trigger).toHaveAttribute('data-state', 'open')
  await page.getByRole('menuitemradio').filter({ hasText: code }).click()
  await expect(trigger).toContainText(code)
  await expect(trigger).toHaveAttribute('data-state', 'closed')
}

test('Russian publication keeps canonical room values and preserves them when switching to Spanish', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.removeItem('112233:listing-draft:v3')
    localStorage.removeItem('112233:listing-draft:v2')
  })

  await page.goto('/#/publicar')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')

  await page.getByRole('button', { name: 'Продолжить' }).click()
  await page.getByRole('button', { name: 'Продолжить' }).click()

  const bathroom = page.locator('#publish-bathroom')
  const toilet = page.locator('#publish-toilet')
  const shower = page.locator('#publish-shower')
  const kitchen = page.locator('#publish-kitchen')

  await bathroom.selectOption({ label: 'Собственная ванная' })
  await toilet.selectOption({ label: 'Собственный туалет' })
  await shower.selectOption({ label: 'Собственный душ' })
  await kitchen.selectOption({ label: 'Собственная кухня' })

  await expect(bathroom).toHaveValue('Baño privado')
  await expect(toilet).toHaveValue('Aseo privado')
  await expect(shower).toHaveValue('Ducha privada')
  await expect(kitchen).toHaveValue('Cocina privada')

  await expect.poll(() => page.evaluate(() => {
    const raw = localStorage.getItem('112233:listing-draft:v3')
    if (!raw) return null
    const draft = JSON.parse(raw).data
    return [draft.bathroom, draft.toilet, draft.shower, draft.kitchen]
  })).toEqual(['Baño privado', 'Aseo privado', 'Ducha privada', 'Cocina privada'])

  await chooseLanguage(page, 'ES')
  await expect(page.locator('html')).toHaveAttribute('lang', 'es')

  await expect(bathroom).toHaveValue('Baño privado')
  await expect(toilet).toHaveValue('Aseo privado')
  await expect(shower).toHaveValue('Ducha privada')
  await expect(kitchen).toHaveValue('Cocina privada')
  await expect(bathroom.locator('option:checked')).toHaveText('Baño privado')
  await expect(toilet.locator('option:checked')).toHaveText('Aseo privado')
  await expect(shower.locator('option:checked')).toHaveText('Ducha privada')
  await expect(kitchen.locator('option:checked')).toHaveText('Cocina privada')
})
