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

test('listing deletion is offered to an ordinary owner regardless of email allowlists', async ({ page }) => {
  await openMyListings(page, user('host@example.test', true))
  await page.getByLabel(/Más acciones para/).first().click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toBeVisible()

  await page.getByRole('menuitem', { name: 'Eliminar' }).click()
  const dialog = page.getByRole('alertdialog', { name: '¿Eliminar este anuncio?' })
  await expect(dialog).toContainText('búsquedas, mapas y Mis anuncios')
  await expect(dialog.getByRole('button', { name: 'Eliminar anuncio' })).toBeVisible()
})

test('listing deletion is also offered when email verification is not the authorization boundary', async ({ page }) => {
  await openMyListings(page, user('another-owner@example.test', false))
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
