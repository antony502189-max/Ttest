import { expect, test } from '@playwright/test'

const cases = [
  { language: 'es', label: 'Predeterminada (clara)' },
  { language: 'en', label: 'Default (light)' },
  { language: 'ru', label: 'По умолчанию (светлый)' },
] as const

for (const { language, label } of cases) {
  test(`white appearance menu copy is correct in ${language}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addInitScript((lang) => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', lang)
    }, language)

    await page.goto('/#/menu')
    await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)

    await expect(page.locator('.m2-menu')).toBeVisible()
    await expect(page.getByText(label, { exact: true })).toBeVisible()
  })
}
