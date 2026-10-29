import { expect, test } from '@playwright/test'

for (const width of [320, 1280]) {
  test(`owned AI collection restores names, paginates and deletes after reload at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      const id = '00000000-0000-4000-8000-000000000011'
      localStorage.setItem('112233:language:v1', 'es')
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:session:v1', JSON.stringify(id))
      localStorage.setItem('112233:users:v1', JSON.stringify([{ id, name: 'Synthetic', email: 'synthetic@example.test',
        password: '', passwordHash: 'offline', role: 'tenant', initials: 'S', phone: '', whatsapp: '', telegram: '', about: '',
        showPhone: false, showWhatsApp: false, emailVerified: true }]))
    })
    const firstName = 'Mi búsqueda de habitación tranquila junto al trabajo y transporte'
    const rows = [
      { id: '00000000-0000-4000-8000-000000000021', name: firstName, matcher: 'ai.v1', revision: 1, enabled: true },
      { id: '00000000-0000-4000-8000-000000000022', name: 'Otra búsqueda', matcher: 'ai.v1', revision: 2, enabled: false },
    ]
    let rejectDelete = true
    await page.route('**/api/v1/saved-searches/**', route => {
      const url = new URL(route.request().url())
      if (route.request().method() === 'DELETE') {
        if (rejectDelete) { rejectDelete = false; return route.fulfill({ status: 503, json: { detail: 'try again' } }) }
        const index = rows.findIndex(row => url.pathname.endsWith(row.id))
        rows.splice(index, 1)
        return route.fulfill({ status: 204 })
      }
      const start = url.searchParams.has('after') ? 1 : 0
      return route.fulfill({ json: { items: rows.slice(start, start + 1), collection_count: rows.length,
        next_cursor: start === 0 && rows.length > 1 ? rows[0].id : null } })
    })
    await page.goto('/#/busquedas-guardadas')
    const collection = page.getByRole('region', { name: 'Búsquedas IA guardadas', exact: true })
    await expect(collection.getByRole('heading', { name: firstName, exact: true })).toBeVisible()
    const firstButton = collection.getByRole('button', { name: `Eliminar: ${firstName}`, exact: true })
    const bounds = await firstButton.boundingBox()
    expect(bounds).not.toBeNull()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
    await collection.getByRole('button', { name: 'Cargar más' }).click()
    await expect(collection.getByRole('heading', { name: 'Otra búsqueda' })).toBeVisible()
    await page.reload()
    await expect(collection.getByRole('heading', { name: firstName, exact: true })).toBeVisible()
    const remove = collection.getByRole('button', { name: `Eliminar: ${firstName}`, exact: true })
    await remove.click()
    await expect(collection.getByRole('alert')).toBeVisible()
    await expect(remove).toBeEnabled()
    await remove.click()
    await expect(collection.getByRole('heading', { name: firstName, exact: true })).toHaveCount(0)
    await expect(collection.getByRole('heading', { name: 'Otra búsqueda' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  })
}
