import { test } from '@playwright/test'
import '../../tests/province-top.spec'
import '../../tests/spain-community-search.spec'
import '../../tests/owner-promotion-flow.spec'

test.beforeEach(async ({ page }) => {
  await page.route('https://**/*', route => route.abort())
})
