import { expect, test } from '@playwright/test'

const orderId = '00000000-0000-4000-8000-000000000101'
const adId = '00000000-0000-4000-8000-000000000102'

test('admin refund requires a reason, confirmation and clears the review queue', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo')))
  let resolved = false
  await page.route('**/admin/advertisements**', route => route.fulfill({ json: [] }))
  await page.route('**/payments/admin/review-required', route => route.fulfill({ json: resolved ? [] : [{ id: orderId, kind: 'listing_top', amountCents: 3000, note: 'Needs resolution', status: 'paid', financialStatus: 'normal' }] }))
  await page.route(`**/payments/admin/orders/${orderId}/resolve`, route => {
    expect(route.request().postDataJSON()).toEqual({ action: 'refund', reason: 'Unused paid service refund' })
    resolved = true
    return route.fulfill({ json: { resolved: true, financialStatus: 'refunded' } })
  })
  await page.goto('/#/admin/publicidad', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Devolver pago' }).click()
  await expect(page.getByRole('alert')).toHaveText('Indica un motivo de al menos 10 caracteres.')
  expect(resolved).toBe(false)
  await page.getByLabel('Motivo de resolución').fill('Unused paid service refund')
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Devolver pago' }).click()
  await expect(page.getByRole('heading', { name: 'Pagos que necesitan revisión' })).toHaveCount(0)
  expect(resolved).toBe(true)
})

test('failed asynchronous payment stops confirmation and allows a new purchase', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.route(`**/advertisements/${adId}`, route => route.fulfill({ json: { id: adId, title: 'Local service', description: 'Our local community service.', imageUrl: '', packageId: 'homepage_1d', status: 'pending_payment', paymentStatus: 'unpaid' } }))
  await page.route(`**/payments/advertisements/${adId}/status`, route => route.fulfill({ json: { orderStatus: 'failed', fulfillmentStatus: 'pending' } }))
  await page.route(`**/payments/advertisements/${adId}/quote**`, route => route.fulfill({ json: { days: 10, amountCents: 1000, currency: 'EUR', available: true } }))
  await page.goto(`/#/publicidad/${adId}/checkout?payment=return`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Pago fallido. Puedes volver a intentarlo.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pagar con Stripe' })).toBeEnabled()
})
