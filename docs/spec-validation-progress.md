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

