import { expect, test, type Page } from '@playwright/test'
import { initialListings } from '@/data/listings'
import { getImageCriticalRestrictions } from '@/lib/listings'

const listingRoute = `/#/habitacion/${encodeURIComponent(initialListings[0].id)}`

async function reset(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
}

test.beforeEach(async ({ page }) => {
  await reset(page)
})

test('LOCK-OVERLAY derives at most two truthful image restrictions and omits empty overlays', async ({ page }) => {
  const unrestricted = {
    ...initialListings[1],
    tenantRequirement: 'any' as const,
    roomCapacity: 2 as const,
    petsAllowed: true,
    childrenAllowed: true,
    smokingAllowed: true,
  }
  expect(getImageCriticalRestrictions(initialListings[0]).length).toBeGreaterThan(0)
  expect(getImageCriticalRestrictions(initialListings[0]).length).toBeLessThanOrEqual(2)
  expect(getImageCriticalRestrictions(unrestricted)).toEqual([])

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife')
  const firstCard = page.locator('.property-card').first()
  const cardOverlay = firstCard.locator('.critical-restriction-overlay')
  await expect(cardOverlay).toBeVisible()
  expect(await cardOverlay.locator('span').count()).toBeLessThanOrEqual(2)

  await page.goto(listingRoute)
  const galleryOverlay = page.locator('.property-gallery .critical-restriction-overlay')
  await expect(galleryOverlay).toBeVisible()
  expect(await galleryOverlay.locator('span').count()).toBeLessThanOrEqual(2)

  await page.goto('/#/buscar?q=Tenerife&vista=mapa')
  await page.locator('.room-cluster-shell').first().click({ timeout: 15_000 })
  await page.locator('.price-marker-shell').first().click({ timeout: 15_000 })
  await expect(page.locator('.map-selected-card')).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('.map-selected-card__media > span')).toBeVisible()
})

test('LOCK-CARD exposes image, price, title and body navigation without nesting controls', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife')
  const card = page.locator('.property-card').first()
  const mediaLink = card.locator('.property-card__media > a')
  const bodyLink = card.locator('.property-card__body-link')
  const expectedHref = await mediaLink.getAttribute('href')
  await expect(bodyLink).toHaveAttribute('href', expectedHref ?? '')
  await expect(card.locator('.price-block').locator('xpath=ancestor::a[1]')).toHaveClass(/property-card__body-link/)
  await expect(card.locator('h3').locator('xpath=ancestor::a[1]')).toHaveClass(/property-card__body-link/)
  await expect(bodyLink.getByRole('button')).toHaveCount(0)

  const originalUrl = page.url()
  const favorite = card.locator('.favorite-button')
  await favorite.click()
  await expect(page).toHaveURL(originalUrl)
  await expect(favorite).toHaveAttribute('aria-pressed', 'true')

  const previousSrc = await card.locator('.property-card__media img').getAttribute('src')
  await card.getByRole('button', { name: /Foto siguiente/i }).click()
  await expect(page).toHaveURL(originalUrl)
  await expect.poll(() => card.locator('.property-card__media img').getAttribute('src')).not.toBe(previousSrc)

  await card.getByRole('button', { name: /Más opciones/i }).click()
  await expect(page).toHaveURL(originalUrl)
  await expect(page.getByRole('menu')).toBeVisible()
  await page.keyboard.press('Escape')

  await bodyLink.click()
  await expect(page).toHaveURL(/#\/habitacion\//)
})

test('LOCK-COMMENTS supports honest user-scoped create, edit, delete and account cleanup', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(listingRoute)
  await page.getByRole('button', { name: 'Añadir comentario' }).click()
  await page.getByLabel('Comentario personal').fill('Primera nota local')
  await page.getByRole('button', { name: 'Guardar comentario' }).click()
  const comments = page.locator('.local-listing-comments')
  await expect(comments).toContainText('Primera nota local')
  await expect(comments).toContainText('Guardado en este dispositivo')

  await comments.getByRole('button', { name: 'Editar' }).click()
  await page.getByLabel('Editar comentario').fill('Nota local editada')
  await page.getByRole('button', { name: 'Guardar comentario' }).click()
  await expect(comments).toContainText('Nota local editada')
  await comments.getByRole('button', { name: 'Eliminar' }).click()
  await expect(comments).toHaveCount(0)

  await page.getByRole('button', { name: 'Añadir comentario' }).click()
  await page.getByLabel('Comentario personal').fill('Nota de invitado')
  await page.getByRole('button', { name: 'Guardar comentario' }).click()
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('tenant-demo')))
  await page.reload()
  await expect(page.locator('.local-listing-comments')).toHaveCount(0)

  await page.getByRole('button', { name: 'Añadir comentario' }).click()
  await page.getByLabel('Comentario personal').fill('Nota de la cuenta')
  await page.getByRole('button', { name: 'Guardar comentario' }).click()
  await expect.poll(() => page.evaluate(() => {
    const stored = JSON.parse(localStorage.getItem('112233:listing-comments:v1') ?? '{}')
    return { guest: stored.data?.guest?.length, tenant: stored.data?.['tenant-demo']?.length }
  })).toEqual({ guest: 1, tenant: 1 })

  await page.goto('/#/perfil')
  await page.getByRole('button', { name: 'Eliminar cuenta' }).click()
  await page.getByRole('alertdialog', { name: '¿Eliminar tu cuenta?' }).getByRole('button', { name: 'Eliminar definitivamente' }).click()
  await expect(page).toHaveURL(/#\/acceso/)
  await expect.poll(() => page.evaluate(() => {
    const stored = JSON.parse(localStorage.getItem('112233:listing-comments:v1') ?? '{}')
    return { guest: stored.data?.guest?.length, tenant: stored.data?.['tenant-demo'] }
  })).toEqual({ guest: 1, tenant: undefined })
})
