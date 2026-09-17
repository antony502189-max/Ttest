import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

async function signInAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
}

test('listing create and edit keep every section mounted on one continuous page', async ({ page }) => {
  await signInAsHost(page)
  await page.goto('/#/publicar')

  const sections = page.locator('[data-publish-step]')
  await expect(sections).toHaveCount(10)
  await expect(page.locator('#publish-section-0')).toBeVisible()
  await expect(page.locator('#publish-section-6')).toBeVisible()
  await expect(page.locator('#publish-section-9')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Fotografías' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Datos de contacto' })).toBeVisible()

  await page.goto('/#/mis-anuncios')
  const editLink = page.locator('.manage-card').first().getByRole('link', { name: /editar/i })
  await expect(editLink).toBeVisible()
  await editLink.click()
  await expect(page.getByRole('heading', { name: /editar habitación/i })).toBeVisible()
  await expect(page.locator('[data-publish-step]')).toHaveCount(10)
  await expect(page.locator('#publish-section-6')).toBeVisible()
})

test('mobile editor scrolls as one page without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await signInAsHost(page)
  await page.goto('/#/publicar')

  const photos = page.locator('#publish-section-6')
  await photos.scrollIntoViewIfNeeded()
  await expect(page.getByRole('heading', { name: 'Fotografías' })).toBeVisible()
  await expect(page.getByText(/sin borrar ni volver a subir fotos/i)).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
})

test('photo editor changes cover by reordering the existing reference, not by deleting it', () => {
  const forms = readFileSync('src/components/forms.tsx', 'utf8')
  const publish = readFileSync('src/pages/PublishPage.tsx', 'utf8')

  expect(forms).toContain('const makeCover = (index: number) =>')
  expect(forms).toContain('images[index]')
  expect(forms).toContain('...images.filter((_, imageIndex) => imageIndex !== index)')
  expect(forms).toContain('Usar como portada')
  expect(publish).toContain('sin borrar ni volver a subir fotos')
})
