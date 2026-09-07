import { expect, test } from '@playwright/test'

const internalListingId = 'armeñime-luminosa-01'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('mobile listing hero preserves the full uploaded photo instead of cover-cropping it', async ({ page }) => {
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
    return {
      objectFit: imageStyle.objectFit,
      objectPosition: imageStyle.objectPosition,
      galleryHeight: galleryNode?.getBoundingClientRect().height ?? 0,
      background: galleryStyle?.backgroundColor ?? '',
    }
  })

  expect(styles.objectFit).toBe('contain')
  expect(styles.objectPosition).toContain('50%')
  expect(styles.galleryHeight).toBeGreaterThanOrEqual(440)
  expect(styles.background).not.toBe('rgba(0, 0, 0, 0)')
})

test('search result cards keep their existing cover crop', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Armeñime')

  const image = page.locator('.m2-result-card__media img').first()
  await expect(image).toBeVisible()
  await expect.poll(() => image.evaluate((node) => getComputedStyle(node).objectFit)).toBe('cover')
})
