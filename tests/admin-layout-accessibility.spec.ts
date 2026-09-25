import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

async function openAdmin(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo'))
  })
  await page.goto('/#/admin')
  await expect(page.locator('.admin-page')).toBeVisible()
}

test('admin desktop stays readable and contained without global bottom navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await openAdmin(page)

  await expect(page.locator('.bottom-nav')).toHaveCount(0)
  await expect(page.locator('.admin-sidebar')).toBeVisible()
  await expect(page.locator('.admin-user')).toBeVisible()

  const metrics = await page.evaluate(() => {
    const root = document.querySelector<HTMLElement>('.admin-page')
    const navButton = document.querySelector<HTMLElement>('.admin-sidebar nav button')
    const heading = document.querySelector<HTMLElement>('.admin-main h1')
    if (!root || !navButton || !heading) throw new Error('Admin layout did not render')
    return {
      pageFont: parseFloat(getComputedStyle(root).fontSize),
      navFont: parseFloat(getComputedStyle(navButton).fontSize),
      headingFont: parseFloat(getComputedStyle(heading).fontSize),
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
    }
  })

  expect(metrics.pageFont).toBeGreaterThanOrEqual(17)
  expect(metrics.navFont).toBeGreaterThanOrEqual(16)
  expect(metrics.headingFont).toBeGreaterThanOrEqual(30)
  expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.viewportWidth + 1)
})

test('admin mobile navigation remains readable and does not overflow the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openAdmin(page)

  await expect(page.locator('.bottom-nav')).toHaveCount(0)
  const navigation = page.locator('.admin-sidebar nav')
  await expect(navigation).toBeVisible()

  const metrics = await page.evaluate(() => {
    const pageRoot = document.querySelector<HTMLElement>('.admin-page')
    const navButton = document.querySelector<HTMLElement>('.admin-sidebar nav button')
    if (!pageRoot || !navButton) throw new Error('Admin mobile layout did not render')
    return {
      pageFont: parseFloat(getComputedStyle(pageRoot).fontSize),
      navFont: parseFloat(getComputedStyle(navButton).fontSize),
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
    }
  })

  expect(metrics.pageFont).toBeGreaterThanOrEqual(16)
  expect(metrics.navFont).toBeGreaterThanOrEqual(16)
  expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.viewportWidth + 1)
})

test('production admin listing actions wrap instead of widening the page', () => {
  const css = readFileSync('src/admin-moderation.css', 'utf8')
  const productionAdmin = readFileSync('src/pages/AdminPage.tsx', 'utf8')
  const layout = readFileSync('src/components/layout.tsx', 'utf8')

  expect(productionAdmin).toContain('className="admin-listing-actions"')
  expect(css).toMatch(/\.admin-listing-actions\s*\{[\s\S]*?flex-wrap:\s*wrap;/)
  expect(css).toMatch(/\.admin-main\s*\{[\s\S]*?overflow-x:\s*clip;/)
  expect(layout).toContain("const hideBottomNavigation = pathname === '/admin'")
})
