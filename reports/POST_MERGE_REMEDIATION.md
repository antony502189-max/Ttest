# Исправления замечаний post-merge аудита

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
