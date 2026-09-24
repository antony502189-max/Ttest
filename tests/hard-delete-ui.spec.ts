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

test('local owner delete is available without the retired email allowlist', async ({ page }) => {
  await openMyListings(page, user('host@example.test', true))
  await page.getByLabel(/Más acciones para/).first().click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toBeVisible()

  await page.keyboard.press('Escape')
  await openMyListings(page, user('ordinary-unverified@example.test', false))
  await page.getByLabel(/Más acciones para/).first().click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toBeVisible()
})

test('owner delete is hidden for imported listings', async ({ page }) => {
  await openMyListings(page, user('host@example.test', true))
  await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    payload.data = (payload.data ?? []).map((listing: { ownerUserId?: string }) =>
      listing.ownerUserId === 'host-demo' ? { ...listing, isExternal: true } : listing
    )
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
  })
  await page.reload()
  await page.getByLabel(/Más acciones para/).first().click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toHaveCount(0)
})

test('the authenticated notification center is reachable without adding a fifth mobile tab', async ({ page }) => {
  await openMyListings(page, user('host@example.test', true))
  await page.goto('/#/notificaciones')
  await expect(page.getByRole('heading', { name: 'Notificaciones', exact: true })).toBeVisible()
  await expect(page.getByText('Aún no tienes notificaciones')).toBeVisible()
  await expect(page.locator('.bottom-nav__item')).toHaveCount(4)
})
