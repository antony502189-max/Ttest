# План сборки и запуска AI-контура

Дата: 31 октября 2026, Europe/Moscow.

Обновление 1 ноября: текущая работа — пункт 4 только offline; живые вызовы
владелец пока не разрешил. Пункт 3 пропущен, не выполнен. Ниже сохранены
исторические исходные SHA и результаты, актуальные статусы указаны в пунктах.

Владелец согласовал этот план и поручил в новом чате реализовать пункт 1.
Ближайший результат — закрытый функциональный текстовый стенд на синтетических
данных. Он собирается параллельно с оптимизацией производительности.

## Исходное состояние

- Рабочий checkout: `C:\Users\HONOR\.codex\worktrees\main-integration-audit\Ttest`.
- Ветка: `codex/post-merge-remediation`; существующий draft PR
  [#403](https://github.com/antony502189-max/Ttest/pull/403).
- Последний runtime SHA: `06af013856798f4eb93572433b522796edc69fdc`.
- Evidence HEAD перед сохранением плана:
  `891569945ed5425f2ff91269b7dca2a879af7531`.
- Migration head: `0075_ai_proof_population`.
- Оба указанных SHA прошли все 11 исполнявшихся CI workflows;
  два conditional visual workflows skipped.
- Новый isolated capacity experiment `74074e06e9d748909889d1567a541f2c`:
  100k/500k/1m, 54 сценария, 8800 попыток, 5200 ошибок, 0 SLO-pass.
  Protocol COMPLETE / SLO FAIL; ISSUE-004 остаётся OPEN.
- Приложение намеренно не создаёт `AISearchRuntime` по умолчанию.
  Offline intent adapter допускает только `httpx.MockTransport`.
- Есть проверенные services, HTTP boundary и UI; их наличие не означает,
  что готова запускаемая сборка приложения с активным AI runtime.

Актуальные доказательства: [отчёт](../../reports/POST_MERGE_REMEDIATION.md),
[capacity](../../reports/AI_MAP_CAPACITY_PERFORMANCE_20261031.md),
[архив и hashes](../../reports/post-merge-remediation-evidence/performance-capacity-evidence.json).
Старые документы о промежуточных PR читать как историю; фактический код и новые
отчёты определяют текущее состояние.

## Ограничения и разрешённая работа

Владелец разрешил реализацию пункта 1 в новом чате: закрытый локальный стенд,
синтетические данные, реальные frontend/backend/PostGIS/Redis и тестовый parser.
Merge в main для этого не нужен. Нельзя подменять весь AI API браузерными mocks:
подменяется только граница модели/извлечения, остальная цепочка настоящая.

Сохраняются запреты на merge PR #403, public AI, внешнее deployment, реальные
LLM/data providers/ASR, production/application DB, crawling/backfill реального
каталога, платежи, уведомления и Pages. Реальные ключи для пункта 1 не нужны.
Не ослаблять Secure cookies, CSRF/origin, ownership, proof/currentness или quotas.

Использовать существующий worktree и ветку. Не менять исходный грязный checkout
`C:\Users\HONOR\Documents\Codex\Ttest`; новый worktree не создавать без запроса.
Следующие изменения добавлять в тот же PR. Старые lab DB и опубликованные raw
artifacts не изменять и не переиспользовать для новой certification.

## 1. Закрытый текстовый стенд

**Статус: выполнен 31 октября 2026; закрытый функциональный smoke PASS.**

Проверенный source `3693f897e79cbe2e426b8ea3e5c04b4310acdc0b`,
UI/API `https://localhost:9443`, отдельные PostGIS/Redis/backend/frontend.
13 проверок реального Chromium smoke, 5 unit guards, shared Redis/fail-closed
проверки и воспроизводимый stop/start прошли; обычный production runtime disabled.
Модель и extraction синтетические, карта — локальная координатная сетка с
настоящим verified map API. Это не принятие пункта 2 или performance/model release.

[Запуск и запросы](AI_TEXT_LAB_RU.md),
[отчёт пункта 1](../../reports/AI_TEXT_LAB_20261031.md),
[browser evidence](../../reports/ai-text-lab-evidence/browser-smoke.json),
[source/isolation](../../reports/ai-text-lab-evidence/source-attestation.json).

Собрать отдельные PostgreSQL/PostGIS, Redis, backend и frontend с закрытым
доступом и собственными именами/volumes/ports. По умолчанию использовать local
loopback, а не внешний сервер. Для браузерной проверки нужен контур с корректной
работой Secure guest cookies и same-origin; production protections не отключать.

Добавить явную сборку зависимостей: `AISearchRuntime`, sessions, quota ledger,
распределённые HTTP/attempt gates, guest/cursor signing, HTTP policy, parser,
verified cards/map и execution/finalization. Использовать отдельные тестовые
ключи и явные bounded test policies. Production default остаётся disabled;
секрет или env key сам по себе не должен включать общий runtime.

Загрузить небольшой контролируемый синтетический каталог через настоящий
FactPipeline → facts/projections → QueryProofs.prepare. В наборе нужны известные
положительные/отрицательные результаты, несовместимые hard criteria, неполные
данные и случаи устаревания/скрытия/несовпадения цены. Не отдавать fixture cards
в обход реального SQL и не выдавать mock parser за проверенную модель.

В браузере должна работать цепочка:

`ввод → тестовый parser → typed intent → owned query → настоящая БД → карточки → карта → уточнение`.

Тестовый parser должен быть детерминированным и поддерживать документированные
сценарии для ручного прогона. Сеть к внешним моделям и источникам отсутствует.

Подготовить воспроизводимые start/seed/status/stop команды, конфигурационный
пример без реальных секретов, описание тестовых пользователей и запросов.
Launcher должен различать собственные контейнеры и существующие/shared сервисы;
не останавливать и не пересоздавать чужую инфраструктуру.

Критерии готовности пункта 1:

- стенд запускается из фиксированного source и понятной инструкции;
- реальные UI/API/DB возвращают ожидаемые IDs, counts, карты и typed conditions;
- работают guest/auth session ownership, квоты, follow-up, result/card/map reads;
- runtime включён только внутри явной test-only сборки;
- отсутствуют реальные provider calls и использование application DB;
- выполнен сквозной браузерный smoke с реальным backend;
- отчёт фиксирует URL, source SHA, собственные ресурсы, ограничения и результаты;
- пункт 1 не объявляется прохождением capacity, model quality или public release.

## 2. Функциональная приёмка стенда

**Статус: выполнен 31 октября 2026; 29 сценариев PASS.**

Runtime `70330a138cdb1a8313fc0ed61bc69b7ecbfc4985`, test driver
`59ee317b9c4c77ca8fe0e1b985bf0f2a947ac494`. Реальный browser/API/PostGIS/Redis:
ES/EN/RU × 320/768/1440, paging/IDs/map, reload guest/auth, hard/soft/unknown,
потерянные ответы, duplicates, cancellation, expiry и live изменения каталога.
Исправлены reload recovery, invalidated-card presentation и mobile overflow.
[Ручная/автоматическая матрица](AI_TEXT_ACCEPTANCE_RU.md),
[отчёт](../../reports/AI_TEXT_ACCEPTANCE_20261031.md),
[evidence](../../reports/ai-text-acceptance-evidence/acceptance.json).
Обычный поиск сохранён; production default disabled, real model не подключалась.

Проверить обычный поиск и уточнения, hard/soft criteria, нулевой результат,
пагинацию, карту, восстановление после reload и актуальные подписи условий.
Пройти повторную отправку, потерянный ответ, cancellation, истечение сессии,
смену источника/модерации/цены между страницами.

Повтор операции не должен повторно вызывать parser или списывать quota.
Неподтверждённые/устаревшие объявления не остаются в выдаче; отсутствующие
доказательства не превращаются в разрешение. Не смешивать текущую editable
session с прежним committed result. Проверить ошибки и основные размеры экрана
и языки, сохранив обычный поиск на его существующем пути.

Результат — воспроизводимый ручной и автоматический набор сценариев с известными
ожидаемыми результатами. Полная матрица пункта 2 следует за smoke пункта 1.

## 3. Производительность — параллельное направление

**Статус: пропущен по поручению владельца 31 октября; НЕ выполнен.**
К оптимизации и большим нагрузочным прогонам не возвращаться без нового
поручения. ISSUE-004 OPEN / capacity BLOCKED. Ниже сохранены результаты
и прежние предложения для истории; они не являются текущим заданием.
Миграция `0076_ai_fact_population` устраняет полный cursor count/sum при
чтении карточек; прямые SQL writers охвачены транзакционными триггерами.
[Контракт и воспроизведение](AI_FACT_POPULATION_RU.md),
[отчёт и планы](../../reports/AI_FACT_POPULATION_20261031.md).
Следующий шаг реализован в `a38a4f3d`: версии входов, FK-backed атомарная
инвалидация proof и общие неизменяемые профили matching. При неизменных входах
больше не читаются facts/dependencies на каждого кандидата; changed/legacy
проверяются исходным live v2 digest, missing state исключается. Public и
time-dependent guards остаются живыми до count/LIMIT/aggregate.
Все 11 обязательных CI и локальные 1566 unit / 315 PG / 68 integration / 5
composition checks успешны. Точный capacity source `ea333e15` дополнительно
делает single-writer только synthetic setup, без ослабления нагрузки поиска.

Свежий experiment `3056bd59405546c984354b07f2382a1f`: 100k объектов,
18 сценариев, 3600 попыток, 1161 ошибок, 0 SLO-pass. 100k evidence полное;
трёхмасштабный протокол INCOMPLETE, 500k/1m отложены до новой оптимизации.
Стенд остановлен, raw artifacts сохранены. ISSUE-004 OPEN / capacity BLOCKED.
[Контракт, результаты и следующий bottleneck](../../reports/AI_LIVE_INPUTS_20261031.md).

Текущие планы показывают повторный обход кандидатов для cohort, 100k отдельных
proof probes на широком viewport и стоимость сборки SQL graph в приложении.
Устранить эти расходы; далее рассмотреть агрегаты на пути записи.
Покрыть source changes, canonical/room, facts/batches, remap/delete, direct SQL,
concurrency/rollback/CAS и актуальную public eligibility. Учесть moderation,
blocked owners и изменения по времени, включая TOP/freshness policy.

Counter prepared-proof population относится только к cursor context. Он не
является готовой версией live eligibility и не заменяет текущие guards.
Проверки остаются до count/order/seek/LIMIT/агрегации. TTL, stale cache или
быстрые ошибки не считаются выполнением SLO.

Оптимизировать также card count/page и оставшийся fact catalog aggregate.
Сначала использовать bounded correctness tests и реальные планы/профили;
после подтверждённого выигрыша измерить новый exact SHA на свежем dataset.
Полный протокол: 100k/500k/1m, concurrency 50/100/200, p95≤500 ms,
p99≤1000 ms, без ошибок, прежние SQL5s/pool30 и согласованные ресурсы.
Отдельно измерить HTTP/browser путь: repository map benchmark не включает
HTTP/session/provider latency и не является полной продуктовой сертификацией.

Разрешение на изолированные synthetic измерения сохраняется в согласованном
объёме. Не переносить результаты прежнего SHA на новый и не менять raw timings.

## 4. Настоящая модель в закрытом контуре

**Статус: offline реализация закрытого transport/evaluator; live НЕ проверен.**
1 ноября 2026 владелец явно разрешил пока только offline и отказал в живых
вызовах. Рабочий HTTPS transport, bounded policies, persistent budget journal,
строгие decisions и семантический evaluator подготовлены отдельно от приложения.
MockTransport adapter и default-disabled runtime сохранены. Предложены 24
синтетических запроса/эталона; они ещё не утверждены для live. Качество модели
и реальные расходы не измерены, пункт 4 не принят как выполненный.
[Контракт, набор, ограничения и воспроизведение](AI_INTENT_MODEL_LAB_RU.md).
[Offline результат и evidence](../../reports/AI_INTENT_MODEL_OFFLINE_20261101.md).

После отдельного разрешения на живые вызовы и политики исходящих данных создать
рабочий provider transport; offline MockTransport adapter сохранить для тестов.
Задать bounded timeout/retry/response/cost policies и отдельный тестовый ключ.

Первый сценарий — преобразование запроса в strict typed intent. Модель не
выбирает SQL, identity или quota и не придумывает подтверждённые свойства жилья.
Проверить неоднозначности, отрицания, периоды цен, pets/party, конфликтующие
ограничения, no-op и разные языки. Валидный JSON не доказывает правильный смысл.

Результат — измеренное качество понимания на утверждённом наборе запросов,
контролируемая стоимость и корректная обработка отказов.

## 5. Настоящий каталог и качество фактов

Отдельно от intent parser подготовить разрешённые источники и правила извлечения
фактов: provider-by-field coverage, происхождение evidence, противоречия,
обновления, retirement/remap/delete и повторная подготовка proof.

Если применяется LLM extraction, выполнять его при подготовке фактов, а не
отдельно для каждой карточки при поиске. До real-content ingestion нужны
разрешённый состав данных и minimization/retention policy.

Интерфейс различает отсутствие подходящих вариантов и недостаток проверенных
данных. Stored-source equality не доказывает недавнюю проверку источника.

## 6. Продуктовые и эксплуатационные правила

Определить допустимый outbound payload, хранение и реальное удаление данных,
источник freshness/health и поведение при недоступности источников, session/key
lifetime, leases/attempts/recovery и технические лимиты. Зафиксировать поведение
при уточнениях и неоднозначности без неявного выбора спорных business policies.

Проверить cleanup с зависимостями receipts/results/jobs и сохранением защиты
от повторного списания. Expiry доступа не означает физическое удаление.
Проверить реальную telemetry pipeline без приватного текста, credentials,
audio/transcripts и provider bodies.

## 7. Общая приёмка и выпуск

Провести реальные browser/HTTP guest/auth сценарии, отказы Redis/DB/model,
network timeout/disconnect/cancel и неопределённый finalize acknowledgement.
Добавить наблюдаемость latency/errors/queue/provider cost/coverage/freshness
без приватного текста. Проверить migrations, backup/restore, binary rollback,
быстрое отключение AI и сохранение обычного поиска.

Merge PR #403 сейчас запрещён. После отдельного решения владельца о merge
потребуются successful push/main checks точного main SHA. Public activation
отдельна от merge/deploy и требует выполнения performance, privacy, freshness,
coverage и runtime gates. Затем — закрытый pilot, наблюдение и управляемое
расширение доступа, с возможностью немедленно отключить AI.

## 8. Голос и сохранённые поиски/уведомления — отдельные этапы

Для голоса нужны реальная проверка audio container/header/codec/duration/truncated
media, согласованный ASR transport, microphone UI и audio privacy policy.
ASR+intent+search остаются одной durable operation с одним списанием.

Для AI saved searches нужны публичный save/UI, надёжный rematch worker,
fencing/retry/idempotency, повторная live проверка перед delivery, защита от дублей,
background quota и retention/delivery policy. Уведомления не включать автоматически.

Voice и delivery не являются условием первого текстового стенда. Их capability
остаётся false до отдельной реализации, проверки и разрешения на активацию.

## Как продолжать

Пункты 1–2 выполнены. Пункт 3 пропущен по поручению владельца; ISSUE-004 открыт.
Пункт 4 подготовлен offline, live зависит от отдельного тестового ключа и
согласованного запуска. До получения ключа можно независимо готовить пункт 5
на локальных fixtures: [порядок работы](AI_FACT_QUALITY_WORKPLAN_RU.md).
Это не разрешение на настоящий ingestion/crawling или отправку объявлений LLM.
Пункты 3–8 не объявлять готовыми
по одному работающему стенду. Если потребуется внешний доступ или настоящий
provider, сначала подготовить конкретную проверяемую конфигурацию и обозначить
недостающую авторизацию; независимую локальную работу продолжать.

## Обновление пункта 5 — 1 ноября 2026

Offline source × field инвентарь и golden проверки подготовлены отдельно от
intent; реальные объявления и внешние модели не использовались. Real coverage
и freshness остаются unknown; пункт 5 НЕ завершён. Подробности и предложенная
политика pilot: [отчёт](../../reports/AI_FACT_QUALITY_OFFLINE_20261101.md).

Продолжение пункта 5 без ключей: реализованы явные counters, SQL freshness guard
и физическая очистка AI evidence с проверками proof/rollback. Это закрытые
primitives, не активация production и не измерение real coverage.
[Контракт](AI_FACT_QUALITY_POLICY_RU.md), [результат](../../reports/AI_FACT_QUALITY_NEXT_20261101.md).
