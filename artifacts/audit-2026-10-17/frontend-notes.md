# Frontend/UI audit — 2026-10-17

Проверены HEAD `15b67386` и непосредственный baseline `1b2805e4`. Production source не изменялся; commits не создавались. Все harness, baseline export и screenshots находятся в `artifacts/audit-2026-10-17/frontend/`.

## Метод и выполненные проверки

- Прочитан diff всех frontend файлов province/TOP, прослежены подключенные publication enhancers, search URL → request body → list/map, owner TOP dialog → availability hook → checkout.
- Запущен Vite HEAD на localhost:4174 и экспорт frontend baseline `1b2805e4` на localhost:4185. Использованы mock mode, test Maps SDK, headless Microsoft Edge 155.0.4283.45 через Playwright. Внешние https assets в harness блокированы одинаково на обеих версиях. Реальные Google, Stripe и database операции не выполнялись.
- После завершения baseline server его log выявил Vite allow-list403 на local Geist fonts из root node_modules. Поэтому screenshot comparison не сертифицирует font/typographic parity. Подтвержденные FE-003 различия class/wrapper, ширины1216→384px, min-height, темного list background и отсутствия map actions не зависят от загрузки этого шрифта.
- `node artifacts/audit-2026-10-17/frontend/ui-audit.mjs`: exit 0. Проверены province selector 320/768/1280×900, sold-out текст и disabled continue, client clock +24h, countdown 4s → revalidation → continue enabled.
- `node artifacts/audit-2026-10-17/frontend/flows-audit.mjs`: exit 0. Проверены обычный пользовательский ввод и выбор Madrid address prediction, baseline/HEAD desktop selector screenshots, client clock −24h и browser reload countdown.
- `node artifacts/audit-2026-10-17/frontend/map-history-audit.mjs`: exit 0. Проверен Madrid province map при сохраненной прежней Tenerife camera; контроль с community13.
- Первый browser запуск в sandbox завершался из-за Windows profile/NamedPipe; повышенный read-only запуск разрешен автоматически. Vite из sandbox был недоступен elevated browser. После повышенного запуска Vite проверки исполнены. Первые навигации ждали remote assets/модульную загрузку; итоговые harness используют commit или DOMContentLoaded и блокируют remote assets. Это ограничения тестового окружения, не дефекты сайта.
- Lint/typecheck/build/test:provinces выполняет основной агент; не дублировались.

## FE-001 — пользовательский выбор адреса вне Tenerife остается заблокированным

**Severity:** P1. Нарушение основной новой функции, неполная интеграция нового province задания с существующим address lifecycle. Ограничение было корректным для прежнего Tenerife scope; после расширения на Spain требуется его обновить.

**Location:** `src/components/publish-smart-address-autocomplete.tsx:270-275` (решающий guard), `:304` (Tenerife restriction); `src/components/publish-exact-address-sync.tsx:109`, `:153` (отдельные ограничения fallback); `src/components/publish-route-enhancers.tsx:6-7` и `src/components/publish-address-lifecycle.tsx` показывают реальное подключение этих компонентов.

**Problem:** Изменен базовый PublishLocationEnhancer и ApproximateLocationMap, но поверх них реально работает PublishSmartAddressAutocomplete, заменяющий Google widget нативным полем. Его `dispatchResolved` отвергает любые coordinates вне Tenerife. Полноценный адрес Madrid не проходит обычный пользовательский путь. Тест `tests/province-top.spec.ts` dispatches `112233:publish-location-selected` напрямую, минуя этот guard, поэтому не обнаруживает проблему.

**Reproduction:** В mock UI открыть `/#/publicar`, ввести `Calle Mayor 1, Madrid` в реальный `#publish-street`, предоставить валидный Google prediction: lat40.4168/lng−3.7038, route Calle Mayor, number1, postal28013, localityMadrid, neighborhoodCentro, countrySpain; щелкнуть suggestion. Harness `flows-audit.mjs` воспроизводит именно input + suggestion click, без обходного `publish-location-selected` dispatch.

**Expected:** province Madrid, postcode28013, cityMadrid, markerMadrid. **Actual:** статус «Не удалось открыть эту подсказку. Выберите другую или введите полный адрес.»; provinceSanta Cruz de Tenerife, postcode38678, cityAdeje, marker28.12976/−16.75563 остаются от исходного draft.

**Impact:** Пользователь не может штатно опубликовать/редактировать адрес в остальных провинциях; требование автоматического определения province по адресу не выполнено в интегрированном UI.

**Fix:** Обновить все реально подключенные autocomplete/exact-address/fallback boundaries до согласованной Spain geography; на backend отдельно обеспечить проверку согласованности адреса. Сохранить дизайн поля. **Regression:** Настоящий ввод/выбор Madrid и Las Palmas, postcode-only fallback, смена Tenerife→Madrid, отсутствие ручного city выбора.

**Evidence/confidence:** Высокая; выполненный browser сценарий с детерминированным Google prediction, `frontend/flows-results.json` entry `Madrid-real-user-autocomplete`, `frontend/madrid-autocomplete-rejected.png`. Реальная Google выдача не вызывалась; guard по переданным валидным coordinates наблюден напрямую.

## FE-002 — province search не определяет camera, старый регион перекрывает новый

**Severity:** P2. Функциональная регрессия map search новой province ветки.

**Location:** `src/components/mobile-app-v2.tsx:962-968`; связанный production путь `src/components/mobile-map-listings-layer.tsx:58-70`, `backend/app/repositories/listings.py:703-711`.

**Problem:** `selectedRegionCamera` обрабатывает только `comunidad`; новый `provincia` не имеет camera resolver. При запросе Madrid fallback берет прежний сохраненный viewport Tenerife. `preserveCamera` подавляет автоматический fit по listings. Production map API добавляет текущие north/south/east/west к province фильтру; сервер пересекает province с viewport.

**Reproduction:** Сохранить обычный map history `{center:{lat:28.2916,lng:-16.6291}, savedAt:Date.now()}` под `112233:map-last-search-area:v2`. Открыть `/#/buscar?q=Madrid&provincia=28&vista=mapa&alquiler=long`. Контрольный equivalent Madrid community URL: `comunidad=13`.

**Expected:** При новой явной province выборке camera показывает Madrid province, как прежний явный community selection. **Actual (executed):** province28: center28.278568/−16.809734, zoom8.58 (Tenerife); community13: center40.525686/−3.81559, zoom8.38 (Madrid). В пустом localStorage province search остается общим Atlantic overview32.45/−11.2 zoom5.25.

**Impact:** Заголовок Madrid и карта прежнего региона; production Madrid markers исключаются bounds Tenerife, пока пользователь вручную не переместит карту. Последний вывод — прямой source trace, не исполненный PostgreSQL E2E.

**Fix:** Добавить province-specific map camera/bounds и приоритет явного province selection над remembered view, сохранив согласованность списка/карты. **Regression:** Прежний регион Tenerife → выбрать Madrid province → открыть карту; проверять реальный center и production marker request bounds, а не только заголовок.

**Evidence/confidence:** Высокая для camera bug; `frontend/map-history-results.json`, `frontend/madrid-map-history.png`, исполняемый `map-history-audit.mjs`. API/database effect доказан source path, отдельно пометить как не исполненный E2E.

## FE-003 — approved desktop location dialog заменен другим layout и потерял действия карты

**Severity:** P2. Подтвержденное нарушение design preservation и ограниченный functional regression.

**Location:** `src/components/marketplace.tsx:204-205`; CSS `src/mobile-app-v2.css:181`, `:354`; shared `src/components/ui/dialog.tsx`.

**Problem:** `SearchLocationInput` заменил существующий `LocationSelector` новым `DialogContent className="m2-location"`. Новый class задает minimum100dvh, shared dialog по умолчанию max-width384px. Повторно используются mobile community styles с темным `#202020` background вместо прежнего desktop light dialog. Вместе с заменой удалены действия «Выбрать зоны на карте», «Нарисовать зону», «Искать на карте», «Искать рядом» из этого входа.

**Reproduction:** На viewport1280×900 открыть homepage и location selector на baseline1b2805e4 и HEAD15b67386, языкRU, одинаковый mock и блок внешних assets. **Expected:** Обновление geographic choices с сохранением approved оболочки, palette, spacing и существующих альтернатив карты. **Actual:** baseline dialog rect x32/y34/1216×832 → HEAD x448/y0/384×900; новый list background rgb32/32/32; поле поиска занимает около137px в высоту; прежних map actions нет.

**Impact:** Существенно изменен desktop selector без необходимости для province filtering; обычные map/nearby entry points внутри него потеряны. Смена Municipality→Province и добавление доступности необходимы по заданию; переход на узкий full-height dark-list layout этим не обусловлен.

**Fix:** Использовать прежний location-selector-dialog wrapper и established light row/search styles; заменить geographic content минимально, сохранить map/draw/nearby alternatives. **Regression:** Screenshot comparison baseline-approved на desktop/tablet/mobile; assert присутствие map/draw/nearby действий и отсутствие horizontal overflow.

**Evidence/confidence:** Высокая; визуально просмотрены `frontend/baseline-selector-1280.png` и `frontend/current-selector-1280.png`, bounds/colors записаны в `frontend/flows-results.json`; HEAD также снят320/768/1280px. На768px document scrollWidth801 > viewport768; происхождение этого дополнительного overflow не сравнивалось с baseline и отдельным подтвержденным regression не считается.

## Acceptance tests (frontend scope)

| ID | Статус | Реально проверенное и ограничения |
|---|---|---|
| T10 | PASS (mock API/UI) | Русский sold-out message исполненно проверен; Continue disabled. Реальный full province backend — другой audit поток. |
| T11 | NOT VERIFIED в frontend scope | Hook использует availableAt−serverNow. Исполнено форматирование01:01:05 и04s; выбор minimum из трех expirations осуществляется backend и здесь не симулировался. |
| T12 | PASS (mock API/UI) | 00:00:04 → clock fastForward5s → второй availability запрос → ответ available true → Continue enabled. Не было per-second API polling: setInterval poll15s, tick1s, zero triggers load. |
| T16 | PASS (mock API/UI), PARTIAL относительно всей системы | Реальный page.reload и повторное открытие dialog вызывают API заново; timer01:01:05 до/после на одном authoritative fixture. Реальное движение serverNow между refresh требует интеграции backend. |
| T17 | PASS (mock API/UI) | Client Date offset+24h и−24h не меняет server delta; performance.now используется для tick. UTC ISO fixture. Network roundtrip compensation отдельно не проверялась. |
| T25 | FAIL | FE-001 normal user address path и FE-002 province map camera; FE-003 потеря desktop location actions. Остальные страницы целиком не сертифицированы. |
| T26 | FAIL | Исполненный baseline/HEAD1280px comparison показывает FE-003. HEAD renders320/768/1280; полная pixel parity всех страниц/состояний и browser engines не заявляется. |

## Countdown и API контракт: подтвержденные положительные свойства и пробелы

- Hook сбрасывает availability/error/remaining при listing/days/enabled changes, aborts stale request при cleanup, очищает интервалы. Покупка проверяется canBuy и в Continue, и в payForTop; checkout error вызывает refresh. Эти пункты — source inspection, кроме исполненной disabled/enabled проверки.
- Countdown не использует client Date.now для delta; вычисляет Date.parse(availableAt)−Date.parse(serverNow), затем тикает по performance.now. Формат часов допускает >24h; отрицательное значение ограничено нулем.
- При availableAt=null выводится pending confirmation message вместо выдуманного timer. Полностью исполняемый тест null timestamps и transient503 не добавлялся.
- Poll15s может заметить освобождение места раньше заданного availableAt. Чужая покупка между poll и checkout все равно требует backend authority; frontend самостоятельно не доказывает capacity.
- Официальный `tests/province-top.spec.ts` clock boundary и refresh не тестирует; sold-out fixture возвращает3665s, затем externally toggles released и ждет15s poll. Province address тест dispatches synthetic successful selected event, не проверяя реальный input workflow. Нет province camera regression, parent screenshot comparison, client clock skew, null availableAt, delayed response или calendar-duration state race.

## История, security, baseline

- `6689c826` (merge PR#347) — ancestor HEAD; файлы approved commercial carousel, owner homepage purchase, promotion-period component/CSS в latest province diff не менялись. AccountPages использует тот же PromotionPeriod, добавляет Availability и canBuy checks. Это source/history evidence, не полная visual certification этих flows.
- В local history видны `837a9221` integration security onto approved PR347 и merge#348 `45646036`. PR#345/#346 contents/status должны подтверждаться root через remote metadata; frontend агент их merge status не угадывает.
- Latest diff не меняет API auth client, protected media-origin helper, listing-link filtering implementation, native-video security implementation; блокировки listing links в create/edit validation остаются. Это не доказывает отсутствие всех frontend security defects. Новых подтвержденных XSS/security findings в данном frontend scope не найдено.
- Не запускались реальные платежи, Google production geocoder, интегрированный database/backend E2E, full accessibility suite, все 52 provinces и full-site visual regression suite. Их отсутствие не заменяется PASS по исходному коду.

## Приоритет исправлений frontend

1. P1: согласовать Spain address boundaries во всех реально подключенных компонентах и проверить normal input flow.
2. P2: province camera resolver + explicit province precedence; проверять API viewport вместе с UI.
3. P2: вернуть approved desktop wrapper/styles/map alternatives; выполнить screenshot regression на320/768/1280.
4. После этого расширить acceptance tests на настоящие address suggestions, zero/reload/client skew (настоящие API ответы), stale/error/null availability и baseline visuals.

Вывод frontend: **NOT READY FOR RELEASE** по FE-001 и нарушению обязательного preservation критерия FE-003. В frontend scope подтверждено P1=1, P2=2; P0/P3=0. При интеграции общего отчета FE-001 объединить с geographic agent finding, а не считать дважды.
