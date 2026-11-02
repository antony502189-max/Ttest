# Пункт 3: транзакционная актуальность proof и общие профили matching

Runtime/backend: `a38a4f3d9078f285e1403e022c150ca602cad090`.
Точный source нового capacity experiment, включая single-writer fixture driver:
`ea333e156d74bc441f66d27a9314fdaad59bc5d5`.
Ветка `codex/post-merge-remediation`, draft PR #403, без merge/activation.

ISSUE-004 OPEN / capacity BLOCKED до полной приёмки. Результаты функциональных
тестов и малых планов не закрывают SLO или HTTP/browser acceptance.

## Реализовано

Миграция 0077 записывает случайные версии исходных listing/external/batch
identities в транзакции изменения canonical/room, sources, facts, batches,
catalog и projection. Прямой SQL, COPY, upsert, remap/delete и TRUNCATE
охвачены statement triggers. Представление JSON сравнивается текстом, включая
различие 1 и 1.0; views/updated_at canonical исключены как в исходном v2.

Миграция 0078 связывает подготовленный proof с точными version tokens через
FK ON UPDATE/DELETE CASCADE. Изменение токена атомарно переводит proof в changed,
утрата зависимости — в missing. FK-синхронизация защищает от писателя со старым
REPEATABLE READ snapshot и появления/переноса связи одновременно с prepare.
Подготовка сохраняет исходный полный query-proof.v2 и canonical equality,
блокирует version parents FOR KEY SHARE и CAS-проверяет актуальные входы.

Чтение current proof проверяет typed contract/epoch/schema и использует общий
неизменяемый профиль matching. Оно не читает facts/versions/dependencies для
каждого кандидата. Changed proof требует исходного live v2 digest и текущего
matching: точное восстановление исходных данных сохраняет прежнюю семантику.
Missing/bad readiness исключаются. Legacy proofs читаются исходным v2 путём.
Целостность vector/binding и соответствие cohort реальной projection
проверяются ALWAYS write guard. Schema readiness включает enabled state и
определения функций/триггеров/ключей; повреждённая инфраструктура не разрешает
новый быстрый путь. Guard и RI triggers работают и при replica role.

Matching выполняется один раз на профиль среди профилей текущих кандидатов.
Нормализация убирает только supporting_fact_ids, сохраняет дубли/порядок и
все условия typed matching. Strict JSONPath отбирает нужный key до старых
проверок типов, scope, uniqueness, numeric/period/currency/approval; malformed
и вложенные массивы не получают разрешение из-за lax unwrapping.

Public visibility, moderation, blocked owners, текущая экономика, bounds и
зависящие от времени TOP/freshness остаются живыми до count/LIMIT/aggregate.
Single-pass-jit.v1, SQL5s, lock1s, pool30 и нагрузка 50/100/200 сохранены.
Result cache, TTL, singleflight и spatial summaries этим изменением не добавлены.

Отдельная offline CPU-диагностика (без БД и вне capacity runner) обнаружила
заметную стоимость повторной сборки SQL graph, особенно legacy v2 expression.
Экспериментальное переиспользование этого выражения уменьшило profiled CPU
на сборку примерно с 41 до 25–27 ms. Это overhead под cProfile, не latency
запроса и не benchmark production. Изменение осталось только в диагностическом
процессе; exact runtime/driver capacity experiment не менялись.

## Проверки

- 1566 unit PASS, 39 optional/platform SKIP; 315 PG facts/proofs PASS.
- 68 integration PASS, 1 optional SKIP; 5 disabled-runtime guard PASS.
- mypy 155 файлов, ruff, migration compatibility PASS.
- Полный исторический migration chain до 0078 и combined schema PASS.
- Все 11 обязательных CI exact ea333e15 успешны; 2 неприменимых workflow SKIP.
- Git archive проверен против blob identities; 427 backend Python files.
- Bounded plans: current путь без per-candidate facts/version/dependency scans;
  узкий запрос не сканирует 4096 посторонних cohort; legacy v2 сохраняет
  индексируемые identity probes. Это структурные тесты, не capacity acceptance.

## Промежуточные эксперименты

Изолированный 1000-object prototype a38, experiment
`e4c85f5fcb82458595f425d74f368cb1`: все 24 baseline-case вернули правильные
counts; полный viewport first-touch примерно 39.5–49.3 ms. Это не нагрузочная
сертификация, не OS-cold и не валидное сравнение p95/p99.
Попытка наполнить 100k с восемью writers остановилась до измерений на счётчике
population identity. Все chunk-транзакции откатились; dataset остался 1000,
служебный listings trigger восстановлен, стенд остановлен. Raw failure сохранён.
Исправлен только setup parallelism; новый exact source и новый experiment,
старые manifests/timings/DB не переиспользуются для приёмки.

Новый experiment: `3056bd59405546c984354b07f2382a1f`, isolated internal network,
без host ports, synthetic-only. DB 8 CPU/8 GiB, driver 2 CPU/2 GiB.

## Результат 100k: SLO FAIL

Измерение exact `ea333e15` завершено 31 октября 2026, 20:31 UTC. В dataset
100000 объектов, 200000 source records, 2000000 фактов; вне viewport ещё один
верифицированный template. Все 100001 proof аттестованы как current.
Seed, 28 baseline/plan-case, 18 load-case по 200 попыток, freeze/stability,
provenance и resource coverage прошли проверки протокола для этого масштаба.

| Viewport | Попытки | Ошибки | SLO-pass | p95 результата/ошибки при 50 / 100 / 200, s |
|---|---:|---:|---:|---|
| 300 | 1200 | 0 | 0/6 | 2.21–2.38 / 3.29–4.03 / 7.22–7.68 |
| 10000 | 1200 | 0 | 0/6 | 2.23–2.33 / 4.23–4.29 / 8.62–9.13 |
| 100000 | 1200 | 1161 | 0/6 | 11.16–11.18 / 19.74–20.42 / 32.51–32.68 |

Итого **1161 ошибок / 3600 попыток, 0/18 SLO-pass**. Длительности ошибок
не являются percentiles успешного SQL. SQL5s, pool30 и SLO не менялись.
Все успешные baseline и load ответы имеют ожидаемые counts. Отмена:
20/20 реально активных SQL отменены за 109.3 ms, оставшихся активных 0,
пул повторно работает. 190 resource samples, 0 ошибок/пропусков мониторинга.

500k/1m отложены до следующей оптимизации после провала уже на 100k.
Общий трёхмасштабный протокол **INCOMPLETE**, ISSUE-004 OPEN / capacity BLOCKED.
Это не полная HTTP/browser performance certification. У baseline один общий
нормализованный профиль свойств; разнородность реального каталога не измерена.

[Полный автоматически проверенный отчёт](ai-live-inputs-evidence/capacity-100000/REPORT_RU.md),
[summary](ai-live-inputs-evidence/capacity-100000/summary.json),
[исходные попытки](ai-live-inputs-evidence/capacity-100000/load-100000.json),
[baseline и SQL](ai-live-inputs-evidence/capacity-100000/baseline-100000.json).

Широкий SQL-план сохраняет 100000 индексных обращений к wide proof table и
дублирует набор при отборе cohort. В одном EXPLAIN execution 1673.6 ms,
planning 13.9 ms; ненужные ветви legacy digest при current proof не выполняются.
После завершения основного прогона отдельная read-only диагностика с
`enable_nestloop=off` дала execution 778.5 ms. Это исследование planner, не
production setting и не SLO acceptance. Оно показало, что нужно устранить
повторный обход и сделать чтение metadata дешевле. Покрывающий индекс после
подготовки занимает 19817 страниц; сама wide proof table — 42858 страниц.
[Диагностический план и инвентаризация](ai-live-inputs-evidence/post-run-plan-diagnostic.json).

Новый capacity DB остановлен после сохранения evidence, без удаления raw
данных: [состояние](ai-live-inputs-evidence/capacity-stopped-state.log).
Дальнейшие результаты другого source требуют новой аттестации/свежего набора.

## Ограничения эксплуатации

Миграции пока применяются только к disposable DB. Установка ENABLE ALWAYS
для native RI triggers требует достаточно привилегированной migration role.
Добавлены locks/write amplification и зависимости; production write throughput
и rollout не сертифицированы. Глобальные population counters сериализуют
изменяющие statements, что проявилось на synthetic bulk setup.
Downgrade/older binary fallback сохраняет v2; public activation отдельно запрещена.

Локальные test logs/XML, планы, source attestation и CI snapshots находятся в
[evidence](ai-live-inputs-evidence/). Backend runtime a38 и capacity source
ea333 имеют 461 одинаковый backend-файл; все 427 Python files фактически
извлечённого test snapshot совпали с Git blobs. Новые CI включают реальные
Chromium/HTTP cookie/ownership/lost-ack сценарии, но прежние 29 ручных lab
сценариев не объявляются повторно выполненными на новом source.
Исходный dirty checkout не менялся; PR остаётся draft, merge запрещён.
Ноутбук не выключается: прежний запрос явно отменён пользователем.
