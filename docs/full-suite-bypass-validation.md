# Full regression validation with onboarding bypass

| npm ci | `0` |
| browser install | `0` |
| lint | `0` |
| typecheck | `0` |
| build | `0` |
| full e2e excluding dedicated reload test | `1` |

```text

Running 158 tests using 4 workers

  ✓    3 [chromium] › tests/apk-regression-recovery.spec.ts:19:3 › PR43 regression recovery › location keeps all four APK actions and phone lookup is reachable (3.5s)
  ✓    1 [chromium] › tests/apk-parity.spec.ts:15:3 › APK shell connected to the canonical web app › onboarding is completed once and survives reload (5.9s)
  ✓    5 [chromium] › tests/apk-regression-recovery.spec.ts:27:3 › PR43 regression recovery › nearby success stores coordinates and radius in the URL (5.3s)
  ✓    4 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: inicio (9.6s)
  ✓    7 [chromium] › tests/apk-regression-recovery.spec.ts:38:3 › PR43 regression recovery › nearby rejects coordinates outside Tenerife without pretending success (2.9s)
  ✓    9 [chromium] › tests/apk-regression-recovery.spec.ts:47:3 › PR43 regression recovery › nearby handles denied permission (3.2s)
  ✓    2 [chromium] › tests/acceptance-flows.spec.ts:65:1 › 01–03 rental mode, búsqueda por fecha y selección de varias zonas (16.1s)
  ✓   10 [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles unavailable (2.2s)
  ✘    6 [chromium] › tests/apk-parity.spec.ts:22:3 › APK shell connected to the canonical web app › location, search, back and reload use real URLs (12.0s)
  ✓   12 [chromium] › tests/apk-regression-recovery.spec.ts:59:5 › PR43 regression recovery › nearby handles timeout (2.9s)
  ✓    8 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: resultados (13.2s)
  ✓   14 [chromium] › tests/apk-regression-recovery.spec.ts:80:3 › PR43 regression recovery › nearby handles an unavailable Geolocation API (3.4s)
  ✓   16 [chromium] › tests/apk-regression-recovery.spec.ts:89:3 › PR43 regression recovery › polygon exposes Search this area and survives map-list-reload (6.3s)
  ✓   17 [chromium] › tests/customer-qa.spec.ts:3:1 › mobile search filters are fully localized and clamp numeric values (4.1s)
  ✓   15 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: mapa (14.5s)
  ✓   19 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: detalle (8.8s)
  ✓   20 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: acceso (4.4s)
  ✓   18 [chromium] › tests/delta-matrix.spec.ts:50:1 › USR-03..05 history, discarded listings and guest data stay in separate scopes (17.1s)
  ✓   11 [chromium] › tests/acceptance-flows.spec.ts:86:1 › 04 every visible filter is wired to data and URL (36.4s)
  ✓   21 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: registro (4.4s)
  ✓   22 [chromium] › tests/delta-matrix.spec.ts:91:1 › STORE-05 validator rejects incomplete listing payloads instead of accepting corrupted data (6.5s)
  ✓   24 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: recuperar (4.3s)
  ✓   26 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: restablecer (4.6s)
  ✓   23 [chromium] › tests/acceptance-flows.spec.ts:177:1 › 05–08 filter count, individual chips, clear, URL reload and history navigation (11.5s)
  ✓   27 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: favoritos (4.7s)
  ✓   25 [chromium] › tests/delta-matrix.spec.ts:101:1 › MEDIA-05..08 exact MIME, cleanup, quota feedback and missing-blob fallback work (11.1s)
  ✓   28 [chromium] › tests/acceptance-flows.spec.ts:202:1 › 09 sorting by date and both prices plus real disjoint pagination (8.6s)
  ✓   29 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: ayuda (4.9s)
  ✓   32 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: guardadas (5.1s)
  ✓   30 [chromium] › tests/delta-matrix.spec.ts:139:1 › ROOM-01..04 MODE-01..03 holiday wizard values persist and all new filters affect results (15.4s)
  ✓   33 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: perfil (6.6s)
  ✘   13 [chromium] › tests/apk-parity.spec.ts:38:3 › APK shell connected to the canonical web app › listing, account and publication actions open canonical routes (1.1m)
  ✓   31 [chromium] › tests/acceptance-flows.spec.ts:252:1 › 10–13 map marker/card sync, marker preview, bounds and polygon filtering (16.6s)
  ✓   35 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: mis anuncios (7.0s)
  ✓   34 [chromium] › tests/delta-matrix.spec.ts:185:1 › LOC-01 selected zone coordinates persist, edit restores them and exact street stays private (11.6s)
  ✓   38 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: publicar (5.2s)
  ✓   37 [chromium] › tests/acceptance-flows.spec.ts:309:1 › 14–15 favorites and complete saved-search restoration persist (12.9s)
  ✓   40 [chromium] › tests/a11y.spec.ts:68:3 › axe sin impactos serious/critical: administración (5.8s)
  ✓   39 [chromium] › tests/delta-matrix.spec.ts:205:1 › PROFILE-02 publish defaults and preview expose only enabled contact methods (9.9s)
  ✓   42 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: inicio (4.0s)
  ✓   41 [chromium] › tests/acceptance-flows.spec.ts:334:1 › 16–18 listing gallery keyboard, contact, share and report mutate state (7.7s)
  ✓   44 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: resultados (8.0s)
  ✓   45 [chromium] › tests/acceptance-flows.spec.ts:381:1 › 19–20 registration, login persistence, logout, recovery and reset flows (7.2s)
  ✓   43 [chromium] › tests/delta-matrix.spec.ts:230:1 › FILTER-02..06 new filters have chips, reset, reload and history navigation (12.1s)
  ✓   46 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: mapa (5.3s)
  ✓   48 [chromium] › tests/delta-matrix.spec.ts:267:1 › MAP-04 visible-area state activates after movement and resets after search (9.9s)
  ✓   49 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: detalle (8.4s)
  ✓   47 [chromium] › tests/acceptance-flows.spec.ts:409:1 › 21–24 wizard validates, restores/reset draft, previews user data, creates and edits (14.0s)
  ✓   50 [chromium] › tests/delta-matrix.spec.ts:279:1 › MAP-05 Google Maps loader errors expose the accessible map fallback (6.7s)
  ✓   51 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: publicar (5.3s)
  ✓   52 [chromium] › tests/acceptance-flows.spec.ts:462:1 › 25–26 hide/show, renew and delete listing all change shared data (8.8s)
  ✓   54 [chromium] › tests/a11y.spec.ts:85:3 › axe móvil 390px sin impactos serious/critical: administración (5.5s)
  ✓   53 [chromium] › tests/delta-matrix.spec.ts:287:1 › WIZ-04 reset clears dirty state and short-height filter drawer remains usable (7.3s)
  ✓   56 [chromium] › tests/a11y.spec.ts:95:1 › delta contact dialog supports keyboard focus and axe (7.5s)
  ✓   57 [chromium] › tests/delta.spec.ts:51:1 › OWN-01..04 owner isolation and foreign edit/actions are blocked (9.4s)
  ✓   58 [chromium] › tests/a11y.spec.ts:108:1 › delta fullscreen location flow has no serious or critical axe issues (5.8s)
  ✓   55 [chromium] › tests/acceptance-flows.spec.ts:487:1 › 27 admin status filter, approve/hide/reject, user blocking and CSV are stateful (13.9s)
  ✘   36 [chromium] › tests/apk-parity.spec.ts:54:3 › APK shell connected to the canonical web app › bottom tabs are deep links and favorites display stored data (1.1m)
  ✓   59 [chromium] › tests/delta.spec.ts:61:1 › OWN-05 new host has an empty cabinet while demo host keeps seed listings (6.5s)
  ✓   60 [chromium] › tests/a11y.spec.ts:117:1 › delta drawing announcement and controls have no serious or critical axe issues (8.2s)
  ✓   62 [chromium] › tests/apk-parity.spec.ts:67:3 › APK shell connected to the canonical web app › map and drawing screens are reflected in the URL (6.3s)
  ✓   64 [chromium] › tests/a11y.spec.ts:126:1 › delta avatar uploader has no serious or critical axe issues (5.1s)
  ✓   65 [chromium] › tests/apk-parity.spec.ts:77:3 › APK shell connected to the canonical web app › missing APK location actions work: nearby and phone lookup (6.8s)
  ✘   61 [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path (15.4s)
  ✓   63 [chromium] › tests/delta.spec.ts:74:1 › USR-01..03 favorites, saved searches and history are user scoped (13.7s)
  ✓   67 [chromium] › tests/apk-parity.spec.ts:99:1 › desktop keeps the existing responsive route-based design (4.2s)
  ✓   66 [chromium] › tests/a11y.spec.ts:133:1 › delta image uploader has no serious or critical axe issues (8.9s)
  ✓   70 [chromium] › tests/final-cleanup.spec.ts:54:1 › MEDIA-09 orphan cleanup removes only unreferenced blobs (7.5s)
  ✓   69 [chromium] › tests/delta.spec.ts:88:1 › STORE-01..02 versioned payload survives mass deletion and migrates legacy v2 (10.0s)
  ✓   68 [chromium] › tests/e2e.spec.ts:32:1 › 01–03 inicio, navegación y dataset completo (10.8s)
  ✓   71 [chromium] › tests/a11y.spec.ts:140:1 › delta approximate location map and controls have no serious or critical axe issues (7.6s)
  ✓   75 [chromium] › tests/a11y.spec.ts:148:1 › delta account deletion confirmation has no serious or critical axe issues (7.3s)
  ✓   72 [chromium] › tests/final-cleanup.spec.ts:67:1 › MEDIA-10 shared listing photo survives until its final reference is deleted (10.5s)
  ✓   73 [chromium] › tests/delta.spec.ts:107:1 › STORE-03..04 corrupted JSON falls back and quota errors are visible (12.0s)
  ✓   74 [chromium] › tests/e2e.spec.ts:42:1 › 04–07 filtros, chips, URL y restauración al recargar (14.8s)
  ✓   77 [chromium] › tests/final-cleanup.spec.ts:85:1 › MEDIA-11 replacing an edited listing photo removes the obsolete blob (13.0s)
  ✓   76 [chromium] › tests/final-mobile-delta-evidence.spec.ts:33:1 › capture unmasked final mobile delta evidence (14.3s)
  ✓   81 [chromium] › tests/final-mobile-delta.spec.ts:14:1 › DELTA-MOBILE-01 home, occupant selector and location actions stay connected without changing the locked design (4.1s)
  ✓   79 [chromium] › tests/e2e.spec.ts:54:1 › 08–10 ordenación, paginación y back/forward (11.7s)
  ✓   80 [chromium] › tests/final-cleanup.spec.ts:109:1 › DRAFT-05 reset removes only draft media and preserves listing media (12.3s)
  ✓   82 [chromium] › tests/final-mobile-delta.spec.ts:31:1 › DELTA-MOBILE-02 list, filters, sorting, map, back and reload are URL-backed (13.3s)
  ✓   78 [chromium] › tests/delta.spec.ts:125:1 › MEDIA-01..03 IndexedDB photo refs survive draft, publish and reload (32.2s)
  ✓   84 [chromium] › tests/final-cleanup.spec.ts:129:1 › ACCOUNT-01 deletion clears owned local data, draft and unused media after reload (12.1s)
  ✓   83 [chromium] › tests/e2e.spec.ts:68:1 › 11–15 Google Maps, кластер, выбор, границы и полигон (19.0s)
  ✓   85 [chromium] › tests/final-mobile-delta.spec.ts:52:1 › DELTA-MOBILE-03 drawing and nearby search expose dedicated working map states (8.3s)
  ✓   89 [chromium] › tests/final-mobile-delta.spec.ts:70:1 › DELTA-MOBILE-04 phone lookup opens a real listing and canonical detail remains usable (6.7s)
  ✓   86 [chromium] › tests/delta.spec.ts:165:1 › MEDIA-04 avatar upload/remove persists and profile cancel restores values (16.8s)
  ✓   88 [chromium] › tests/e2e.spec.ts:102:1 › 16–19 ficha: sin bloqueo, galería, favorito, descarte (15.0s)
  ✓   87 [chromium] › tests/final-cleanup.spec.ts:171:1 › CONTACT-07 cooldown survives dialog close and sensitive values are cleared (15.4s)
  ✓   90 [chromium] › tests/final-mobile-delta.spec.ts:82:1 › DELTA-MOBILE-05 bottom tabs, favorites and protected account actions are real routes (10.4s)
  ✓   92 [chromium] › tests/e2e.spec.ts:118:1 › 20–22 login erróneo, demo y ruta protegida (5.5s)
  ✓   93 [chromium] › tests/final-cleanup.spec.ts:198:1 › CONTACT-08 disabled phone and WhatsApp are absent from the DOM (7.1s)
  ✓   91 [chromium] › tests/delta.spec.ts:195:1 › ROOM-01..04 and MODE-01..03 migrated room and rental models render consistently (8.3s)
  ✓   94 [chromium] › tests/final-mobile-delta.spec.ts:96:1 › DELTA-MOBILE-06 ES, EN and RU persist and never introduce horizontal overflow (10.4s)
  ✓   96 [chromium] › tests/final-cleanup.spec.ts:212:1 › FILTER-07 legacy URLs migrate to one tenant requirement and distinct resident/capacity controls (8.3s)
  ✓   95 [chromium] › tests/e2e.spec.ts:131:1 › 23–26 registro y perfil persistente (10.5s)
  ✓   97 [chromium] › tests/delta.spec.ts:205:1 › CONTACT-01..06 confirmation gates channels and local form handles abuse states (13.2s)
  ✓   99 [chromium] › tests/final-cleanup.spec.ts:226:1 › LISTING-STATUS-01 user-facing status filter excludes moderation-only values (8.1s)
  ✓  100 [chromium] › tests/e2e.spec.ts:148:1 › 27–29 publicación completa, CRUD y edición (11.0s)
  ✓  101 [chromium] › tests/delta.spec.ts:237:1 › LIFE-01..04 expiration hides public listing and renew republishes it (14.0s)
  ✓  103 [chromium] › tests/e2e.spec.ts:160:1 › 30 admin, búsqueda, moderación y exportación CSV (9.7s)
  ✓  102 [chromium] › tests/final-cleanup.spec.ts:240:1 › MAP-06 selecting a card or marker preserves viewport and map instance (14.5s)
  ✓   98 [chromium] › tests/final-mobile-delta.spec.ts:112:1 › DELTA-RESPONSIVE-01 critical routes have no horizontal overflow across the supported matrix (25.5s)
  ✓  104 [chromium] › tests/delta.spec.ts:277:1 › WIZ-01..03 dirty state warns only after edits and save clears it (9.6s)
  ✓  107 [chromium] › tests/final-mobile-delta.spec.ts:128:1 › DELTA-DIAGNOSTICS-01 critical mobile routes emit no application errors or failed first-party requests (5.0s)
  ✓  105 [chromium] › tests/e2e.spec.ts:172:1 › 31 responsive móvil sin desbordamiento y navegación inferior (9.6s)
  ✓  109 [chromium] › tests/google-maps-final-acceptance.spec.ts:26:1 › selected Advanced Marker has priority, opens the sheet, and programmatic selection stays clean (10.0s)
  ✓  106 [chromium] › tests/final-cleanup.spec.ts:263:1 › RESP-06 short mobile dialogs and critical map/uploader targets remain reachable (17.6s)
  ✓  108 [chromium] › tests/delta.spec.ts:292:1 › FILTER-01 and MAP-01..03 new filters serialize and map preview shows restrictions (15.7s)
  ✓  110 [chromium] › tests/map-responsive-parity.spec.ts:25:1 › results map keeps the current mobile shell and desktop split geometry across the responsive matrix (14.9s)
  ✓  112 [chromium] › tests/final-cleanup.spec.ts:287:1 › I18N-01 Russian and English versions switch and persist without changing routes (10.3s)
  ✓  115 [chromium] › tests/master-task.spec.ts:13:1 › P0 current mobile home preserves the locked APK hierarchy and links all five tabs (2.4s)
  ✓  114 [chromium] › tests/master-task-visual.spec.ts:25:1 › master current home responsive matrix (8.0s)
  ✘  111 [chromium] › tests/google-maps-final-acceptance.spec.ts:40:1 › manual pan exposes Search this area while a result refit does not (18.3s)
  ✓  117 [chromium] › tests/master-task-visual.spec.ts:35:1 › master current mobile list, map, drawing and location states (7.2s)
  ✓  116 [chromium] › tests/master-task.spec.ts:30:1 › P1 desktop multiple municipalities stay synchronized with URL, filters and reload (14.6s)
  ✓  120 [chromium] › tests/master-task.spec.ts:47:1 › P1 municipality list remains usable when detailed GeoJSON cannot load (13.7s)
  ✓  119 [chromium] › tests/master-task-visual.spec.ts:59:1 › master desktop municipality selection and split map states (20.8s)
  ✓  118 [chromium] › tests/google-maps-final-acceptance.spec.ts:53:1 › map/list, multiple canonical zones, and polygon restore from URL and reload (27.4s)
  ✓  122 [chromium] › tests/mobile-freehand-map.spec.ts:14:1 › map stays interactive until the drawing button is pressed (13.5s)
  ✓  121 [chromium] › tests/master-task.spec.ts:59:1 › P0 mobile and desktop maps retain their intended separate implementations (15.8s)
  ✓  124 [chromium] › tests/mobile-location-map.spec.ts:34:1 › country selection contains only Tenerife and returns correctly from location editing (4.0s)
  ✓  126 [chromium] › tests/mobile-location-map.spec.ts:49:1 › housing modes start inactive and occupant selector supports safe multi-select (5.2s)
  ✓  127 [chromium] › tests/mobile-location-map.spec.ts:78:1 › location screen contains the four APK actions and address submit opens map (6.8s)
  ✓  123 [chromium] › tests/google-maps-final-acceptance.spec.ts:71:1 › official district hierarchy selects a stable ID and restores it from URL (27.4s)
  ✓  113 [chromium] › tests/delta.spec.ts:307:1 › RESP-01..05 critical routes have no horizontal overflow at the required matrix (1.2m)
  ✓  128 [chromium] › tests/mobile-location-map.spec.ts:96:1 › current location opens the map and keeps the user coordinates even when no nearby listing is required (5.9s)
  ✓  131 [chromium] › tests/mobile-location-map.spec.ts:110:1 › map current-location control centers the map and renders the user marker (6.8s)
  ✓  129 [chromium] › tests/google-maps-final-acceptance.spec.ts:88:1 › production configuration is secret-backed and auth errors keep a usable fallback (9.3s)
  ✓  125 [chromium] › tests/master-task.spec.ts:80:1 › P1 core routes have no horizontal overflow or unexpected console errors across the responsive matrix (29.4s)
  ✓  130 [chromium] › tests/delta.spec.ts:348:1 › A11Y-01 contact dialog has no serious or critical axe issues (10.9s)
  ✓  134 [chromium] › tests/mobile-publication-gate.spec.ts:15:1 › publication gate has no duplicate top notice or close icon and opens existing auth (4.1s)
  ✓  133 [chromium] › tests/mobile-map-ideal.spec.ts:38:1 › map is freely zoomable before explicit drawing activation (7.2s)
  ✓  132 [chromium] › tests/mobile-location-map.spec.ts:121:1 › draw and search map interfaces expose the connected listing layer without a result-count redesign (9.0s)
  ✓  136 [chromium] › tests/mobile-publication-gate.spec.ts:33:1 › publication entry in menu opens the same clean gate (3.3s)
  ✓  138 [chromium] › tests/mobile-location-map.spec.ts:139:1 › menu keeps deleted sections absent and settings rows work without restarting registration (2.9s)
  ✓  137 [chromium] › tests/mobile-map-ideal.spec.ts:57:1 › published listings are visible on the map and open the matching result (6.4s)
  ✓  140 [chromium] › tests/mobile-location-map.spec.ts:159:1 › login opened from an app tab uses the canonical account route (3.7s)
  ✘  135 [chromium] › tests/mobile-search-results.spec.ts:33:1 › Vivienda and Turismo are the only rental-mode controls and filter real listings (11.8s)
  ✓  142 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 320px (3.7s)
  ✓  139 [chromium] › tests/screenshot-locked-contract.spec.ts:17:1 › LOCK-OVERLAY derives at most two truthful image restrictions and omits empty overlays (9.8s)
  ✓  144 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 360px (2.5s)
  ✓  146 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 390px (2.3s)
  ✘  141 [chromium] › tests/mobile-map-ideal.spec.ts:79:1 › listing requirements are visually prominent in results (11.1s)
  ✓  145 [chromium] › tests/screenshot-locked-contract.spec.ts:57:1 › LOCK-CARD exposes image, price, title and body navigation without nesting controls (5.7s)
  ✓  147 [chromium] › tests/mobile-location-map.spec.ts:173:3 › main, location, modal and map do not overflow at 430px (3.2s)
  ✘  143 [chromium] › tests/mobile-search-results.spec.ts:64:1 › price, area, room count and housing type filters change the listing set (11.3s)
  ✓  150 [chromium] › tests/true-target-parity.spec.ts:5:1 › capture and gate the mandatory current Idealista-derived target states (6.9s)
  -  152 [chromium] › tests/v4-exact-design-evidence.spec.ts:145:1 › capture V4 golden-indexed live evidence
  ✓  149 [chromium] › tests/screenshot-locked-evidence.spec.ts:5:1 › capture the current screenshot-locked live matrix (8.2s)
  ✓  148 [chromium] › tests/screenshot-locked-contract.spec.ts:89:1 › LOCK-COMMENTS supports honest user-scoped create, edit, delete and account cleanup (14.5s)
  ✓  154 [chromium] › tests/visual-parity.spec.ts:24:1 › current mobile home, results, location and map visual states (6.4s)
  ✘  151 [chromium] › tests/mobile-search-results.spec.ts:98:1 › sorting, photo carousel, favorites and hiding listings work together (12.0s)
  ✓  155 [chromium] › tests/visual-parity.spec.ts:43:1 › current mobile menu, auth and Russian visual states (4.6s)
  ✓  153 [chromium] › tests/visual-evidence.spec.ts:13:1 › responsive final evidence at the required viewport matrix (14.2s)
  ✓  157 [chromium] › tests/visual-parity.spec.ts:57:1 › existing desktop results, listing and publication designs stay visually locked (4.5s)
  ✘  156 [chromium] › tests/mobile-search-results.spec.ts:128:1 › contact opens the existing authentication flow and map returns to Google Maps (10.0s)
  ✘  158 [chromium] › tests/mobile-search-results.spec.ts:141:1 › results, sorting and filters fit every supported mobile width (8.8s)


  1) [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path 

    Error: expect(page).toHaveURL(expected) failed

    Expected pattern: /buscar/
    Received string:  "http://127.0.0.1:4173/#/?panel=ubicacion"
    Timeout: 7000ms

    Call log:
      - Expect "toHaveURL" with timeout 7000ms
        17 × unexpected value "http://127.0.0.1:4173/#/?panel=ubicacion"


      546 |   await search.focus();
      547 |   await page.keyboard.press("Enter");
    > 548 |   await expect(page).toHaveURL(/buscar/);
          |                      ^
      549 |   await expect(page.locator(".m2-bottom-nav")).toBeVisible();
      550 |   const filters = page.locator(".m2-results__toolbar button").first();
      551 |   await filters.focus();
        at /home/runner/work/Ttest/Ttest/tests/acceptance-flows.spec.ts:548:22

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

  5) [chromium] › tests/google-maps-final-acceptance.spec.ts:40:1 › manual pan exposes Search this area while a result refit does not 

    Error: expect(locator).toHaveCount(expected) failed

    Locator:  getByRole('button', { name: /buscar en esta zona/i })
    Expected: 0
    Received: 1
    Timeout:  7000ms

    Call log:
      - Expect "toHaveCount" with timeout 7000ms
      - waiting for getByRole('button', { name: /buscar en esta zona/i })
        18 × locator resolved to 1 element
           - unexpected value "1"


      48 |   await expect(searchArea).toBeVisible({ timeout: 10_000 })
      49 |   await searchArea.click()
    > 50 |   await expect(searchArea).toHaveCount(0)
         |                            ^
      51 | })
      52 |
      53 | test('map/list, multiple canonical zones, and polygon restore from URL and reload', async ({ page }) => {
        at /home/runner/work/Ttest/Ttest/tests/google-maps-final-acceptance.spec.ts:50:28

    attachment #1: screenshot (image/png) ──────────────────────────────────────────────────────────
    test-results/google-maps-final-acceptan-ef89c-ile-a-result-refit-does-not-chromium/test-failed-1.png
    ────────────────────────────────────────────────────────────────────────────────────────────────

    attachment #2: video (video/webm) ──────────────────────────────────────────────────────────────
    test-results/google-maps-final-acceptan-ef89c-ile-a-result-refit-does-not-chromium/video.webm
    ────────────────────────────────────────────────────────────────────────────────────────────────

    Error Context: test-results/google-maps-final-acceptan-ef89c-ile-a-result-refit-does-not-chromium/error-context.md

    attachment #4: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/google-maps-final-acceptan-ef89c-ile-a-result-refit-does-not-chromium/trace.zip
    Usage:

        npx playwright show-trace test-results/google-maps-final-acceptan-ef89c-ile-a-result-refit-does-not-chromium/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────

  6) [chromium] › tests/mobile-map-ideal.spec.ts:79:1 › listing requirements are visually prominent in results 

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

  7) [chromium] › tests/mobile-search-results.spec.ts:33:1 › Vivienda and Turismo are the only rental-mode controls and filter real listings 

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

  8) [chromium] › tests/mobile-search-results.spec.ts:64:1 › price, area, room count and housing type filters change the listing set 

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

  9) [chromium] › tests/mobile-search-results.spec.ts:98:1 › sorting, photo carousel, favorites and hiding listings work together 

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

  10) [chromium] › tests/mobile-search-results.spec.ts:128:1 › contact opens the existing authentication flow and map returns to Google Maps 

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

  11) [chromium] › tests/mobile-search-results.spec.ts:141:1 › results, sorting and filters fit every supported mobile width 

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

  11 failed
    [chromium] › tests/acceptance-flows.spec.ts:521:1 › 28–29 mobile navigation and keyboard-only critical path 
    [chromium] › tests/apk-parity.spec.ts:22:3 › APK shell connected to the canonical web app › location, search, back and reload use real URLs 
    [chromium] › tests/apk-parity.spec.ts:38:3 › APK shell connected to the canonical web app › listing, account and publication actions open canonical routes 
    [chromium] › tests/apk-parity.spec.ts:54:3 › APK shell connected to the canonical web app › bottom tabs are deep links and favorites display stored data 
    [chromium] › tests/google-maps-final-acceptance.spec.ts:40:1 › manual pan exposes Search this area while a result refit does not 
    [chromium] › tests/mobile-map-ideal.spec.ts:79:1 › listing requirements are visually prominent in results 
    [chromium] › tests/mobile-search-results.spec.ts:33:1 › Vivienda and Turismo are the only rental-mode controls and filter real listings 
    [chromium] › tests/mobile-search-results.spec.ts:64:1 › price, area, room count and housing type filters change the listing set 
    [chromium] › tests/mobile-search-results.spec.ts:98:1 › sorting, photo carousel, favorites and hiding listings work together 
    [chromium] › tests/mobile-search-results.spec.ts:128:1 › contact opens the existing authentication flow and map returns to Google Maps 
    [chromium] › tests/mobile-search-results.spec.ts:141:1 › results, sorting and filters fit every supported mobile width 
  1 skipped
  146 passed (7.5m)
```
