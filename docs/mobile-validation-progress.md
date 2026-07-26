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
