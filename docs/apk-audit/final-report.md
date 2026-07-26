# Финальный отчёт: Idealista APK → 112233.es

## Идентификаторы

- main до работы: `74afdf6ced0b4bc089ffca2bcac88dc426035223`
- visual baseline: `19b3b8d3f3b29b8a39df686fe588c36faddb1592`
- ветка: `agent/idealista-apk-audit-fixes`
- итоговый commit и PR: опубликованы из ветки `agent/idealista-apk-audit-fixes`; ссылка указана в итоговой передаче

## APK acceptance

Idealista 14.5.0 реально установлен и запущен в Android Emulator API 35. В guest-маршруте пройдены onboarding, home, location, draw, map, menu, phone и nearby permission. Evidence находится в [reference](reference/) и перечислен в [screen inventory](screen-inventory.md).

Успешный post-auth Idealista не выполнялся: тестовые credentials внешнего сервиса отсутствуют, а создание внешней учётной записи требует отдельного e-mail/подтверждения. Авторизованные потоки сайта проверены локальными demo-аккаунтами.

## Исправления PR42/PR43

- возвращена видимость Search this area;
- восстановлены entry points nearby и phone;
- nearby работает без фиктивного fallback;
- добавлены success/denied/timeout/unavailable/unsupported/outside/empty;
- current location центрирует карту и показывает marker;
- mobile map/list/filter используют один selector и URL-state;
- polygon фильтрует карту и список и переживает reload;
- phone lookup открывает точное объявление;
- mobile и desktop карты не монтируются одновременно;
- desktop UI не перекрывается mobile portal;
- удалён prototype patch с DOM/click/MutationObserver coupling;
- Vivienda/Turismo сохраняется после list → home.

## Новые/возвращённые состояния

- nearby и phone на location;
- достижимый phone search screen;
- nearby feedback states;
- current-location marker;
- Search this area после polygon;
- persistent polygon/nearby/focused-listing URL states.

Web evidence: [location](../../artifacts/true-target-parity/location.png), [phone](../../artifacts/true-target-parity/phone.png), [map](../../artifacts/true-target-parity/map.png), [results](../../artifacts/true-target-parity/results.png).

## ES / EN / RU

| Область | ES | EN | RU |
|---|---:|---:|---:|
| onboarding/home/location | pass | pass | pass |
| map/drawing/nearby/phone | pass | pass | pass |
| list/filter/sort/cards | pass | pass | pass |
| favorites/saved/messages/menu | pass | pass | pass |
| auth/profile/publication | pass | pass | pass |
| geo errors/aria-label | pass | pass | pass |

## QA

| Проверка | Результат |
|---|---|
| `npm ci` | pass; upstream audit: 3 moderate, 3 high |
| `npm run lint` | pass; одно существующее unused-helper warning |
| `npm run typecheck` | pass |
| `npm run build` | pass; стандартное chunk-size warning |
| targeted PR43 regressions | 9/9 pass |
| полный `npx playwright test --project=chromium --workers=1 --retries=2` | 156 pass, 1 штатно skipped, 0 fail; retry не потребовался |
| `npm run test:visual` | 4/4 Playwright pass; 4/4 blocking APK-derived states pass |

Headless Chromium сообщает ожидаемый Google Maps Vector → Raster fallback; интерактивность, markers, clusters, preview и fallback проверяются независимо. Неблокирующие старые comparison-кадры Python-протокола не обновлялись, потому что visual baseline сайта зафиксирован.

## CSS

- `src/freehand-map-drawing.css`: удалено скрытие Search this area.
- `src/mobile-app-v2.css`: только новые geo/status/marker/Search-area states и локальный файл уже существующего hero-фото.

Существующие visual snapshots не обновлялись.

## Состав поставки

В PR не входят APK, decompiled resources, secrets, `.env.local`, `node_modules`, `dist`, test-results, Playwright videos и временные emulator-файлы. PR не должен автоматически merge-иться.
