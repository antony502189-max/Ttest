# Mobile location validation with production Maps configuration

Overall: **PASS**

| Check | Result | Exit |
|---|---:|---:|
| npm ci | PASS | `0` |
| playwright install | PASS | `0` |
| lint | PASS | `0` |
| typecheck | PASS | `0` |
| build | PASS | `0` |
| mobile location tests | PASS | `0` |

```text

added 447 packages, and audited 448 packages in 11s

120 packages are looking for funding
  run `npm fund` for details

6 vulnerabilities (3 moderate, 3 high)

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force

Run `npm audit` for details.
Installing dependencies...
Switching to root user to install dependencies...
Hit:1 https://packages.microsoft.com/repos/azure-cli noble InRelease
Get:2 https://packages.microsoft.com/ubuntu/24.04/prod noble InRelease [3600 B]
Get:3 file:/etc/apt/apt-mirrors.txt Mirrorlist [144 B]
Hit:4 http://azure.archive.ubuntu.com/ubuntu noble InRelease
Get:5 http://azure.archive.ubuntu.com/ubuntu noble-updates InRelease [126 kB]
Get:6 http://azure.archive.ubuntu.com/ubuntu noble-backports InRelease [126 kB]
Get:7 http://azure.archive.ubuntu.com/ubuntu noble-security InRelease [126 kB]
Get:8 https://dl.google.com/linux/chrome-stable/deb stable InRelease [2548 B]
Get:9 https://packages.microsoft.com/ubuntu/24.04/prod noble/main arm64 Packages [203 kB]
Get:10 https://packages.microsoft.com/ubuntu/24.04/prod noble/main armhf Packages [11.7 kB]
Get:11 https://packages.microsoft.com/ubuntu/24.04/prod noble/main amd64 Packages [237 kB]
Get:12 http://azure.archive.ubuntu.com/ubuntu noble-updates/main amd64 Packages [1141 kB]
Get:13 http://azure.archive.ubuntu.com/ubuntu noble-updates/main Translation-en [276 kB]
Get:14 http://azure.archive.ubuntu.com/ubuntu noble-updates/main amd64 Components [180 kB]
Get:15 http://azure.archive.ubuntu.com/ubuntu noble-updates/universe amd64 Packages [1676 kB]
Get:16 http://azure.archive.ubuntu.com/ubuntu noble-updates/universe Translation-en [333 kB]
Get:17 http://azure.archive.ubuntu.com/ubuntu noble-updates/universe amd64 Components [388 kB]
Get:18 http://azure.archive.ubuntu.com/ubuntu noble-updates/restricted amd64 Packages [1348 kB]
Get:19 http://azure.archive.ubuntu.com/ubuntu noble-updates/restricted Translation-en [302 kB]
Get:20 http://azure.archive.ubuntu.com/ubuntu noble-updates/multiverse amd64 Packages [45.4 kB]
Get:21 http://azure.archive.ubuntu.com/ubuntu noble-updates/multiverse Translation-en [12.1 kB]
Get:22 http://azure.archive.ubuntu.com/ubuntu noble-updates/multiverse amd64 Components [940 B]
Get:23 http://azure.archive.ubuntu.com/ubuntu noble-backports/main amd64 Components [5760 B]
Get:24 http://azure.archive.ubuntu.com/ubuntu noble-backports/universe amd64 Packages [32.5 kB]
Get:25 http://azure.archive.ubuntu.com/ubuntu noble-backports/universe amd64 Components [12.7 kB]
Get:26 http://azure.archive.ubuntu.com/ubuntu noble-security/main amd64 Packages [881 kB]
Get:27 http://azure.archive.ubuntu.com/ubuntu noble-security/main Translation-en [196 kB]
Get:28 http://azure.archive.ubuntu.com/ubuntu noble-security/main amd64 Components [46.3 kB]
Get:29 http://azure.archive.ubuntu.com/ubuntu noble-security/universe amd64 Packages [1197 kB]
Get:30 http://azure.archive.ubuntu.com/ubuntu noble-security/universe Translation-en [238 kB]
Get:31 http://azure.archive.ubuntu.com/ubuntu noble-security/universe amd64 Components [76.4 kB]
Get:32 http://azure.archive.ubuntu.com/ubuntu noble-security/restricted amd64 Packages [1240 kB]
Get:33 http://azure.archive.ubuntu.com/ubuntu noble-security/restricted Translation-en [281 kB]
Get:34 http://azure.archive.ubuntu.com/ubuntu noble-security/multiverse amd64 Packages [40.3 kB]
Get:35 http://azure.archive.ubuntu.com/ubuntu noble-security/multiverse Translation-en [10.4 kB]
Get:36 https://dl.google.com/linux/chrome-stable/deb stable/main amd64 Packages [1428 B]
Fetched 10.8 MB in 1s (7708 kB/s)
Reading package lists...
Reading package lists...
Building dependency tree...
Reading state information...
libasound2t64 is already the newest version (1.2.11-1ubuntu0.3).
libasound2t64 set to manually installed.
libatk-bridge2.0-0t64 is already the newest version (2.52.0-1build1).
libatk-bridge2.0-0t64 set to manually installed.
libatk1.0-0t64 is already the newest version (2.52.0-1build1).
libatk1.0-0t64 set to manually installed.
libatspi2.0-0t64 is already the newest version (2.52.0-1build1).
libatspi2.0-0t64 set to manually installed.
libcairo2 is already the newest version (1.18.0-3build1).
libcairo2 set to manually installed.
libcups2t64 is already the newest version (2.4.7-1.2ubuntu7.14).
libcups2t64 set to manually installed.
libdbus-1-3 is already the newest version (1.14.10-4ubuntu4.1).
libdbus-1-3 set to manually installed.
libdrm2 is already the newest version (2.4.125-1ubuntu0.1~24.04.2).
libdrm2 set to manually installed.
libgbm1 is already the newest version (25.2.8-0ubuntu0.24.04.2).
libgbm1 set to manually installed.
libglib2.0-0t64 is already the newest version (2.80.0-6ubuntu3.8).
libglib2.0-0t64 set to manually installed.
libnspr4 is already the newest version (2:4.35-1.1build1).
libnspr4 set to manually installed.
libnss3 is already the newest version (2:3.98-1ubuntu0.2).
libnss3 set to manually installed.
libpango-1.0-0 is already the newest version (1.52.1+ds-1build1).
libpango-1.0-0 set to manually installed.
libx11-6 is already the newest version (2:1.8.7-1build1).
libx11-6 set to manually installed.
libxcb1 is already the newest version (1.15-1ubuntu2).
libxcb1 set to manually installed.
libxcomposite1 is already the newest version (1:0.4.5-1build3).
libxcomposite1 set to manually installed.
libxdamage1 is already the newest version (1:1.1.6-1build1).
libxdamage1 set to manually installed.
libxext6 is already the newest version (2:1.3.4-1build2).
libxext6 set to manually installed.
libxfixes3 is already the newest version (1:6.0.0-2build1).
libxfixes3 set to manually installed.
libxkbcommon0 is already the newest version (1.6.0-1build1).
libxkbcommon0 set to manually installed.
libxrandr2 is already the newest version (2:1.5.2-2build1).
libxrandr2 set to manually installed.
xvfb is already the newest version (2:21.1.12-1ubuntu1.6).
fonts-noto-color-emoji is already the newest version (2.047-0ubuntu0.24.04.1).
libfontconfig1 is already the newest version (2.15.0-1.1ubuntu2).
libfontconfig1 set to manually installed.
libfreetype6 is already the newest version (2.13.2+dfsg-1ubuntu0.1).
libfreetype6 set to manually installed.
fonts-liberation is already the newest version (1:2.1.5-3).
fonts-liberation set to manually installed.
The following additional packages will be installed:
  xfonts-encodings xfonts-utils
Recommended packages:
  fonts-ipafont-mincho fonts-tlwg-loma
The following NEW packages will be installed:
  fonts-freefont-ttf fonts-ipafont-gothic fonts-tlwg-loma-otf fonts-unifont
  fonts-wqy-zenhei xfonts-cyrillic xfonts-encodings xfonts-scalable
  xfonts-utils
0 upgraded, 9 newly installed, 0 to remove and 66 not upgraded.
Need to get 21.1 MB of archives.
After this operation, 79.5 MB of additional disk space will be used.
Get:1 file:/etc/apt/apt-mirrors.txt Mirrorlist [144 B]
Get:2 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-ipafont-gothic all 00303-21ubuntu1 [3513 kB]
Get:3 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 fonts-freefont-ttf all 20211204+svn4273-2 [5641 kB]
Get:4 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-tlwg-loma-otf all 1:0.7.3-1 [107 kB]
Get:5 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-unifont all 1:15.1.01-1build1 [2993 kB]
Get:6 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 fonts-wqy-zenhei all 0.9.45-8 [7472 kB]
Get:7 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 xfonts-encodings all 1:1.0.5-0ubuntu2 [578 kB]
Get:8 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 xfonts-utils amd64 1:7.7+6build3 [94.4 kB]
Get:9 http://azure.archive.ubuntu.com/ubuntu noble/universe amd64 xfonts-cyrillic all 1:1.0.5+nmu1 [384 kB]
Get:10 http://azure.archive.ubuntu.com/ubuntu noble/main amd64 xfonts-scalable all 1:1.0.3-1.3 [304 kB]
Fetched 21.1 MB in 1s (16.6 MB/s)
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

> task@0.0.0 lint
> oxlint

::warning file=tests/mobile-map-ideal.spec.ts,line=25,endLine=25,col=16,endColumn=42,title=eslint(no-unused-vars)::Function 'revealVisibleListingMarker' is declared but never used.

Found 1 warning and 0 errors.
Finished in 25ms on 112 files with 102 rules using 4 threads.

> task@0.0.0 typecheck
> tsc -b --pretty false


> task@0.0.0 build
> tsc -b && vite build

[36mvite v8.1.5 [32mbuilding client environment for production...[36m[39m
[2Ktransforming...✓ 1979 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                                0.99 kB │ gzip:   0.48 kB
dist/assets/geist-cyrillic-ext-wght-normal-DjL33-gN.woff2      7.42 kB
dist/assets/geist-vietnamese-wght-normal-6IgcOCM7.woff2        8.00 kB
dist/assets/geist-cyrillic-wght-normal-BEAKL7Jp.woff2         15.08 kB
dist/assets/geist-latin-ext-wght-normal-DC-KSUi6.woff2        16.51 kB
dist/assets/geist-latin-wght-normal-BgDaEnEv.woff2            29.40 kB
dist/assets/mobile-hero-Ca3OVflG.jpg                         112.14 kB
dist/assets/tenerife-zone-hierarchy-Dmwy3B_M.geojson       1,700.48 kB
dist/assets/tenerife-municipalities-B_tDJRHs.geojson       5,787.52 kB
dist/assets/list-map-switcher-CNUF_ej3.css                     1.15 kB │ gzip:   0.41 kB
dist/assets/map-view-C-qPHZg9.css                              1.86 kB │ gzip:   0.64 kB
dist/assets/HomePage-CNsezEiv.css                              6.58 kB │ gzip:   1.70 kB
dist/assets/zone-selection-map-Cmj9rRbl.css                   21.42 kB │ gzip:   4.51 kB
dist/assets/index-fQiqt-9Z.css                               284.28 kB │ gzip:  48.40 kB
dist/assets/arrow-right-CWYc2_J1.js                            0.15 kB │ gzip:   0.15 kB
dist/assets/ellipsis-0yWQXs2j.js                               0.21 kB │ gzip:   0.15 kB
dist/assets/log-out-CqNSXFgr.js                                0.22 kB │ gzip:   0.18 kB
dist/assets/eye-DMiteXQ5.js                                    0.24 kB │ gzip:   0.19 kB
dist/assets/eye-off-BlAYcZWw.js                                0.42 kB │ gzip:   0.26 kB
dist/assets/save-Tz5Wnx3X.js                                   0.46 kB │ gzip:   0.28 kB
dist/assets/geojson-hrl4MCc3.js                                0.49 kB │ gzip:   0.27 kB
dist/assets/file-text-DWxSfyJq.js                              0.57 kB │ gzip:   0.33 kB
dist/assets/textarea-Dms_Qaw5.js                               0.72 kB │ gzip:   0.39 kB
dist/assets/separator-D4KyK9Fm.js                              0.75 kB │ gzip:   0.43 kB
dist/assets/list-map-switcher-B6FvvTUa.js                      0.99 kB │ gzip:   0.52 kB
dist/assets/alert-Cj3-r48C.js                                  1.25 kB │ gzip:   0.57 kB
dist/assets/avatar-DQ8bBs0J.js                                 2.84 kB │ gzip:   1.28 kB
dist/assets/MobilePages-BZNUjnVe.js                            4.75 kB │ gzip:   1.70 kB
dist/assets/checkbox-B2pLLiPD.js                               4.76 kB │ gzip:   2.07 kB
dist/assets/AdminPage-BqlSmTAJ.js                              8.56 kB │ gzip:   3.16 kB
dist/assets/HomePage-kL6TQ9f0.js                               8.95 kB │ gzip:   3.17 kB
dist/assets/AuthPages-1zJRISCe.js                              9.23 kB │ gzip:   3.07 kB
dist/assets/InfoPages-CZYNnXbJ.js                              9.24 kB │ gzip:   3.65 kB
dist/assets/badge-DX2h9ZCo.js                                  9.42 kB │ gzip:   3.17 kB
dist/assets/zone-selection-map-t38uI6Xw.js                    12.37 kB │ gzip:   4.56 kB
dist/assets/ListingPage-BEAUWBg2.js                           12.68 kB │ gzip:   4.02 kB
dist/assets/forms-DBNDfRhl.js                                 13.40 kB │ gzip:   4.65 kB
dist/assets/AccountPages-l01fihpv.js                          19.75 kB │ gzip:   6.57 kB
dist/assets/map-view-CPThpWOS.js                              20.25 kB │ gzip:   7.39 kB
dist/assets/PublishPage-JJDJiwMr.js                           28.97 kB │ gzip:   8.11 kB
dist/assets/button-3IfC_Ze8.js                                43.09 kB │ gzip:  14.45 kB
dist/assets/media-image-BlLK5FlK.js                           52.69 kB │ gzip:  18.94 kB
dist/assets/SearchPage-C_qhzzVU.js                            53.02 kB │ gzip:  16.39 kB
dist/assets/marketplace-localized-CvIte_I8.js                 79.15 kB │ gzip:  22.45 kB
dist/assets/index-BlshjfBs.js                                556.07 kB │ gzip: 176.72 kB

[32m✓ built in 590ms[39m
[33m[plugin builtin:vite-reporter] 
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rolldownOptions.output.codeSplitting to improve chunking: https://rolldown.rs/reference/OutputOptions.codeSplitting
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.[39m

Running 13 tests using 1 worker

  ✓   1 [chromium] › tests/mobile-location-map.spec.ts:22:1 › onboarding restarts after every full page reload and language names are never machine-translated (2.3s)
  ✓   2 [chromium] › tests/mobile-location-map.spec.ts:34:1 › country selection contains only Tenerife and returns correctly from location editing (1.2s)
  ✓   3 [chromium] › tests/mobile-location-map.spec.ts:49:1 › housing modes start inactive and occupant selector supports safe multi-select (1.4s)
  ✓   4 [chromium] › tests/mobile-location-map.spec.ts:78:1 › location screen contains the four APK actions and address submit opens map (2.6s)
  ✓   5 [chromium] › tests/mobile-location-map.spec.ts:96:1 › current location opens the map and keeps the user coordinates even when no nearby listing is required (2.1s)
  ✓   6 [chromium] › tests/mobile-location-map.spec.ts:110:1 › map current-location control centers the map and renders the user marker (2.3s)
  ✓   7 [chromium] › tests/mobile-location-map.spec.ts:121:1 › draw and search map interfaces expose the connected listing layer without a result-count redesign (4.3s)
  ✓   8 [chromium] › tests/mobile-location-map.spec.ts:139:1 › menu keeps deleted sections absent and settings rows work without restarting registration (1.3s)
  ✓   9 [chromium] › tests/mobile-location-map.spec.ts:159:1 › login opened from an app tab uses the canonical account route (1.3s)
  ✓  10 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 320px (1.2s)
  ✓  11 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 360px (1.2s)
  ✓  12 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 390px (1.3s)
  ✓  13 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 430px (1.2s)

  13 passed (26.6s)
```
