import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
})

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/#/acceso')
  const input = page.getByLabel(/^email$/i)
  if (!(await input.isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /iniciar sesión con email/i }).click()
  }
  await input.fill(email)
  await page.locator('#login-password').or(page.getByLabel(/^contraseña$/i)).fill(password)
  const submit = page.getByRole('button', { name: /^acceder$/i })
  if (await submit.isVisible().catch(() => false)) await submit.click()
  else await page.getByRole('button', { name: /iniciar sesión con email/i }).click()
  await expect(page).not.toHaveURL(/acceso/)
  await page.goto('/#/menu')
  await expect(page.getByTestId('mobile-menu')).toBeVisible()
}

for (const width of [320, 390, 430]) {
  test(`guest menu has large spaced actions and no admin at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/#/menu')
    const menu = page.getByTestId('mobile-menu')
    await expect(menu).toBeVisible()
    await expect(page.getByTestId('menu-admin-entry')).toHaveCount(0)
    const account = menu.locator('.m2-menu-account-card')
    const property = menu.locator('.m2-menu-section').first()
    const sections = menu.locator('.m2-menu-section')
    await expect(sections).toHaveCount(2)
    await expect(menu.getByRole('button', { name: 'Publica tu anuncio' })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Región de búsqueda España/ })).toBeVisible()
    await expect(menu.getByRole('button', { name: /Idioma Español/ })).toBeVisible()
    await expect(menu.getByText('Buscar agencias para vender')).toHaveCount(0)
    const panel = await menu.evaluate((el) => ({
      viewport: document.documentElement.clientWidth,
      documentWidth: document.documentElement.scrollWidth,
      menuWidth: el.getBoundingClientRect().width,
    }))
    expect(panel.documentWidth).toBeLessThanOrEqual(panel.viewport + 1)
    const accountBox = await account.boundingBox(), propertiesBox = await property.boundingBox()
    expect(accountBox).not.toBeNull()
    expect(propertiesBox).not.toBeNull()
    expect(accountBox!.bottom).toBeLessThan(propertiesBox!.top)
    const rows = menu.locator('.m2-menu-group .m2-menu-row')
    expect(await rows.count()).toBeGreaterThanOrEqual(3)
    for (const row of await rows.all()) {
      const box = await row.boundingBox()
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(60)
      const radius = await row.evaluate((node) => parseFloat(getComputedStyle(node).borderTopLeftRadius))
      expect(radius).toBeGreaterThanOrEqual(24)
    }
  })
}

test('tenant sees account first and profile actions, never administration card', async ({ page }) => {
  await signIn(page, 'inquilina@112233.es', 'demo112233')
  const menu = page.getByTestId('mobile-menu')
  await expect(menu.getByTestId('menu-admin-entry')).toHaveCount(0)
  await expect(menu.getByRole('button', { name: /Ver y crear anuncios/ })).toBeVisible()
  await expect(menu.getByRole('button', { name: 'Editar perfil' })).toBeVisible()
  await expect(menu.getByRole('button', { name: 'Mis campañas publicitarias' })).toBeVisible()
  await menu.getByRole('button', { name: 'Editar perfil' }).click()
  await expect(page).toHaveURL(/#\/perfil/)
})

test('administrator receives the blue admin card above their profile and can open it', async ({ page }) => {
  await signIn(page, 'admin@112233.es', 'admin112233')
  const menu = page.getByTestId('mobile-menu')
  const admin = page.getByTestId('menu-admin-entry')
  await expect(admin).toBeVisible()
  await expect(admin).toContainText('PANEL DE ADMINISTRACIÓN')
  await expect(admin).toContainText('Abrir panel de administración')
  const panelBox = await admin.boundingBox(), accountBox = await menu.locator('.m2-menu-account-card').boundingBox()
  expect(panelBox).not.toBeNull()
  expect(accountBox).not.toBeNull()
  expect(panelBox!.bottom).toBeLessThan(accountBox!.top)
  expect(panelBox!.height).toBeGreaterThan(120)
  const colors = await admin.evaluate((node) => ({
    background: getComputedStyle(node).backgroundImage,
    icon: getComputedStyle(node.querySelector('.m2-menu-admin-card__icon')!).backgroundColor,
  }))
  expect(colors.background).toContain('linear-gradient')
  expect(colors.icon).toBe('rgb(8, 123, 241)')
  await admin.click()
  await expect(page).toHaveURL(/#\/admin/)
})

test('draw-zone button visibly latches on while drawing and releases on cancel', async ({ page }) => {
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Seleccionar ubicación actual' }).click()
  await page.getByTestId('search-map').click()
  const map = page.getByTestId('map-search')
  await expect(map).toBeVisible()
  const button = map.locator('.m2-draw-cta')
  await expect(button).toBeEnabled()
  await expect(button).toHaveAttribute('aria-pressed', 'false')
  await button.click()
  await expect(button).toHaveAttribute('aria-pressed', 'true')
  await expect(button).toContainText('Cancelar dibujo')
  await expect(button).toHaveCSS('background-color', 'rgb(210, 255, 63)')
  const active = await button.evaluate((node) => {
    const style = getComputedStyle(node)
    return { border: parseFloat(style.borderTopWidth), color: style.borderTopColor, shadow: style.boxShadow }
  })
  expect(active.border).toBeGreaterThanOrEqual(3)
  expect(active.shadow).not.toBe('none')
  await button.click()
  await expect(button).toHaveAttribute('aria-pressed', 'false')
  await expect(button).toContainText('Dibujar tu zona')
  await expect(button).not.toHaveCSS('background-color', 'rgb(210, 255, 63)')
})
