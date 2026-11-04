# S2.2 / A3, A9 — текстовый сценарий и обновление карты

4 ноября 2026. Base: merged main `ecfe3a7b114c4142b396c2b64a918d34f105e8cf` (#407), подтверждён GitHub connector и `git ls-remote origin refs/heads/main`. Runtime/test source: `b0a33c6ed0ff7a4395187bbf46861ca915d1b831`.

Создан [draft PR#408](https://github.com/antony502189-max/Ttest/pull/408), open/merged=false. Exact-head CI нового PR ещё не подтверждён; merge/deploy не выполнялись.

## Результат

В существующем интерфейсе исправлено обновление каталога: после успешного «Actualizar resultados sin gastar una búsqueda» открытая карта заново читает текущий viewport, даже если result_ref и intent_hash не изменились. Раньше карточки обновлялись, а карта оставляла прежние маркеры до движения карты или повторного открытия.

Версия обновления включена в existing serverSource.key. Сам Google Map не перемонтируется: viewport/zoom сохраняются, existing effect отменяет старый запрос и очищает маркеры. Pagination не инициирует новое чтение карты. Ошибка чтения карточек сохраняет предыдущую карту. Binding intent_hash и исходный result_ref сохраняются. Это два независимых live-чтения каталога, не атомарный snapshot карточек и карты.

Изменены только два frontend-компонента, existing browser suite и два blob hash в обязательном runtime manifest. Backend, consumer, DB migrations, capability flags и deployment не менялись.

## Проверки

- До изменений исходная TypeScript/production-сборка merged main прошла; Vite сообщил существующее предупреждение о крупных chunks.
- RED: корректный browser regression на исходном runtime не получил fresh-source после обновления списка. Первый development запуск имел неверное ожидание тела cards POST; после исправления на `{search:{limit:6}}` повтор сохранил настоящий RED по отсутствующему новому маркеру.
- GREEN: три новых regression cases — видимая карта, запоздавший старый ответ, ошибка503 при обновлении карточек — PASS.
- Новый synthetic journey PASS: запрос → карточка → карта → изменение fixture-каталога → бесплатное обновление карточки/маркера → follow-up с сохранёнными hard budget/pet и добавленным balcony. Два разных query keys, expected_version0/1, remaining2→1; обновление каталога не создаёт третий query.
- TypeScript, Oxlint, i18n source guard и input-policy PASS. Общий lint сохраняет шесть прежних warnings в других файлах; изменённые файлы без warnings.
- Build-mode matrix:5/5 PASS, включая production с унаследованным lab env и два ожидаемых отказа invalid config. Это сборки, без запуска providers.
- Release pairing:13/13 mocked browser PASS.
- Полный AI browser suite:79/79 PASS на неизменном runtime/test source `b0a33c6e`;4новых cases включены в этот count. Existing manual Maps, recovery и saved-list/delete регрессии также прошли.
- Provenance:947runtime inputs match; historicalEvidenceAppliesToCurrentRuntime=false. Историческая container acceptance не переносится на новый frontend.

Raw logs, screenshots и hashes: [evidence](ai-search-s2-text-refresh-20261104-evidence/validation.json). Targeted cases входят в полный suite; counts не суммируются.

## Предел доказательства и продолжение

Все browser API routes, карточки, typed intent и Maps SDK — synthetic/mocked; внешние запросы запрещены fixture route. Сохранение hard условий проверяет отображение server contract и версии, не semantic correctness настоящей модели. Карточка прямо содержит «Muestra sintética» и «no es un anuncio real». Скриншоты просмотрены локально.

Существующие application/closed-lab containers не изменялись; их старый source `72468b2e` не выдан за текущую сборку. Платных provider calls, настоящего source crawling/backfill, budget journal mutations, больших benchmarks, activation/merge/deploy не было. Старый root checkout и чужие изменения сохранены; canonical plan синхронизируется отдельно.

S2 остаётся partial: real coverage/freshness и standing supervised refresh не доказаны. Следующий gate — exact-head CI/review этого frontend increment; затем незавершённый обязательный S2.2 блокер — bounded pre-HTTP claim/lease/fence/request-budget и process-lifecycle composition существующего detail consumer, с сохранением запрета на реальные источники. S3–S7/B2–B6, настоящий текстовый provider, voice, saved и delivery остаются открытыми.
