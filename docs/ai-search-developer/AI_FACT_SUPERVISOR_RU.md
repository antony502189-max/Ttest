# S2.2 — synthetic supervisor harness

`backend/lab/ai_fact_supervisor.py` — явно вызываемый finite harness над existing `OfflineFactCoordinator`. Он не подключён к приложению, startup, importer, provider, cron или production supervisor. `run_once()` делает один poll, `run_steps(steps=1..100)` — ограниченную последовательность polls без ожиданий. Внешний процесс отвечает за периодический запуск и остановку.

## Разрешённая среда и конфигурация

Конфигурация требует loopback PostgreSQL URL с БД `ai_facts_test_*`; другие адреса/имена, включая текущую application/lab БД, отвергаются до запуска. SQLite journal должен иметь отдельное имя `DISPOSABLE-fact-supervisor-<name>.sqlite3`. Обычные budget journals, symlink-файл и существующий SQLite с чужими таблицами/application ID не принимаются. Harness не читает и не сбрасывает настоящий provider budget.

`configuration_digest()` связывает source mappings/TTL/job limits/versions/retry policy, vocabulary, resolver, queue/quality policy, payload/page bounds, loopback catalog destination и два обязательных SHA-256: reviewed synthetic builder bundle и уникальная catalog/schema identity. Эти два digest задаёт caller, они не являются самостоятельной аттестацией source privacy или identity БД. Изменение конфигурации требует нового disposable journal, а не сброса старого checkpoint. Worker configuration сверяется с объявленной source policy. Binding проверяется перед каждым poll и health read.

`SupervisorPolicy` требует interval, cooperative deadline, lease, initial/capped backoff, stale threshold, maximum retained receipts и bounded health sample. Lease должен быть длиннее deadline. Нет production defaults.

## Durable protocol

SQLite FULL-synchronous короткие транзакции никогда не охватывают работу coordinator. Claim атомарно выдаёт случайный owner и возрастающий fence. Только действующий owner, revision, fence и непросроченный lease могут записать результат. `complete()` одной транзакцией сохраняет весь receipt (включая `content_refresh_due`) и следующий cursor/revision/last-success/next-at. SQL/файловый сбой откатывает обе записи. Устаревший owner не может завершить или записать failure поверх нового владельца.

После падения до checkpoint commit следующий владелец повторяет прежний cursor после истечения lease. Уже завершённые факты/queue jobs/proofs не откатываются: existing CAS/fencing/idempotency coordinator предотвращают повторную публикацию. При потере ACK после checkpoint commit повторное открытие читает подтверждённый cursor; failure старого claim не стирает успех. Cancellation не подтверждает успех, оставляет lease для restart.

Failure сохраняет только `TICK_FAILED` или `TICK_DEADLINE`, число последовательных failures и capped exponential backoff; checkpoint и last-success остаются прежними. Внешние исключения redacted. После успеха failure streak сбрасывается. Wall-clock journal timestamps нужны для restart; monotonic time проверяет продолжительность отдельного tick. Async timeout отменяет cooperative работу, а проверка длительности после возврата не позволяет признать своевременным успехом синхронный overrun.

**Ограничение:** asyncio не способен принудительно остановить зависший синхронный builder. Harness не устанавливает hard process deadline, не управляет постоянным OS supervisor и не доказывает production restart/termination. Для этого остаётся отдельный process-isolated rehearsal перед эксплуатацией; потоки/таймауты не заменяют его.

Journal удерживает receipts до явного внешнего решения. При достижении `max_receipts` новые claims запрещены, checkpoint не продвигается, refresh IDs не теряются. Автоматического удаления/ack/pruning или выполнения refresh здесь нет. Explicit consumer может вызвать `acknowledge(revision, expected_digest=receipt_digest)` после обработки конкретного receipt. Ack атомарен, durable и idempotent; повтор старого ack не касается новых revisions, не удаляет evidence и не освобождает retention capacity. Старые disposable journals получают bounded one-time backfill сигналов без сброса checkpoint. Это ограниченный rehearsal, не готовый delivery/outbox consumer.

## Health

Health содержит только aggregate counts, без source IDs, URLs, текста и SQL details: last checkpoint revision, stale/clock-regression, failure streak, sampled terminal/pending/retry jobs, expired leases, truncation, незакрытые rejected/deferred/refresh occurrences по всем receipts, pending receipt count и receipt capacity. Pending totals обновляются атомарно вместе с receipt/checkpoint и уменьшаются только явным exact-receipt ack; health не сканирует историю JSON. Дополнительно проверяется bounded current source sample: общий с SQL eligibility chronology predicate сообщает `source_check_errors`, а `content_refresh_needed` показывает текущий refresh TTL. Ошибки probe не скрываются за parse/proof success; положительный presence очищает check error без обновления content age. Любой из этих незавершённых/ошибочных сигналов требует attention. Успешный supervisor tick не скрывает terminal job. Empty/no-claim не объявляется глобальной пустотой очереди. При превышении health sample пометка `sample_truncated=true` запрещает назвать результат здоровым; это не точный глобальный census. Failure health storage также redacted, а не green.

## Воспроизведение

Existing release runtime, `PYTHONPATH=backend`, disposable `AI_FACTS_TEST_DATABASE_URL`:

```text
python -m pytest -q backend/lab/test_synthetic_fact_supervisor.py
python -m pytest -q backend/tests/ai_facts_pg/test_fact_supervision.py
```

Unit suite создаёт только собственные SQLite в pytest temp directory; отдельный child process завершает claim через `os._exit`, проверяя durable recovery. PG suite использует existing unique-schema fixtures, actual queue/worker/proofs и отдельный journal в pytest temp directory. Existing combined CI запускает PG suite через весь `backend/tests/ai_facts_pg`, unit suite добавлена в explicit lab step и executable acceptance inventory.

S2.2 продвинут локально. S2.1 real measurements, разрешённый source-specific detail importer, постоянная supervised refresh chain, process lifecycle, migrations/backup/erasure и production gates остаются открытыми. Голос, saved searches и notification delivery сохраняются в обязательном продуктовом scope.

Backend test import policy: `[tool.pytest.ini_options] pythonpath=["."]` задаёт source root относительно backend/pyproject.toml для console `pytest` и `python -m pytest`, в том числе whole-tree `-m "not integration"` collection. Production package finder по-прежнему включает только `app*`; lab не устанавливается в production package. Из root можно использовать `PYTHONPATH=backend python -m pytest backend/tests/...`.
