# Full application validation with production Maps configuration

Overall: **FAIL**

| Check | Result | Exit |
|---|---:|---:|
| npm ci | PASS | `0` |
| playwright install | PASS | `0` |
| lint | PASS | `0` |
| typecheck | PASS | `0` |
| build | PASS | `0` |
| full e2e | FAIL | `1` |

```text
    Error Context: test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  19) [chromium] › tests/final-cleanup.spec.ts:263:1 › RESP-06 short mobile dialogs and critical map/uploader targets remain reachable 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-map-canvas')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-map-canvas')


      278 |   await page.reload()
      279 |   const mapCanvas = page.locator('.m2-map-canvas')
    > 280 |   await expect(mapCanvas).toBeVisible()
          |                           ^
      281 |   const drawAction = await page.getByRole('button', { name: 'Dibujar tu zona' }).boundingBox()
      282 |   const layersAction = await page.getByRole('button', { name: 'Cambiar capas' }).boundingBox()
      283 |   expect(drawAction && drawAction.height >= 44).toBeTruthy()
        at /home/runner/work/Ttest/Ttest/tests/final-cleanup.spec.ts:280:27

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-cleanup-RESP-06-shor-7e72d-er-targets-remain-reachable-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-cleanup-RESP-06-shor-7e72d-er-targets-remain-reachable-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-cleanup-RESP-06-shor-7e72d-er-targets-remain-reachable-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-cleanup-RESP-06-shor-7e72d-er-targets-remain-reachable-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-cleanup-RESP-06-shor-7e72d-er-targets-remain-reachable-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  20) [chromium] › tests/final-mobile-delta-evidence.spec.ts:33:1 › capture unmasked final mobile delta evidence 

    Test timeout of 180000ms exceeded.

    Error: locator.click: Test timeout of 180000ms exceeded.
    Call log:
      - waiting for locator('.m2-select-row')


      57 |   await page.setViewportSize({ width: 390, height: 844 })
      58 |   await page.goto('/#/')
    > 59 |   await page.locator('.m2-select-row').click()
         |                                        ^
      60 |   await expect(page.getByTestId('location-screen')).toBeVisible()
      61 |   await screenshot(page, 'location-390x844')
      62 |
        at /home/runner/work/Ttest/Ttest/tests/final-mobile-delta-evidence.spec.ts:59:40

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-mobile-delta-evidenc-37870-final-mobile-delta-evidence-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-mobile-delta-evidenc-37870-final-mobile-delta-evidence-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-mobile-delta-evidenc-37870-final-mobile-delta-evidence-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-mobile-delta-evidenc-37870-final-mobile-delta-evidence-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-mobile-delta-evidenc-37870-final-mobile-delta-evidence-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  21) [chromium] › tests/final-mobile-delta.spec.ts:14:1 › DELTA-MOBILE-01 home, occupant selector and location actions stay connected without changing the locked design 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-home')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-home')


      14 | test('DELTA-MOBILE-01 home, occupant selector and location actions stay connected without changing the locked design', async ({ page }) => {
      15 |   await readyMobile(page)
    > 16 |   await expect(page.locator('.m2-home')).toBeVisible()
         |                                          ^
      17 |   await expect(page.locator('.m2-mode-switch button')).toHaveCount(2)
      18 |   const cardHeight = (await page.locator('.m2-search-card').boundingBox())?.height
      19 |   await page.getByRole('button', { name: 'Turismo', exact: true }).click()
        at /home/runner/work/Ttest/Ttest/tests/final-mobile-delta.spec.ts:16:42

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2d52d--changing-the-locked-design-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2d52d--changing-the-locked-design-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-mobile-delta-DELTA-M-2d52d--changing-the-locked-design-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2d52d--changing-the-locked-design-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-mobile-delta-DELTA-M-2d52d--changing-the-locked-design-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  22) [chromium] › tests/final-mobile-delta.spec.ts:31:1 › DELTA-MOBILE-02 list, filters, sorting, map, back and reload are URL-backed 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('map-search')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('map-search')


      42 |
      43 |   await results.getByRole('button', { name: 'Mapa' }).click()
    > 44 |   await expect(page.getByTestId('map-search')).toBeVisible()
         |                                                ^
      45 |   await expect(page).toHaveURL(/vista=mapa/)
      46 |   await page.reload()
      47 |   await expect(page.getByTestId('map-search')).toBeVisible()
        at /home/runner/work/Ttest/Ttest/tests/final-mobile-delta.spec.ts:44:48

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-6853c-k-and-reload-are-URL-backed-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-6853c-k-and-reload-are-URL-backed-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-mobile-delta-DELTA-M-6853c-k-and-reload-are-URL-backed-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-6853c-k-and-reload-are-URL-backed-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-mobile-delta-DELTA-M-6853c-k-and-reload-are-URL-backed-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  23) [chromium] › tests/final-mobile-delta.spec.ts:52:1 › DELTA-MOBILE-03 drawing and nearby search expose dedicated working map states 

    Test timeout of 60000ms exceeded.

    Error: locator.click: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for getByTestId('draw-zone')


      55 |   await readyMobile(page, '/#/?panel=ubicacion')
      56 |
    > 57 |   await page.getByTestId('draw-zone').click()
         |                                       ^
      58 |   await expect(page.getByTestId('map-draw')).toBeVisible()
      59 |   await page.getByRole('button', { name: 'Dibujar tu zona' }).click()
      60 |   await expect(page.getByTestId('freehand-overlay')).toBeVisible()
        at /home/runner/work/Ttest/Ttest/tests/final-mobile-delta.spec.ts:57:39

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-fa902-edicated-working-map-states-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-fa902-edicated-working-map-states-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-mobile-delta-DELTA-M-fa902-edicated-working-map-states-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-fa902-edicated-working-map-states-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-mobile-delta-DELTA-M-fa902-edicated-working-map-states-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  24) [chromium] › tests/final-mobile-delta.spec.ts:70:1 › DELTA-MOBILE-04 phone lookup opens a real listing and canonical detail remains usable 

    Test timeout of 60000ms exceeded.

    Error: locator.click: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for getByTestId('search-phone')


      70 | test('DELTA-MOBILE-04 phone lookup opens a real listing and canonical detail remains usable', async ({ page }) => {
      71 |   await readyMobile(page, '/#/?panel=ubicacion')
    > 72 |   await page.getByTestId('search-phone').click()
         |                                          ^
      73 |   await expect(page.getByTestId('phone-search-screen')).toBeVisible()
      74 |   await page.getByLabel('Teléfono').fill('600 112 233')
      75 |   await page.getByTestId('submit-phone-search').click()
        at /home/runner/work/Ttest/Ttest/tests/final-mobile-delta.spec.ts:72:42

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2e02b-nical-detail-remains-usable-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2e02b-nical-detail-remains-usable-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-mobile-delta-DELTA-M-2e02b-nical-detail-remains-usable-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2e02b-nical-detail-remains-usable-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-mobile-delta-DELTA-M-2e02b-nical-detail-remains-usable-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  25) [chromium] › tests/final-mobile-delta.spec.ts:82:1 › DELTA-MOBILE-05 bottom tabs, favorites and protected account actions are real routes 

    Test timeout of 60000ms exceeded.

    Error: locator.click: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for getByRole('button', { name: 'Favoritos', exact: true })


      84 |   await page.locator('.m2-result-card__favorite').first().click()
      85 |   await page.getByRole('button', { name: 'Volver' }).click()
    > 86 |   await page.getByRole('button', { name: 'Favoritos', exact: true }).click()
         |                                                                      ^
      87 |   await expect(page).toHaveURL(/#\/favoritos/)
      88 |   await expect(page.locator('.m2-collection__list > button')).toHaveCount(1)
      89 |
        at /home/runner/work/Ttest/Ttest/tests/final-mobile-delta.spec.ts:86:70

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-8a565-unt-actions-are-real-routes-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-8a565-unt-actions-are-real-routes-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-mobile-delta-DELTA-M-8a565-unt-actions-are-real-routes-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-8a565-unt-actions-are-real-routes-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-mobile-delta-DELTA-M-8a565-unt-actions-are-real-routes-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  26) [chromium] › tests/final-mobile-delta.spec.ts:96:1 › DELTA-MOBILE-06 ES, EN and RU persist and never introduce horizontal overflow 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-home')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-home')


      101 |     await page.reload()
      102 |     await expect(page.locator('html')).toHaveAttribute('lang', language)
    > 103 |     await expect(page.locator('.m2-home')).toBeVisible()
          |                                            ^
      104 |     const dimensions = await page.evaluate(() => ({
      105 |       client: document.documentElement.clientWidth,
      106 |       scroll: document.documentElement.scrollWidth,
        at /home/runner/work/Ttest/Ttest/tests/final-mobile-delta.spec.ts:103:44

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2bf77-troduce-horizontal-overflow-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2bf77-troduce-horizontal-overflow-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/final-mobile-delta-DELTA-M-2bf77-troduce-horizontal-overflow-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/final-mobile-delta-DELTA-M-2bf77-troduce-horizontal-overflow-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/final-mobile-delta-DELTA-M-2bf77-troduce-horizontal-overflow-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  27) [chromium] › tests/map-responsive-parity.spec.ts:25:1 › results map keeps the current mobile shell and desktop split geometry across the responsive matrix 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-map-canvas')
    Expected: visible
    Timeout: 20000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 20000ms
      - waiting for locator('.m2-map-canvas')


      37 |     await openMap(page, viewport.width, viewport.height)
      38 |     const mapSelector = viewport.mode === 'mobile' ? '.m2-map-canvas' : '.google-map-canvas'
    > 39 |     await expect(page.locator(mapSelector)).toBeVisible({ timeout: 20_000 })
         |                                             ^
      40 |     if (viewport.mode !== 'mobile') {
      41 |       await expect(page.locator(mapSelector)).toHaveAttribute('data-map-instance', 'google-ready', { timeout: 20_000 })
      42 |     }
        at /home/runner/work/Ttest/Ttest/tests/map-responsive-parity.spec.ts:39:45

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/map-responsive-parity-resu-fb436-cross-the-responsive-matrix-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/map-responsive-parity-resu-fb436-cross-the-responsive-matrix-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/map-responsive-parity-resu-fb436-cross-the-responsive-matrix-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/map-responsive-parity-resu-fb436-cross-the-responsive-matrix-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/map-responsive-parity-resu-fb436-cross-the-responsive-matrix-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  28) [chromium] › tests/master-task-visual.spec.ts:25:1 › master current home responsive matrix ───

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-home')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-home')


      27 |   for (const [width, height] of [[360, 800], [390, 844], [430, 932], [768, 1024], [1024, 900], [1440, 900]] as const) {
      28 |     await open(page, '/#/', width, height)
    > 29 |     if (width < 768) await expect(page.locator('.m2-home')).toBeVisible()
         |                                                             ^
      30 |     else await expect(page.locator('.home-hero')).toBeVisible()
      31 |     await shot(page, `master-current-home-${width}x${height}`)
      32 |   }
        at /home/runner/work/Ttest/Ttest/tests/master-task-visual.spec.ts:29:61

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/master-task-visual-master-current-home-responsive-matrix-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/master-task-visual-master-current-home-responsive-matrix-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/master-task-visual-master-current-home-responsive-matrix-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/master-task-visual-master-current-home-responsive-matrix-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/master-task-visual-master-current-home-responsive-matrix-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  29) [chromium] › tests/master-task-visual.spec.ts:35:1 › master current mobile list, map, drawing and location states 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('map-search')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('map-search')


      40 |
      41 |   await open(page, '/#/buscar?q=Tenerife&vista=mapa', 390, 844)
    > 42 |   await expect(page.getByTestId('map-search')).toBeVisible()
         |                                                ^
      43 |   await expect(page.locator('.m2-map-toolbar')).toBeVisible()
      44 |   await expect(page.locator('.m2-map-canvas')).toBeVisible()
      45 |   await shot(page, 'master-current-results-map-390x844')
        at /home/runner/work/Ttest/Ttest/tests/master-task-visual.spec.ts:42:48

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/master-task-visual-master--c6877-drawing-and-location-states-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/master-task-visual-master--c6877-drawing-and-location-states-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/master-task-visual-master--c6877-drawing-and-location-states-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/master-task-visual-master--c6877-drawing-and-location-states-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/master-task-visual-master--c6877-drawing-and-location-states-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  30) [chromium] › tests/master-task.spec.ts:13:1 › P0 current mobile home preserves the locked APK hierarchy and links all five tabs 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-home')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-home')


      15 |   await page.goto('/#/')
      16 |   await settle(page)
    > 17 |   await expect(page.locator('.m2-home')).toBeVisible()
         |                                          ^
      18 |   await expect(page.locator('.m2-mode-switch button')).toHaveCount(2)
      19 |   await expect(page.locator('.m2-occupant-trigger')).toBeVisible()
      20 |   await expect(page.locator('.m2-select-row')).toBeVisible()
        at /home/runner/work/Ttest/Ttest/tests/master-task.spec.ts:17:42

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/master-task-P0-current-mob-6df2b-chy-and-links-all-five-tabs-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/master-task-P0-current-mob-6df2b-chy-and-links-all-five-tabs-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/master-task-P0-current-mob-6df2b-chy-and-links-all-five-tabs-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/master-task-P0-current-mob-6df2b-chy-and-links-all-five-tabs-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/master-task-P0-current-mob-6df2b-chy-and-links-all-five-tabs-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  31) [chromium] › tests/master-task.spec.ts:59:1 › P0 mobile and desktop maps retain their intended separate implementations 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('map-search')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('map-search')


      60 |   await page.setViewportSize({ width: 390, height: 844 })
      61 |   await page.goto('/#/buscar?q=Tenerife&vista=mapa')
    > 62 |   await expect(page.getByTestId('map-search')).toBeVisible()
         |                                                ^
      63 |   await expect(page.locator('.m2-map-canvas')).toBeVisible()
      64 |   await expect(page.locator('.google-map-canvas')).toHaveCount(0)
      65 |   await page.getByRole('button', { name: 'Lista' }).click()
        at /home/runner/work/Ttest/Ttest/tests/master-task.spec.ts:62:48

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/master-task-P0-mobile-and--501c9-ed-separate-implementations-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/master-task-P0-mobile-and--501c9-ed-separate-implementations-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/master-task-P0-mobile-and--501c9-ed-separate-implementations-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/master-task-P0-mobile-and--501c9-ed-separate-implementations-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/master-task-P0-mobile-and--501c9-ed-separate-implementations-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  32) [chromium] › tests/master-task.spec.ts:80:1 › P1 core routes have no horizontal overflow or unexpected console errors across the responsive matrix 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-map-canvas')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-map-canvas')


      92 |       await settle(page)
      93 |       const mapSelector = width < 768 ? '.m2-map-canvas' : '.google-map-canvas'
    > 94 |       if (route.includes('vista=mapa')) await expect(page.locator(mapSelector)).toBeVisible()
         |                                                                                 ^
      95 |       const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth)
      96 |       expect(overflow, `${route} at ${width}px`).toBeLessThanOrEqual(1)
      97 |     }
        at /home/runner/work/Ttest/Ttest/tests/master-task.spec.ts:94:81

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/master-task-P1-core-routes-bc3fd-cross-the-responsive-matrix-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/master-task-P1-core-routes-bc3fd-cross-the-responsive-matrix-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/master-task-P1-core-routes-bc3fd-cross-the-responsive-matrix-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/master-task-P1-core-routes-bc3fd-cross-the-responsive-matrix-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/master-task-P1-core-routes-bc3fd-cross-the-responsive-matrix-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  33) [chromium] › tests/mobile-map-ideal.spec.ts:79:1 › listing requirements are visually prominent in results 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('mobile-results')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('mobile-results')


      82 |   await page.getByTestId('open-location').click()
      83 |   const results = page.getByTestId('mobile-results')
    > 84 |   await expect(results).toBeVisible()
         |                         ^
      85 |   const badges = results.locator('.m2-result-card').first().locator('.m2-result-card__badges span')
      86 |   await expect(badges).not.toHaveCount(0)
      87 |   await expect(badges.filter({ hasText: /Habitación para/ })).toHaveCount(1)
        at /home/runner/work/Ttest/Ttest/tests/mobile-map-ideal.spec.ts:84:25

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-listing-r-bfbab-sually-prominent-in-results-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-listing-r-bfbab-sually-prominent-in-results-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-map-ideal-listing-r-bfbab-sually-prominent-in-results-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-listing-r-bfbab-sually-prominent-in-results-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-map-ideal-listing-r-bfbab-sually-prominent-in-results-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  34) [chromium] › tests/mobile-search-results.spec.ts:33:1 › Vivienda and Turismo are the only rental-mode controls and filter real listings 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('mobile-results')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('mobile-results')


      17 |   await page.getByTestId('open-location').click()
      18 |   const results = page.getByTestId('mobile-results')
    > 19 |   await expect(results).toBeVisible()
         |                         ^
      20 |   return results
      21 | }
      22 |
        at openResults (/home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:19:25)
        at /home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:35:19

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-search-results-Vivi-46027-ls-and-filter-real-listings-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-search-results-Vivi-46027-ls-and-filter-real-listings-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-search-results-Vivi-46027-ls-and-filter-real-listings-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-search-results-Vivi-46027-ls-and-filter-real-listings-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-search-results-Vivi-46027-ls-and-filter-real-listings-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  35) [chromium] › tests/mobile-search-results.spec.ts:64:1 › price, area, room count and housing type filters change the listing set 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('mobile-results')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('mobile-results')


      17 |   await page.getByTestId('open-location').click()
      18 |   const results = page.getByTestId('mobile-results')
    > 19 |   await expect(results).toBeVisible()
         |                         ^
      20 |   return results
      21 | }
      22 |
        at openResults (/home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:19:25)
        at /home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:66:19

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-search-results-pric-2a292-ters-change-the-listing-set-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-search-results-pric-2a292-ters-change-the-listing-set-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-search-results-pric-2a292-ters-change-the-listing-set-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-search-results-pric-2a292-ters-change-the-listing-set-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-search-results-pric-2a292-ters-change-the-listing-set-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  36) [chromium] › tests/mobile-search-results.spec.ts:98:1 › sorting, photo carousel, favorites and hiding listings work together 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('mobile-results')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('mobile-results')


      17 |   await page.getByTestId('open-location').click()
      18 |   const results = page.getByTestId('mobile-results')
    > 19 |   await expect(results).toBeVisible()
         |                         ^
      20 |   return results
      21 | }
      22 |
        at openResults (/home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:19:25)
        at /home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:100:19

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-search-results-sort-ef127-ding-listings-work-together-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-search-results-sort-ef127-ding-listings-work-together-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-search-results-sort-ef127-ding-listings-work-together-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-search-results-sort-ef127-ding-listings-work-together-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-search-results-sort-ef127-ding-listings-work-together-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  37) [chromium] › tests/mobile-search-results.spec.ts:128:1 › contact opens the existing authentication flow and map returns to Google Maps 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('mobile-results')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('mobile-results')


      17 |   await page.getByTestId('open-location').click()
      18 |   const results = page.getByTestId('mobile-results')
    > 19 |   await expect(results).toBeVisible()
         |                         ^
      20 |   return results
      21 | }
      22 |
        at openResults (/home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:19:25)
        at /home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:130:17

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-search-results-cont-61d05--map-returns-to-Google-Maps-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-search-results-cont-61d05--map-returns-to-Google-Maps-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-search-results-cont-61d05--map-returns-to-Google-Maps-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-search-results-cont-61d05--map-returns-to-Google-Maps-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-search-results-cont-61d05--map-returns-to-Google-Maps-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  38) [chromium] › tests/mobile-search-results.spec.ts:141:1 › results, sorting and filters fit every supported mobile width 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('mobile-results')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('mobile-results')


      17 |   await page.getByTestId('open-location').click()
      18 |   const results = page.getByTestId('mobile-results')
    > 19 |   await expect(results).toBeVisible()
         |                         ^
      20 |   return results
      21 | }
      22 |
        at openResults (/home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:19:25)
        at /home/runner/work/Ttest/Ttest/tests/mobile-search-results.spec.ts:145:21

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-search-results-resu-20022-very-supported-mobile-width-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-search-results-resu-20022-very-supported-mobile-width-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-search-results-resu-20022-very-supported-mobile-width-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-search-results-resu-20022-very-supported-mobile-width-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-search-results-resu-20022-very-supported-mobile-width-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  39) [chromium] › tests/true-target-parity.spec.ts:5:1 › capture and gate the mandatory current Idealista-derived target states 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-home')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-home')


      20 |   for (const [name, route, selector] of targets) {
      21 |     await page.goto(route)
    > 22 |     await expect(page.locator(selector)).toBeVisible()
         |                                          ^
      23 |     await page.screenshot({ path: path.join(output, `${name}.png`), animations: 'disabled' })
      24 |   }
      25 | })
        at /home/runner/work/Ttest/Ttest/tests/true-target-parity.spec.ts:22:42

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/true-target-parity-capture-f36b6-lista-derived-target-states-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/true-target-parity-capture-f36b6-lista-derived-target-states-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/true-target-parity-capture-f36b6-lista-derived-target-states-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/true-target-parity-capture-f36b6-lista-derived-target-states-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/true-target-parity-capture-f36b6-lista-derived-target-states-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  40) [chromium] › tests/visual-parity.spec.ts:24:1 › current mobile home, results, location and map visual states 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-home')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-home')


      24 | test('current mobile home, results, location and map visual states', async ({ page }) => {
      25 |   await open(page, '/#/')
    > 26 |   await expect(page.locator('.m2-home')).toBeVisible()
         |                                          ^
      27 |   await shot(page, 'current-home-390x844')
      28 |
      29 |   await open(page, '/#/buscar?q=Tenerife')
        at /home/runner/work/Ttest/Ttest/tests/visual-parity.spec.ts:26:42

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/visual-parity-current-mobi-201de-ation-and-map-visual-states-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/visual-parity-current-mobi-201de-ation-and-map-visual-states-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/visual-parity-current-mobi-201de-ation-and-map-visual-states-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/visual-parity-current-mobi-201de-ation-and-map-visual-states-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/visual-parity-current-mobi-201de-ation-and-map-visual-states-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  41) [chromium] › tests/visual-parity.spec.ts:43:1 › current mobile menu, auth and Russian visual states 

    Error: expect(page).toHaveScreenshot(expected) failed

      43038 pixels (ratio 0.14 of all image pixels) are different.

      Snapshot: current-menu-390x844.png

    Call log:
      - Expect "toHaveScreenshot(current-menu-390x844.png)" with timeout 7000ms
        - verifying given screenshot expectation
      - taking page screenshot
        - disabled all CSS animations
      - waiting for fonts to load...
      - fonts loaded
      - 43038 pixels (ratio 0.14 of all image pixels) are different.
      - waiting 100ms before taking screenshot
      - taking page screenshot
        - disabled all CSS animations
      - waiting for fonts to load...
      - fonts loaded
      - captured a stable screenshot
      - 43038 pixels (ratio 0.14 of all image pixels) are different.


       9 |
      10 | async function shot(page: Page, name: string) {
    > 11 |   await expect(page).toHaveScreenshot(`${name}.png`, {
         |                      ^
      12 |     animations: 'disabled',
      13 |     caret: 'hide',
      14 |     mask: [page.locator('.gm-style img[role="presentation"], .m2-result-card img, .property-card__media img, .property-gallery img')],
        at shot (/home/runner/work/Ttest/Ttest/tests/visual-parity.spec.ts:11:22)
        at /home/runner/work/Ttest/Ttest/tests/visual-parity.spec.ts:45:9

    attachment #1: current-menu-390x844 (image/png) ────────────────────────────────────────────────
    Expected: tests/visual-snapshots/chromium/current-menu-390x844.png
    Received: test-results/visual-parity-current-mobi-78df0-h-and-Russian-visual-states-chromium/current-menu-390x844-actual.png
    Diff:     test-results/visual-parity-current-mobi-78df0-h-and-Russian-visual-states-chromium/current-menu-390x844-diff.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/visual-parity-current-mobi-78df0-h-and-Russian-visual-states-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #3: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/visual-parity-current-mobi-78df0-h-and-Russian-visual-states-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/visual-parity-current-mobi-78df0-h-and-Russian-visual-states-chromium/error-context.md

    attachment #5: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/visual-parity-current-mobi-78df0-h-and-Russian-visual-states-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/visual-parity-current-mobi-78df0-h-and-Russian-visual-states-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  41 failed
    [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: mapa ─────
    [chromium] › tests/a11y.spec.ts:108:1 › delta fullscreen location flow has no serious or critical axe issues 
    [chromium] › tests/a11y.spec.ts:117:1 › delta drawing announcement and controls have no serious or critical axe issues 
    [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path 
    [chromium] › tests/apk-parity.spec.ts:15:3 › APK shell connected to the canonical web app › onboarding is completed once and survives reload 
    [chromium] › tests/apk-parity.spec.ts:22:3 › APK shell connected to the canonical web app › location, search, back and reload use real URLs 
    [chromium] › tests/apk-parity.spec.ts:38:3 › APK shell connected to the canonical web app › listing, account and publication actions open canonical routes 
    [chromium] › tests/apk-parity.spec.ts:54:3 › APK shell connected to the canonical web app › bottom tabs are deep links and favorites display stored data 
    [chromium] › tests/apk-regression-recovery.spec.ts:19:3 › PR43 regression recovery › location keeps all four APK actions and phone lookup is reachable 
    [chromium] › tests/apk-regression-recovery.spec.ts:27:3 › PR43 regression recovery › nearby success stores coordinates and radius in the URL 
    [chromium] › tests/apk-regression-recovery.spec.ts:38:3 › PR43 regression recovery › nearby rejects coordinates outside Tenerife without pretending success 
    [chromium] › tests/apk-regression-recovery.spec.ts:47:3 › PR43 regression recovery › nearby handles denied permission 
    [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles unavailable 
    [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles timeout 
    [chromium] › tests/apk-regression-recovery.spec.ts:80:3 › PR43 regression recovery › nearby handles an unavailable Geolocation API 
    [chromium] › tests/apk-regression-recovery.spec.ts:89:3 › PR43 regression recovery › polygon exposes Search this area and survives map-list-reload 
    [chromium] › tests/delta.spec.ts:307:1 › RESP-01..05 critical routes have no horizontal overflow at the required matrix 
    [chromium] › tests/e2e.spec.ts:172:1 › 31 responsive móvil sin desbordamiento y navegación inferior 
    [chromium] › tests/final-cleanup.spec.ts:263:1 › RESP-06 short mobile dialogs and critical map/uploader targets remain reachable 
    [chromium] › tests/final-mobile-delta-evidence.spec.ts:33:1 › capture unmasked final mobile delta evidence 
    [chromium] › tests/final-mobile-delta.spec.ts:14:1 › DELTA-MOBILE-01 home, occupant selector and location actions stay connected without changing the locked design 
    [chromium] › tests/final-mobile-delta.spec.ts:31:1 › DELTA-MOBILE-02 list, filters, sorting, map, back and reload are URL-backed 
    [chromium] › tests/final-mobile-delta.spec.ts:52:1 › DELTA-MOBILE-03 drawing and nearby search expose dedicated working map states 
    [chromium] › tests/final-mobile-delta.spec.ts:70:1 › DELTA-MOBILE-04 phone lookup opens a real listing and canonical detail remains usable 
    [chromium] › tests/final-mobile-delta.spec.ts:82:1 › DELTA-MOBILE-05 bottom tabs, favorites and protected account actions are real routes 
    [chromium] › tests/final-mobile-delta.spec.ts:96:1 › DELTA-MOBILE-06 ES, EN and RU persist and never introduce horizontal overflow 
    [chromium] › tests/map-responsive-parity.spec.ts:25:1 › results map keeps the current mobile shell and desktop split geometry across the responsive matrix 
    [chromium] › tests/master-task-visual.spec.ts:25:1 › master current home responsive matrix ─────
    [chromium] › tests/master-task-visual.spec.ts:35:1 › master current mobile list, map, drawing and location states 
    [chromium] › tests/master-task.spec.ts:13:1 › P0 current mobile home preserves the locked APK hierarchy and links all five tabs 
    [chromium] › tests/master-task.spec.ts:59:1 › P0 mobile and desktop maps retain their intended separate implementations 
    [chromium] › tests/master-task.spec.ts:80:1 › P1 core routes have no horizontal overflow or unexpected console errors across the responsive matrix 
    [chromium] › tests/mobile-map-ideal.spec.ts:79:1 › listing requirements are visually prominent in results 
    [chromium] › tests/mobile-search-results.spec.ts:33:1 › Vivienda and Turismo are the only rental-mode controls and filter real listings 
    [chromium] › tests/mobile-search-results.spec.ts:64:1 › price, area, room count and housing type filters change the listing set 
    [chromium] › tests/mobile-search-results.spec.ts:98:1 › sorting, photo carousel, favorites and hiding listings work together 
    [chromium] › tests/mobile-search-results.spec.ts:128:1 › contact opens the existing authentication flow and map returns to Google Maps 
    [chromium] › tests/mobile-search-results.spec.ts:141:1 › results, sorting and filters fit every supported mobile width 
    [chromium] › tests/true-target-parity.spec.ts:5:1 › capture and gate the mandatory current Idealista-derived target states 
    [chromium] › tests/visual-parity.spec.ts:24:1 › current mobile home, results, location and map visual states 
    [chromium] › tests/visual-parity.spec.ts:43:1 › current mobile menu, auth and Russian visual states 
  1 skipped
  117 passed (28.9m)
```
