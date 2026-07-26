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

