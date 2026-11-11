# Полный независимый аудит PR #397–400

Дата: 28 октября 2026 года, Europe/Moscow. Репозиторий: [antony502189-max/Ttest](https://github.com/antony502189-max/Ttest).

Аудит выполнен без изменения production-кода, коммитов, публикации GitHub-комментариев, merge или deployment. В рабочем репозитории создан только этот отчёт. Исходные незакоммиченные изменения пользователя сохранены. Код извлечён из Git-объектов в отдельную временную папку; тестовые изменения сделаны только там. База — новый локальный контейнер PostgreSQL/PostGIS, не application/staging/production DB. Платные провайдеры, настоящая ASR, crawling и доставка уведомлений не запускались.

## Часть 1 — Резюме для принятия решения

Проверены актуальные GitHub-описания, полный paginated file-patch inventory четырёх PR, локальные Git-диффы, история коммитов, обсуждения, review threads, CI и существенные зависимости: HTTP/auth/guest boundary, sessions/results/quota, verified facts/proofs/cards/map, manual saved searches и notification service. Обсуждения и review threads у всех четырёх PR пусты. Повторное получение метаданных в конце проверки подтвердило неизменность четырёх HEAD.

**Вердикт по каждому PR: REQUEST CHANGES. По всей цепочке: REQUEST CHANGES. Публичная активация не готова.** Это не утверждение о найденном критическом взломе: P0/P1 в проверенных новых путях не подтверждены. Выявлены пять уникальных проблем уровня P2, включая один интеграционный блокер; четыре функциональные проблемы воспроизведены дополнительными тестами, интеграционный конфликт воспроизведён Git. Наследуемые проблемы не посчитаны несколько раз.

Основные результаты:

1. **R-01:** цепочка отстаёт от родителей. #398–400 не содержат финальные исправления #395, дошедшие до HEAD #397. Сведение #397 и #400 даёт реальный конфликт тестового helper. Сам #397 также не содержит актуальный HEAD #396. Зелёные checks старых merge refs не проверяют это объединение.
2. **R-02:** после terminal failure `SESSION_EXPIRED` интерфейс сохраняет `pending`, поскольку сначала требует успешно прочитать истёкшую сессию. Поле текста и выбор нового диалога остаются заблокированы; повтор отправляет тот же навсегда завершённый запрос. Ошибка наследуется от #396.
3. **R-03:** #398 создаёт новые unused sessions с непустыми criteria, но существующая очистка удаляет только `criteria = {}`. Истёкшие сессии с явным rental mode никогда не очищаются этим механизмом.
4. **R-04:** общий monotonic budget голосовой операции не ограничивает cleanup после timeout. Реальная блокировка строки квоты удерживает выполнение после истечения `total_budget_seconds`; для offline-вызова без HTTP wrapper нет собственного ограниченного cleanup budget.
5. **R-05:** сохранение AI snapshot держит одно соединение и collection lock, затем через `sessions.result()` запрашивает второе соединение того же пула. При допустимом пуле из одного соединения сохранение всегда падает; при насыщении более крупного пула возникает та же зависимость.

Положительные результаты существенны: в проверенных сценариях ownership не обходится, result snapshot не подменяется новой editable session, `false` и нулевой депозит сохраняются, quota debit атомарен, ack loss не вызывает повторного inference, AI rows не попадают в legacy notifier, dry-run не пишет уведомления или mail outbox. Локально прошли 1403 unit-теста, 218 facts-PG тестов, 55 тестов полной схемы PostGIS, focused quota/session/voice/saved tests и 22 браузерных теста на mock-сборке. Есть ограничения воспроизводимости frontend dependencies — см. часть 7.

**Безопасность merge и безопасность включения — разные решения.** После исправлений и обновления цепочки код можно повторно рассматривать как выключенную основу. Это не снимает R-01 representative SQL capacity gate из документации #395, требования privacy/freshness/retention, реальной ASR-интеграции и будущей доставки.

## Часть 2 — Инвентаризация PR и точные ревизии

В таблице BASE SHA — значение, полученное из PR metadata. Оно не всегда равно текущему live HEAD целевой ветки; это отдельно проверено через `git ls-remote`.

| PR | Название | HEAD SHA | Base: ветка / BASE SHA из API | Файлов | Статус | CI для указанного HEAD | Вердикт |
|---|---|---|---|---:|---|---|---|
| [397](https://github.com/antony502189-max/Ttest/pull/397) | Connect AI result map without manual catalog fallback | `bc9b8b1de6012e70f138f1d6d591ee93cce87fd3` | `codex/ai-home-search-panel` / `68c79f77ae6fd9322beda00dbbfef6ad3e09fb83` | 13 | OPEN, draft | 3/3 success | REQUEST CHANGES |
| [398](https://github.com/antony502189-max/Ttest/pull/398) | AI Search: normalized conditions and explicit home rental mode | `02d7029161677a7a1076899c2f678e912cf6f35b` | `codex/ai-result-map-ui` / `a3742df11e433fa26c5926bc0a6e30e24aab08d3` | 16 | OPEN, draft | 5/5 success | REQUEST CHANGES |
| [399](https://github.com/antony502189-max/Ttest/pull/399) | AI Search: offline ASR and intent with one durable debit | `5d3a2a362d384e3a6af1e3884d5e9a273251366c` | `codex/ai-normalized-conditions` / `02d7029161677a7a1076899c2f678e912cf6f35b` | 5 | OPEN, draft | 4/4 success | REQUEST CHANGES |
| [400](https://github.com/antony502189-max/Ttest/pull/400) | AI Search: registered snapshots and fail-closed rematch dry runs | `df9653aaa8ee95658a6ad56a74b91f773c676fd9` | `codex/ai-voice-single-operation` / `5d3a2a362d384e3a6af1e3884d5e9a273251366c` | 16 | OPEN, draft | 4/4 success | REQUEST CHANGES |

Фактический `main`: `e50f96a5f62d0989d9d91c35c001ca35fd6db445`. Предыдущие PR #392, #393, #394, #395 уже merged. Их финальные HEAD: соответственно `3db07f7dfedc36d0e9ebf62f9fc104ae06d6034c`, `8fb8c58b5dfe24c8fec3205a3bce90c009c8bfdb`, `b186e5d4db9e79949ab4a5ca755b24ccba6b20f1`, `e68a47e8ab1571309e89be721d61e60aefc7dc56`.

Актуальный live HEAD `codex/ai-home-search-panel`, то есть #396: `21f1f0ef3c0177d87cf6ff60e27ddcfdb01fd8bb`; #396 OPEN, не draft. Его актуальный код не является предком #397. Дополнительная разница относительно recorded base #397: четыре файла, 43 добавления / 14 удалений — docs и `tests/final-mobile-delta.spec.ts`. Это внешний prerequisite к рассматриваемым четырём PR, а не пятый независимо одобренный PR.

Полные patches получены через GitHub `fetch_pr_patch`, который обходит все страницы changed files. Числа файлов совпали с inventory. Для анализа наследования дополнительно использовались локальные three-dot и two-dot diff. История каждой incremental ветки проверена через `git log`; значимые коммиты реализации: #397 `33499d3c`, `23eaf53e`; #398 `3ca2972a`, `02d70291`; #399 `d997e92d`, `9d996801`, `a1f6c918`; #400 `d9a70c17`, `faad2038`, `1600f58f`, `95a52bf1`, `daadd5d9`. Merge commits оценивались по изменениям дерева и ancestry, а не по сообщениям.

### Перечень изменённых файлов

**#397 (13):** `.github/workflows/ai-search-frontend.yml`; `docs/ai-search-developer/POST_392_REFRESH.md`; `docs/ai-search-developer/RESULT_MAP_UI.md`; `playwright.ai-search.config.ts`; `src/api/ai-search.ts`; `src/components/ai-result-map.tsx`; `src/components/home-ai-search.tsx`; `src/components/map/results-map.tsx`; `src/components/marketplace.tsx`; `src/contexts/i18n-context.tsx`; `src/home-ai-search.css`; `tests/ai-home-search.spec.ts`; `tests/google-maps-final-acceptance.spec.ts`.

**#398 (16):** `backend/app/api/v1/ai_search.py`; `backend/app/repositories/ai_search_sessions.py`; `backend/app/schemas/ai_search_intent.py`; `backend/tests/ai_http_browser/test_ai_http_browser.py`; `backend/tests/ai_search_pg/test_sessions.py`; `backend/tests/test_ai_http_boundary.py`; `docs/ai-search-normalized-conditions.md`; `src/api/ai-intent.ts`; `src/api/ai-search.ts`; `src/components/ai-conditions.tsx`; `src/components/home-ai-search.tsx`; `src/components/home-mandatory-search.tsx`; `src/components/mobile-app-v2.tsx`; `src/contexts/i18n-context.tsx`; `src/home-ai-search.css`; `tests/ai-home-search.spec.ts`.

**#399 (5):** `backend/app/services/ai_offline_asr.py`; `backend/app/services/ai_voice_execution.py`; `backend/tests/ai_search_pg/test_voice_execution.py`; `backend/tests/test_ai_offline_asr.py`; `docs/ai-search-voice-offline.md`.

**#400 (16):** `.github/workflows/ai-search-facts.yml`; `backend/alembic/versions/0072_ai_saved_searches.py`; `backend/app/models/__init__.py`; `backend/app/models/ai_saved_search.py`; `backend/app/repositories/ai_saved_searches.py`; `backend/app/schemas/searches.py`; `backend/app/services/notifications.py`; `backend/app/services/search_state.py`; `backend/tests/ai_facts_pg/test_combined_schema.py`; `backend/tests/ai_search_pg/test_saved_searches.py`; `backend/tests/integration/test_ai_saved_searches.py`; `backend/tests/integration/test_ai_verified_cards.py`; `backend/tests/test_ai_saved_search_boundary.py`; `backend/tests/test_municipality_search.py`; `backend/tests/test_notification_service.py`; `docs/ai-search-saved-offline.md`.

## Часть 3 — Индивидуальные ревью

### PR #397 — карта исходного AI result

Связка `HomeAISearch → AIResultMap → MapView → ResultsMap.serverSource` действительно использует result endpoint. `AIResultMap` замыкает `resultRef/intentHash`; тело содержит только viewport и zoom. `response.intent_hash` проверяется до передачи markers. Ветка `source.load()` не переходит к manual catalog при ошибке: fallback `getMapMarkers` выбирается только когда самого serverSource нет.

Ключ React-компонента содержит ref/hash. Новый результат размонтирует старую карту и сбрасывает selection. Эффект загрузки удаляет idle-listener, timer и aborts request; callback проверяет `signal.aborted`, поэтому поздний ответ отменённого запроса не заменяет markers. Debounce 180 ms ограничивает idle burst, но это не server-side abuse protection: для этого остаётся обязательный HTTP gate. Строгой гарантии «один запрос на жест» нет и она не обещается.

`independentSearch` исключает сохранённый manual polygon и area overlay. Исходный массив items пустой, поэтому локальные manual listings не используются как AI fallback. Камера карты по-прежнему использует общее URL/history поведение; карта не обещает автоматически вписать все AI matches. Markers, clusters и TOP z-order берутся из существующего renderer. Preview загружает обычную публичную карточку для ID проверенного marker; это отдельный live-read, а не frozen AI snapshot.

На ошибке markers очищаются и показывается scoped notice; повтор требует изменения viewport. При zero result остаётся текстовое состояние, cards доступны независимо от отображения карты. Ошибка загрузки Google Maps сохраняет альтернативную навигацию. CSS поднимает AI и вложенные dialogs над mobile navigation. Браузерные проверки покрывают promoted marker, clusters, intent mismatch, поздний предыдущий map response, мобильную ширину и обычную карту.

Bounding-box backend принимает обычный упорядоченный диапазон, а не antimeridian interval. Frontend пропускает `east <= west`; утверждать поддержку пересечения 180° нельзя. Для испанского каталога это ограничение, а не подтверждённая новая регрессия. Координатные диапазоны ограничены схемой; финальный #397 также наследует исправление private 422 для неправильного порядка границ.

**Проблемы:** R-02 находится в используемом HomeAISearch и наследуется из #396; R-01 мешает считать текущую интеграцию проверенной. Собственного подтверждённого обхода ownership или fallback в новом map loader не найдено. Исправлять R-02 следует в #396 и затем передавать вниз. Недостающие проверки: настоящая Google SDK/network, физические touch-жесты, assistive technology, живой moderated-preview race и representative map load. Mock SDK не закрывает эти проверки.

### PR #398 — нормализованные условия и явный rental mode

`aiConditionRows()` проходит весь объект прежде, чем вернуть summary; неизвестная схема, поле или enum даёт `null`, и `AIConditions` показывает фиксированный alert вместо частичного правдоподобного summary. `value: false` обрабатывается через проверку типа boolean, а не truthiness. Hard/soft выводятся отдельно.

Результат связан с original committed metadata по ref/hash/session/version/count; editable session читается отдельно. Failed followup не переподписывает старые cards новыми criteria. Hash — identity intent, не ревизия live listings. Исходное receipt count не обязано совпадать с новым live count при paging; UI не вводит такого ложного требования.

| Условие | Тип / единицы и вывод | Hard matching и существенная проверка |
|---|---|---|
| rental_mode | `long/holiday` | Точный category и текущий canonical mode |
| budget | decimal string, EUR, monthly/weekly/nightly | Верхняя граница; без выдуманной конвертации; confirmed amount/period отдельно от native card price |
| geography | INE province/municipality + zone code | Backend проверяет принадлежность и server vocabulary; frontend показывает идентификаторы |
| accommodation | строгий kind, catalog code только для catalog_other | Отсутствующее неизвестное catalog значение не принимается backend |
| party | adults 1–10, children 0–10, total ≤10 | Capacity и available_spots; children/couple/friends требуют соответствующих подтверждений |
| pets | species/size/count, непустой список, общий count ≤10 | Scope и лимит; ambiguous/approval-required evidence не подтверждает условие |
| smoking | indoors/outdoors/balcony/terrace | Scope coverage; отсутствие данных не равно разрешению |
| furnished | boolean, включая false | Точное подтверждённое boolean значение |
| bills_included | boolean, включая false | То же |
| deposit | EUR one_off либо integer months, включая 0 | Сравнение только в той же единице |
| balcony | boolean, включая false | То же, soft не превращается в обязательный SQL filter |
| terrace | boolean, включая false | То же |
| amenities | непустые уникальные server codes | По одному обязательному правилу на hard amenity; unknown codes отклоняются |
| dates | реальные ISO dates, checkout > checkin | Покрытие интервала + min/max stay; календарная валидность проверяется backend |
| stay | positive integer nights/months | Exact unit; месяц не превращается автоматически в 30 ночей |

Absent criteria исключаются при сериализации. Явный null внутри Criteria запрещён; пустые pets/amenities запрещены; отсутствие rental_mode в SessionCreate означает отсутствие ограничения. Депозит 0 и children 0 валидны; stay 0 невалиден по контракту. Backend дополнительно проверяет совместимость hard dates и stay nights; frontend summary не заменяет backend validation. UI-типизация сама по себе не является доверенной границей безопасности.

Новый select начинает с пустого значения; отправка без выбора невозможна. Выбор home mode создаёт только typed hard rental_mode; none создаёт пустые criteria. Occupants/manual filters не передаются. Существующий диалог при изменении внешнего home mode не переписывается. Боди-less session creation сохранён, per-subject issuance gate и атомарный active-session cap не удалены.

**Подтверждённый новый дефект:** R-03 — seed ломает применимость cleanup_unused. **Наследуемые:** R-01/R-02. Штатный тест cap проверяет явный mode, но cleanup-тест создаёт только пустые sessions и не замечает R-03. Браузерные ES/RU/EN проверки и дополнительный expired-session тест описаны в части 7. Production activation и реальный provider не проверялись.

### PR #399 — ASR + intent под одним debit

Новый путь не вызывает TextSearchExecution и не создаёт второй ключ. Fingerprint связывает server SHA256 финальных bytes, media type, session/version и весь validated card payload. Новый message с cursor отклоняется до reserve. Повтор успешного или failed logical operation не вызывает ASR/parser снова. Changed audio/media/request/version/channel дают idempotency conflict. Один успешный meaningful result, в том числе с count=0, расходует одну единицу.

Основные переходы: reserve (`reserved`) → claim (`running`, fence++) → session/version + attempts gate → bounded ASR → strict transcript → bounded intent → candidate query → atomic `finalize_patch`. Finalize находится вне speculative release; callback/session CAS/result/used++ выполняются в одной транзакции с повторной проверкой lease. Ack loss пробрасывается, повтор читает ledger. Expired fence не может завершить новую/восстановленную операцию. Recovery завершает старую как failed, не даёт разрешение повторно запустить провайдер с прежним ключом.

OfflineASR принимает только MockTransport и фиксированный `.invalid` host. Есть обязательный local outbound gate, ограничение audio bytes и transcript bytes, strict JSON, duplicate-key rejection, проверка content type/status/content length, запрет redirects/compression, raw streaming bound и фиксированная ошибка без transcript/provider body. В DTO transcript исключён из repr. Audio/transcript не записываются в ledger/session/result. Синтетические bytes не проверяются как настоящий звуковой контейнер; media sniffing/duration/consent/retention остаются требованиями будущей реальной интеграции, а не ошибкой отключённого fake adapter.

**Новый дефект:** R-04 в timeout cleanup. Это не доказательство двойного debit: accounting сохраняется, но вызывающая задача может оставаться в DB cleanup существенно дольше объявленного total budget. Сохранённый из #394 HTTP_DEADLINE корректно ограничивает cancellation cleanup при реальном HTTP wrapper; новый голосовой сервис пока не зарегистрирован в HTTP, поэтому собственный offline-вызов не получает этот предел автоматически. Нельзя исправлять проблему возвратом speculative release после ambiguous finalize.

Штатные тесты сильно покрывают bytes/media/card mutations, provider failures, concurrency, stale lease, no-op DeepSeek, ack loss и ASR cancellation. До аудита отсутствовал тест блокировки SQL cleanup после собственного voice timeout. Настоящий vendor transport/SSRF sandbox здесь не реализован и не считается проверенным.

### PR #400 — сохранённый intent, legacy boundary и dry-run

`save()` принимает только registered subject, owned result_ref и bounded name; caller criteria/hash не принимаются. Копируется committed result, не актуальный editable session. `SavedIntent` намеренно не имеет FK на conversation: сохранённый snapshot продолжает читаться после expiry/reset/deletion original conversation. `get()` проверяет schema/vocabulary/content hash. Enable/disable использует row lock и expected revision; stale revision даёт conflict. Общий collection advisory lock и count включают manual + AI rows.

Manual write/patch/import проверяют reserved metadata рекурсивно; typed `{strength,value}` внутри filters не игнорируется. В notifier есть два барьера: SQL `matcher = manual.v1` и per-row reject metadata/nonmanual. Manual list/update исключают AI rows; общий delete удаляет owned parent и каскадно child. Проверены call sites публикации/редактирования listings, admin и external import: они используют тот же guarded notifier. Прямого альтернативного AI→mail/notification пути в новой реализации не найдено.

`dry_run` и `dry_run_event` используют одну `_decision`, общий `verified_intent_predicate`, canonical visibility и read-only repeatable-read transaction. Event даёт canonical_listing_id; его hash/revision не служат разрешением на доставку. Current proofs/sources/moderation перепроверяются. Duplicate/out-of-order events только наблюдают текущее состояние; event не ack/consume. `delivery_enabled=false` соответствует поведению: нет create_notification/enqueue_mail/worker registration. Это не готовый event delivery protocol и не должно трактоваться как такой протокол.

**Новый дефект:** R-05 — вложенный checkout из пула внутри save transaction. Штатный конкурентный тест проверяет один AI + один manual save при pool_size=16 и потому его не обнаруживает. Нужен тест насыщенного пула и проверка, что чтение результата использует то же соединение.

Миграция/ORM и deployment ограничения рассмотрены в части 6. Публичного save/voice endpoint, UI и worker нет намеренно; их отсутствие не записано как функциональная регрессия. Criteria edit API тоже не заявлен: сохранённый intent immutable, существующий CAS покрывает enable/disable. Тестировать «редактирование criteria» как будто такой endpoint существует было бы неправильно.

## Часть 4 — Интеграция между PR

### Фактическая ancestry

```text
main e50f96a5  (#392–395 merged)
  └─ #396 live 21f1f0ef   [ещё не включён в #397]

#397 bc9b8b1d
  ├─ включает исправленный #395 e68a47e8
  └─ общий предок с #398: a3742df1
       └─ #398 02d70291
            └─ #399 5d3a2a36
                 └─ #400 df9653aa
```

Верхняя схема показывает логические зависимости и отставание; это не утверждение, что #397 является descendant финального merge commit main. Финальные исправления #395 включены в его дерево через merge родительской ветки.

Результаты выполненных команд:

```text
git merge-base pr397 pr398
a3742df11e433fa26c5926bc0a6e30e24aab08d3

git merge-base --is-ancestor pr397 pr398  -> exit 1
git merge-base --is-ancestor pr398 pr399  -> exit 0
git merge-base --is-ancestor pr399 pr400  -> exit 0
git merge-base --is-ancestor pr396 pr397  -> exit 1
git merge-base --is-ancestor e68a47e8 pr400 -> exit 1
git merge-base main pr400
86117c01212d1e8bf5b52d89d05649fb7820f6e8
```

Здесь `prNNN` обозначает локальный `refs/audit/prNNN`, fetched непосредственно из `refs/pull/NNN/head`. `git branch -a --contains e68a47e8` отдельно подтвердил его наличие в обновлённых parent branches; ancestor check исключает ошибку интерпретации названий веток.

У #398–400 отсутствуют **семь файлов** изменений после a3742df1 в актуальном #397: HTTP MapView ordering validator; reuse одного compiled hard plan в cards; новые HTTP и dense-map tests; PR_395 resolution; уточнённая VERIFIED_MAP_QUOTA; обновлённый API inventory. Значит, в отдельных HEAD #398–400 неправильный порядок bounds ещё даёт handler-time private 400 вместо исправленного 422, а cards повторно компилируют plan. Это не новая независимая уязвимость каждого потомка: одна проблема синхронизации R-01.

`git merge-tree --write-tree pr397 pr398` и `pr397 pr399` завершились без конфликтов. Но `pr397 pr400` вернул exit 1:

```text
Auto-merging backend/app/api/v1/ai_search.py
Auto-merging backend/tests/integration/test_ai_verified_cards.py
CONFLICT (content): Merge conflict in backend/tests/integration/test_ai_verified_cards.py
```

В общем helper #395 добавляет сценарии дополнительных unverified rows, а #400 добавляет настраиваемый vocabulary. Нужно сохранить оба изменения и все dense/HTTP/saved parity regressions. Применить `ours/theirs` ко всему файлу — недостаточное разрешение. В production frontend файлах конфликт при этой конкретной проверке не возник; утверждать их уже произошедшую потерю нельзя.

### Сквозные сценарии A–H

| Сценарий | Что прослежено и проверено | Итог / предел |
|---|---|---|
| A. Text → conditions → result → map/cards | Явный seed, session/version, server fingerprint, committed ref/hash/count, separate editable summary, owned result/map reads | Нормальный путь проходит. R-02 ломает recovery при expiry; R-03 затрагивает abandoned seeded sessions |
| B. Audio → ASR → intent → debit | Immutable bytes/media/full request, reserve/claim, bounded providers, CAS/fence/finalize, replay | Debit один в выполненных тестах; R-04 в cleanup budget. Реальный ASR отсутствует намеренно |
| C. Save → expiry → listing change → dry-run | Owned committed snapshot, независимый hash, отсутствие conversation FK, текущий verified predicate | Стабильность criteria и invalidation source/proof/moderation проходят; R-05 при checkout пула |
| D. Быстрые новые запросы / map pan / старый ответ | Submit/page lock; отдельный abort/cleanup map loader; remount ref/hash; delayed old-map test | Старый ответ не заменил новый result в тестах. Произвольный порядок нескольких вкладок физически не исчерпан |
| E. Legacy compatibility | Manual discriminator, write/patch/import guards, common notifier call sites, existing manual tests | Typed metadata не становится broad manual match; ordinary extensions без reserved AI keys сохраняются |
| F. User A против User B | Session/result ownership, guest/auth separation, foreign saved result/get/disable/dry-run | Проверенные операции отклоняются; IDOR/BOLA не воспроизведён |
| G. Partial deployment | ORM требует matcher; old backend не знает mode seed; old workers не знают typed parents | Требуется migration → guarded backend/workers → frontend; save writes только после всех legacy guards |
| H. Marketplace regression | Shared map renderer, ordinary map tests, public visibility/gallery/TOP/native price + confirmed price, auth/cookies | Focused regressions проходят; не утверждается полная проверка всех платежей и UI marketplace |

### Порядок исправления и интеграции

1. Исправить recovery формы в исходном #396; актуализировать его checks и review. Сам аудит не одобряет автоматически весь #396.
2. Перенести актуальный #396 в #397 обычным merge или согласованным rebase, сохранить UI/map changes, повторить frontend/HTTP regressions.
3. Перенести актуальный #397 в #398 вместе с **финальным** #395, исправить R-03 и повторить session/body/conditions tests.
4. Обновить #399 от исправленного #398, исправить R-04, повторить quota/voice/HTTP cancellation tests.
5. Обновить #400 от исправленного #399, вручную объединить helper additions, исправить R-05 и повторить full migrations/PostGIS + saved parity + legacy guards.
6. После каждого изменения base/head получать свежие checks на новой комбинации. Только затем принимать отдельные решения о merge. Не заменять ветки wholesale старым child tree.

Обычный корректный merge способен вернуть недостающие parent fixes. Не установлено, что Git сам молча их удаляет. Установлено другое: текущие child HEAD их не содержат, а последний шаг требует ручного решения конфликта; нынешний CI этого дерева не проверял.

## Часть 5 — Безопасность

### Проверенные границы доверия

| Область | Доказательство в реализации / тестах | Результат аудита |
|---|---|---|
| Result/session BOLA | `_owned` проверяет subject kind + id; result lookup повторяет ownership, валидирует session и hash/version | Обход не обнаружен; foreign requests в PG/HTTP tests отклоняются |
| Saved-search ownership | registered subject; `_active`; SavedSearch.user_id; owned original result; caller criteria/hash не принимаются | Обход не обнаружен; nested pool problem R-05 влияет на доступность |
| Replay/quota | fingerprint включает input + request + session/version/channel; SQL day/request locks; fence; atomic finalize | Повторный debit в выполненных гонках не обнаружен |
| Hard criteria / private listings | SQL proof/source/current canonical predicate + visible_query до count/order/limit/cluster | Проверенные несовместимые/hidden/stale-source/proof rows исключаются |
| CSRF / cookie / proxy | Mandatory X-AI-Request + origin, same-origin guest, trusted proxy networks, Secure/HttpOnly/Strict | Сохранены guards #394. Реальный локальный Chrome cookie test прошёл |
| Provider response poisoning | Strict patch/transcript contracts, vocabulary, full merged state validation, bounded reads | Невалидные ответы отклоняются; quality настоящего model inference не проверена |
| SSRF | Только synthetic MockTransport ASR и offline DeepSeek, фиксированные destinations | Публичного voice SSRF пути нет; это не production transport sandbox |
| SQL injection | SQLAlchemy expressions и bound values, server-owned vocabulary; нет динамического SQL из transcript | Нового подтверждённого injection пути не найдено |
| XSS | Conditions выводятся React text, map price labels через textContent; нет нового raw HTML вывода transcript | Нового подтверждённого XSS не найдено |
| Notification isolation | SQL/manual discriminator + per-row guard + DB alerts boundary, read-only dry-run | Настоящей доставки из AI dry-run не обнаружено |
| Private data/logging | Fixed private errors, repr exclusions, no transcript persistence в новых сервисах; сохранён private HTTP log handling | Нового подтверждённого экспорта audio/transcript не найдено; инфраструктурные логи вне локальной проверки |

R-03 — риск роста хранилища при множественных abandoned seeded sessions. Active-session bound ограничивает одновременно активные сессии, но expired rows более не считаются активными и могут накапливаться по дням. Это **не** обход тарифицируемой квоты и **не** доказанный внешний DoS, пока public runtime выключен.

R-04/R-05 — подтверждённые availability/reliability проблемы, не IDOR и не утечка данных. До появления публичных voice/save endpoints прямой удалённый exploit этих injected methods не заявляется.

### Сохранность требований #392–395

Из resolution docs и зависимых путей проверены query-proof.v2/canonical inventory binding, full-request idempotency, fail-closed empty/no-op provider response, compression bounds, total HTTP boundary, guest origin при TLS termination, explicit proxy trust, private logging, active-session cap, Retry-After, confirmed budget/native price separation. Проверенные #392/#393/#394 controls не были удалены новыми incremental реализациями. R-01 относится к более поздним #395 corrections, которые ещё не дошли до #398–400.

Не вводились утверждения о смене политик price/paid placement или живых платежах. Тесты Payment audit были зелёными в GitHub, но настоящие payment операции локально не выполнялись.

## Часть 6 — База данных, миграции и производительность

### Миграция 0072

Проверена вся миграция и совпадение с ORM. Один parent `0071_ai_query_proofs`, одна линейная Alembic head. Старые migration blobs не переписаны. Полная историческая цепочка на новой базе успешно обновилась до head; `alembic check` вернул `No new upgrade operations detected`.

Существующие rows получают `matcher=manual.v1`; старый NOT NULL rental_mode уже гарантировал совместимость старых записей с manual branch нового CHECK. AI parent допускает NULL rental_mode только с пустыми query/filters/polygon и выключенными legacy alerts. Composite unique `(id,matcher)` обеспечивает target composite FK child; child не может прикрепиться к manual matcher. Проверяются schema/taxonomy, positive revision, hash format и JSON object/size. Удаление parent каскадно удаляет child. Для reads по saved id достаточно PK/FK; user_id index существовал ранее. Полноценного SQL background matcher нет, поэтому отсутствие будущих worker indexes не названо сегодняшней ошибкой.

Тесты seeded legacy row проверили default/manual compatibility. Дополнительно выполнены полные legacy/manual notification regressions и full-schema saved tests. База с реальным историческим production dump не использовалась; malformed persisted criteria проверялись синтетическими corruption tests, а не реальным дампом.

DDL добавляет UNIQUE и CHECK на существующую таблицу обычными ALTER, без `CONCURRENTLY`/`NOT VALID` phased validation. Эти операции могут брать существенные блокировки/сканировать таблицу; длительность на production размерах не измерена. Это deployment/capacity risk, а не измеренная регрессия. Нужен rehearsal на репрезентативной копии с согласованными lock/statement budgets. Переписывать ранее released migrations ради этого нельзя.

### Downgrade: подтверждённое поведение, но не новый дефект PR

`0072_ai_saved_searches.py:40–43` содержит intentional no-op downgrade. Отдельный эксперимент на новой `ai_quota_test_rollback`:

```text
alembic upgrade head                       -> success
alembic downgrade 0071_ai_query_proofs       -> success
alembic current                            -> 0071_ai_query_proofs
alembic upgrade head                       -> failure
psycopg.errors.DuplicateColumn:
column "matcher" of relation "saved_searches" already exists
```

Причина: revision stamp откатился, физическая схема сохранилась. В репозитории это существующая expand-only/binary rollback policy: `docs/ai-search-developer/COMBINED_RUNTIME.md` прямо объясняет сохранение additive schema и отказ от проверки downgrade как физического отката. Аналогичный no-op уже есть в 0071. Поэтому этот результат **не включён в реестр новых пяти дефектов** и не служит самостоятельным merge blocker #400. Он опровергает только ожидание, что здесь поддерживается обычный downgrade→upgrade roundtrip.

Эксплуатационный runbook должен откатывать binary без понижения Alembic stamp и не разрешать такой roundtrip. Если команда должна поддерживаться, нужен отдельный design: явно отказать в неподдерживаемом downgrade до stamp change либо безопасно реализовать обратимые/idempotent операции без потери snapshots и security constraints. Автоматическое удаление AI snapshots не рекомендуется.

### Транзакции и конкуренция

Quota mutators блокируют day → request; claim блокирует request без попытки взять day, поэтому рассмотренная схема не образует обратного порядка day/request. Finalize выполняет session commit в savepoint, повторно проверяет lease, debit и result writes в одной транзакции. Ack uncertainty не трактуется как доказанный rollback. Stale-worker recovery не переиспользует провайдера.

Saved enable/disable берёт row locks и увеличивает revision; concurrent stale revision отклоняется. Dry-run read-only RR возвращает наблюдение на своём snapshot. Если disable/delete/block committed после начала snapshot, уже начавшийся dry-run может вернуть старое наблюдение; это соответствует документированному контракту и не разрешает последующую доставку. Будущий sender обязан отдельно fence/revalidate.

R-05 — отдельная проблема acquisition order: collection lock + checked-out connection → second checkout. PostgreSQL deadlock detector не обязан её обнаружить, потому что часть ожидания находится в application pool. Pool timeout ограничивает ожидание, но превращает валидное сохранение в ошибку.

### Производительность

Подтверждённые сложности и ограничения:

- Map loader debounces viewport reads и отменяет прошлые запросы, но каждая новая допустимая область выполняет verified query. Обязательный distributed HTTP gate остаётся необходимым.
- Proof/current-source SQL вычисляет коррелированные проверки и JSON predicates до count/limit/aggregation. На функциональных наборах правильность доказана; стоимость на большом каталоге не доказана.
- Card cursors включают proof population signature и агрегаты facts; вычисление зависит от размера соответствующей популяции, а не только текущей страницы. Это причина требовать measurement, не основание объявлять доказанный production slowdown.
- Выбранный map preview может выполнить до 20 публичных detail reads для coincident markers. Лимит конечный; отмена защищает от записи устаревшего состояния, но underlying detail fetch здесь не получает общий AbortSignal. Ненужные сетевые расходы возможны; нагрузка не измерялась и отдельный новый дефект не заявлен.
- Audio ограничено 20 MiB верхней границей policy, raw ASR response — максимум 1 MiB, transcript — bounded bytes/characters. Реальный decoder/duration policy отсутствует намеренно.
- Existing legacy notifier по-прежнему читает manual saved searches и делает per-search query. #400 добавляет discriminator и не вводит новый массовый AI worker; существующий N+1 не приписан этому PR как новая регрессия.

**Документированный R-01 capacity gate остаётся открытым.** Это обозначение из review #395, не совпадающее с номером интеграционной находки R-01 данного отчёта. Последний #395 требует representative dataset, approved numeric budgets, EXPLAIN ANALYZE BUFFERS для probe/aggregate, p50/p95/p99, resource/concurrency/cancellation measurements и zoom/density matrix. Ни локальные функциональные тесты, ни 24 synthetic timings из старого CI не закрывают этот gate. Для публичной активации он блокирующий; сам по себе не запрещает merge выключенного компонента после исправлений.

## Часть 7 — Тесты, CI и воспроизводимость

### Среда

Исходники: точный `df9653aaa8ee95658a6ad56a74b91f773c676fd9`, извлечённый `git archive`; отдельные parent HEAD дополнительно анализировались через Git. Путь: `C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit`. Windows, PowerShell, Python **3.13.17**, отдельный venv; зависимости backend установлены с `backend/constraints.txt`. PostgreSQL 16/PostGIS 3.4 — отдельный Docker container `ttest-pr397-400-audit-db`, только `127.0.0.1:55479`, disposable database `ttest_test` и отдельная `ai_quota_test_rollback`. Тесты quota/facts создают и удаляют случайные schemas. Redis не запускался: optional Redis test skipped, а не passed.

Тестовые DSN и JWT secret были синтетическими. `.env.local` пользователя не копировался. Production/staging DSN, SMTP, paid keys, live crawlers не использовались.

### Что реально выполнено

`PY` ниже — `C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-venv/Scripts/python.exe`. Backend test commands выполнены с loopback DSN в `DATABASE_URL`, `TEST_DATABASE_URL`, `AI_QUOTA_TEST_DATABASE_URL`, `AI_FACTS_TEST_DATABASE_URL` по назначению.

| Команда / проверка | Фактический результат | Локальное свидетельство |
|---|---|---|
| `PY -m pip install --constraint backend/constraints.txt -e './backend[dev]'` | Успех; первый ранний запуск pytest до завершения установки дал missing pytest_asyncio и был повторён после установки | [install](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-install.log) |
| `PY -m pytest -q -m 'not integration' backend/tests` | **1403 passed, 15 skipped, 845 deselected**, 17.99 s | [units](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-units.log) |
| `PY -m pytest -q backend/tests/ai_search_pg backend/tests/test_ai_offline_asr.py backend/tests/test_ai_saved_search_boundary.py backend/tests/test_ai_http_boundary.py` | **296 passed, 1 skipped**, 103.52 s; включает первые 3 audit probes. То есть 293 существующих passed + 3 дополнительных; это не 296 новых независимых тестов | [focused PG](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-pg.log) |
| `PY -m pytest -q backend/tests/ai_facts_pg` | **218 passed**, 75.89 s | [facts](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-facts.log) |
| `PY -m alembic upgrade head`, затем `PY -m alembic check` из backend | Успех; no new upgrade operations | [migration](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-migration.log) |
| `PY -m pytest -q backend/tests/integration/test_ai_verified_cards.py backend/tests/integration/test_ai_http.py backend/tests/integration/test_ai_saved_searches.py backend/tests/integration/test_listing_gallery_cards.py` | **55 passed**, 93.93 s, полная PostGIS schema | [full schema](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-fullschema.log) |
| `PY -m pytest -s -q backend/tests/ai_search_pg/test_audit_extra.py` | **4 passed**, финальный прогон 3.08 s; тесты утверждают наблюдаемые дефекты | [пробы](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/backend/tests/ai_search_pg/test_audit_extra.py), [вывод](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-extra-final.log) |
| `ruff check backend/app`; `PY -m mypy backend/app`; `PY -m pip check` | Успех; mypy **153 source files**, requirements consistent | [Ruff](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-ruff.log), [mypy](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-mypy.log), [pip](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-pip-check.log) |
| `node node_modules/typescript/bin/tsc -b --pretty false` | Успех | [TS](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-typecheck.log) |
| `node node_modules/vite/bin/vite.js build` в mock и production configs | Обе сборки успешны; предупреждение bundle size не считается дефектом | [mock build](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-build.log), [production build](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-production-build.log) |
| `node scripts/check-production-bundle.mjs`; `node scripts/check-i18n-source.mjs`; `node node_modules/oxlint/bin/oxlint` | bundle-security и i18n guard OK; oxlint exit 0, имеются предупреждения, в том числе существующие refs/effects warnings вне рассматриваемой функциональности | [bundle](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-bundle-security.log), [i18n](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-i18n.log), [lint](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-frontend-lint.log) |
| Playwright AI + ordinary map suites на статической mock-сборке через временный preview config | **22 passed**, 36.6 s: 21 существующий + 1 audit expired-session probe | [browser](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-preview-browser-final.log), [config](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/playwright.audit-preview.config.ts) |
| Настоящий loopback cookie/CORS pytest с `AI_HTTP_BROWSER_TEST=1`, `AI_HTTP_CHROMIUM_EXECUTABLE` = installed Chrome | **1 passed**, 3.34 s | [Chrome](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-real-browser-cookie-chrome.log) |
| Migration downgrade→upgrade probe на отдельной базе | Воспроизведён DuplicateColumn после no-op downgrade; classification: policy limitation | [rollback](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-rollback.log) |
| `git merge-tree --write-tree pr397 pr400` | Реальный conflict, exit 1 | [merge tree](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/audit-merge-tree.log) |
| `git diff --check` трёх incremental backend/feature deltas | Без ошибок | Выполнено для #398, #399, #400 относительно их fetched parent HEAD/merge-base |

Counts разных suites пересекаются; они намеренно не сложены в «общее количество независимых проверок». Дополнительные probes проходят потому, что assert наблюдаемое неправильное поведение, а не потому, что implementation исправлен.

### Ограничения frontend и неуспешные попытки

Локальные frontend checks использовали существующий dependency directory пользователя через временную junction. Это **не точное восстановление package-lock**: lock/installed соответственно Vite 8.3.5/8.3.4, React 19.2.7/19.3.1, Playwright 1.61.1/1.64.1; TypeScript 6.0.3 совпадает. Попытка восстановить точные зависимости в другой временной папке через pnpm import/install столкнулась с registry timeouts/error (23) и остановлена. Поэтому локальный browser/build success является дополнительным свидетельством поведения, а pinned-install evidence берётся из GitHub CI. Полного локального `npm ci` success не заявляется; `npm` CLI не был доступен.

Исходный dev-server Playwright прогон прерван после page.goto load timeouts; trace показывал незавершённые module/CSS requests. Эти ошибки не названы product defects. Переход на static preview позволил проверить приложение без dev-server module-loading проблемы. Первый preview запуск имел 9 passed / 2 failed / 11 not run: для production build не был задан обязательный map ID. После добавления **синтетического** `VITE_GOOGLE_MAPS_MAP_ID=AUDIT_SYNTHETIC_MAP`, с Mock SDK и запретом nonlocal ресурсов, полный прогон дал 22 passed. Настоящего Google Maps API вызова не было.

Первый Python Playwright запуск bundled Chromium завершился `BrowserType.launch: spawn UNKNOWN`; повтор с установленным Chrome прошёл. Неуспех запуска бинарника не замаскирован под product failure. Аналогично собственный downgrade эксперимент не засчитан как успешная проверка обратимости.

### GitHub CI: актуальный HEAD против реального тестируемого дерева

| PR | Полученные workflow runs, все completed/success |
|---|---|
| #397 | [Frontend 40584423585](https://github.com/antony502189-max/Ttest/actions/runs/40584423585), [Payment 40584423760](https://github.com/antony502189-max/Ttest/actions/runs/40584423760), [Security 40584423622](https://github.com/antony502189-max/Ttest/actions/runs/40584423622) |
| #398 | [Combined 40575808873](https://github.com/antony502189-max/Ttest/actions/runs/40575808873), [Frontend 40575809219](https://github.com/antony502189-max/Ttest/actions/runs/40575809219), [Quota 40575809244](https://github.com/antony502189-max/Ttest/actions/runs/40575809244), [Security 40575809340](https://github.com/antony502189-max/Ttest/actions/runs/40575809340), [Payment 40575809133](https://github.com/antony502189-max/Ttest/actions/runs/40575809133) |
| #399 | [Combined 40575817614](https://github.com/antony502189-max/Ttest/actions/runs/40575817614), [Quota 40575817619](https://github.com/antony502189-max/Ttest/actions/runs/40575817619), [Security 40575817754](https://github.com/antony502189-max/Ttest/actions/runs/40575817754), [Payment 40575817710](https://github.com/antony502189-max/Ttest/actions/runs/40575817710) |
| #400 | [Combined 40575826602](https://github.com/antony502189-max/Ttest/actions/runs/40575826602), [Quota 40575826724](https://github.com/antony502189-max/Ttest/actions/runs/40575826724), [Security 40575826591](https://github.com/antony502189-max/Ttest/actions/runs/40575826591), [Payment 40575826603](https://github.com/antony502189-max/Ttest/actions/runs/40575826603) |

Просмотрены jobs для всех трёх combined runs и #397 frontend; скачаны полные logs job `122442586805` (#400 combined) и `122472010208` (#397 frontend). Первый явно checkout `23482a4…` = merge `df9653aa…` в `5d3a2a36…`; в нём **1411 units / 7 skips**, **701 focused**, **55 full PostGIS**, **1 real Chromium**. Второй checkout `27db266…` = merge `bc9b8b1d…` в `68c79f77…`; в нём **16 browser tests passed**, npm ci/lint/typecheck/build success.

Эти runs связаны с текущими feature HEAD, но `actions/checkout` тестировал pull-request merge ref. Они не являются evidence для будущего объединения с более новым родителем. Особенно #398–400 не тестировали `bc9b8b1d`, а #397 — новый `21f1f0ef`. Более ранние зелёные counts из описаний PR не использовались как доказательство нового дерева. Существующие CI logs/metadata не показали failing current checks; failure logs отсутствуют, поскольку полученные runs успешны. Пагинированный diff получен полностью; workflow connector возвращает только первую страницу runs/jobs, поэтому абсолютная полнота всех исторических запусков не заявляется.

Сырые GitHub patches/discussions/CI metadata сохранены во временном [github-evidence.json](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/github-evidence.json); финальные metadata — [github-final-pr-state.json](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/github-final-pr-state.json). Полные logs: [#400 job](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/github-job-122442586805.json), [#397 job](C:/Users/HONOR/AppData/Local/Temp/ttest-pr397-400-audit/github-job-122472010208.json). Временные файлы не являются изменениями исходного репозитория и могут быть удалены системой после аудита.

### Что не выполнено и что ещё нужно проверить

Не запускались representative SQL EXPLAIN/load/cancellation benchmarks; настоящий ASR/LLM; production/staging DB или исторический production dump; live Google Maps; SMTP/push/payment/crawler; полный marketplace Playwright matrix; сетевой fault injection настоящего DB TCP disconnect в каждом voice phase. Не проверены все физические мобильные устройства и screen readers. Локальный security dependency/static workflow целиком не дублировался: проверены точные GitHub success и локальный production bundle guard. Синтетический provider/transcriber не доказывает security реального provider transport.

Матрица требуемых voice cancellation stages: before reserve/after reserve-before claim — shared ledger durability/recovery + недостающий orchestration failpoint test; during ASR/intent — штатные voice cancellation tests; между фазами/during query — общие execution/HTTP и total voice query tests, нужен отдельный failpoint на каждом handoff; during finalize — shared real transaction rollback/fencing и HTTP callback cancellation tests; provider success/ack loss — voice ack-loss replay test; deadline expiry — штатные tests + R-04 real row-lock probe; DB connection loss — существующий outer rollback/ack-loss simulation, полного TCP kill не было; concurrent retry/recovery — штатные running duplicate/stale fence/recovery tests, не exhaustive scheduler exploration.

Воспроизводимый план непокрытых случаев: на новой loopback PostGIS базе добавить barriers после reserve, claim, ASR и candidate query; отменять task/обрывать выделенное test connection через отдельный admin connection; проверять ledger/request/session/result в новой транзакции, recovery после grace, отсутствие повторного ASR/parser при прежнем ключе и `used+reserved` invariant. Для каждого high-risk finalize случая отличать uncommitted rollback от commit-ack loss. Никаких real provider или public delivery не требуется.

## Часть 8 — Приоритизированный реестр дефектов

Здесь R-01 — интеграционная находка настоящего отчёта. Не смешивать её с capacity finding R-01 из документа #395. Все пять замечаний имеют **P2**; более высокая severity не обоснована текущим выключенным runtime и установленным impact. «Воспроизведено» означает воспроизведение сбоя/неправильного поведения, не успешное устранение.

| ID | Priority | PR | Файл:строка | Проблема | Влияние | Воспроизведение | Исправление | Статус |
|---|---|---|---|---|---|---|---|---|
| R-01 | P2 | #397–400 | `backend/tests/integration/test_ai_verified_cards.py:31` (#400); `backend/app/api/v1/ai_search.py:285` (#398–400) | Child chain не содержит latest parent fixes; реальный helper conflict | Нет проверенного интегрированного дерева; риск выбросить одну ветвь regression tests | merge-base/ancestor checks + `merge-tree pr397 pr400`, exit 1 | Последовательно обновить от #396/#397, объединить оба helper расширения, fresh CI | Воспроизведено Git; отсутствие исправлений статически доказано |
| R-02 | P2 | #397–400, исходно #396 | `src/components/home-ai-search.tsx:104` на #398–400 | Очистка terminal pending зависит от GET истёкшей сессии | Невозможно редактировать текст или начать новый диалог без remount/reload | Failed SESSION_EXPIRED + GET409; retry повторяет key, controls disabled | Отделить terminal operation от session refresh; явный безопасный reset/new conversation | Воспроизведено браузером |
| R-03 | P2 | #398–400 | `backend/app/repositories/ai_search_sessions.py:159`, `:208` | Новый rental-mode seed несовместим с predicate cleanup_unused | Неограниченный во времени рост abandoned expired rows при повторном использовании | Empty + seeded version0, expire, cleanup → удалён только empty | Обновить понятие unused с сохранением всех referenced/audited sessions | Воспроизведено PostgreSQL |
| R-04 | P2 | #399–400 | `backend/app/services/ai_voice_execution.py:126` | Timeout cleanup вне voice total deadline | Длительное удержание caller task/resources при SQL contention/failure | Valid 100ms policy + real usage-day FOR UPDATE → task ждёт дольше 250ms | Bounded cleanup с учётом own/HTTP deadlines; recovery после исчерпания | Воспроизведено PostgreSQL и controlled waiter |
| R-05 | P2 | #400 | `backend/app/repositories/ai_saved_searches.py:115` | Второй checkout того же pool внутри save transaction | Валидный save падает на малом/насыщенном pool; lock держится во время pool wait | pool_size1, overflow0 → SQLAlchemy TimeoutError | Читать owned committed result тем же conn; сохранить collection cap atomicity | Воспроизведено PostgreSQL |

### R-01 — Не синхронизированная цепочка и конфликт интеграционных регрессий

**Commit evidence:** #397 `bc9b8b1de6012e70f138f1d6d591ee93cce87fd3`, #398 `02d7029161677a7a1076899c2f678e912cf6f35b`, #399 `5d3a2a362d384e3a6af1e3884d5e9a273251366c`, #400 `df9653aaa8ee95658a6ad56a74b91f773c676fd9`. Конфликтующая точка — [test helper #400, строки 31–39](https://github.com/antony502189-max/Ttest/blob/df9653aaa8ee95658a6ad56a74b91f773c676fd9/backend/tests/integration/test_ai_verified_cards.py#L31). Отсутствующий validator виден в [MapView #398](https://github.com/antony502189-max/Ttest/blob/02d7029161677a7a1076899c2f678e912cf6f35b/backend/app/api/v1/ai_search.py#L284) в сравнении с [исправленным #397](https://github.com/antony502189-max/Ttest/blob/bc9b8b1de6012e70f138f1d6d591ee93cce87fd3/backend/app/api/v1/ai_search.py#L287).

**Причина:** descendants обновлены только до a3742df1; после этого parent получил e68a47e8 fixes. Сам #397 затем также отстал от live #396. Предусловие проблемы — попытка считать четыре текущих HEAD полностью согласованным stack или интегрировать финальный child с актуальным parent без содержательного разрешения конфликта.

**Шаги:** fetch все head refs; выполнить команды части 4; сравнить `git diff a3742df1 pr397 -- backend/app/api/v1/ai_search.py backend/app/repositories/ai_verified_cards.py`; выполнить `git merge-tree --write-tree pr397 pr400`.

**Ожидается:** все принятые parent fixes присутствуют; объединение сохраняет обе группы тестов и проверяется новым CI. **Факт:** parent не ancestor child, seven-file corrections отсутствуют, merge-tree даёт content conflict. Зелёный старый child CI не включает эту комбинацию.

**Impact:** неверная готовность merge, риск утраты dense-map либо saved-search parity checks при механическом выборе стороны. Сам по себе conflict теста не означает production data corruption. Проблема дедуплицирована: отсутствие 422/one-plan/docs/tests не посчитано отдельными новыми багами во всех трёх child PR.

**Исправление / regression:** обновлять по порядку #396→397→398→399→400, объединить параметры/helper logic, проверить единый compiled plan, invalid-bound private422, dense thresholds и 15 saved/card/map parity cases на итоговом HEAD. Сохранить public predicate API для #400. **Статус:** reproduced + statically proven. **Merge blocker:** да, для заявления о согласованной цепочке.

### R-02 — Terminal expiry навсегда оставляет UI в pending

**Commit / path:** [#398 home-ai-search.tsx, строки 103–107](https://github.com/antony502189-max/Ttest/blob/02d7029161677a7a1076899c2f678e912cf6f35b/src/components/home-ai-search.tsx#L103), те же строки на #400 `df9653aa`. На [#397 соответствующий участок — строки 89–92](https://github.com/antony502189-max/Ttest/blob/bc9b8b1de6012e70f138f1d6d591ee93cce87fd3/src/components/home-ai-search.tsx#L89). Источник: `59eeaf46b236d3b4c4b9f64e6219cd052cfd5fcf` из #396; это наследуемый дефект используемого компонента, а не независимо новый баг #397 и #398.

**Неправильная реализация:** после terminal ответа frontend сначала делает `await getAISession(message.session_id)`, затем очищает pending. Истёкшая/закрытая сессия гарантированно не читается. Catch очищает pending только для 413/422. `pending !== null` блокирует textarea и, начиная с #398, mode selector, включая создание новой conversation.

**Предусловия:** диалог остаётся смонтирован; backend возвращает terminal failed `SESSION_EXPIRED` (например, followup после inactivity cutoff) и GET session возвращает 409. Возможен также потерянный successful response, восстановление которого происходит уже после conversation expiry; его отдельный live-server UI тест не выполнялся.

**Шаги воспроизведения:** создать session; дать ей истечь; отправить followup. Или использовать локальный audit browser test с ответом `{operation:{status:'failed',failure_code:'SESSION_EXPIRED',remaining:3,receipt:null},cards:null}` и GET409 `SESSION_EXPIRED`. Нажать retry два раза, проверить idempotency keys и disabled controls.

**Ожидается:** terminal operation распознаётся как завершённая; пользователь может явно начать новый диалог без переотправки неопределённого платного запроса. **Факт:** две отправки одного key, обе terminal; текст и mode остаются disabled, кнопка предлагает бесконечно проверять прежнюю попытку. Закрытие dialog само по себе не размонтирует panel state.

**Impact:** поиск в текущем mounted panel перестаёт быть пригодным к использованию; требуется reload/navigation/remount. Подмена результата и двойной debit не доказаны.

**Исправление:** отделить clearing terminal operation от обновления editable session. Коды SESSION_EXPIRED/NOT_FOUND и confirmed terminal failure должны приводить к явному recovery state с новой conversation; original committed result и uncertain operations не подменять. Для ambiguous timeout сохранять exact-key replay до authoritative terminal state. Не обрабатывать любой transport error как разрешение создать новый key.

**Regression:** создать первый result, перевести session в expired, отправить followup, получить terminal failure; проверить разблокировку safe new-session action, сохранность старых labels/cards, новый session ID и отсутствие повторного debit старой операции. Дополнительно guest cookie expiry и ack-loss-after-session-expiry.

**Свидетельство:** `audit: terminal expired session permanently locks editable controls`, test line 457 во временной копии; вошёл в финальный прогон 22 passed. **Статус:** reproduced. **Merge blocker:** да, функциональный сценарий принятого AI panel. Исправление лучше внести в #396 и наследовать.

### R-03 — Неиспользованные сессии с rental-mode seed выпадают из очистки

**Commit / path:** #398 `02d7029161677a7a1076899c2f678e912cf6f35b`; [создание criteria](https://github.com/antony502189-max/Ttest/blob/02d7029161677a7a1076899c2f678e912cf6f35b/backend/app/repositories/ai_search_sessions.py#L128), [persist seed](https://github.com/antony502189-max/Ttest/blob/02d7029161677a7a1076899c2f678e912cf6f35b/backend/app/repositories/ai_search_sessions.py#L159), [cleanup predicate, строки 208–211](https://github.com/antony502189-max/Ttest/blob/02d7029161677a7a1076899c2f678e912cf6f35b/backend/app/repositories/ai_search_sessions.py#L208). Введено `3ca2972a`; наследуется #399/#400.

**Причина:** ранее version0 unused sessions имели `{}`. Новый seed сохраняет `{rental_mode:{strength:'hard',value:...}}` уже при create, однако cleanup по-прежнему требует exact `{}`. Ни операции, ни result для такой abandoned session может не существовать.

**Шаги:** создать одному subject пустую session и SessionCreate(rental_mode='long'); не выполнять reserve/query; установить обеим expires_at в прошлое; вызвать `cleanup_unused(older_than=aware_past_cutoff, limit=100)`; прочитать remaining IDs.

**Ожидается:** явная bounded cleanup policy распространяется на abandoned pre-message sessions обоих способов создания, с защитой любого audit/result/reference. **Факт:** removed=1; удалена только empty, seeded version0 осталась. Последующие calls с более поздним cutoff не меняют predicate, поэтому строка так и не становится eligible.

**Impact:** рост таблицы после истечения каждой серии active sessions; active cap не ограничивает исторические expired rows. Автоматический cleanup worker не запущен и не требуется его включать ради исправления; сломан уже существующий explicit cleanup seam. Проблема не означает потери пользовательских результатов.

**Исправление:** пересмотреть invariant unused для version0/pre-message seeds. Безопасный вариант — явно распознавать пустые criteria и единственный initial rental-mode seed, при этом сохранять NOT EXISTS request/result и past cutoff/batch/skip-locked. Если поддерживаются другие initial user data, сначала определить их retention meaning; не удалять произвольные nonempty conversations по упрощённому условию.

**Regression:** seeded/empty long/holiday, referenced reserved/failed/succeeded rows, result references, ещё активные sessions, max batch и locked rows. Проверить, что quota/result audit не удаляется.

**Свидетельство:** PostgreSQL probe `test_seeded_unused_sessions_are_never_cleaned`, вывод `seeded unused retained; empty removed 1`; existing `test_http_review` использует empty seeds, поэтому проходит. **Статус:** reproduced. **Merge blocker:** да для #398, поскольку seed меняет существующий lifecycle invariant.

### R-04 — Голосовой total budget не ограничивает cleanup после timeout

**Commit / path:** #399 `5d3a2a362d384e3a6af1e3884d5e9a273251366c`; [ai_voice_execution.py:126–129](https://github.com/antony502189-max/Ttest/blob/5d3a2a362d384e3a6af1e3884d5e9a273251366c/backend/app/services/ai_voice_execution.py#L126), cancellation без HTTP deadline также строки 117–119. Наследуется #400.

**Причина:** `asyncio.timeout_at(deadline)` охватывает ASR/intent/query внутри try. Timeout становится Exception, затем `ledger.release()` awaited уже вне этого timeout. Если HTTP_DEADLINE отсутствует, нет отдельного remaining-budget bound. В cancellation branch без HTTP контекста release также не ограничен собственным voice budget. PostgreSQL/app timeouts могут прекратить ожидание позже, но не реализуют установленный VoicePolicy deadline.

**Предусловия:** нормальный injected/offline caller, который пока является единственным реализованным voice consumer; медленный provider вызывает timeout, а release ждёт DB row lock/connection. Публичного voice HTTP route нет. Необходимости в malicious ASR/transport нет.

**Реальное воспроизведение:** validated VoicePolicy ASR=0.03 s, intent=0.03 s, total=0.1 s, running lease=60 s; ASR ждёт Event. После сигнала входа ASR отдельная PostgreSQL transaction блокирует принадлежащую subject строку AIUsageDay через FOR UPDATE. Удерживать lock 0.25 s. ASR timeout вызывает release; проверка после 0.25 s показывает `task.done() == false`. После release blocker transaction задача завершается failed. Второй controlled-waiter probe использует validated ASR=0.01, intent=0.01, total=0.03 и показывает ожидание release ещё через 0.1 s. Валидатор allocation в финальных probes не обходится.

**Ожидается:** собственный total budget и явно ограниченный cleanup не позволяют задаче ждать произвольно дольше; если cleanup не успел, остаётся durable fenced reservation для recovery. **Факт:** task продолжает ожидать release после истечения total; на application DB существующие statement/pool timeout defaults могут растянуть ожидание на секунды/десятки секунд.

**Impact:** нарушение latency/cancellation contract и занятие ресурсов при contention/DB problems. Нет evidence двойного списания, неправильного release completed operation или permanent reservation leak: проверенный путь сохранил accounting и завершился после освобождения lock.

**Исправление:** явно выбрать deadline для post-failure cleanup как ограниченный остаток own deadline и HTTP deadline, либо отдельный bounded cleanup allowance с документированным total contract. По исчерпанию не начинать бесконечный release; оставить fenced recovery. Finalize acknowledgement по-прежнему считать ambiguous и не помещать его в generic speculative-release handler. Саму finalize транзакцию тоже учитывать в caller/request budget, не ослабляя atomicity.

**Regression:** real PG lock во время ASR timeout, intent timeout, external cancellation без HTTP context и с исчерпанным HTTP context; bounded completion, последующий recovery, stale fence rejection, exact-key replay, invariant used/reserved. **Свидетельство:** два probes в `test_audit_extra.py`, оба прошли с assert нарушения deadline. **Статус:** reproduced. **Merge blocker:** да для заявленного bounded offline operation.

### R-05 — Nested pool checkout при сохранении snapshot

**Commit / path:** #400 `df9653aaa8ee95658a6ad56a74b91f773c676fd9`; [ai_saved_searches.py:109–115](https://github.com/antony502189-max/Ttest/blob/df9653aaa8ee95658a6ad56a74b91f773c676fd9/backend/app/repositories/ai_saved_searches.py#L109); зависимость [SearchSessions.result, строки 276–282](https://github.com/antony502189-max/Ttest/blob/df9653aaa8ee95658a6ad56a74b91f773c676fd9/backend/app/repositories/ai_search_sessions.py#L276), которая открывает новую session. Введено `d9a70c17`.

**Причина:** outer save transaction уже получила connection для collection advisory lock и `_active/count`. Затем `self.sessions.result()` создаёт вторую AsyncSession из того же factory, которой нужен ещё один checkout. Constructor как раз требует общий factory authority, но не гарантирует свободный второй connection.

**Предусловия:** допустимый pool_size=1/max_overflow=0 либо исчерпание доступных соединений большего пула. Settings допускает size≥1 и overflow≥0. Нужны текущий registered owner, owned committed result, свободный collection cap — без злонамеренного input.

**Шаги:** на disposable PG создать owner/result штатными fixtures; создать engine с тем же DB/schema и `pool_size=1,max_overflow=0`; передать один maker ledger и pipeline; вызвать RegisteredAISearches.save. Для быстрого probe установлен pool_timeout=0.15 s; при разрешённом runtime timeout≥1 s механизм тот же.

**Ожидается:** один save может завершиться на минимально допустимом pool, либо сервис заранее валидирует и документирует иную необходимую topology. **Факт:** SQLAlchemy PoolTimeout при nested result read, хотя outer connection простаивает, удерживая collection lock. На более крупном насыщенном pool такие же nested waits возможны; полный default-size нагрузочный эксперимент не выполнялся и его failure rate не выдуман.

**Impact:** отказ валидной операции и увеличение времени удержания collection lock, в том числе для manual saves/import. Потеря snapshot или обход cap не обнаружены; outer transaction откатывается.

**Исправление:** реализовать чтение owned committed result с переданным AsyncSession и выполнить ownership/schema/session/hash проверки в том же conn, где идут collection lock/count/write. Альтернатива read-before-transaction требует повторной проверки важных current-owner/expiry invariants; простое увеличение pool маскирует проблему и не устраняет acquisition dependency.

**Regression:** pool_size1/overflow0 success; несколько concurrent AI/manual saves при маленьком pool и cap=1; foreign result rejection; blocked/deleted user; expired conversation; отсутствие result/session mutation, quota/mail side effects; проверка отсутствия второго checkout. **Свидетельство:** PG probe `test_save_nested_checkout_exhausts_supported_small_pool`, зафиксирован PoolTimeout. **Статус:** reproduced. **Merge blocker:** да для нового save seam.

### Классификация остальных замечаний

Подозрения без установленного exploit condition не внесены как confirmed vulnerabilities. Unknown-source freshness, real provider transport, public saved/voice UI, durable delivery decisions и representative SQL — **known activation gates**. Непроверенные failpoints, физические устройства и actual TCP disconnect — **missing tests / limitations**, а не доказанные дефекты. No-op migration downgrade — **существующая policy limitation**, см. часть 6. Субъективный стиль, размер компонентов и inherited unrelated lint warnings не повышались до findings.

## Часть 9 — План исправлений

| Порядок | Работа и PR | Сложность | Зависимости | Проверки регрессии | Блокирует merge? |
|---:|---|---|---|---|---|
| 1 | R-02: recovery terminal expired session в исходном #396; передать #397–400 | M | Отделить confirmed terminal от ambiguous operation | Failed expiry, expired guest, ack loss, controls/new-session identity, old result labels | Да для panel |
| 2 | R-01: актуализировать #397 от #396, #398 от #397, #399 от #398, #400 от #399 | M | Порядок parents; сохранить shared predicate API и обе ветви helper | Full combined tree, MapView422, dense map, 15-criterion parity, frontend/mobile | Да для stack |
| 3 | R-03: cleanup predicate учитывает безопасные initial mode seeds в #398 | S–M | Не удалять audit/result/used conversations; retention cutoff остаётся caller-defined | Empty/seeded, both modes, active, locked, referenced, batch | Да для #398 |
| 4 | R-04: ограничить failure/cancellation cleanup deadline в #399 | M | Соблюсти #394 request deadline, lease fencing и finalize ack uncertainty | Real PG locks, every provider timeout, cancellation, recovery/replay, no duplicate debit | Да для #399 |
| 5 | R-05: same-connection committed-result read в #400 | M | Общая validated result-read seam, collection cap atomicity | pool1, small-pool concurrency, cap, ownership, expiry, legacy | Да для #400 |
| 6 | Проверить миграцию/rollout на репрезентативной disposable copy; уточнить binary-only rollback runbook | M | Approved dataset и deployment budgets | Legacy rows, lock duration, old/new binary combinations, отсутствие downgrade stamp drift | Для deployment; policy downgrade не отдельный merge blocker |
| 7 | Повторить exact-head CI после всех parent/head changes | M | Все исправления и conflict resolution | Backend units + PG/PostGIS/migration, frontend pinned install, security/payment/ordinary regressions | Да |
| 8 | Закрыть documented capacity/privacy/provider/freshness/retention gates | L–XL | Operator/product approval, representative data и budgets | EXPLAIN/load/cancel, approved sources, real transport security, abuse and privacy E2E | Для public activation |
| 9 | Если нужен delivery: отдельный versioned/fenced/idempotent delivery design и quota/retention policy | L–XL | Собственное явное решение об активации уведомлений | Disable/delete/block race, duplicate/out-of-order, ack retry, actual delivery dedupe | Для delivery activation |

Сложности — инженерная оценка объёма, не обещание сроков. Никакие исправления не требуют ослабления ownership, hard predicates, CSRF, quota либо возврата к manual fallback. Вносить функциональные изменения следует в самый ранний содержащий их PR, чтобы потомки наследовали исправления и regression tests.

### Порядок deployment после будущего одобрения

1. Миграция 0072 перед новым ORM/backend, с измеренным lock budget.
2. Все backend instances и legacy notification/import/publish workers получают manual discriminator/metadata guards.
3. Новый frontend только после backend с поддержкой explicit mode seed. Старый backend может принять body, не применив seed; смешанный rollout без гарантии версии не сохраняет обещанный typed hard mode.
4. Пока новая система остаётся выключенной, voice/saved/delivery capability остаются false. AI saved writes допустимы лишь после вывода всех старых workers из обслуживания соответствующих путей: DB alerts constraint не превращает старый код в код, понимающий typed snapshots.
5. Public text/map activation — отдельное решение после всех gates. Voice и notification delivery требуют отдельной проверки и явного включения; merge helper classes не даёт этого разрешения.

## Часть 10 — Итоговый вердикт

| PR | Решение | Что требуется до одобрения |
|---|---|---|
| #397 | **REQUEST CHANGES** | Унаследовать исправление R-02 в #396, обновиться от актуального #396, сохранить map binding/no-fallback и получить свежие checks |
| #398 | **REQUEST CHANGES** | R-03, актуальный parent с финальными #395 corrections, унаследованный R-02, свежие session/conditions/frontend checks |
| #399 | **REQUEST CHANGES** | R-04, исправленный parent, real PG contention/cancellation regression и свежие quota/voice/combined checks |
| #400 | **REQUEST CHANGES** | R-05, актуальная цепочка, содержательное разрешение helper conflict с сохранением обеих групп tests, повтор migration/legacy/saved/PostGIS checks |

**Integrated stack: REQUEST CHANGES — текущую совокупность HEAD считать готовой к merge нельзя.** Исходники доступны и review проведён, поэтому `BLOCKED / NOT REVIEWABLE` к этим PR неприменим. Draft-статус и зелёный CI не заменяют устранение перечисленных проблем. Ни один PR не merged и ни один GitHub review от имени пользователя этим аудитом не отправлен.

**После исправлений возможно одобрение merge выключенной основы. Public production activation сейчас не одобрена.** Для неё отдельно нужны documented representative SQL capacity gate, реальные provider/source coverage и freshness, privacy/retention/consent, production ingress/logging/abuse configuration и сквозные production-like тесты. Saved dry-run должен оставаться наблюдением без доставки до отдельного утверждённого delivery lifecycle.

### Сохранность рабочей папки

Начальный `git status` содержал пользовательское изменение `deploy/manual-production-runner.sh` и ранее существовавшие untracked artifacts/build directories. Они не редактировались. Production code, миграции, tests, package manifests/lockfiles в рабочем checkout не изменены. Все дополнительные tests/configs/builds/venv/logs находятся в Temp; единственный новый исходный рабочий artifact — этот Markdown-отчёт. В Git добавлены только локальные audit refs для анализа fetched объектов, без push и изменения пользовательской ветки.

После проверки тестовый Docker container остановлен; данные не удалены. Для повторного запуска можно выполнить `docker start ttest-pr397-400-audit-db`. Мобильный screenshot `output/ai-home-dialog-mobile.png` дополнительно просмотрен визуально: controls/summary помещаются по ширине, содержимое диалога прокручивается; это не проверка всех devices или assistive technology.
