# Mobile validation report

Generated: 2026-07-26T11:16:50Z

Overall: **FAIL**

| Check | Result | Exit code |
|---|---:|---:|
| npm ci | PASS | `0` |
| playwright install | PASS | `0` |
| lint | PASS | `0` |
| typecheck | PASS | `0` |
| build | PASS | `0` |
| e2e | FAIL | `1` |

## Last 700 log lines

```text
        at /home/runner/work/Ttest/Ttest/tests/mobile-location-map.spec.ts:106:48

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-location-map-curren-0ade2--nearby-listing-is-required-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-location-map-curren-0ade2--nearby-listing-is-required-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-location-map-curren-0ade2--nearby-listing-is-required-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-location-map-curren-0ade2--nearby-listing-is-required-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-location-map-curren-0ade2--nearby-listing-is-required-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  51) [chromium] › tests/mobile-location-map.spec.ts:110:1 › map current-location control centers the map and renders the user marker 

    Test timeout of 60000ms exceeded.

    Error: locator.click: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for getByRole('button', { name: 'Mi ubicación' })
        - locator resolved to <button disabled type="button" aria-label="Mi ubicación">…</button>
      - attempting click action
        2 × waiting for element to be visible, enabled and stable
          - element is not enabled
        - retrying click action
        - waiting 20ms
        2 × waiting for element to be visible, enabled and stable
          - element is not enabled
        - retrying click action
          - waiting 100ms
        117 × waiting for element to be visible, enabled and stable
            - element is not enabled
          - retrying click action
            - waiting 500ms


      114 |   await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
      115 |   await page.getByTestId('search-map').click()
    > 116 |   await page.getByRole('button', { name: 'Mi ubicación' }).click()
          |                                                            ^
      117 |   await expect(page.getByText('Ubicación encontrada')).toBeVisible()
      118 |   await expect(page.locator('.m2-user-location-marker')).toHaveCount(1)
      119 | })
        at /home/runner/work/Ttest/Ttest/tests/mobile-location-map.spec.ts:116:60

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-location-map-map-cu-5b594-and-renders-the-user-marker-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-location-map-map-cu-5b594-and-renders-the-user-marker-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-location-map-map-cu-5b594-and-renders-the-user-marker-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-location-map-map-cu-5b594-and-renders-the-user-marker-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-location-map-map-cu-5b594-and-renders-the-user-marker-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  52) [chromium] › tests/mobile-location-map.spec.ts:121:1 › draw and search map interfaces expose the connected listing layer without a result-count redesign 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('map-draw')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('map-draw')


      123 |   await page.getByRole('button', { name: 'Buscar en Tenerife' }).click()
      124 |   await page.getByTestId('draw-zone').click()
    > 125 |   await expect(page.getByTestId('map-draw')).toBeVisible()
          |                                              ^
      126 |   await expect(page.getByTestId('google-map')).toBeVisible()
      127 |   await expect(page.getByText('Tu propia zona')).toBeVisible()
      128 |   await expect(page.getByRole('button', { name: 'Cambiar capas' })).toBeVisible()
        at /home/runner/work/Ttest/Ttest/tests/mobile-location-map.spec.ts:125:46

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-location-map-draw-a-b984d-out-a-result-count-redesign-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-location-map-draw-a-b984d-out-a-result-count-redesign-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-location-map-draw-a-b984d-out-a-result-count-redesign-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-location-map-draw-a-b984d-out-a-result-count-redesign-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-location-map-draw-a-b984d-out-a-result-count-redesign-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  53) [chromium] › tests/mobile-map-ideal.spec.ts:38:1 › map is freely zoomable before explicit drawing activation 

    Error: expect(locator).toHaveAttribute(expected) failed

    Locator:  getByTestId('google-map')
    Expected: "interactive"
    Received: ""
    Timeout:  20000ms

    Call log:
      - Expect "toHaveAttribute" with timeout 20000ms
      - waiting for getByTestId('google-map')
        44 × locator resolved to <div class="m2-map-canvas" data-testid="google-map"></div>
           - unexpected value "null"


      19 |   const map = page.getByTestId('google-map')
      20 |   await expect(map).toBeVisible()
    > 21 |   await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
         |                     ^
      22 |   return map
      23 | }
      24 |
        at openMap (/home/runner/work/Ttest/Ttest/tests/mobile-map-ideal.spec.ts:21:21)
        at /home/runner/work/Ttest/Ttest/tests/mobile-map-ideal.spec.ts:40:15

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-map-is-fr-2a61e-explicit-drawing-activation-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-map-is-fr-2a61e-explicit-drawing-activation-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-map-ideal-map-is-fr-2a61e-explicit-drawing-activation-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-map-is-fr-2a61e-explicit-drawing-activation-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-map-ideal-map-is-fr-2a61e-explicit-drawing-activation-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  54) [chromium] › tests/mobile-map-ideal.spec.ts:57:1 › published listings are visible on the map and open the matching result 

    Error: expect(locator).toHaveAttribute(expected) failed

    Locator:  getByTestId('google-map')
    Expected: "interactive"
    Received: ""
    Timeout:  20000ms

    Call log:
      - Expect "toHaveAttribute" with timeout 20000ms
      - waiting for getByTestId('google-map')
        44 × locator resolved to <div class="m2-map-canvas" data-testid="google-map"></div>
           - unexpected value "null"


      19 |   const map = page.getByTestId('google-map')
      20 |   await expect(map).toBeVisible()
    > 21 |   await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
         |                     ^
      22 |   return map
      23 | }
      24 |
        at openMap (/home/runner/work/Ttest/Ttest/tests/mobile-map-ideal.spec.ts:21:21)
        at /home/runner/work/Ttest/Ttest/tests/mobile-map-ideal.spec.ts:59:15

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-published-f2999-nd-open-the-matching-result-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-published-f2999-nd-open-the-matching-result-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-map-ideal-published-f2999-nd-open-the-matching-result-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-map-ideal-published-f2999-nd-open-the-matching-result-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-map-ideal-published-f2999-nd-open-the-matching-result-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  55) [chromium] › tests/mobile-map-ideal.spec.ts:79:1 › listing requirements are visually prominent in results 

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

  56) [chromium] › tests/mobile-search-results.spec.ts:33:1 › Vivienda and Turismo are the only rental-mode controls and filter real listings 

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

  57) [chromium] › tests/mobile-search-results.spec.ts:64:1 › price, area, room count and housing type filters change the listing set 

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

  58) [chromium] › tests/mobile-search-results.spec.ts:98:1 › sorting, photo carousel, favorites and hiding listings work together 

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

  59) [chromium] › tests/mobile-search-results.spec.ts:128:1 › contact opens the existing authentication flow and map returns to Google Maps 

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

  60) [chromium] › tests/mobile-search-results.spec.ts:141:1 › results, sorting and filters fit every supported mobile width 

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

  61) [chromium] › tests/screenshot-locked-contract.spec.ts:17:1 › LOCK-OVERLAY derives at most two truthful image restrictions and omits empty overlays 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.price-marker-shell:visible').first()
    Expected: visible
    Timeout: 15000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 15000ms
      - waiting for locator('.price-marker-shell:visible').first()


      49 |   }
      50 |   const marker = page.locator('.price-marker-shell:visible').first()
    > 51 |   await expect(marker).toBeVisible({ timeout: 15_000 })
         |                        ^
      52 |   await marker.evaluate((element: HTMLElement) => element.click())
      53 |   await expect(page.locator('.map-selected-card')).toBeVisible({ timeout: 15_000 })
      54 |   await expect(page.locator('.map-selected-card__media > span')).toBeVisible()
        at /home/runner/work/Ttest/Ttest/tests/screenshot-locked-contract.spec.ts:51:24

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/screenshot-locked-contract-c9132-ns-and-omits-empty-overlays-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/screenshot-locked-contract-c9132-ns-and-omits-empty-overlays-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/screenshot-locked-contract-c9132-ns-and-omits-empty-overlays-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/screenshot-locked-contract-c9132-ns-and-omits-empty-overlays-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/screenshot-locked-contract-c9132-ns-and-omits-empty-overlays-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  62) [chromium] › tests/true-target-parity.spec.ts:5:1 › capture and gate the mandatory current Idealista-derived target states 

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

  63) [chromium] › tests/visual-parity.spec.ts:24:1 › current mobile home, results, location and map visual states 

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

  64) [chromium] › tests/visual-parity.spec.ts:43:1 › current mobile menu, auth and Russian visual states 

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

  64 failed
    [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: mapa ─────
    [chromium] › tests/a11y.spec.ts:108:1 › delta fullscreen location flow has no serious or critical axe issues 
    [chromium] › tests/a11y.spec.ts:117:1 › delta drawing announcement and controls have no serious or critical axe issues 
    [chromium] › tests/acceptance-flows.spec.ts:252:1 › 10–13 map marker/card sync, marker preview, bounds and polygon filtering 
    [chromium] › tests/acceptance-flows.spec.ts:409:1 › 21–24 wizard validates, restores/reset draft, previews user data, creates and edits 
    [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path 
    [chromium] › tests/apk-parity.spec.ts:15:3 › APK shell connected to the canonical web app › onboarding is completed once and survives reload 
    [chromium] › tests/apk-parity.spec.ts:22:3 › APK shell connected to the canonical web app › location, search, back and reload use real URLs 
    [chromium] › tests/apk-parity.spec.ts:38:3 › APK shell connected to the canonical web app › listing, account and publication actions open canonical routes 
    [chromium] › tests/apk-parity.spec.ts:54:3 › APK shell connected to the canonical web app › bottom tabs are deep links and favorites display stored data 
    [chromium] › tests/apk-parity.spec.ts:67:3 › APK shell connected to the canonical web app › map and drawing screens are reflected in the URL 
    [chromium] › tests/apk-parity.spec.ts:77:3 › APK shell connected to the canonical web app › missing APK location actions work: nearby and phone lookup 
    [chromium] › tests/apk-regression-recovery.spec.ts:19:3 › PR43 regression recovery › location keeps all four APK actions and phone lookup is reachable 
    [chromium] › tests/apk-regression-recovery.spec.ts:27:3 › PR43 regression recovery › nearby success stores coordinates and radius in the URL 
    [chromium] › tests/apk-regression-recovery.spec.ts:38:3 › PR43 regression recovery › nearby rejects coordinates outside Tenerife without pretending success 
    [chromium] › tests/apk-regression-recovery.spec.ts:47:3 › PR43 regression recovery › nearby handles denied permission 
    [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles unavailable 
    [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles timeout 
    [chromium] › tests/apk-regression-recovery.spec.ts:80:3 › PR43 regression recovery › nearby handles an unavailable Geolocation API 
    [chromium] › tests/apk-regression-recovery.spec.ts:89:3 › PR43 regression recovery › polygon exposes Search this area and survives map-list-reload 
    [chromium] › tests/delta-matrix.spec.ts:267:1 › MAP-04 visible-area state activates after movement and resets after search 
    [chromium] › tests/delta.spec.ts:292:1 › FILTER-01 and MAP-01..03 new filters serialize and map preview shows restrictions 
    [chromium] › tests/delta.spec.ts:307:1 › RESP-01..05 critical routes have no horizontal overflow at the required matrix 
    [chromium] › tests/e2e.spec.ts:68:1 › 11–15 Google Maps, кластер, выбор, границы и полигон ─────
    [chromium] › tests/e2e.spec.ts:172:1 › 31 responsive móvil sin desbordamiento y navegación inferior 
    [chromium] › tests/final-cleanup.spec.ts:240:1 › MAP-06 selecting a card or marker preserves viewport and map instance 
    [chromium] › tests/final-cleanup.spec.ts:263:1 › RESP-06 short mobile dialogs and critical map/uploader targets remain reachable 
    [chromium] › tests/final-mobile-delta-evidence.spec.ts:33:1 › capture unmasked final mobile delta evidence 
    [chromium] › tests/final-mobile-delta.spec.ts:14:1 › DELTA-MOBILE-01 home, occupant selector and location actions stay connected without changing the locked design 
    [chromium] › tests/final-mobile-delta.spec.ts:31:1 › DELTA-MOBILE-02 list, filters, sorting, map, back and reload are URL-backed 
    [chromium] › tests/final-mobile-delta.spec.ts:52:1 › DELTA-MOBILE-03 drawing and nearby search expose dedicated working map states 
    [chromium] › tests/final-mobile-delta.spec.ts:70:1 › DELTA-MOBILE-04 phone lookup opens a real listing and canonical detail remains usable 
    [chromium] › tests/final-mobile-delta.spec.ts:82:1 › DELTA-MOBILE-05 bottom tabs, favorites and protected account actions are real routes 
    [chromium] › tests/final-mobile-delta.spec.ts:96:1 › DELTA-MOBILE-06 ES, EN and RU persist and never introduce horizontal overflow 
    [chromium] › tests/google-maps-final-acceptance.spec.ts:26:1 › selected Advanced Marker has priority, opens the sheet, and programmatic selection stays clean 
    [chromium] › tests/google-maps-final-acceptance.spec.ts:40:1 › manual pan exposes Search this area while a result refit does not 
    [chromium] › tests/google-maps-final-acceptance.spec.ts:53:1 › map/list, multiple canonical zones, and polygon restore from URL and reload 
    [chromium] › tests/google-maps-final-acceptance.spec.ts:71:1 › official district hierarchy selects a stable ID and restores it from URL 
    [chromium] › tests/google-maps-final-acceptance.spec.ts:88:1 › production configuration is secret-backed and auth errors keep a usable fallback 
    [chromium] › tests/map-responsive-parity.spec.ts:25:1 › results map keeps the current mobile shell and desktop split geometry across the responsive matrix 
    [chromium] › tests/master-task-visual.spec.ts:25:1 › master current home responsive matrix ─────
    [chromium] › tests/master-task-visual.spec.ts:35:1 › master current mobile list, map, drawing and location states 
    [chromium] › tests/master-task-visual.spec.ts:59:1 › master desktop municipality selection and split map states 
    [chromium] › tests/master-task.spec.ts:13:1 › P0 current mobile home preserves the locked APK hierarchy and links all five tabs 
    [chromium] › tests/master-task.spec.ts:47:1 › P1 municipality list remains usable when detailed GeoJSON cannot load 
    [chromium] › tests/master-task.spec.ts:59:1 › P0 mobile and desktop maps retain their intended separate implementations 
    [chromium] › tests/master-task.spec.ts:80:1 › P1 core routes have no horizontal overflow or unexpected console errors across the responsive matrix 
    [chromium] › tests/mobile-freehand-map.spec.ts:14:1 › map stays interactive until the drawing button is pressed 
    [chromium] › tests/mobile-location-map.spec.ts:78:1 › location screen contains the four APK actions and address submit opens map 
    [chromium] › tests/mobile-location-map.spec.ts:96:1 › current location opens the map and keeps the user coordinates even when no nearby listing is required 
    [chromium] › tests/mobile-location-map.spec.ts:110:1 › map current-location control centers the map and renders the user marker 
    [chromium] › tests/mobile-location-map.spec.ts:121:1 › draw and search map interfaces expose the connected listing layer without a result-count redesign 
    [chromium] › tests/mobile-map-ideal.spec.ts:38:1 › map is freely zoomable before explicit drawing activation 
    [chromium] › tests/mobile-map-ideal.spec.ts:57:1 › published listings are visible on the map and open the matching result 
    [chromium] › tests/mobile-map-ideal.spec.ts:79:1 › listing requirements are visually prominent in results 
    [chromium] › tests/mobile-search-results.spec.ts:33:1 › Vivienda and Turismo are the only rental-mode controls and filter real listings 
    [chromium] › tests/mobile-search-results.spec.ts:64:1 › price, area, room count and housing type filters change the listing set 
    [chromium] › tests/mobile-search-results.spec.ts:98:1 › sorting, photo carousel, favorites and hiding listings work together 
    [chromium] › tests/mobile-search-results.spec.ts:128:1 › contact opens the existing authentication flow and map returns to Google Maps 
    [chromium] › tests/mobile-search-results.spec.ts:141:1 › results, sorting and filters fit every supported mobile width 
    [chromium] › tests/screenshot-locked-contract.spec.ts:17:1 › LOCK-OVERLAY derives at most two truthful image restrictions and omits empty overlays 
    [chromium] › tests/true-target-parity.spec.ts:5:1 › capture and gate the mandatory current Idealista-derived target states 
    [chromium] › tests/visual-parity.spec.ts:24:1 › current mobile home, results, location and map visual states 
    [chromium] › tests/visual-parity.spec.ts:43:1 › current mobile menu, auth and Russian visual states 
  1 skipped
  94 passed (36.9m)
exit=1
```
