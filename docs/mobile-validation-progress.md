# Staged mobile validation

- started: PASS
- npm ci: PASS (exit 0)

added 447 packages, and audited 448 packages in 9s

120 packages are looking for funding
  run `npm fund` for details

6 vulnerabilities (3 moderate, 3 high)

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force

Run `npm audit` for details.
- lint: PASS (exit 0)

> task@0.0.0 lint
> oxlint

::warning file=tests/mobile-map-ideal.spec.ts,line=25,endLine=25,col=16,endColumn=42,title=eslint(no-unused-vars)::Function 'revealVisibleListingMarker' is declared but never used.

Found 1 warning and 0 errors.
Finished in 35ms on 112 files with 102 rules using 4 threads.
- typecheck: PASS (exit 0)

> task@0.0.0 typecheck
> tsc -b --pretty false

- build: PASS (exit 0)

> task@0.0.0 build
> tsc -b && vite build

[36mvite v8.1.5 [32mbuilding client environment for production...[36m[39m
[2Ktransforming...✓ 1979 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                                2.56 kB │ gzip:  0.78 kB
dist/assets/geist-cyrillic-ext-wght-normal-DjL33-gN.woff2      7.42 kB
dist/assets/geist-vietnamese-wght-normal-6IgcOCM7.woff2        8.00 kB
dist/assets/geist-cyrillic-wght-normal-BEAKL7Jp.woff2         15.08 kB
dist/assets/geist-latin-ext-wght-normal-DC-KSUi6.woff2        16.51 kB
dist/assets/geist-latin-wght-normal-BgDaEnEv.woff2            29.40 kB
dist/assets/mobile-hero-Ca3OVflG.jpg                         112.14 kB
dist/assets/tenerife-zone-hierarchy-Dmwy3B_M.geojson       1,700.48 kB
dist/assets/tenerife-municipalities-B_tDJRHs.geojson       5,787.52 kB
dist/assets/list-map-switcher-CNUF_ej3.css                     1.15 kB │ gzip:  0.41 kB
dist/assets/map-view-C-qPHZg9.css                              1.86 kB │ gzip:  0.64 kB
dist/assets/HomePage-CNsezEiv.css                              6.58 kB │ gzip:  1.70 kB
dist/assets/zone-selection-map-Cmj9rRbl.css                   21.42 kB │ gzip:  4.51 kB
dist/assets/layout-BSPp6DhP.css                               28.61 kB │ gzip:  6.16 kB
dist/assets/index-D-ZKOVYT.css                               255.67 kB │ gzip: 43.38 kB
dist/assets/plus-BlyXGzvW.js                                   0.14 kB │ gzip:  0.14 kB
dist/assets/arrow-right-CWYc2_J1.js                            0.15 kB │ gzip:  0.15 kB
dist/assets/circle-check-DCmj_5PD.js                           0.16 kB │ gzip:  0.16 kB
dist/assets/user-round-CwEIfLGm.js                             0.17 kB │ gzip:  0.17 kB
dist/assets/info-D4zXigUX.js                                   0.19 kB │ gzip:  0.17 kB
dist/assets/mail-COtTdKy6.js                                   0.20 kB │ gzip:  0.19 kB
dist/assets/ellipsis-0yWQXs2j.js                               0.21 kB │ gzip:  0.15 kB
dist/assets/log-out-CqNSXFgr.js                                0.22 kB │ gzip:  0.18 kB
dist/assets/message-circle-DqvEPWgv.js                         0.23 kB │ gzip:  0.20 kB
dist/assets/eye-DMiteXQ5.js                                    0.24 kB │ gzip:  0.19 kB
dist/assets/bell-Bl67OJMu.js                                   0.28 kB │ gzip:  0.22 kB
dist/assets/pencil-Brb2RyMI.js                                 0.37 kB │ gzip:  0.26 kB
dist/assets/eye-off-BlAYcZWw.js                                0.42 kB │ gzip:  0.26 kB
dist/assets/save-Tz5Wnx3X.js                                   0.46 kB │ gzip:  0.28 kB
dist/assets/geojson-hrl4MCc3.js                                0.49 kB │ gzip:  0.27 kB
dist/assets/users-C0-hINEC.js                                  0.50 kB │ gzip:  0.31 kB
dist/assets/file-text-DWxSfyJq.js                              0.57 kB │ gzip:  0.33 kB
dist/assets/sliders-horizontal-DdcboGDc.js                     0.70 kB │ gzip:  0.36 kB
dist/assets/textarea-Dms_Qaw5.js                               0.72 kB │ gzip:  0.39 kB
dist/assets/separator-D4KyK9Fm.js                              0.75 kB │ gzip:  0.43 kB
dist/assets/input-DiW5s7I-.js                                  0.85 kB │ gzip:  0.43 kB
dist/assets/phone-9cpLyHEI.js                                  0.87 kB │ gzip:  0.45 kB
dist/assets/listing-access-ujjyfOZs.js                         0.91 kB │ gzip:  0.44 kB
dist/assets/list-map-switcher-CEjyNqYn.js                      0.98 kB │ gzip:  0.51 kB
dist/assets/loader-BcGFiOKy.js                                 1.21 kB │ gzip:  0.69 kB
dist/assets/alert-Cj3-r48C.js                                  1.25 kB │ gzip:  0.57 kB
dist/assets/avatar-DQ8bBs0J.js                                 2.84 kB │ gzip:  1.28 kB
dist/assets/x-_XrRyRTL.js                                      4.83 kB │ gzip:  1.91 kB
dist/assets/checkbox-aBT7wExj.js                               4.83 kB │ gzip:  2.11 kB
dist/assets/MobilePages-B66HsyWZ.js                            5.03 kB │ gzip:  1.81 kB
dist/assets/toggle-group-BXG7Brnu.js                           5.52 kB │ gzip:  1.91 kB
dist/assets/badge-B5C7OX05.js                                  8.64 kB │ gzip:  2.99 kB
dist/assets/AdminPage-m6WACj6Q.js                              8.73 kB │ gzip:  3.22 kB
dist/assets/HomePage-DaUnAsbu.js                               9.16 kB │ gzip:  3.26 kB
dist/assets/InfoPages-jAne8HOh.js                              9.32 kB │ gzip:  3.68 kB
dist/assets/AuthPages-BAArUR5k.js                              9.33 kB │ gzip:  3.10 kB
dist/assets/zone-selection-map-CuDyyVk_.js                    12.41 kB │ gzip:  4.57 kB
dist/assets/ListingPage-DZ3qEied.js                           12.88 kB │ gzip:  4.11 kB
dist/assets/forms-BHexr313.js                                 13.40 kB │ gzip:  4.64 kB
dist/assets/AccountPages-BSKDg0cF.js                          19.95 kB │ gzip:  6.64 kB
dist/assets/map-view-BooGPh--.js                              20.40 kB │ gzip:  7.43 kB
dist/assets/geolocation-Bh2XBNRE.js                           23.74 kB │ gzip:  8.70 kB
dist/assets/es2015-dSSJq6P1.js                                23.99 kB │ gzip:  8.52 kB
dist/assets/PublishPage-DHzxdscw.js                           29.11 kB │ gzip:  8.16 kB
dist/assets/button-3IfC_Ze8.js                                43.09 kB │ gzip: 14.45 kB
dist/assets/dropdown-menu-Dc1HU9Th.js                         47.21 kB │ gzip: 15.91 kB
dist/assets/media-image-BlLK5FlK.js                           52.69 kB │ gzip: 18.94 kB
dist/assets/SearchPage-CQ99Rpdi.js                            53.24 kB │ gzip: 16.44 kB
dist/assets/dist-cO3g0yGJ.js                                  70.83 kB │ gzip: 21.84 kB
dist/assets/marketplace-localized-C3x_AqPC.js                 73.93 kB │ gzip: 21.10 kB
dist/assets/layout-eXZ2i5_C.js                                80.82 kB │ gzip: 25.46 kB
dist/assets/map-pin-jqZ9WSSD.js                              110.17 kB │ gzip: 34.94 kB
dist/assets/index-IDlsH0Um.js                                189.33 kB │ gzip: 60.00 kB

[32m✓ built in 800ms[39m
- playwright install: PASS (exit 0)
Get:2 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-ipafont-gothic all 00303-21ubuntu1 [3513 kB]
Get:3 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 fonts-freefont-ttf all 20211204+svn4273-2 [5641 kB]
Get:4 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-tlwg-loma-otf all 1:0.7.3-1 [107 kB]
Get:5 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-unifont all 1:15.1.01-1build1 [2993 kB]
Get:6 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-wqy-zenhei all 0.9.45-8 [7472 kB]
Get:7 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 xfonts-encodings all 1:1.0.5-0ubuntu2 [578 kB]
Get:8 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 xfonts-utils amd64 1:7.7+6build3 [94.4 kB]
Get:9 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 xfonts-cyrillic all 1:1.0.5+nmu1 [384 kB]
Get:10 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 xfonts-scalable all 1:1.0.3-1.3 [304 kB]
Fetched 21.1 MB in 1s (22.4 MB/s)
Selecting previously unselected package fonts-ipafont-gothic.
(Reading database ... (Reading database ... 5%(Reading database ... 10%(Reading database ... 15%(Reading database ... 20%(Reading database ... 25%(Reading database ... 30%(Reading database ... 35%(Reading database ... 40%(Reading database ... 45%(Reading database ... 50%(Reading database ... 55%(Reading database ... 60%(Reading database ... 65%(Reading database ... 70%(Reading database ... 75%(Reading database ... 80%(Reading database ... 85%(Reading database ... 90%(Reading database ... 95%(Reading database ... 100%(Reading database ... 202954 files and directories currently installed.)
Preparing to unpack .../0-fonts-ipafont-gothic_00303-21ubuntu1_all.deb ...
Unpacking fonts-ipafont-gothic (00303-21ubuntu1) ...
Selecting previously unselected package fonts-freefont-ttf.
Preparing to unpack .../1-fonts-freefont-ttf_20211204+svn4273-2_all.deb ...
Unpacking fonts-freefont-ttf (20211204+svn4273-2) ...
Selecting previously unselected package fonts-tlwg-loma-otf.
Preparing to unpack .../2-fonts-tlwg-loma-otf_1%3a0.7.3-1_all.deb ...
Unpacking fonts-tlwg-loma-otf (1:0.7.3-1) ...
Selecting previously unselected package fonts-unifont.
Preparing to unpack .../3-fonts-unifont_1%3a15.1.01-1build1_all.deb ...
Unpacking fonts-unifont (1:15.1.01-1build1) ...
Selecting previously unselected package fonts-wqy-zenhei.
Preparing to unpack .../4-fonts-wqy-zenhei_0.9.45-8_all.deb ...
Unpacking fonts-wqy-zenhei (0.9.45-8) ...
Selecting previously unselected package xfonts-encodings.
Preparing to unpack .../5-xfonts-encodings_1%3a1.0.5-0ubuntu2_all.deb ...
Unpacking xfonts-encodings (1:1.0.5-0ubuntu2) ...
Selecting previously unselected package xfonts-utils.
Preparing to unpack .../6-xfonts-utils_1%3a7.7+6build3_amd64.deb ...
Unpacking xfonts-utils (1:7.7+6build3) ...
Selecting previously unselected package xfonts-cyrillic.
Preparing to unpack .../7-xfonts-cyrillic_1%3a1.0.5+nmu1_all.deb ...
Unpacking xfonts-cyrillic (1:1.0.5+nmu1) ...
Selecting previously unselected package xfonts-scalable.
Preparing to unpack .../8-xfonts-scalable_1%3a1.0.3-1.3_all.deb ...
Unpacking xfonts-scalable (1:1.0.3-1.3) ...
Setting up fonts-wqy-zenhei (0.9.45-8) ...
Setting up fonts-freefont-ttf (20211204+svn4273-2) ...
Setting up fonts-tlwg-loma-otf (1:0.7.3-1) ...
Setting up xfonts-encodings (1:1.0.5-0ubuntu2) ...
Setting up fonts-ipafont-gothic (00303-21ubuntu1) ...
update-alternatives: using /usr/share/fonts/opentype/ipafont-gothic/ipag.ttf to provide /usr/share/fonts/truetype/fonts-japanese-gothic.ttf (fonts-japanese-gothic.ttf) in auto mode
Setting up fonts-unifont (1:15.1.01-1build1) ...
Setting up xfonts-utils (1:7.7+6build3) ...
Setting up xfonts-cyrillic (1:1.0.5+nmu1) ...
Setting up xfonts-scalable (1:1.0.3-1.3) ...
Processing triggers for man-db (2.12.0-4build2) ...
Not building database; man-db/auto-update is not 'true'.
Processing triggers for fontconfig (2.15.0-1.1ubuntu2) ...

Running kernel seems to be up-to-date.

No services need to be restarted.

No containers need to be restarted.

No user sessions are running outdated binaries.

No VM guests are running outdated hypervisor (qemu) binaries on this host.
Downloading Chrome for Testing 149.0.7827.55 (playwright chromium v1228) from https://cdn.playwright.dev/builds/cft/149.0.7827.55/linux64/chrome-linux64.zip
|                                                                                |   0% of 177 MiB
|■■■■■■■■                                                                        |  10% of 177 MiB
|■■■■■■■■■■■■■■■■                                                                |  20% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■                                                        |  30% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                                |  40% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                        |  50% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                |  60% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                        |  70% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                |  80% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■        |  90% of 177 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100% of 177 MiB
Chrome for Testing 149.0.7827.55 (playwright chromium v1228) downloaded to /home/runner/.cache/ms-playwright/chromium-1228
Downloading FFmpeg (playwright ffmpeg v1011) from https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-linux.zip
|                                                                                |   0% of 2.3 MiB
|■■■■■■■■                                                                        |  10% of 2.3 MiB
|■■■■■■■■■■■■■■■■                                                                |  20% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■                                                        |  30% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                                |  40% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                        |  50% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                |  60% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                        |  70% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                |  80% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■        |  90% of 2.3 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100% of 2.3 MiB
FFmpeg (playwright ffmpeg v1011) downloaded to /home/runner/.cache/ms-playwright/ffmpeg-1011
Downloading Chrome Headless Shell 149.0.7827.55 (playwright chromium-headless-shell v1228) from https://cdn.playwright.dev/builds/cft/149.0.7827.55/linux64/chrome-headless-shell-linux64.zip
|                                                                                |   0% of 114.2 MiB
|■■■■■■■■                                                                        |  10% of 114.2 MiB
|■■■■■■■■■■■■■■■■                                                                |  20% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■                                                        |  30% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                                |  40% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                        |  50% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                                |  60% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                        |  70% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■                |  80% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■        |  90% of 114.2 MiB
|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■| 100% of 114.2 MiB
Chrome Headless Shell 149.0.7827.55 (playwright chromium-headless-shell v1228) downloaded to /home/runner/.cache/ms-playwright/chromium_headless_shell-1228
- mobile-location-map.spec.ts: FAIL (exit 1)

Running 13 tests using 1 worker

  ✓   1 [chromium] › tests/mobile-location-map.spec.ts:22:1 › onboarding restarts after every full page reload and language names are never machine-translated (3.3s)
  ✓   2 [chromium] › tests/mobile-location-map.spec.ts:34:1 › country selection contains only Tenerife and returns correctly from location editing (1.7s)
  ✓   3 [chromium] › tests/mobile-location-map.spec.ts:49:1 › housing modes start inactive and occupant selector supports safe multi-select (2.0s)
  ✘   4 [chromium] › tests/mobile-location-map.spec.ts:78:1 › location screen contains the four APK actions and address submit opens map (9.1s)
  ✘   5 [chromium] › tests/mobile-location-map.spec.ts:96:1 › current location opens the map and keeps the user coordinates even when no nearby listing is required (9.2s)
  ✘   6 [chromium] › tests/mobile-location-map.spec.ts:110:1 › map current-location control centers the map and renders the user marker (1.0m)
  ✘   7 [chromium] › tests/mobile-location-map.spec.ts:121:1 › draw and search map interfaces expose the connected listing layer without a result-count redesign (9.1s)
  ✓   8 [chromium] › tests/mobile-location-map.spec.ts:139:1 › menu keeps deleted sections absent and settings rows work without restarting registration (1.9s)
  ✓   9 [chromium] › tests/mobile-location-map.spec.ts:159:1 › login opened from an app tab uses the canonical account route (1.7s)
  ✓  10 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 320px (1.6s)
  ✓  11 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 360px (1.7s)
  ✓  12 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 390px (1.7s)
  ✓  13 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 430px (1.7s)


  1) [chromium] › tests/mobile-location-map.spec.ts:78:1 › location screen contains the four APK actions and address submit opens map 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('map-search')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('map-search')


      90 |   await input.fill('Santa Cruz de Tenerife')
      91 |   await input.press('Enter')
    > 92 |   await expect(page.getByTestId('map-search')).toBeVisible()
         |                                                ^
      93 |   await expect(page.getByText('Santa Cruz de Tenerife', { exact: true })).toBeVisible()
      94 | })
      95 |
        at /home/runner/work/Ttest/Ttest/tests/mobile-location-map.spec.ts:92:48

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/mobile-location-map-locati-b63a4-nd-address-submit-opens-map-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/mobile-location-map-locati-b63a4-nd-address-submit-opens-map-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/mobile-location-map-locati-b63a4-nd-address-submit-opens-map-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/mobile-location-map-locati-b63a4-nd-address-submit-opens-map-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/mobile-location-map-locati-b63a4-nd-address-submit-opens-map-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  2) [chromium] › tests/mobile-location-map.spec.ts:96:1 › current location opens the map and keeps the user coordinates even when no nearby listing is required 

    Error: expect(locator).toBeVisible() failed

    Locator: getByTestId('map-search')
    Expected: visible
    Timeout: 7000ms
    Error: element(s) not found

    Call log:
      - Expect "toBeVisible" with timeout 7000ms
      - waiting for getByTestId('map-search')


      104 |   await expect(page).toHaveURL(/lat=28\.2916/)
      105 |   await expect(page).toHaveURL(/lng=-16\.6291/)
    > 106 |   await expect(page.getByTestId('map-search')).toBeVisible()
          |                                                ^
      107 |   await expect(page.locator('.m2-user-location-marker')).toHaveCount(1)
      108 | })
      109 |
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

  3) [chromium] › tests/mobile-location-map.spec.ts:110:1 › map current-location control centers the map and renders the user marker 

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

  4) [chromium] › tests/mobile-location-map.spec.ts:121:1 › draw and search map interfaces expose the connected listing layer without a result-count redesign 

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

  4 failed
    [chromium] › tests/mobile-location-map.spec.ts:78:1 › location screen contains the four APK actions and address submit opens map 
    [chromium] › tests/mobile-location-map.spec.ts:96:1 › current location opens the map and keeps the user coordinates even when no nearby listing is required 
    [chromium] › tests/mobile-location-map.spec.ts:110:1 › map current-location control centers the map and renders the user marker 
    [chromium] › tests/mobile-location-map.spec.ts:121:1 › draw and search map interfaces expose the connected listing layer without a result-count redesign 
  9 passed (1.9m)
