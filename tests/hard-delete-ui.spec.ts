import { expect, test } from '@playwright/test'

const user = (email: string, emailVerified: boolean) => ({
  id: 'host-demo', name: 'Delete profile', email, password: '', passwordHash: '', role: 'host',
  phone: '', whatsapp: '', telegram: '', about: '', initials: 'DP', showPhone: false, showWhatsApp: false, emailVerified, blocked: false,
})

async function openMyListings(page: import('@playwright/test').Page, profile: ReturnType<typeof user>) {
  await page.addInitScript((stored) => {
    localStorage.setItem('112233:users:v1', JSON.stringify(stored.users))
    localStorage.setItem('112233:session:v1', JSON.stringify(stored.session))
  }, { users: [profile], session: profile.id })
  await page.goto('/#/mis-anuncios')
}

test('hard delete is hidden for every unverified or non-allowlisted UI profile', async ({ page }) => {
  await openMyListings(page, user('host@example.test', true))
  await page.getByLabel(/Más acciones para/).first().click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toHaveCount(0)

  await page.keyboard.press('Escape')
  await openMyListings(page, user('antony502189@gmail.com', false))
  await page.getByLabel(/Más acciones para/).first().click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toHaveCount(0)
})

test('hard delete is offered only to a verified canonical profile', async ({ page }) => {
  await openMyListings(page, user(' TF.SHULER@gmail.com ', true))
  await page.getByLabel(/Más acciones para/).first().click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toBeVisible()
})

test('the authenticated notification center is reachable without adding a fifth mobile tab', async ({ page }) => {
  await openMyListings(page, user('host@example.test', true))
  await page.goto('/#/notificaciones')
  await expect(page.getByRole('heading', { name: 'Notificaciones', exact: true })).toBeVisible()
  await expect(page.getByText('Aún no tienes notificaciones')).toBeVisible()
  await expect(page.locator('.bottom-nav__item')).toHaveCount(4)
})
