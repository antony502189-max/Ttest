# S2.2 — bounded offline coordinator

`backend/app/services/ai_fact_coordinator.py` связывает существующие stored-source capture/bridge/observe, `OfflineFactJobRunner`, `FactPipeline.reconcile` и `QueryProofs.prepare`. Это явно вызываемый локальный service, без startup/import hook, HTTP/provider, discovery, удаления legacy данных или изменения capabilities.

## Явная конфигурация

Конструктор требует pipeline с `FactQualityPolicy`, 1–16 `SourceFactPolicy`, `max_sources`, `max_reconcile`, `max_payload_bytes`. Каждая source policy задаёт точное имя источника, reviewed builder, `BridgeMapping`, extractor version, content TTL, число job attempts за tick и retry policy. Этот TTL определяет `content_refresh_due`; SQL eligibility по-прежнему применяет существующую `FactQualityPolicy`, отдельный per-source SQL cutoff здесь не вводится. Production mapping/default builder не добавлены. Builder синхронный, работает после освобождения capture-транзакции; разрешение outbound он не получает.

Лимиты: source page ≤100; отдельная catalog page ≤100; сумма job attempts по всем sources ≤100; capture ≤2 MiB; source TTL положительный и не больше минимального operating price/policy TTL. Каждый listing сохраняет существующий bound 128 источников. Reconcile/proof работают максимум с объединением двух страниц (≤200 listing IDs); worker может завершить другие ранее queued IDs, их proof будет подготовлен очередной catalog sweep. Это лимиты количества операций/данных, не wall-clock SLO: process deadline и остановку зависшего builder обеспечивает supervisor.

Worker выбирает jobs одновременно по версии и имени источника. Единая bridge-compatible grammar source name: `[A-Za-z][A-Za-z0-9_-]{0,63}`; invalid names отвергаются при configuration без вывода исходного значения. Проверяется полный captured identifier `<name>:<uuidhex>`, без lossy split. Capture повторно проверяет имя до builder: одинаковые extractor versions и смена source name между scan/claim/capture не разрешают чужой mapping. Остальные source membership/snapshot/fence проверки остаются в существующих primitives. Переименование/remap требуют reviewed reconciliation, автоматического переноса authority нет.

## Tick и recovery

Первый вызов: `await coordinator.run_once(FactCoordinatorCursor())`. Успешный результат содержит следующий cursor, счётчики scans/observations/rejections, bounded source IDs `content_refresh_due`, job outcomes и числа подготовленных/deferred proofs. `proofs_prepared` означает актуальную привязку projection, не пригодное покрытие или verified match: пустая projection также может иметь proof. Query quality/freshness/visibility guards обязательны по-прежнему.

Source и catalog keyset cursors независимы. Полная страница продвигает ключ; неполная сбрасывает его для следующего sweep. Вставки/изменения позади cursor возвращаются на следующем sweep. Один `no_claim` завершает попытки только соответствующего worker в этом tick, не доказывает пустоту всей очереди. Очистка одного exhausted/superseded кандидата возвращает `skipped_terminal`/`skipped_superseded`, расходует одну попытку и позволяет следующей попытке продвинуть runnable job. При исчерпании бюджета remaining queue видна в health; unbounded claim loop не добавлен. Direct legacy callers claim без `report_skips=True` сохраняют прежний return contract.

При исключении service возвращает только `FactCoordinatorUnavailable("OFFLINE_FACT_COORDINATOR_UNAVAILABLE")`, без payload/SQL/adapter details, и не подтверждает checkpoint. Supervisor повторяет прежний cursor после backoff, используя существующие durable leases/retry budgets/CAS; неизвестный commit outcome не вызывает немедленного второго builder внутри tick. `CancelledError` распространяется. Живой lease не отбирается; expired lease получает новый fence в existing claim. Terminal failed jobs не сбрасываются автоматически.

## Контракт supervisor, пока без активации

Будущий supervisor обязан:

1. Хранить предыдущий cursor и фиксировать receipt + следующий cursor атомарно, с CAS/эксклюзивным владельцем конкретного coordinator configuration. После падения до commit повторять прежний cursor. Receipt с refresh IDs нельзя терять при продвижении checkpoint.
2. Назначать период следующего sweep, backoff, process deadline/shutdown и конфигурационную версию. Отдельно наблюдать durable queue terminal failures, retries/lease exhaustion, rejections, deferred proofs и возраст последнего успешного sweep. Сбой не считается успешным heartbeat; не логировать source payload, текст или URLs.
3. Передавать `content_refresh_due` только в разрешённый source-specific detail importer с отдельными budget/lease/robots/authorization ограничениями. Этот coordinator читает уже сохранённый payload. Missing/future/expired `last_success_at` остаётся просроченным после observe, extraction и proof prepare. Presence-health probes сюда не подключены и content TTL не продлевают.
4. Подтвердить lock order и supervision на целевой среде до подключения importer/production hooks. Реальные mappings, coverage/freshness, provider/data permissions, migrations/backup/erasure и release gates остаются открытыми.

Текущие tests используют только synthetic stored snapshots и disposable loopback PostgreSQL. Они проверяют service seam и replay, а не постоянный работающий supervisor или реальный обновляемый каталог. S2.1, supervised S2.2 и S2 в целом не закрыты.
