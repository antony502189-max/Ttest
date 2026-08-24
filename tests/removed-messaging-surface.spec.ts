import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('removed messaging surface has no mobile tab, route or listing entry point', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')

  const nav = page.locator('.m2-bottom-nav')
  await expect(nav.locator('button')).toHaveCount(4)
  await expect(nav).not.toContainText('Chat')
  await expect(nav).not.toContainText('Mensajes')

  await page.goto('/#/menu')
  const menuMain = page.locator('#main-content')
  await expect(menuMain).not.toContainText('Chat')
  await expect(menuMain).not.toContainText('Mensajes')

  await page.goto('/#/habitacion/arme%C3%B1ime-luminosa-01')
  await expect(page.getByRole('button', { name: 'Enviar mensaje' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Chat' })).toHaveCount(0)

  await page.goto('/#/mensajes')
  await expect(page).toHaveURL(/#\/$/)
  await expect(page.locator('.m2-home')).toBeVisible()
})

test('desktop navigation exposes no messaging destination', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/#/')
  await expect(page.locator('.site-header')).not.toContainText('Mensajes')
  await expect(page.locator('.site-header')).not.toContainText('Chat')
  await expect(page.locator('a[href="#/mensajes"], a[href="/mensajes"]')).toHaveCount(0)
})