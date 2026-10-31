# Пункт 3: устранено сканирование каталога фактов для курсоров

31 октября 2026, Europe/Moscow. Source:
`53cf3171e0f8e7ae5be6bbdbe77c34f240dca856`.
Ветка `codex/post-merge-remediation`, существующий draft PR #403, без merge.

**Результат: отдельная оптимизация готова; весь пункт 3 ещё в работе.
ISSUE-004 OPEN / capacity BLOCKED.**

## Изменение и границы

Каждое чтение AI-карточек больше не вычисляет `count(*) / sum(revision)` по
всему `ai_fact_catalogs`. Миграция `0076_ai_fact_population` устанавливает
транзакционную `epoch/revision` и statement triggers. Чтение подписи курсора
теперь обращается к одной служебной строке.

Триггеры охватывают direct/bulk SQL, COPY, upsert, изменение PK/revision,
DELETE и TRUNCATE. Нет обновления singleton при пустой операции или
идентичных данных. Смена данных с прежними count/sum и восстановление
старых значений консервативно инвалидируют курсор. Rollback/savepoint и
REPEATABLE READ snapshot согласованы с данными; CAS без совпадений не меняет
версию. При исчезновении singleton чтение карточек прекращается с ошибкой;
восстановление состояния получает новый random epoch.

Полный live `query-proof.v2`, экономические guards и public eligibility
сохранены перед count/order/seek/LIMIT и агрегацией карты. Главная стоимость
пересчёта digest на каждом кандидате остаётся. Дополнительная запись singleton
может сериализовать импорт: высокая write throughput пока не измерялась.
Новый счётчик нельзя использовать как доказательство live eligibility.

Прежние курсоры после обновления требуют чтения с первой страницы;
обновление committed result не вызывает новую модель и не списывает quota.
Schema additive; older binaries могут читать прежний каталог. Миграция
проверена на непустом synthetic каталоге и в полном историческом chain.

[Контракт, воспроизведение и следующий прототип](../docs/ai-search-developer/AI_FACT_POPULATION_RU.md).

## Реальная ограниченная диагностика

PostgreSQL/PostGIS 16-3.4, отдельная disposable DB, 4096 synthetic catalog rows.
Ниже один настоящий `EXPLAIN ANALYZE`, не percentile и не acceptance latency:

| Запрос | Строк каталога прочитано | Строк служебной таблицы | Shared hit blocks | Execution, ms |
|---|---:|---:|---:|---:|
| Прежний count/sum | 4096 | 0 | 27 | 0.481 |
| Новая identity | 0 | 1 | 1 | 0.018 |

Проверка утверждает структуру плана и число строк, без timing threshold.
[Полные неизменённые планы и timings](ai-fact-population-evidence/bounded-plans.json).
Это не full-card/HTTP/map benchmark, не нагрузочный прогон и не доказательство
SLO на больших каталогах. Исторические raw capacity artifacts не менялись.

## Проверки exact source

Проверялся извлечённый Linux Git archive, созданный с
`core.autocrlf=false`; backend взят из `/frozen/backend`, не из базового image.
Все обычные файлы archive сверены с Git blobs. Все 424 backend Python files,
включая tests/migrations/lab, совпали с проверяемым snapshot.
[Source attestation](ai-fact-population-evidence/source-attestation.json),
[проверка извлечённых файлов](ai-fact-population-evidence/deployed-source.log).

| Проверка | Результат |
|---|---|
| Backend unit | 1563 PASS, 39 platform/optional SKIP |
| PostgreSQL facts/proofs/population/combined-schema | 247 PASS |
| Existing cards/map/HTTP/saved searches/review/gallery | 68 PASS, 1 optional SKIP |
| Explicit synthetic composition guards | 5 PASS |
| Ruff app/tests/lab + новая migration | PASS |
| mypy | PASS, 155 app source files |
| Исторический migration chain до 0076, alembic check | PASS, schema drift отсутствует |
| pip check | PASS |

В новые проверки входят same-count/sum изменение/восстановление и отказ чтения
при отсутствии state без списания quota. Существующие проверки сохраняют
live source/moderation/price/owner/room и time-based eligibility, пагинацию,
immutable results и идемпотентные HTTP execution paths.

JUnit: [unit](ai-fact-population-evidence/unit-final.xml),
[facts](ai-fact-population-evidence/facts-final.xml),
[integration](ai-fact-population-evidence/integration-final.xml).
Логи расположены в той же evidence-директории. Наборы имеют пересечения;
числа не суммируются в уникальные тесты. 29 browser-сценариев предыдущего
этапа относятся к прежнему source `70330a13`, их результат на новый SHA
автоматически не переносится. UI этим изменением не редактировался.

CI exact source: **11/11 исполнявшихся workflows PASS**, два conditional
visual workflows SKIP. Включены production/full/payment/security audits,
frontend/mobile, quota/sessions, facts, foundation и capacity safeguards.
`AI Search combined facts quota sessions` проверил полный migration chain
и настоящие Chromium/HTTP cookie, ownership и lost-ack recovery сценарии.
[Все workflows](ai-fact-population-evidence/ci-runtime.json),
[шаги facts/browser job](ai-fact-population-evidence/ci-facts-jobs.json).
Evidence-only commit после этого source добавляет документы и результаты;
его собственные новые CI runs не смешиваются с принятой ревизией.

## Изоляция и состояние

Только собственные `ttest-ai-fact-population-pg` и
`ttest-ai-fact-population-runner`, label `es.ttest.purpose=ai-fact-population-v1`.
Отдельная internal network, нет published ports/default route; runner делит
network namespace только со своей disposable DB. Для каждого контейнера
2 CPU / 2 GiB; PG data — ограниченный tmpfs 1 GiB. Использованы свежие
test schemas и synthetic data; application/production DB и прежние
capacity/audit DB не запускались и не использовались.
[Топология](ai-fact-population-evidence/topology.json).

Проверки завершены; новые диагностические контейнеры остановлены после
сохранения evidence: [состояние](ai-fact-population-evidence/stopped-state.log).
Временная DB не предназначена для повторной certification.
Исходный dirty checkout не изменялся. PR остаётся draft, public AI/providers/
ASR/payments/notifications/Pages/deploy не включались; новых больших нагрузок
не запускалось. Запрос на выключение ноутбука отменён пользователем;
новая команда выключения не запускается.
