import { readFileSync } from 'node:fs'
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

async function openCreateAsHost(page: Page) {
  await page.setViewportSize({ width: 1100, height: 900 })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/publicar')
  await expect(page.getByRole('heading', { name: 'Publicar habitación' })).toBeVisible()
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

  const [upBox, upIconBox, downBox, downIconBox] = await Promise.all([
    firstUp.boundingBox(),
    firstUp.locator('svg').boundingBox(),
    firstDown.boundingBox(),
    firstDown.locator('svg').boundingBox(),
  ])
  expect(upBox).not.toBeNull()
  expect(upIconBox).not.toBeNull()
  expect(downBox).not.toBeNull()
  expect(downIconBox).not.toBeNull()
  const centered = (button: NonNullable<typeof upBox>, icon: NonNullable<typeof upIconBox>) => ({
    x: Math.abs((icon.x + icon.width / 2) - (button.x + button.width / 2)),
    y: Math.abs((icon.y + icon.height / 2) - (button.y + button.height / 2)),
  })
  const upOffset = centered(upBox!, upIconBox!)
  const downOffset = centered(downBox!, downIconBox!)
  expect(upOffset.x).toBeLessThanOrEqual(1)
  expect(upOffset.y).toBeLessThanOrEqual(1)
  expect(downOffset.x).toBeLessThanOrEqual(1)
  expect(downOffset.y).toBeLessThanOrEqual(1)

  const firstSrc = await photos.nth(0).getAttribute('src')
  const secondSrc = await photos.nth(1).getAttribute('src')
  expect(firstSrc).toBeTruthy()
  expect(secondSrc).toBeTruthy()

  await firstDown.click()
  await expect(photos.nth(0)).toHaveAttribute('src', secondSrc!)
  await expect(photos.nth(1)).toHaveAttribute('src', firstSrc!)
  await expect(page.locator('.upload-photo-card.is-dragging')).toHaveCount(0)

  const secondUp = page.getByRole('button', { name: 'Subir foto 2 en el orden' })
  await secondUp.click()
  await expect(photos.nth(0)).toHaveAttribute('src', firstSrc!)
  await expect(photos.nth(1)).toHaveAttribute('src', secondSrc!)
})

test('press-and-drag moves a photo to a new position and updates the cover order', async ({ page }) => {
  await openEditAsHost(page)
  await page.setViewportSize({ width: 1100, height: 900 })

  const cards = page.locator('.upload-photo-card')
  const photos = page.locator('.upload-grid img')
  await expect(cards).toHaveCount(6)
  await expect(photos).toHaveCount(6)

  const firstSrc = await photos.nth(0).getAttribute('src')
  const secondSrc = await photos.nth(1).getAttribute('src')
  const thirdSrc = await photos.nth(2).getAttribute('src')
  await cards.nth(0).scrollIntoViewIfNeeded()
  const firstBox = await cards.nth(0).boundingBox()
  const thirdBox = await cards.nth(2).boundingBox()
  expect(firstSrc).toBeTruthy()
  expect(secondSrc).toBeTruthy()
  expect(thirdSrc).toBeTruthy()
  expect(firstBox).not.toBeNull()
  expect(thirdBox).not.toBeNull()

  await page.mouse.move(firstBox!.x + firstBox!.width / 2, firstBox!.y + firstBox!.height / 2)
  await page.mouse.down()
  await page.waitForTimeout(260)
  await expect(cards.nth(0)).toHaveClass(/is-dragging/)
  await page.mouse.move(thirdBox!.x + thirdBox!.width / 2, thirdBox!.y + thirdBox!.height / 2, { steps: 8 })
  await expect(page.locator('.upload-photo-card.is-shifting')).toHaveCount(2)
  await expect(cards.nth(1)).toHaveCSS('transform', /matrix/)
  await expect(cards.nth(2)).toHaveCSS('transform', /matrix/)
  await page.mouse.up()

  await expect(photos.nth(0)).toHaveAttribute('src', secondSrc!)
  await expect(photos.nth(1)).toHaveAttribute('src', thirdSrc!)
  await expect(photos.nth(2)).toHaveAttribute('src', firstSrc!)
  await expect(page.locator('.upload-photo-card.is-dragging')).toHaveCount(0)
  await expect(page.locator('.upload-photo-card').nth(0).locator('.cover-label')).toBeVisible()

  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  const savedOrder = await page.evaluate((id) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{"data":[]}') as { data: Array<{ id: string; images: string[] }> }
    return payload.data.find((item) => item.id === id)?.images
  }, listingId)
  expect(savedOrder?.slice(0, 3)).toEqual([secondSrc, thirdSrc, firstSrc])
})

test('create and edit forms share touch-capable press-and-drag photo ordering', () => {
  const forms = readFileSync('src/components/forms.tsx', 'utf8')
  const create = readFileSync('src/pages/ListingCreatePage.tsx', 'utf8')
  const edit = readFileSync('src/pages/ListingEditPage.tsx', 'utf8')
  const css = readFileSync('src/listing-edit-comfort.css', 'utf8')

  expect(create).toContain('<ImageUploader images={draft.images}')
  expect(edit).toContain('<ImageUploader images={draft.images}')
  expect(create).toContain('<VideoUploader video={draft.video}')
  expect(edit).toContain('<VideoUploader video={draft.video}')
  expect(forms).toContain('MAX_LISTING_PHOTOS')
  expect(forms).toContain('MAX_LISTING_VIDEO_SECONDS')
  expect(forms).toContain('saveVideoFile(file)')
  expect(forms).toContain('onPointerDown={(event) => beginPhotoDrag(event, image, index)}')
  expect(forms).toContain('onPointerMove={updatePhotoDrag}')
  expect(forms).toContain('onPointerUp={finishPhotoDrag}')
  expect(forms).toContain('document.addEventListener("touchmove", preventTouchMove, { passive: false, capture: true })')
  expect(forms).toContain('window.requestAnimationFrame(runPhotoAutoScroll)')
  expect(forms).toContain('const minSpeed = 520')
  expect(forms).toContain('const maxSpeed = 1500')
  expect(forms).toContain('const elapsedMs = Math.min(32')
  expect(forms).toContain('document.documentElement.style.scrollBehavior = "auto"')
  expect(forms).toContain('window.scrollBy({ top: speed * (elapsedMs / 1000), left: 0, behavior: "auto" })')
  expect(forms).toContain('photoReorderDisplacements(drag, drag.targetIndex)')
  expect(forms).toContain('window.scrollY - drag.startScrollY')
  expect(forms).toContain('movePhotoTo(sourceIndex, targetIndex)')
  expect(css).toContain('.upload-photo-card.is-dragging')
  expect(css).toContain('.upload-photo-card.is-shifting')
  expect(css).toContain('.upload-photo-card.is-drop-target')
})

test('dragging a photo near viewport edges auto-scrolls down and up', async ({ page }) => {
  await openEditAsHost(page)
  await page.setViewportSize({ width: 390, height: 600 })

  const cards = page.locator('.upload-photo-card')
  await expect(cards).toHaveCount(6)
  await cards.nth(1).scrollIntoViewIfNeeded()
  const box = await cards.nth(1).boundingBox()
  expect(box).not.toBeNull()

  const x = box!.x + box!.width / 2
  const startY = Math.min(420, box!.y + box!.height / 2)
  const initialScroll = await page.evaluate(() => window.scrollY)

  await page.mouse.move(x, startY)
  await page.mouse.down()
  await page.waitForTimeout(180)
  await expect(cards.nth(1)).toHaveClass(/is-dragging/)
  await expect.poll(() => page.evaluate(() => document.documentElement.style.scrollBehavior)).toBe('auto')

  await page.mouse.move(x, 585, { steps: 4 })
  await expect.poll(() => page.evaluate(() => window.scrollY), { timeout: 1_000 }).toBeGreaterThan(initialScroll + 90)
  const scrolledDown = await page.evaluate(() => window.scrollY)

  await page.mouse.move(x, 15, { steps: 4 })
  await expect.poll(() => page.evaluate(() => window.scrollY), { timeout: 1_000 }).toBeLessThan(scrolledDown - 90)

  await page.mouse.up()
  await expect(page.locator('.upload-photo-card.is-dragging')).toHaveCount(0)
  await expect.poll(() => page.evaluate(() => document.documentElement.style.scrollBehavior)).toBe('')
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

test('photo rotate control turns a selected photo 90 degrees in place on mobile', async ({ page }) => {
  await openEditAsHost(page)

  const photos = page.locator('.upload-grid img')
  const before = await photos.count()
  expect(before).toBeGreaterThan(0)

  await page.locator('#publish-images').setInputFiles({
    name: 'rotate-me.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGP4z8DAwPAfAAcAAf9+CLHQAAAAAElFTkSuQmCC', 'base64'),
  })
  await expect(photos).toHaveCount(before + 1)

  const index = before
  const card = page.locator('.upload-grid > div').nth(index)
  const image = photos.nth(index)
  const rotate = page.getByRole('button', { name: `Girar foto ${index + 1} 90 grados` })

  await card.scrollIntoViewIfNeeded()
  await expect(rotate).toBeVisible()
  await expect(page.locator('input[aria-label="Sustituir foto del anuncio"]')).toHaveCount(0)

  const rotateBox = await rotate.boundingBox()
  expect(rotateBox?.width ?? 0).toBeGreaterThanOrEqual(46)
  expect(rotateBox?.height ?? 0).toBeGreaterThanOrEqual(46)

  await expect.poll(() => image.evaluate((node) => ({
    width: (node as HTMLImageElement).naturalWidth,
    height: (node as HTMLImageElement).naturalHeight,
  }))).toEqual({ width: 2, height: 1 })

  const beforeSrc = await image.getAttribute('src')
  expect(beforeSrc).toBeTruthy()
  await rotate.click()
  await expect(page.locator('.upload-photo-card.is-dragging')).toHaveCount(0)

  await expect(image).toHaveAttribute('data-preview-rotation', '90', { timeout: 500 })
  await expect(page.locator('.listing-edit-topbar button').filter({ hasText: 'Procesando foto' })).toBeDisabled()
  await expect.poll(() => image.getAttribute('src')).not.toBe(beforeSrc)
  await expect(image).not.toHaveAttribute('data-preview-rotation')
  await expect.poll(() => image.evaluate((node) => ({
    width: (node as HTMLImageElement).naturalWidth,
    height: (node as HTMLImageElement).naturalHeight,
  }))).toEqual({ width: 1, height: 2 })
})

test('four rapid photo rotations collapse to 360 degrees without re-encoding', async ({ page }) => {
  await openEditAsHost(page)

  const photos = page.locator('.upload-grid img')
  const before = await photos.count()
  await page.locator('#publish-images').setInputFiles({
    name: 'rotate-360.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGP4z8DAwPAfAAcAAf9+CLHQAAAAAElFTkSuQmCC', 'base64'),
  })
  await expect(photos).toHaveCount(before + 1)

  const image = photos.nth(before)
  const rotate = page.getByRole('button', { name: `Girar foto ${before + 1} 90 grados` })
  const beforeSrc = await image.getAttribute('src')
  expect(beforeSrc).toBeTruthy()

  await rotate.evaluate((button) => {
    button.click()
    button.click()
    button.click()
    button.click()
  })

  await expect(image).not.toHaveAttribute('data-preview-rotation')
  await page.waitForTimeout(450)
  await expect(image).toHaveAttribute('src', beforeSrc!)
  await expect(page.locator('.listing-edit-topbar button').filter({ hasText: 'Guardar' })).toBeEnabled()
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

test('create form drags a unique photo through duplicate URLs without React warnings', async ({ page }) => {
  const reactWarnings: string[] = []
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (['warning', 'error'].includes(message.type()) && /key|duplicate/i.test(message.text())) reactWarnings.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))
  await openCreateAsHost(page)

  const cards = page.locator('.upload-photo-card')
  const photos = page.locator('.upload-grid img')
  const initialCount = await cards.count()
  expect(initialCount).toBeGreaterThanOrEqual(2)
  const duplicateSrc = await photos.nth(0).getAttribute('src')
  await expect(photos.nth(1)).toHaveAttribute('src', duplicateSrc!)

  await page.locator('#publish-images').setInputFiles({
    name: 'unique-cover.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGP4z8DAwPAfAAcAAf9+CLHQAAAAAElFTkSuQmCC', 'base64'),
  })
  await expect(cards).toHaveCount(initialCount + 1)
  const uniqueRef = await cards.nth(initialCount).getAttribute('data-photo-reference')
  expect(uniqueRef).toBeTruthy()
  expect(uniqueRef).not.toBe(duplicateSrc)

  await cards.nth(initialCount).scrollIntoViewIfNeeded()
  const from = await cards.nth(initialCount).boundingBox()
  const to = await cards.nth(initialCount - 1).boundingBox()
  expect(from).not.toBeNull()
  expect(to).not.toBeNull()
  await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2)
  await page.mouse.down()
  await expect(cards.nth(initialCount)).toHaveClass(/is-dragging/)
  await page.mouse.move(to!.x + to!.width / 2, to!.y + to!.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect(cards.nth(initialCount - 1)).toHaveAttribute('data-photo-reference', uniqueRef!)
  await cards.nth(initialCount - 1).getByRole('button', { name: 'Usar como portada' }).click()
  await expect(cards.nth(0)).toHaveAttribute('data-photo-reference', uniqueRef!)
  await expect(cards.nth(0).locator('.cover-label')).toBeVisible()
  await expect(page.locator('.upload-photo-card.is-dragging')).toHaveCount(0)
  expect(reactWarnings).toEqual([])
  expect(runtimeErrors).toEqual([])
})

test.describe('touch photo ordering', () => {
  test.use({ hasTouch: true })

  test('mobile scroll gesture stays available before hold, then long press reorders photos', async ({ page }) => {
    await openEditAsHost(page)
    const cards = page.locator('.upload-photo-card')
    const originalFirst = await cards.nth(0).getAttribute('data-photo-reference')
    const originalSecond = await cards.nth(1).getAttribute('data-photo-reference')
    await cards.nth(0).scrollIntoViewIfNeeded()
    const session = await page.context().newCDPSession(page)
    const first = await cards.nth(0).boundingBox()
    expect(first).not.toBeNull()
    const start = { x: first!.x + first!.width / 2, y: first!.y + first!.height / 2 }

    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [start] })
    await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: start.x, y: start.y - 24 }] })
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect(cards.nth(0)).not.toHaveClass(/is-dragging/)
    await expect(cards.nth(0)).toHaveAttribute('data-photo-reference', originalFirst!)

    await cards.nth(0).scrollIntoViewIfNeeded()
    const from = await cards.nth(0).boundingBox()
    const to = await cards.nth(1).boundingBox()
    expect(from).not.toBeNull()
    expect(to).not.toBeNull()
    await session.send('Input.dispatchTouchEvent', {
      type: 'touchStart',
      touchPoints: [{ x: from!.x + from!.width / 2, y: from!.y + from!.height / 2 }],
    })
    await expect(cards.nth(0)).toHaveClass(/is-dragging/)
    await session.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x: to!.x + to!.width / 2, y: to!.y + to!.height / 2 }],
    })
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect(cards.nth(0)).toHaveAttribute('data-photo-reference', originalSecond!)
    await expect(cards.nth(1)).toHaveAttribute('data-photo-reference', originalFirst!)
    await expect(cards.nth(0).locator('.cover-label')).toBeVisible()
  })
})
