import { expect, test, type Page } from '@playwright/test'

async function clearLocalState(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
}

async function openAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
}

async function continueWizard(page: Page, count: number) {
  for (let index = 0; index < count; index += 1) {
    await page.getByRole('button', { name: 'Continuar' }).click()
  }
}

test.beforeEach(async ({ page }) => clearLocalState(page))

test('CUSTOMER-FEEDBACK open-ended availability, Wi-Fi and monthly extra costs work together', async ({ page }) => {
  await openAsHost(page)
  await continueWizard(page, 2)

  await expect(page.getByText('Wi-Fi', { exact: true })).toBeVisible()
  await expect(page.getByText('Fibra', { exact: true })).toHaveCount(0)

  await continueWizard(page, 1)
  await page.getByLabel('Gastos de suministros').selectOption('extra')
  await page.getByLabel('Gastos adicionales aproximados (€/mes)').fill('45')
  await continueWizard(page, 1)

  const availableUntil = page.getByLabel('Disponible hasta (opcional)')
  await expect(availableUntil).toHaveValue('')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByRole('heading', { name: 'Convivencia' })).toBeVisible()
  await expect(page.getByText('Selecciona una fecha final.')).toHaveCount(0)

  const draft = await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}') as {
      data?: {
        availableUntil?: string
        billsIncluded?: boolean
        billsNote?: string
        amenities?: string[]
      }
    }
    return payload.data
  })

  expect(draft?.availableUntil).toBe('')
  expect(draft?.billsIncluded).toBe(false)
  expect(draft?.billsNote).toBe('45')
  expect(draft?.amenities).toContain('Wi-Fi')
  expect(draft?.amenities).not.toContain('Fibra')
})

test('CUSTOMER-FEEDBACK search uses Wi-Fi terminology instead of fiber', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const equipment = page.locator('.filter-section').filter({ hasText: 'Espacios y equipamiento' })
  await expect(equipment.getByText('Wi-Fi', { exact: true })).toBeVisible()
  await expect(equipment.getByText('Fibra', { exact: true })).toHaveCount(0)
})
