import { expect, test, type Page } from '@playwright/test'

const listingId = 'armeñime-luminosa-01'

async function openEditAsHost(page: Page) {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto(`/#/mis-anuncios/${encodeURIComponent(listingId)}/editar`)
}

test('mobile listing editor can jump straight to photos without paging through prior steps', async ({ page }) => {
  await openEditAsHost(page)

  const jump = page.getByLabel('Ir directamente a una sección del anuncio')
  await expect(jump).toBeVisible()
  await jump.selectOption({ label: 'Fotografías' })

  await expect(page.getByRole('heading', { name: 'Fotografías' })).toBeVisible()
  await expect(page.getByText('Puedes sustituir una foto, cambiar la portada y reordenar las imágenes sin volver a subir las demás.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Sustituir foto 1/ })).toBeVisible()
})

test('editing unlocks every section while the normal publication wizard keeps future steps gated', async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 800 })
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))

  await page.goto(`/#/mis-anuncios/${encodeURIComponent(listingId)}/editar`)
  await expect(page.locator('.stepper ol button')).toHaveCount(10)
  await expect(page.locator('.stepper ol button:disabled')).toHaveCount(0)

  await page.goto('/#/publicar')
  await expect(page.locator('.stepper ol button:disabled')).toHaveCount(9)
})