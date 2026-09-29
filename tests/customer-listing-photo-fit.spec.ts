import { expect, test } from '@playwright/test'

const internalListingId = 'armeñime-luminosa-01'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('mobile listing hero fills one fixed frame for uploaded photos', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)

  const gallery = page.locator('.idealista-listing-page .listing-gallery-container .property-gallery')
  const image = gallery.locator('.gallery-main > img').first()
  await expect(gallery).toBeVisible()
  await expect(image).toBeVisible()

  const styles = await image.evaluate((node) => {
    const imageStyle = getComputedStyle(node)
    const galleryNode = node.closest('.property-gallery') as HTMLElement | null
    const galleryStyle = galleryNode ? getComputedStyle(galleryNode) : null
    const mainNode = node.parentElement
    const mainStyle = mainNode ? getComputedStyle(mainNode) : null
    return {
      objectFit: imageStyle.objectFit,
      objectPosition: imageStyle.objectPosition,
      galleryHeight: galleryNode?.getBoundingClientRect().height ?? 0,
      galleryBackground: galleryStyle?.backgroundColor ?? '',
      mainBackground: mainStyle?.backgroundColor ?? '',
      imageBackground: imageStyle.backgroundColor,
    }
  })

  expect(styles.objectFit).toBe('cover')
  expect(styles.objectPosition).toContain('50%')
  expect(styles.galleryHeight).toBeGreaterThanOrEqual(440)
  expect(styles.galleryBackground).toBe('rgb(255, 255, 255)')
  expect(styles.mainBackground).toBe('rgb(255, 255, 255)')
  expect(styles.imageBackground).toBe('rgb(255, 255, 255)')

  const before = await gallery.boundingBox()
  await gallery.getByRole('button', { name: 'Foto siguiente', exact: true }).click()
  await expect(image).toBeVisible()
  const after = await gallery.boundingBox()
  expect(before).not.toBeNull()
  expect(after).not.toBeNull()
  expect(Math.round(after!.width)).toBe(Math.round(before!.width))
  expect(Math.round(after!.height)).toBe(Math.round(before!.height))
  expect(await image.evaluate((node) => getComputedStyle(node).objectFit)).toBe('cover')
})

test('search result cards keep their existing cover crop', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Armeñime')

  const image = page.locator('.m2-result-card__media img').first()
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate((node) => getComputedStyle(node).objectFit)).toBe('cover')
})
