# Исправления замечаний post-merge аудита

## Функциональная приёмка текстового стенда, 31 октября

Пункт 2 выполнен: source `70330a138cdb1a8313fc0ed61bc69b7ecbfc4985`,
29 реальных UI/API/DB сценариев PASS, 50 прежних browser regressions PASS.
Добавлены owned reload recovery без сохранения текста, безопасная презентация
invalidated results, исправление overflow 320 px и local acceptance CLI/fixtures.
[Матрица и доказательства](AI_TEXT_ACCEPTANCE_20261031.md).
По просьбе пользователя стенд остановлен перед выключением ноутбука, volumes
сохранены. ISSUE-004 OPEN / capacity BLOCKED, пункты 3–8 не приняты.
Следующий раздел описывает исторический итог пункта 1 и его source.

## Закрытый текстовый стенд, 31 октября

Пункт 1 AI-контура выполнен на отдельном local-loopback synthetic стенде:
source `3693f897e79cbe2e426b8ea3e5c04b4310acdc0b`, https://localhost:9443.
Реальные UI/API/PostGIS/Redis, явная test-only сборка, FactPipeline → projections
→ QueryProofs.prepare, детерминированный parser вместо LLM. Сквозной Chromium
smoke: 13 PASS; isolation/Redis failure/recovery, 5 unit guards, 50 прежних
browser contracts и stop/start PASS. Production default остаётся disabled.
[Отчёт и ограничения](AI_TEXT_LAB_20261031.md),
[инструкция](../docs/ai-search-developer/AI_TEXT_LAB_RU.md).
Стенд оставлен запущенным; старые audit/capacity containers не запускались.
ISSUE-004 OPEN / capacity BLOCKED без новых измерений; пункты 2–8 не приняты.
PR #403 остаётся draft, merge/public AI/providers/deploy не выполнялись.

## Актуальный результат продолжения, 31 октября

Runtime `06af013856798f4eb93572433b522796edc69fdc`, тот же draft PR #403.
Добавлены transaction-local JIT off, один проход карты вместо probe+aggregate
и O(1) epoch/revision для cursor prepared-proof population (миграция `0075_ai_proof_population`).
Полный live `query-proof.v2` digest сохранён до count/order/LIMIT;
новый counter не заменяет актуальность источников/canonical/room/facts.

**ISSUE-004 остаётся OPEN.** Новый fresh experiment
`74074e06e9d748909889d1567a541f2c`: **protocol COMPLETE / SLO FAIL**.

| Listings | Сценариев | Попыток | Ошибок | SLO-pass |
|---:|---:|---:|---:|---:|
|100000|18|3600|2400|0|
|500000|18|2600|1400|0|
|1000000|18|2600|1400|0|

Все seed/baseline/plans/stability/resources attestations подтверждены;
245 resource samples, ошибок и пробелов 0, warnings `[]`. На каждом масштабе
20/20 запросов отменены, активных SQL 0, pool reuse PASS. Acceptance exit 1.
Offline replay из опубликованного архива перепроверил hashes каждого файла,
измеряемых исходников и все RAW: COMPLETE / SLO FAIL / BLOCKED.

Viewport 300 во всех 18 соответствующих нагрузочных сценариях без ошибок,
но p95 превышает 500 ms. На 1m, zoom 13, first-touch 300/302 — 275.5/265.6 ms;
при concurrency 100 p95 ≈ 5.5 s, при 200 ≈ 11 s. Viewport 10k/all даёт SQL/pool timeout.
Это разные виды измерений; одиночные samples не являются p95/p99.
Actual plans подтверждают один map SQL, отсутствие JIT и 302 proof PK lookups
для 302 кандидатов. Полный live digest всё ещё читает 6040 fact rows.

Отдельный read-only профиль 1m, concurrency 1, SHARE freeze, SQL 5 s, JIT off:

| Cursor expression | Три длительности, ms | EXPLAIN execution, ms |
|---|---|---:|
|Прежний prepared-set aggregate|3092.284 / 2114.648 / 1997.297|1865.047|
|Новый epoch/revision|3.707 / 1.443 / 1.385|0.020|
|Оставшийся fact catalog aggregate|91.251 / 41.581 / 46.711|59.044|

Samples включают transaction config и получение соединения. Freeze использует
отдельное второе соединение; одновременно исполняется один diagnostic query.
Это не full-card/HTTP capacity certification. Первый диагностический helper
ошибочно использовал pool 1 одновременно для freeze и query; остановлен,
лог сохранён, повтор выполнен с двумя соединениями. Capacity pool 30 не менялся.
Первый start measure 100k остановлен NOWAIT из-за maintenance до map SQL;
после ожидания выполнен новый run ID, failed manifest и monitoring сохранены.

Локально: 1571 unit passed/31 skipped; 379 fact/proof/toolchain/acceptance
passed/28 Windows-only skipped; 57 cards/map/saved integration; 31 migration/map
PG contracts; отдельно 36 Windows launcher/monitor checks. Ruff/mypy PASS.
Пересекающиеся suites не складываются. Все 11 исполнявшихся runtime CI workflows
PASS, два условных visual skipped. Production audit: 1599 unit/3 skipped,
953 PostgreSQL/PostGIS/6 skipped, 1 MinIO passed.

[Новый полный отчёт](AI_MAP_CAPACITY_PERFORMANCE_20261031.md),
[RAW/JUnit/source archive и hashes](post-merge-remediation-evidence/performance-capacity-evidence.json),
[offline replay](post-merge-remediation-evidence/performance-capacity-replay.json),
[runtime CI](post-merge-remediation-evidence/ci-performance-runtime.json).
Архив SHA256: `4c2e898a97b1640fef5ca77e13c60df19c8d14393ab220ed79d1d60a8fbea64b`.
Git archive с Windows EOL attributes воспроизведён по тому же SHA и совпал
с исходным archive hash; evidence сохраняет исполненные archive bytes.

DB остановлена. Merge/public AI/providers/ASR/payments/notifications/Pages/deploy
не выполнялись. Следующий performance этап требует уменьшения работы live
проверки и широких агрегатов с полным контрактом инвалидации; быстрые отказы
и TTL не заменяют SLO. Остальная часть ниже — исторические результаты прежних SHA.

Дата: 30 октября 2026, Europe/Moscow. Проверенный код: `6548a2aeccb65d1bdec13d40cf9d0e43bd22b13c`,
ветка `codex/post-merge-remediation`. База аудита: `7d4c125574927181511c5f1bc7e201e20a8840a8`.
PR: [#403](https://github.com/antony502189-max/Ttest/pull/403).

Обновление 31 октября: после полного baseline добавлены SQL-оптимизации в
`2dc411f4773f73ec1c200abeb5ee3dde3e5b25e2`; последующий
`e5b7f0981d9642b78a264c7c456a5f5c2b90b66e` исправляет только историческую
формулировку генератора отчёта. Полный capacity ниже относится к `6548a2ae`,
а не к новому SQL. ISSUE-004 остаётся открыт.

Исходный [аудит](MAIN_POST_MERGE_INTEGRATION_AUDIT.md) сохранён как историческая
запись. Его FAIL относится к старому main. Исправления кода проверены в PR;
новый capacity result: **protocol COMPLETE / SLO FAIL**. Зелёный CI не заменяет SLO.

| Замечание | Результат |
|---|---|
| ISSUE-001, P1 | Общий test-only full-stack launcher применяет geocoder harness и при старте, и при seed в обоих PR/main runners. Production address validation сохранена. PR Full audit PASS. |
| ISSUE-002, P2 | Синхронная route authority и сверка с фактическим hash URL защищают Search this area, List/Filters, browser Back и fallback Back. Суперседированный pending camera сбрасывается. Обе новые Back reproduction сначала FAIL, после исправления PASS. |
| ISSUE-003, P2 | AI workflows слушают каждый main push. Manual release требует последние successful push/main checks точного SHA по workflow path. Stale/missing/running/failed/skipped варианты отклоняются. Первые реальные exact-main push checks возможны после merge. |
| ISSUE-004, P2 | **Открыт performance blocker:** новый протокол выполнен, но capacity SLO не пройден. |
| ISSUE-005, P3 | Optional Pages configure/upload/deploy требуют PAGES_PREVIEW_ENABLED=true; обязательный build сохранён. При opt-in ошибки не подавляются. Pages site не включался. |

Актуальные architecture/database/index/troubleshooting ссылки обновлены до
`0074_ai_saved_searches`; датированные snapshots обозначены как исторические.

## Проверки итогового кода

Все 11 исполнявшихся CI workflows на указанном SHA успешны; два условных visual
workflow пропущены по существующим условиям. Полный список:
[CI evidence](post-merge-remediation-evidence/ci-final-code.json).

| Проверка | Результат |
|---|---|
| Production CI unit suite | 1593 passed, 3 opt-in skipped |
| Production CI PostgreSQL/PostGIS suite | 938 passed, 6 conditional skipped |
| Production CI MinIO suite | 1 passed |
| Dedicated facts CI: real HTTP frontend/cookie recovery | PASS; четыре recovery cases и actual browser guest/cross-site step исполнены |
| Финальные toolchain/PG contracts в Linux | 168 passed, 28 Windows-only skipped |
| Windows launcher/monitor contracts | 28 passed отдельно |
| Forced idle + recall, repeat3 | 18 passed |
| Map/navigation/Maps/freehand/APK suite | 67 passed |
| Frontend lint/typecheck/build; backend Ruff/mypy (153 files); supply-chain/migration governance | PASS |

Шесть Production PG skips — browser/recovery/optional ASGI bridge cases; реальные
cookie/recovery steps отдельно обязательны и успешны в dedicated facts workflow.
Пересекающиеся suites не складываются в число уникальных tests. Ранние проверки
основного исправления также сохранены: AI browser — 50, search lifecycle — 62,
actual full-stack — 23 passed / 7 conditional skipped; frontend production Docker build
и bundle/security checks успешны. Детали:
[матрица](post-merge-remediation-evidence/test-results.json).

## Авторизованная изолированная нагрузка

Experiment `aa2f9d3367a44c42acde8ce8b29ee220`, точный source SHA выше. DB PostgreSQL 16 /
PostGIS 3.4 из pinned image; private internal network без host DB ports.
DB: 8 CPU / 8 GiB, driver: 2 CPU / 2 GiB, pool: 30; 10 synthetic providers,
2 source records и 20 observations/listing. 200 requested attempts/case;
полностью неуспешная первая волна на 500k/1m — предусмотренная протоколом остановка.

| Объявлений | Сценариев | Попыток | Ошибок | SLO-pass сценариев | DB GiB |
|---:|---:|---:|---:|---:|---:|
| 100,000 | 18 | 3,600 | 2,504 | 0 | 2.16 |
| 500,000 | 18 | 2,600 | 1,684 | 0 | 10.58 |
| 1,000,000 | 18 | 2,600 | 1,697 | 0 | 20.87 |

Критерии: p95 ≤ 500 ms, p99 ≤ 1000 ms, без ошибок. SQL timeout 5 s и pool timeout 30 s
сохранены. Длительности ошибок не объявляются latency успешного SQL.
Seed, baseline/actual-or-estimated plans, immutable provenance, dataset SHARE
freeze, resource coverage и cancellation/pool reuse аттестованы на всех масштабах.
Сырые данные пересчитаны действующим summarizer; предупреждения: `[]`.
Acceptance gate возвращает 1.

Подробные результаты: [capacity report](AI_MAP_CAPACITY_REMEDIATION.md).
Разрешение владельца, ресурсы и ограничения: [план](../docs/post-merge-remediation.md).

## Card cursor aggregates на 1m

Отдельный bounded read-only sequential profile после map-нагрузки: три повторения
реальных aggregate expressions из `_query_intent`, затем actual EXPLAIN ANALYZE.
Это диагностика при concurrency 1, не full-card/HTTP capacity certification.

| Aggregate | Три длительности, ms | EXPLAIN execution, ms |
|---|---|---:|
| `fact_catalog_revision` | 300.0, 52.1, 51.3 | 73.209 |
| `proof_population_signature` | 5856.4, 2587.4, 2550.7 | 2774.958 |

## Доказательства и границы

### Последующая оптимизация proof SQL, 31 октября

В v2 digest сохранены все входы, границы, нормализация timestamps и исключение
bookkeeping-полей. Полная canonical row теперь сериализуется в JSON один раз
вместо восьми; отдельный SQL boundary сохраняет точечный PK lookup proof и
однократное вычисление digest вместо hash join с повторной проверкой.
Ни один guard не перенесён после count/order/LIMIT; миграций или TTL нет.

Локальные проверки: **235 fact/proof tests**, включая 47 точечных proof cases;
**57** реальных интеграционных tests карточек/карты/saved searches;
**1565 unit passed, 31 skipped** (28 Windows-only + 3 opt-in); **10** capacity
acceptance/safety tests; Ruff и mypy PASS. Ранняя попытка интеграционных tests
не прошла setup при выключенном тестовом Redis; после старта собственного
изолированного Redis все 57 tests прошли. Это не дефект приложения.

Production audit на новом runtime SHA `2dc411f4` также PASS:
**1593 unit passed / 3 skipped**, **946 PostgreSQL/PostGIS passed / 6 skipped**,
**1 MinIO passed**. Это новые CI результаты; верхняя таблица с 938 PG tests
сохраняет исторический результат исходного measured SHA `6548a2ae`.
Все 11 исполнявшихся workflows нового runtime SHA успешны; два условных visual
workflow пропущены: [CI evidence](post-merge-remediation-evidence/ci-proof-optimization.json).

Отдельная диагностика использовала ранее созданную synthetic lab 1m, неизменяемые
source archives `6548a2ae` и `e5b7f098`, concurrency 1, два повторения, viewport
не более 302 кандидатов. DB 8 CPU/8 GiB, driver 2 CPU/2 GiB; только read-only
запросы под SHARE freeze. Исходные capacity artifacts смонтированы read-only.
Это **не повторный capacity protocol** и не доказательство p95/p99.

| Viewport / zoom | Два запроса до, ms | Два запроса после, ms |
|---|---|---|
| 0 / 8 | 93.7 / 23.6 | 104.3 / 24.7 |
| 300 / 13 | 3299.0 / 2544.2 | 446.1 / 361.5 |
| 302 / 13 | 4911.5 / 4974.3 | 2063.9 / 2076.2 |

Actual EXPLAIN для 300: **2587.008 → 349.226 ms**; вместо Seq Scan **1,000,001**
proof rows — 300 PK lookups по одной строке. Все IDs, membership, цены, counts,
promotion/source fields совпали. Маркеры совпали точно; максимальное отличие
координат кластеров от порядка floating-point AVG — **7.11e-15 градуса**.

Оставшиеся задержки подтверждены: в cluster statement на 302 кандидата JIT
занял **1416.251 ms из 1698.023 ms**; на zoom≥13 остаются probe и отдельная
агрегация. Полный cursor aggregate на всём каталоге также не изменён.
Новый SQL не проходил весь 100k/500k/1m concurrency protocol, SLO PASS не заявлен.

[Сырые запросы, actual plans, ответы и JUnit](post-merge-remediation-evidence/proof-optimization-diagnostic.tar.gz),
[hashes и сравнение](post-merge-remediation-evidence/proof-optimization-evidence.json).
SHA256 архива: `ee7e7666c18d320a295ab27aea0ddc736fcb1c8c0e071fb85525b382bcd9f93f`.
Полный исходный baseline ниже остаётся историческим доказательством SLO FAIL.

Текущий raw archive:
[capacity-aa2f9d33.tar.gz](post-merge-remediation-evidence/capacity-aa2f9d33.tar.gz)
SHA256 `21ce1bdbf200b24e4ac40bd6ac415bfb57b687be1fb5e7dd843e77160c3d8b3b`.
[Индекс и hashes каждого файла](post-merge-remediation-evidence/capacity-evidence-index.json)
включает также прежний неполный эксперимент, clock-rejected запуск и ранние
прерванные initialize/seed. Их данные не перенесены в новый experiment и не
засчитаны как успешные. Конкретные исправления instrumentation, в том числе
AUTOCOMMIT initialization guard, отдельные maintenance/preflight deadlines и
UTC-anchored monotonic clocks, описаны в remediation plan. Strict consistency
и SLO checks не ослаблялись. В обвязке исправлены readiness TCP и сравнение
DateTimeOffset; артефакты измерений при этом не переписывались.
Первый start measure 1m отклонён NOWAIT guard из-за autovacuum до timed SQL;
после завершения обслуживания повторена только measure-фаза с новым run ID.
Неуспешный manifest сохранён. Повторный пересчёт из распакованного архива
подтвердил COMPLETE / SLO FAIL, 54 сценария и BLOCKED acceptance.

Локальные raw logs/JUnit: `output/post-merge-remediation/` этого managed worktree.
DB остановлены; production/shared application DB не использовались. Public AI,
ASR/providers, уведомления, Pages и production deploy не активировались. Ветка
не merged. До merge требуется review; после merge обязательны новые green
exact-main push checks. Public AI остаётся заблокированным capacity и отдельными
privacy/freshness/retention/provider gates. Future coverage из раздела 9 исходного
аудита не выдаётся за исполненную public-production сертификацию.
