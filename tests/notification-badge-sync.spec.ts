import { expect, test } from '@playwright/test'

test('notification header badge refreshes immediately after notification state changes', async ({ page }) => {
  let unreadCount = 2
  await page.route('**/api/v1/notifications', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], unreadCount }),
    })
  })

  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()

  const desktopBadge = page.locator('.site-header .notification-count')
  await expect(desktopBadge).toHaveText('2')

  unreadCount = 0
  await page.evaluate(() => window.dispatchEvent(new Event('112233:notifications-updated')))
  await expect(desktopBadge).toHaveCount(0)
})

test('notification center renders system notification copy in Russian', async ({ page }) => {
  await page.route('**/api/v1/notifications', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        unreadCount: 1,
        items: [{
          id: '00000000-0000-4000-8000-000000000777',
          type: 'listing_expired',
          entityListingId: null,
          title: 'Tu anuncio ha finalizado',
          body: 'Spanish backend fallback must not leak into Russian UI.',
          createdAt: '2026-08-25T18:00:00Z',
          readAt: null,
        }],
      }),
    })
  })

  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'ru')
  })
  await page.reload()
  await page.goto('/#/notificaciones')

  await expect(page.getByRole('heading', { name: 'Уведомления' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Срок объявления истёк' })).toBeVisible()
  await expect(page.getByText(/Его можно продлить/)).toBeVisible()
  await expect(page.getByText('Tu anuncio ha finalizado')).toHaveCount(0)
})

test('notification actions never point customers at unavailable listing detail', async ({ page }) => {
  await page.route('**/api/v1/notifications', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fulfill({ status: 204, body: '' })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        unreadCount: 2,
        items: [
          {
            id: '00000000-0000-4000-8000-000000000778',
            type: 'favorite_unavailable',
            entityListingId: 'armeñime-luminosa-01',
            title: 'Un favorito ya no está disponible',
            body: 'Hidden listing',
            createdAt: '2026-08-25T18:00:00Z',
            readAt: null,
          },
          {
            id: '00000000-0000-4000-8000-000000000779',
            type: 'listing_expired',
            entityListingId: 'armeñime-luminosa-01',
            title: 'Tu anuncio ha finalizado',
            body: 'Expired listing',
            createdAt: '2026-08-25T17:00:00Z',
            readAt: null,
          },
        ],
      }),
    })
  })

  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  await page.reload()
  await page.goto('/#/notificaciones')

  await expect(page.getByRole('link', { name: 'Ver favoritos' })).toHaveAttribute('href', '#/favoritos')
  await expect(page.getByRole('link', { name: 'Ir a Mis anuncios' })).toHaveAttribute('href', '#/mis-anuncios')
  await expect(page.getByRole('link', { name: 'Ver anuncio' })).toHaveCount(0)
})
