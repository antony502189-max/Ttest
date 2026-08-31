import { expect, test } from '@playwright/test'

const cases = [
  { language: 'es', appearance: 'Apariencia' },
  { language: 'en', appearance: 'Appearance' },
  { language: 'ru', appearance: 'Внешний вид' },
] as const

for (const { language, appearance } of cases) {
  test(`appearance setting stays removed and light-only in ${language}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.addInitScript((lang) => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', lang)
      localStorage.setItem('112233:appearance:v1', 'dark')
    }, language)

    await page.goto('/#/menu')
    await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)

    await expect(page.locator('.m2-menu')).toBeVisible()
    await expect(page.locator('.m2-menu-row').filter({ hasText: appearance })).toBeHidden()

    const root = page.locator('html')
    await expect(root).toHaveClass(/site-theme-light/)
    await expect(root).not.toHaveClass(/site-theme-dark/)
    await expect(root).toHaveAttribute('data-appearance', 'light')
    expect(await page.evaluate(() => document.documentElement.style.colorScheme)).toBe('light')
    expect(await page.evaluate(() => localStorage.getItem('112233:appearance:v1'))).toBeNull()
  })
}
