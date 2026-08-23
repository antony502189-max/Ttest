import { expect, test, type Page } from '@playwright/test'

const hostSession = 'host-demo'

async function clearAndOpenAsHost(page: Page, path: string) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.evaluate((id) => localStorage.setItem('112233:session:v1', JSON.stringify(id)), hostSession)
  await page.reload()
  await page.goto(path)
}

async function advanceWizard(page: Page, count: number) {
  const stepper = page.locator('.stepper')
  for (let index = 0; index < count; index += 1) {
    const currentStep = Number((await stepper.getAttribute('aria-label'))?.match(/Paso (\d+)/)?.[1])
    await page.getByRole('button', { name: 'Continuar' }).click()
    await expect(stepper).toHaveAttribute('aria-label', new RegExp(`Paso ${currentStep + 1} de`))
  }
}

test('EQUIP-01..08 landlord equipment fields persist, render and remain editable', async ({ page }) => {
  await clearAndOpenAsHost(page, '/#/publicar')
  await advanceWizard(page, 2)

  const bedding = page.locator('#publish-bedding')
  const refrigerator = page.locator('#publish-refrigerator')
  const balcony = page.locator('#publish-balcony')
  const washingMachine = page.locator('#publish-washing-machine')

  await expect(bedding).toHaveValue('included')
  await expect(refrigerator).toHaveValue('shared')
  await expect(balcony).toHaveValue('no')
  await expect(washingMachine).toHaveValue('shared')
  await expect(page.getByText('Balcón', { exact: true })).toHaveCount(1)
  await expect(page.getByText('Lavadora', { exact: true })).toHaveCount(1)

  await bedding.selectOption('not_included')
  await refrigerator.selectOption('individual')
  await balcony.selectOption('yes')
  await washingMachine.selectOption('none')

  await advanceWizard(page, 7)
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText(/se ha enviado a revisión/)).toBeVisible()

  const created = await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{"data":[]}') as {
      data: Array<{ id: string; amenities: string[] }>
    }
    return payload.data[0]
  })

  expect(created.amenities).toEqual(expect.arrayContaining([
    'Ropa de cama no incluida',
    'Frigorífico individual',
    'Balcón disponible',
    'Sin lavadora',
  ]))
  expect(created.amenities).not.toEqual(expect.arrayContaining([
    'Ropa de cama incluida',
    'Frigorífico compartido',
    'Sin frigorífico',
    'Balcón',
    'Sin balcón',
    'Lavadora',
    'Lavadora individual',
    'Lavadora compartida',
  ]))

  await page.goto(`/#/habitacion/${encodeURIComponent(created.id)}`)
  await expect(page.getByText('Ropa de cama no incluida', { exact: true })).toBeVisible()
  await expect(page.getByText('Frigorífico individual', { exact: true })).toBeVisible()
  await expect(page.getByText('Balcón disponible', { exact: true })).toBeVisible()
  await expect(page.getByText('Sin lavadora', { exact: true })).toBeVisible()

  await page.goto(`/#/mis-anuncios/${encodeURIComponent(created.id)}/editar`)
  await advanceWizard(page, 2)
  await expect(page.locator('#publish-bedding')).toHaveValue('not_included')
  await expect(page.locator('#publish-refrigerator')).toHaveValue('individual')
  await expect(page.locator('#publish-balcony')).toHaveValue('yes')
  await expect(page.locator('#publish-washing-machine')).toHaveValue('none')
})

test('EQUIP-09 legacy balcony and washing-machine amenities map into structured controls', async ({ page }) => {
  await clearAndOpenAsHost(page, '/#/mis-anuncios/arme%C3%B1ime-luminosa-01/editar')
  await advanceWizard(page, 2)

  const legacyAmenities = await page.evaluate(() => {
    const raw = localStorage.getItem('112233:listing-draft:v3')
    return raw ? (JSON.parse(raw) as { data?: { amenities?: string[] } }).data?.amenities ?? [] : []
  })

  if (legacyAmenities.includes('Balcón')) await expect(page.locator('#publish-balcony')).toHaveValue('yes')
  if (legacyAmenities.includes('Lavadora')) await expect(page.locator('#publish-washing-machine')).toHaveValue('shared')
})
