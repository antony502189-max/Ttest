import { expect, test, type Page } from '@playwright/test'

const listingId = 'armeñime-luminosa-01'

async function openEditAsHost(page: Page) {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto(`/#/mis-anuncios/${encodeURIComponent(listingId)}/editar`)
  await expect(page.getByRole('heading', { name: 'Editar habitación' })).toBeVisible()
}

test('listing editing is one long scroll form instead of a paged wizard', async ({ page }) => {
  await openEditAsHost(page)

  await expect(page.locator('.stepper')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Continuar/i })).toHaveCount(0)
  await expect(page.locator('.listing-edit-section')).toHaveCount(9)
  await expect(page.locator('.mobile-header')).toBeHidden()
  await expect(page.locator('.bottom-nav')).toBeHidden()

  await expect(page.getByRole('heading', { name: 'Tipo de alquiler' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ubicación' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Habitación y vivienda' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Precio, gastos y fianza' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Disponibilidad' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Convivencia y requisitos' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Fotografías' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Título y descripción' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Contacto' })).toBeVisible()
})

test('photo reorder arrows move photos earlier and later in the order on mobile', async ({ page }) => {
  await openEditAsHost(page)

  const photos = page.locator('.upload-grid img')
  await expect(photos).toHaveCount(6)

  const firstUp = page.getByRole('button', { name: 'Subir foto 1 en el orden' })
  const firstDown = page.getByRole('button', { name: 'Bajar foto 1 en el orden' })
  const lastDown = page.getByRole('button', { name: 'Bajar foto 6 en el orden' })

  await expect(firstUp).toBeDisabled()
  await expect(firstDown).toBeEnabled()
  await expect(lastDown).toBeDisabled()

  const firstSrc = await photos.nth(0).getAttribute('src')
  const secondSrc = await photos.nth(1).getAttribute('src')
  expect(firstSrc).toBeTruthy()
  expect(secondSrc).toBeTruthy()

  await firstDown.click()
  await expect(photos.nth(0)).toHaveAttribute('src', secondSrc!)
  await expect(photos.nth(1)).toHaveAttribute('src', firstSrc!)

  const secondUp = page.getByRole('button', { name: 'Subir foto 2 en el orden' })
  await secondUp.click()
  await expect(photos.nth(0)).toHaveAttribute('src', firstSrc!)
  await expect(photos.nth(1)).toHaveAttribute('src', secondSrc!)
})

test('photo reorder arrows keep ordering semantics in the desktop grid', async ({ page }) => {
  await openEditAsHost(page)
  await page.setViewportSize({ width: 1100, height: 900 })

  const photos = page.locator('.upload-grid img')
  await expect(photos).toHaveCount(6)
  const firstSrc = await photos.nth(0).getAttribute('src')
  const secondSrc = await photos.nth(1).getAttribute('src')
  expect(firstSrc).toBeTruthy()
  expect(secondSrc).toBeTruthy()

  const lowerOrder = page.getByRole('button', { name: 'Bajar foto 1 en el orden' })
  await expect(lowerOrder).toHaveAttribute('title', 'Bajar foto 1 en el orden')
  await lowerOrder.click()

  await expect(photos.nth(0)).toHaveAttribute('src', secondSrc!)
  await expect(photos.nth(1)).toHaveAttribute('src', firstSrc!)
})

test('owner can scroll down, edit distant sections and save without wizard navigation', async ({ page }) => {
  await openEditAsHost(page)

  const sections = page.locator('.listing-edit-section')
  const title = `Scroll edit ${Date.now()}`

  await sections.nth(2).scrollIntoViewIfNeeded()
  const roomSize = page.locator('#edit-room-size')
  const originalRoomSize = Number(await roomSize.inputValue())
  const updatedRoomSize = Math.max(1, originalRoomSize + 1)
  await roomSize.fill(String(updatedRoomSize))

  await sections.nth(7).scrollIntoViewIfNeeded()
  await page.locator('#edit-title').fill(title)

  await sections.nth(8).scrollIntoViewIfNeeded()
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(500)
  await page.locator('#edit-contact-name').fill('Propietario scroll')

  const save = page.getByRole('button', { name: 'Guardar cambios' })
  await save.scrollIntoViewIfNeeded()
  await save.click()

  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await expect(page.locator('.manage-card').filter({ hasText: title })).toBeVisible()
  const stored = await page.evaluate((id) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{"data":[]}') as { data: Array<Record<string, unknown>> }
    return payload.data.find((item) => item.id === id)
  }, listingId)
  expect(stored?.title).toBe(title)
  expect(stored?.roomSizeM2).toBe(updatedRoomSize)
  expect((stored?.owner as { name?: string } | undefined)?.name).toBe('Propietario scroll')
})

test('photo can be replaced in place without deleting the rest', async ({ page }) => {
  await openEditAsHost(page)
  const photos = page.locator('.upload-grid img')
  await expect(photos.first()).toBeAttached()
  const before = await photos.count()
  const beforeSrc = await photos.first().getAttribute('src')
  expect(before).toBeGreaterThan(0)

  const firstCard = page.locator('.upload-grid > div').first()
  const dropzone = page.locator('.upload-dropzone')
  const addPhoto = page.locator('.upload-grid > button').first()
  const replace = page.getByRole('button', { name: /Sustituir foto 1/ })

  await firstCard.scrollIntoViewIfNeeded()
  await expect(replace).toBeVisible()

  const [cardBox, dropzoneBox, replaceBox, addBox] = await Promise.all([
    firstCard.boundingBox(),
    dropzone.boundingBox(),
    replace.boundingBox(),
    addPhoto.count().then(async (count) => count ? addPhoto.boundingBox() : null),
  ])

  expect(cardBox).not.toBeNull()
  expect(cardBox?.width ?? 0).toBeGreaterThanOrEqual(300)
  expect(cardBox?.height ?? 0).toBeGreaterThanOrEqual(220)
  expect(dropzoneBox).not.toBeNull()
  expect(dropzoneBox?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(160)
  expect(replaceBox?.width ?? 0).toBeGreaterThanOrEqual(46)
  expect(replaceBox?.height ?? 0).toBeGreaterThanOrEqual(46)
  if (addBox) expect(addBox.width).toBeGreaterThanOrEqual(300)

  const pageWidth = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }))
  expect(pageWidth.document).toBeLessThanOrEqual(pageWidth.viewport)

  await replace.click()
  await page.locator('input[aria-label="Sustituir foto del anuncio"]').setInputFiles({
    name: 'replacement.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
  })
  await expect(photos).toHaveCount(before)
  await expect.poll(() => photos.first().getAttribute('src')).not.toBe(beforeSrc)
})

test('new publication uses the same one-page long form as editing', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/publicar')

  await expect(page.locator('.stepper')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Continuar/i })).toHaveCount(0)
  await expect(page.locator('.listing-edit-page')).toBeVisible()
  await expect(page.locator('.listing-create-page .listing-edit-section')).toHaveCount(9)
  await expect(page.getByRole('heading', { name: 'Publicar habitación' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Tipo de alquiler' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ubicación' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Habitación y vivienda' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Precio, gastos y fianza' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Disponibilidad' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Convivencia y requisitos' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Fotografías' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Título y descripción' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Contacto' })).toBeVisible()
})