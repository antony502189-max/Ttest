# Playwright spec-by-spec validation

## `tests/a11y.spec.ts` — FAIL (exit 1)

```text

Running 28 tests using 1 worker

  ✓   1 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: inicio (2.2s)
  ✓   2 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: resultados (3.6s)
  ✓   3 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: mapa (5.3s)
  ✓   4 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: detalle (2.9s)
  ✓   5 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: acceso (1.9s)
  ✓   6 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: registro (1.9s)
  ✓   7 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: recuperar (1.8s)
  ✓   8 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: restablecer (1.8s)
  ✓   9 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: favoritos (1.7s)
  ✓  10 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: ayuda (1.9s)
  ✓  11 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: guardadas (1.8s)
  ✓  12 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: perfil (1.9s)
  ✓  13 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: mis anuncios (2.0s)
  ✓  14 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: publicar (1.8s)
  ✓  15 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: administración (2.1s)
  ✓  16 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: inicio (1.5s)
  ✓  17 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: resultados (2.6s)
  ✘  18 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: mapa (1.0m)
  ✓  19 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: detalle (2.6s)
  ✓  20 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: publicar (1.8s)
  ✓  21 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: administración (2.0s)
  ✓  22 [chromium] › tests/a11y.spec.ts:95:1 › delta contact dialog supports keyboard focus and axe (2.6s)
  ✘  23 [chromium] › tests/a11y.spec.ts:108:1 › delta fullscreen location flow has no serious or critical axe issues (1.0m)
  ✘  24 [chromium] › tests/a11y.spec.ts:117:1 › delta drawing announcement and controls have no serious or critical axe issues (1.0m)
  ✓  25 [chromium] › tests/a11y.spec.ts:126:1 › delta avatar uploader has no serious or critical axe issues (2.0s)
  ✓  26 [chromium] › tests/a11y.spec.ts:133:1 › delta image uploader has no serious or critical axe issues (2.8s)
  ✓  27 [chromium] › tests/a11y.spec.ts:140:1 › delta approximate location map and controls have no serious or critical axe issues (1.9s)
  ✓  28 [chromium] › tests/a11y.spec.ts:148:1 › delta account deletion confirmation has no serious or critical axe issues (1.8s)


  1) [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: mapa ────

    Test timeout of 60000ms exceeded.

    Error: locator.waitFor: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for locator('.google-map-canvas, [data-testid="google-map"]') to be visible


      49 |     .catch(() => undefined);
      50 |   if (route.name === "mapa")
    > 51 |     await page.locator('.google-map-canvas, [data-testid="google-map"]').waitFor({ state: "visible" });
         |                                                                          ^
      52 | };
      53 |
      54 | const assertNoSeriousViolations = async (page: Page) => {
        at openRoute (/home/runner/work/Ttest/Ttest/tests/a11y.spec.ts:51:74)
        at /home/runner/work/Ttest/Ttest/tests/a11y.spec.ts:90:5

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/a11y-axe-móvil-390px-sin-impactos-serious-critical-mapa-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/a11y-axe-móvil-390px-sin-impactos-serious-critical-mapa-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/a11y-axe-móvil-390px-sin-impactos-serious-critical-mapa-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/a11y-axe-móvil-390px-sin-impactos-serious-critical-mapa-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/a11y-axe-móvil-390px-sin-impactos-serious-critical-mapa-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  2) [chromium] › tests/a11y.spec.ts:108:1 › delta fullscreen location flow has no serious or critical axe issues 

    Test timeout of 60000ms exceeded.

    Error: locator.click: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for getByRole('button', { name: 'Buscar en Tenerife' })


      109 |   await page.setViewportSize({ width: 390, height: 844 });
      110 |   await openRoute(page, { name: "inicio", path: "/#/" });
    > 111 |   await page.getByRole("button", { name: "Buscar en Tenerife" }).click();
          |                                                                  ^
      112 |   await expect(page.getByTestId("location-screen")).toBeVisible();
      113 |   const results = await new AxeBuilder({ page }).include(".m2-location").analyze();
      114 |   expect(results.violations.filter((item) => item.impact === "serious" || item.impact === "critical")).toEqual([]);
        at /home/runner/work/Ttest/Ttest/tests/a11y.spec.ts:111:66

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/a11y-delta-fullscreen-loca-e211d-ious-or-critical-axe-issues-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/a11y-delta-fullscreen-loca-e211d-ious-or-critical-axe-issues-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/a11y-delta-fullscreen-loca-e211d-ious-or-critical-axe-issues-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/a11y-delta-fullscreen-loca-e211d-ious-or-critical-axe-issues-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/a11y-delta-fullscreen-loca-e211d-ious-or-critical-axe-issues-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  3) [chromium] › tests/a11y.spec.ts:117:1 › delta drawing announcement and controls have no serious or critical axe issues 

    Test timeout of 60000ms exceeded.

    Error: locator.waitFor: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for locator('.google-map-canvas, [data-testid="google-map"]') to be visible


      49 |     .catch(() => undefined);
      50 |   if (route.name === "mapa")
    > 51 |     await page.locator('.google-map-canvas, [data-testid="google-map"]').waitFor({ state: "visible" });
         |                                                                          ^
      52 | };
      53 |
      54 | const assertNoSeriousViolations = async (page: Page) => {
        at openRoute (/home/runner/work/Ttest/Ttest/tests/a11y.spec.ts:51:74)
        at /home/runner/work/Ttest/Ttest/tests/a11y.spec.ts:119:3

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/a11y-delta-drawing-announc-3afd5-ious-or-critical-axe-issues-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/a11y-delta-drawing-announc-3afd5-ious-or-critical-axe-issues-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/a11y-delta-drawing-announc-3afd5-ious-or-critical-axe-issues-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/a11y-delta-drawing-announc-3afd5-ious-or-critical-axe-issues-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/a11y-delta-drawing-announc-3afd5-ious-or-critical-axe-issues-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  3 failed
    [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: mapa ─────
    [chromium] › tests/a11y.spec.ts:108:1 › delta fullscreen location flow has no serious or critical axe issues 
    [chromium] › tests/a11y.spec.ts:117:1 › delta drawing announcement and controls have no serious or critical axe issues 
  25 passed (4.1m)
```

## `tests/acceptance-flows.spec.ts` — FAIL (exit 1)

```text

Running 12 tests using 1 worker

  ✓   1 [chromium] › tests/acceptance-flows.spec.ts:65:1 › 01–03 rental mode, búsqueda por fecha y selección de varias zonas (4.9s)
  ✓   2 [chromium] › tests/acceptance-flows.spec.ts:86:1 › 04 every visible filter is wired to data and URL (7.8s)
  ✓   3 [chromium] › tests/acceptance-flows.spec.ts:177:1 › 05–08 filter count, individual chips, clear, URL reload and history navigation (4.1s)
  ✘   4 [chromium] › tests/acceptance-flows.spec.ts:202:1 › 09 sorting by date and both prices plus real disjoint pagination (2.6s)
  ✓   5 [chromium] › tests/acceptance-flows.spec.ts:252:1 › 10–13 map marker/card sync, marker preview, bounds and polygon filtering (4.7s)
  ✓   6 [chromium] › tests/acceptance-flows.spec.ts:309:1 › 14–15 favorites and complete saved-search restoration persist (5.7s)
  ✓   7 [chromium] › tests/acceptance-flows.spec.ts:334:1 › 16–18 listing gallery keyboard, contact, share and report mutate state (3.3s)
  ✓   8 [chromium] › tests/acceptance-flows.spec.ts:381:1 › 19–20 registration, login persistence, logout, recovery and reset flows (3.6s)
  ✓   9 [chromium] › tests/acceptance-flows.spec.ts:409:1 › 21–24 wizard validates, restores/reset draft, previews user data, creates and edits (6.0s)
  ✓  10 [chromium] › tests/acceptance-flows.spec.ts:462:1 › 25–26 hide/show, renew and delete listing all change shared data (4.5s)
  ✓  11 [chromium] › tests/acceptance-flows.spec.ts:487:1 › 27 admin status filter, approve/hide/reject, user blocking and CSV are stateful (4.6s)
  ✘  12 [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path (1.0m)


  1) [chromium] › tests/acceptance-flows.spec.ts:202:1 › 09 sorting by date and both prices plus real disjoint pagination 

    Error: expect(received).toEqual(expected) // deep equality

    - Expected  - 6
    + Received  + 6

      Array [
    -   755,
    -   710,
    -   620,
    -   530,
    -   485,
    +   350,
        395,
        395,
    -   350,
    +   485,
    +   530,
    +   620,
    +   710,
    +   755,
        350,
      ]

      231 |     await page.locator(".results-list .price-block strong").allTextContents()
      232 |   ).map((value) => Number.parseInt(value.replace(/\D/g, "")));
    > 233 |   expect(high).toEqual([...high].sort((a, b) => b - a));
          |                ^
      234 |   await page.getByLabel("Ordenar resultados").selectOption("Precio más bajo");
      235 |   const low = (
      236 |     await page.locator(".results-list .price-block strong").allTextContents()
        at /home/runner/work/Ttest/Ttest/tests/acceptance-flows.spec.ts:233:16

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/acceptance-flows-09-sortin-23b56-us-real-disjoint-pagination-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/acceptance-flows-09-sortin-23b56-us-real-disjoint-pagination-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/acceptance-flows-09-sortin-23b56-us-real-disjoint-pagination-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/acceptance-flows-09-sortin-23b56-us-real-disjoint-pagination-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/acceptance-flows-09-sortin-23b56-us-real-disjoint-pagination-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  2) [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path 

    Test timeout of 60000ms exceeded.

    Error: locator.focus: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for getByTestId('open-location')


      544 |   await page.keyboard.press("Enter");
      545 |   const search = page.getByTestId("open-location");
    > 546 |   await search.focus();
          |                ^
      547 |   await page.keyboard.press("Enter");
      548 |   await expect(page).toHaveURL(/buscar/);
      549 |   await expect(page.locator(".m2-bottom-nav")).toBeVisible();
        at /home/runner/work/Ttest/Ttest/tests/acceptance-flows.spec.ts:546:16

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/acceptance-flows-28–29-mob-fcd99-keyboard-only-critical-path-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/acceptance-flows-28–29-mob-fcd99-keyboard-only-critical-path-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/acceptance-flows-28–29-mob-fcd99-keyboard-only-critical-path-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/acceptance-flows-28–29-mob-fcd99-keyboard-only-critical-path-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/acceptance-flows-28–29-mob-fcd99-keyboard-only-critical-path-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  2 failed
    [chromium] › tests/acceptance-flows.spec.ts:202:1 › 09 sorting by date and both prices plus real disjoint pagination 
    [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path 
  10 passed (1.9m)
```

## `tests/apk-parity.spec.ts` — FAIL (exit 1)

```text

Running 7 tests using 1 worker

  ✘  1 [chromium] › tests/apk-parity.spec.ts:15:3 › APK shell connected to the canonical web app › onboarding is completed once and survives reload (9.0s)
  ✘  2 [chromium] › tests/apk-parity.spec.ts:22:3 › APK shell connected to the canonical web app › location, search, back and reload use real URLs (8.7s)
  ✘  3 [chromium] › tests/apk-parity.spec.ts:38:3 › APK shell connected to the canonical web app › listing, account and publication actions open canonical routes (1.0m)
  ✘  4 [chromium] › tests/apk-parity.spec.ts:54:3 › APK shell connected to the canonical web app › bottom tabs are deep links and favorites display stored data (1.0m)
  ✓  5 [chromium] › tests/apk-parity.spec.ts:67:3 › APK shell connected to the canonical web app › map and drawing screens are reflected in the URL (2.8s)
  ✓  6 [chromium] › tests/apk-parity.spec.ts:77:3 › APK shell connected to the canonical web app › missing APK location actions work: nearby and phone lookup (3.2s)
  ✓  7 [chromium] › tests/apk-parity.spec.ts:99:1 › desktop keeps the existing responsive route-based design (1.4s)


  1) [chromium] › tests/apk-parity.spec.ts:15:3 › APK shell connected to the canonical web app › onboarding is completed once and survives reload 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('open-location')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('open-location')


      16 |     await finishOnboarding(page)
      17 |     await page.reload()
    > 18 |     await expect(page.getByTestId('open-location')).toBeVisible()
         |                                                     ^
      19 |     await expect(page.getByText('Selecciona el idioma de la aplicación')).toHaveCount(0)
      20 |   })
      21 |
        at /home/runner/work/Ttest/Ttest/tests/apk-parity.spec.ts:18:53

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-adfa2-ed-once-and-survives-reload-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-adfa2-ed-once-and-survives-reload-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-parity-APK-shell-conne-adfa2-ed-once-and-survives-reload-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-adfa2-ed-once-and-survives-reload-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-parity-APK-shell-conne-adfa2-ed-once-and-survives-reload-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  2) [chromium] › tests/apk-parity.spec.ts:22:3 › APK shell connected to the canonical web app › location, search, back and reload use real URLs 

    Error: expect(page).toHaveURL(expected) failed

    Expected pattern: /#\/buscar\?q=Tenerife&alquiler=long/
    Received string:  "http://127.0.0.1:4173/#/?panel=ubicacion"
    Timeout: 7000ms

    Call log:
      - Expect "toHaveURL" with timeout 7000ms
        18 × unexpected value "http://127.0.0.1:4173/#/?panel=ubicacion"


      30 |     await page.getByRole('button', { name: 'Vivienda', exact: true }).click()
      31 |     await page.getByTestId('open-location').click()
    > 32 |     await expect(page).toHaveURL(/#\/buscar\?q=Tenerife&alquiler=long/)
         |                        ^
      33 |     await expect(page.getByTestId('mobile-results')).toBeVisible()
      34 |     await page.reload()
      35 |     await expect(page.getByTestId('mobile-results')).toBeVisible()
        at /home/runner/work/Ttest/Ttest/tests/apk-parity.spec.ts:32:24

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-169a1-ck-and-reload-use-real-URLs-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-169a1-ck-and-reload-use-real-URLs-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-parity-APK-shell-conne-169a1-ck-and-reload-use-real-URLs-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-169a1-ck-and-reload-use-real-URLs-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-parity-APK-shell-conne-169a1-ck-and-reload-use-real-URLs-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  3) [chromium] › tests/apk-parity.spec.ts:38:3 › APK shell connected to the canonical web app › listing, account and publication actions open canonical routes 

    Test timeout of 60000ms exceeded.

    Error: locator.click: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for locator('.m2-result-card__image-button').first()


      40 |     await page.getByTestId('open-location').click()
      41 |     const firstListing = page.locator('.m2-result-card__image-button').first()
    > 42 |     await firstListing.click()
         |                        ^
      43 |     await expect(page).toHaveURL(/#\/habitacion\//)
      44 |     await expect(page.locator('.idealista-listing-page')).toBeVisible()
      45 |
        at /home/runner/work/Ttest/Ttest/tests/apk-parity.spec.ts:42:24

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-69f9e-tions-open-canonical-routes-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-69f9e-tions-open-canonical-routes-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-parity-APK-shell-conne-69f9e-tions-open-canonical-routes-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-69f9e-tions-open-canonical-routes-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-parity-APK-shell-conne-69f9e-tions-open-canonical-routes-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  4) [chromium] › tests/apk-parity.spec.ts:54:3 › APK shell connected to the canonical web app › bottom tabs are deep links and favorites display stored data 

    Test timeout of 60000ms exceeded.

    Error: locator.click: Test timeout of 60000ms exceeded.
    Call log:
      - waiting for locator('.m2-result-card__favorite').first()


      55 |     await finishOnboarding(page)
      56 |     await page.getByTestId('open-location').click()
    > 57 |     await page.locator('.m2-result-card__favorite').first().click()
         |                                                             ^
      58 |     await page.getByRole('button', { name: 'Volver' }).click()
      59 |     await expect(page.getByTestId('mobile-results')).toHaveCount(0)
      60 |     await page.getByRole('button', { name: 'Favoritos', exact: true }).click()
        at /home/runner/work/Ttest/Ttest/tests/apk-parity.spec.ts:57:61

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-2fd6a-vorites-display-stored-data-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-2fd6a-vorites-display-stored-data-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-parity-APK-shell-conne-2fd6a-vorites-display-stored-data-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-parity-APK-shell-conne-2fd6a-vorites-display-stored-data-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-parity-APK-shell-conne-2fd6a-vorites-display-stored-data-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  4 failed
    [chromium] › tests/apk-parity.spec.ts:15:3 › APK shell connected to the canonical web app › onboarding is completed once and survives reload 
    [chromium] › tests/apk-parity.spec.ts:22:3 › APK shell connected to the canonical web app › location, search, back and reload use real URLs 
    [chromium] › tests/apk-parity.spec.ts:38:3 › APK shell connected to the canonical web app › listing, account and publication actions open canonical routes 
    [chromium] › tests/apk-parity.spec.ts:54:3 › APK shell connected to the canonical web app › bottom tabs are deep links and favorites display stored data 
  3 passed (2.5m)
```

## `tests/apk-regression-recovery.spec.ts` — FAIL (exit 1)

```text
        npx playwright show-trace test-results/apk-regression-recovery-PR-29f96-y-handles-denied-permission-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  5) [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles unavailable 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('location-screen')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('location-screen')


       6 |   await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
       7 |   await page.goto('/#/?panel=ubicacion')
    >  8 |   await expect(page.getByTestId('location-screen')).toBeVisible()
         |                                                     ^
       9 | }
      10 |
      11 | async function allowTenerifeLocation(context: BrowserContext) {
        at openLocation (/home/runner/work/Ttest/Ttest/tests/apk-regression-recovery.spec.ts:8:53)
        at /home/runner/work/Ttest/Ttest/tests/apk-regression-recovery.spec.ts:74:7

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-dd9ef--nearby-handles-unavailable-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-dd9ef--nearby-handles-unavailable-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-regression-recovery-PR-dd9ef--nearby-handles-unavailable-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-dd9ef--nearby-handles-unavailable-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-regression-recovery-PR-dd9ef--nearby-handles-unavailable-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  6) [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles timeout 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('location-screen')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('location-screen')


       6 |   await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
       7 |   await page.goto('/#/?panel=ubicacion')
    >  8 |   await expect(page.getByTestId('location-screen')).toBeVisible()
         |                                                     ^
       9 | }
      10 |
      11 | async function allowTenerifeLocation(context: BrowserContext) {
        at openLocation (/home/runner/work/Ttest/Ttest/tests/apk-regression-recovery.spec.ts:8:53)
        at /home/runner/work/Ttest/Ttest/tests/apk-regression-recovery.spec.ts:74:7

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-1ed61-very-nearby-handles-timeout-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-1ed61-very-nearby-handles-timeout-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-regression-recovery-PR-1ed61-very-nearby-handles-timeout-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-1ed61-very-nearby-handles-timeout-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-regression-recovery-PR-1ed61-very-nearby-handles-timeout-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  7) [chromium] › tests/apk-regression-recovery.spec.ts:80:3 › PR43 regression recovery › nearby handles an unavailable Geolocation API 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('location-screen')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('location-screen')


       6 |   await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
       7 |   await page.goto('/#/?panel=ubicacion')
    >  8 |   await expect(page.getByTestId('location-screen')).toBeVisible()
         |                                                     ^
       9 | }
      10 |
      11 | async function allowTenerifeLocation(context: BrowserContext) {
        at openLocation (/home/runner/work/Ttest/Ttest/tests/apk-regression-recovery.spec.ts:8:53)
        at /home/runner/work/Ttest/Ttest/tests/apk-regression-recovery.spec.ts:84:5

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-d70fa-unavailable-Geolocation-API-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-d70fa-unavailable-Geolocation-API-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-regression-recovery-PR-d70fa-unavailable-Geolocation-API-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-d70fa-unavailable-Geolocation-API-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-regression-recovery-PR-d70fa-unavailable-Geolocation-API-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  8) [chromium] › tests/apk-regression-recovery.spec.ts:89:3 › PR43 regression recovery › polygon exposes Search this area and survives map-list-reload 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('search-this-area')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('search-this-area')


      93 |
      94 |     const searchArea = page.getByTestId('search-this-area')
    > 95 |     await expect(searchArea).toBeVisible()
         |                              ^
      96 |     await searchArea.click()
      97 |     await expect(page).toHaveURL(/vista=mapa/)
      98 |     await expect(page).not.toHaveURL(/dibujar=1/)
        at /home/runner/work/Ttest/Ttest/tests/apk-regression-recovery.spec.ts:95:30

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-31f27-nd-survives-map-list-reload-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-31f27-nd-survives-map-list-reload-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/apk-regression-recovery-PR-31f27-nd-survives-map-list-reload-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/apk-regression-recovery-PR-31f27-nd-survives-map-list-reload-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/apk-regression-recovery-PR-31f27-nd-survives-map-list-reload-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  8 failed
    [chromium] › tests/apk-regression-recovery.spec.ts:19:3 › PR43 regression recovery › location keeps all four APK actions and phone lookup is reachable 
    [chromium] › tests/apk-regression-recovery.spec.ts:27:3 › PR43 regression recovery › nearby success stores coordinates and radius in the URL 
    [chromium] › tests/apk-regression-recovery.spec.ts:38:3 › PR43 regression recovery › nearby rejects coordinates outside Tenerife without pretending success 
    [chromium] › tests/apk-regression-recovery.spec.ts:47:3 › PR43 regression recovery › nearby handles denied permission 
    [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles unavailable 
    [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles timeout 
    [chromium] › tests/apk-regression-recovery.spec.ts:80:3 › PR43 regression recovery › nearby handles an unavailable Geolocation API 
    [chromium] › tests/apk-regression-recovery.spec.ts:89:3 › PR43 regression recovery › polygon exposes Search this area and survives map-list-reload 
```

## `tests/customer-qa.spec.ts` — PASS (exit 0)

```text

Running 1 test using 1 worker

  ✓  1 [chromium] › tests/customer-qa.spec.ts:3:1 › mobile search filters are fully localized and clamp numeric values (1.5s)

  1 passed (2.6s)
```

## `tests/delta-matrix.spec.ts` — PASS (exit 0)

```text

Running 10 tests using 1 worker

  ✓   1 [chromium] › tests/delta-matrix.spec.ts:50:1 › USR-03..05 history, discarded listings and guest data stay in separate scopes (6.5s)
  ✓   2 [chromium] › tests/delta-matrix.spec.ts:91:1 › STORE-05 validator rejects incomplete listing payloads instead of accepting corrupted data (2.7s)
  ✓   3 [chromium] › tests/delta-matrix.spec.ts:101:1 › MEDIA-05..08 exact MIME, cleanup, quota feedback and missing-blob fallback work (4.5s)
  ✓   4 [chromium] › tests/delta-matrix.spec.ts:139:1 › ROOM-01..04 MODE-01..03 holiday wizard values persist and all new filters affect results (6.8s)
  ✓   5 [chromium] › tests/delta-matrix.spec.ts:185:1 › LOC-01 selected zone coordinates persist, edit restores them and exact street stays private (4.2s)
  ✓   6 [chromium] › tests/delta-matrix.spec.ts:205:1 › PROFILE-02 publish defaults and preview expose only enabled contact methods (4.5s)
  ✓   7 [chromium] › tests/delta-matrix.spec.ts:230:1 › FILTER-02..06 new filters have chips, reset, reload and history navigation (4.4s)
  ✓   8 [chromium] › tests/delta-matrix.spec.ts:267:1 › MAP-04 visible-area state activates after movement and resets after search (3.0s)
  ✓   9 [chromium] › tests/delta-matrix.spec.ts:279:1 › MAP-05 Google Maps loader errors expose the accessible map fallback (2.7s)
  ✓  10 [chromium] › tests/delta-matrix.spec.ts:287:1 › WIZ-04 reset clears dirty state and short-height filter drawer remains usable (3.1s)

  10 passed (43.7s)
```

## `tests/delta.spec.ts` — FAIL (exit 1)

```text

Running 14 tests using 1 worker

  ✓   1 [chromium] › tests/delta.spec.ts:51:1 › OWN-01..04 owner isolation and foreign edit/actions are blocked (3.5s)
  ✓   2 [chromium] › tests/delta.spec.ts:61:1 › OWN-05 new host has an empty cabinet while demo host keeps seed listings (2.2s)
  ✓   3 [chromium] › tests/delta.spec.ts:74:1 › USR-01..03 favorites, saved searches and history are user scoped (4.7s)
  ✓   4 [chromium] › tests/delta.spec.ts:88:1 › STORE-01..02 versioned payload survives mass deletion and migrates legacy v2 (2.8s)
  ✓   5 [chromium] › tests/delta.spec.ts:107:1 › STORE-03..04 corrupted JSON falls back and quota errors are visible (3.9s)
  ✓   6 [chromium] › tests/delta.spec.ts:125:1 › MEDIA-01..03 IndexedDB photo refs survive draft, publish and reload (9.9s)
  ✓   7 [chromium] › tests/delta.spec.ts:165:1 › MEDIA-04 avatar upload/remove persists and profile cancel restores values (4.7s)
  ✓   8 [chromium] › tests/delta.spec.ts:195:1 › ROOM-01..04 and MODE-01..03 migrated room and rental models render consistently (2.4s)
  ✓   9 [chromium] › tests/delta.spec.ts:205:1 › CONTACT-01..06 confirmation gates channels and local form handles abuse states (4.2s)
  ✓  10 [chromium] › tests/delta.spec.ts:237:1 › LIFE-01..04 expiration hides public listing and renew republishes it (3.9s)
  ✓  11 [chromium] › tests/delta.spec.ts:277:1 › WIZ-01..03 dirty state warns only after edits and save clears it (3.1s)
  ✓  12 [chromium] › tests/delta.spec.ts:292:1 › FILTER-01 and MAP-01..03 new filters serialize and map preview shows restrictions (3.8s)
  ✘  13 [chromium] › tests/delta.spec.ts:307:1 › RESP-01..05 critical routes have no horizontal overflow at the required matrix (4.1m)
  ✓  14 [chromium] › tests/delta.spec.ts:348:1 › A11Y-01 contact dialog has no serious or critical axe issues (3.1s)


  1) [chromium] › tests/delta.spec.ts:307:1 › RESP-01..05 critical routes have no horizontal overflow at the required matrix 

    Test timeout of 240000ms exceeded.

    Error: locator.waitFor: Test timeout of 240000ms exceeded.
    Call log:
      - waiting for locator('.google-map-canvas, .m2-map-canvas') to be visible


      322 |       await page.goto(route)
      323 |       await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
    > 324 |       if (route.includes('vista=mapa')) await page.locator('.google-map-canvas, .m2-map-canvas').waitFor({ state: 'visible' })
          |                                                                                                  ^
      325 |       expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), `${route} at ${width}x${height}`).toBeTruthy()
      326 |     }
      327 |     await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify(null)))
        at /home/runner/work/Ttest/Ttest/tests/delta.spec.ts:324:98

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/delta-RESP-01-05-critical--18b45-flow-at-the-required-matrix-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/delta-RESP-01-05-critical--18b45-flow-at-the-required-matrix-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/delta-RESP-01-05-critical--18b45-flow-at-the-required-matrix-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/delta-RESP-01-05-critical--18b45-flow-at-the-required-matrix-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/delta-RESP-01-05-critical--18b45-flow-at-the-required-matrix-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  1 failed
    [chromium] › tests/delta.spec.ts:307:1 › RESP-01..05 critical routes have no horizontal overflow at the required matrix 
  13 passed (5.0m)
```

## `tests/e2e.spec.ts` — FAIL (exit 1)

```text

Running 10 tests using 1 worker

  ✓   1 [chromium] › tests/e2e.spec.ts:32:1 › 01–03 inicio, navegación y dataset completo (2.8s)
  ✓   2 [chromium] › tests/e2e.spec.ts:42:1 › 04–07 filtros, chips, URL y restauración al recargar (3.8s)
  ✓   3 [chromium] › tests/e2e.spec.ts:54:1 › 08–10 ordenación, paginación y back/forward (2.8s)
  ✓   4 [chromium] › tests/e2e.spec.ts:68:1 › 11–15 Google Maps, кластер, выбор, границы и полигон (5.0s)
  ✓   5 [chromium] › tests/e2e.spec.ts:102:1 › 16–19 ficha: sin bloqueo, galería, favorito, descarte (3.8s)
  ✓   6 [chromium] › tests/e2e.spec.ts:118:1 › 20–22 login erróneo, demo y ruta protegida (2.1s)
  ✓   7 [chromium] › tests/e2e.spec.ts:131:1 › 23–26 registro y perfil persistente (3.3s)
  ✓   8 [chromium] › tests/e2e.spec.ts:148:1 › 27–29 publicación completa, CRUD y edición (3.8s)
  ✓   9 [chromium] › tests/e2e.spec.ts:160:1 › 30 admin, búsqueda, moderación y exportación CSV (2.7s)
  ✘  10 [chromium] › tests/e2e.spec.ts:172:1 › 31 responsive móvil sin desbordamiento y navegación inferior (9.7s)


  1) [chromium] › tests/e2e.spec.ts:172:1 › 31 responsive móvil sin desbordamiento y navegación inferior 

    Error: expect(locator).toBeVisible() failed

    Locator: locator('.m2-bottom-nav')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for locator('.m2-bottom-nav')


      176 |   await page.reload()
      177 |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    > 178 |   await expect(page.locator('.m2-bottom-nav')).toBeVisible()
          |                                                ^
      179 |   await page.locator('.m2-results__toolbar button').nth(2).click()
      180 |   await expect(page.locator('.m2-map-canvas')).toBeVisible()
      181 | })
        at /home/runner/work/Ttest/Ttest/tests/e2e.spec.ts:178:48

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/e2e-31-responsive-móvil-si-3681e-iento-y-navegación-inferior-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  1 failed
    [chromium] › tests/e2e.spec.ts:172:1 › 31 responsive móvil sin desbordamiento y navegación inferior 
  9 passed (41.1s)
```

## `tests/final-cleanup.spec.ts` — FAIL (exit 1)

```text

Running 12 tests using 1 worker

  ✓   1 [chromium] › tests/final-cleanup.spec.ts:54:1 › MEDIA-09 orphan cleanup removes only unreferenced blobs (2.3s)
  ✓   2 [chromium] › tests/final-cleanup.spec.ts:67:1 › MEDIA-10 shared listing photo survives until its final reference is deleted (3.6s)
  ✓   3 [chromium] › tests/final-cleanup.spec.ts:85:1 › MEDIA-11 replacing an edited listing photo removes the obsolete blob (4.1s)
  ✓   4 [chromium] › tests/final-cleanup.spec.ts:109:1 › DRAFT-05 reset removes only draft media and preserves listing media (3.9s)
  ✓   5 [chromium] › tests/final-cleanup.spec.ts:129:1 › ACCOUNT-01 deletion clears owned local data, draft and unused media after reload (3.5s)
  ✓   6 [chromium] › tests/final-cleanup.spec.ts:171:1 › CONTACT-07 cooldown survives dialog close and sensitive values are cleared (4.9s)
  ✓   7 [chromium] › tests/final-cleanup.spec.ts:198:1 › CONTACT-08 disabled phone and WhatsApp are absent from the DOM (2.4s)
  ✓   8 [chromium] › tests/final-cleanup.spec.ts:212:1 › FILTER-07 legacy URLs migrate to one tenant requirement and distinct resident/capacity controls (2.2s)
  ✓   9 [chromium] › tests/final-cleanup.spec.ts:226:1 › LISTING-STATUS-01 user-facing status filter excludes moderation-only values (2.5s)
  ✓  10 [chromium] › tests/final-cleanup.spec.ts:240:1 › MAP-06 selecting a card or marker preserves viewport and map instance (4.9s)
  ✘  11 [chromium] › tests/final-cleanup.spec.ts:263:1 › RESP-06 short mobile dialogs and critical map/uploader targets remain reachable (11.8s)
  ✓  12 [chromium] › tests/final-cleanup.spec.ts:287:1 › I18N-01 Russian and English versions switch and persist without changing routes (4.1s)


  1) [chromium] › tests/final-cleanup.spec.ts:263:1 › RESP-06 short mobile dialogs and critical map/uploader targets remain reachable 

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

  1 failed
    [chromium] › tests/final-cleanup.spec.ts:263:1 › RESP-06 short mobile dialogs and critical map/uploader targets remain reachable 
  11 passed (52.1s)
```

## `tests/final-mobile-delta-evidence.spec.ts` — FAIL (exit 1)

```text

Running 1 test using 1 worker

  ✘  1 [chromium] › tests/final-mobile-delta-evidence.spec.ts:33:1 › capture unmasked final mobile delta evidence (3.1m)


  1) [chromium] › tests/final-mobile-delta-evidence.spec.ts:33:1 › capture unmasked final mobile delta evidence 

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

  1 failed
    [chromium] › tests/final-mobile-delta-evidence.spec.ts:33:1 › capture unmasked final mobile delta evidence 
```

## `tests/final-mobile-delta.spec.ts` — FAIL (exit 1)

```text
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

  3) [chromium] › tests/final-mobile-delta.spec.ts:52:1 › DELTA-MOBILE-03 drawing and nearby search expose dedicated working map states 

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

  4) [chromium] › tests/final-mobile-delta.spec.ts:70:1 › DELTA-MOBILE-04 phone lookup opens a real listing and canonical detail remains usable 

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

  5) [chromium] › tests/final-mobile-delta.spec.ts:82:1 › DELTA-MOBILE-05 bottom tabs, favorites and protected account actions are real routes 

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

  6) [chromium] › tests/final-mobile-delta.spec.ts:96:1 › DELTA-MOBILE-06 ES, EN and RU persist and never introduce horizontal overflow 

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

  6 failed
    [chromium] › tests/final-mobile-delta.spec.ts:14:1 › DELTA-MOBILE-01 home, occupant selector and location actions stay connected without changing the locked design 
    [chromium] › tests/final-mobile-delta.spec.ts:31:1 › DELTA-MOBILE-02 list, filters, sorting, map, back and reload are URL-backed 
    [chromium] › tests/final-mobile-delta.spec.ts:52:1 › DELTA-MOBILE-03 drawing and nearby search expose dedicated working map states 
    [chromium] › tests/final-mobile-delta.spec.ts:70:1 › DELTA-MOBILE-04 phone lookup opens a real listing and canonical detail remains usable 
    [chromium] › tests/final-mobile-delta.spec.ts:82:1 › DELTA-MOBILE-05 bottom tabs, favorites and protected account actions are real routes 
    [chromium] › tests/final-mobile-delta.spec.ts:96:1 › DELTA-MOBILE-06 ES, EN and RU persist and never introduce horizontal overflow 
  2 passed (3.7m)
```

