import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

async function resetAndOpenAs(page: Page, userId: string, path: string) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.evaluate((id) => localStorage.setItem('112233:session:v1', JSON.stringify(id)), userId)
  await page.reload()
  await page.goto(path)
}

test('ordinary owner can delete their own listing without an email allowlist', async ({ page }) => {
  await resetAndOpenAs(page, 'host-demo', '/#/mis-anuncios')
  const cards = page.locator('.manage-card')
  await expect(cards.first()).toBeVisible()
  const before = await cards.count()
  expect(before).toBeGreaterThan(0)

  const card = cards.first()
  const title = await card.locator('h2').innerText()
  const deleteButton = card.getByRole('button', { name: /^Eliminar / })
  await expect(deleteButton).toBeVisible()
  await deleteButton.click()
  const dialog = page.getByRole('alertdialog', { name: '¿Eliminar este anuncio?' })
  await expect(dialog).toContainText('se eliminarán definitivamente')
  await dialog.getByRole('button', { name: 'Eliminar', exact: true }).click()

  await expect(cards).toHaveCount(before - 1)
  await expect(page.getByRole('heading', { name: title })).toHaveCount(0)
})

test('mock admin can delete a listing from administration without the retired allowlist', async ({ page }) => {
  await resetAndOpenAs(page, 'admin-demo', '/#/admin')
  await page.getByRole('button', { name: 'Anuncios', exact: true }).click()
  const rows = page.locator('tbody tr')
  const before = await rows.count()
  expect(before).toBeGreaterThan(0)

  const first = rows.first()
  await first.getByRole('button', { name: /Acciones para/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Eliminar' })).toBeVisible()
  await page.getByRole('menuitem', { name: 'Eliminar' }).click()
  await page.getByRole('button', { name: 'Eliminar', exact: true }).click()
  await expect(rows).toHaveCount(before - 1)
})

test('production owner/admin delete surfaces use server authorization rather than client email gates', () => {
  const ownerPage = readFileSync('src/pages/AccountPages.tsx', 'utf8')
  const adminPage = readFileSync('src/pages/AdminPage.tsx', 'utf8')
  const context = readFileSync('src/contexts/app-context.tsx', 'utf8')
  const service = readFileSync('backend/app/services/listings.py', 'utf8')

  expect(ownerPage).not.toContain('canUseHardDelete')
  expect(ownerPage).toContain('onConfirm={async () => {')
  expect(adminPage).toContain('await deleteAdminListing(listing.id)')
  expect(context).toContain('await deleteRemoteListing(id)')
  expect(service).not.toContain('HARD_DELETE_EMAILS')
  expect(service).toContain('admin = await ensure_owner_or_admin(listing, user, session)')
  expect(ownerPage).toContain('!listing.isExternal')
  expect(adminPage).toContain('!listing.isExternal')
  expect(service).toContain('EXTERNAL_LISTING_DELETE_FORBIDDEN')
  expect(service).toContain('await session.execute(delete(Listing).where(Listing.id == listing.id))')
})
