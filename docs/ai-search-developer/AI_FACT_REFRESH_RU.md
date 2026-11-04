# S2.2 — finite synthetic detail refresh contract

`backend/lab/ai_fact_refresh.py` — явно вызываемый source-only rehearsal между durable supervisor receipt и existing fact/proof pipeline. Нет discovery, импорта фотографий, canonical upsert, notifications, automatic ACK, scheduler/startup или изменения capabilities. Это не standing ingestion и не production importer.

## Явный допуск и setup

Caller передаёт existing `SyntheticFactSupervisor`, `SyntheticRefreshPolicy`, tuple source UUID→canonical UUID (1–100), exact `httpx.MockTransport` и SHA-256 reviewed mock fixture bundle. Источник должен входить в coordinator configuration и иметь synthetic prefix; host — один явный `<name>.invalid`. URL должен быть HTTPS с этим host, без credentials/query/fragment/нестандартного port. Network transports и MockTransport subclasses отвергаются. Client создаётся внутри с `trust_env=False`, `follow_redirects=False`, без caller mounts. Mock handler доверенный: это не sandbox произвольного Python callback.

Existing supervisor guard проверяет loopback `ai_facts_test_*`/`ttest_test`. Дополнительно actual schema должна иметь unique-fixture форму `ai_facts_<32hex>`, а её SHA-256 совпадать с supervisor catalog identity. Грант source→canonical и source name сверяются до GET и при source CAS; при remap/rename/visibility race данные не записываются.

`await consumer.initialize()` выполняется только явным caller. В уже owned SQLite supervisor journal добавляется один immutable config/namespace row, в owned PG schema — таблица `synthetic_ai_detail_refresh_receipts`. Production migrations не меняются. Binding включает supervisor config, source policy, cohort и mock bundle digest; namespace переживает reopening и различает независимые journals. Caller-provided digest не является самостоятельной аттестацией полномочий или полного runtime bundle. Изменение policy/cohort/bundle/sessions/transport не обходит binding. Runtime/test provenance проверяется отдельно через runtime-input manifest.

## Один exact receipt

```python
await consumer.initialize()  # explicit disposable setup, once or idempotent reopen
result = await consumer.run_receipt(revision, expected_digest=journal.receipt_digest(revision))
```

Revision/digest должны совпасть с retained SQLite receipt. Весь список refresh IDs проверяется до первого GET: no duplicate IDs, принадлежность явному cohort, source/canonical identity и request bound. Неподтверждённая часть receipt не отбрасывается ради частичного успеха. Один consumer обслуживает один явно разрешённый synthetic source; mixed/out-of-cohort receipt требует отдельного reviewed dispatcher, а не молчаливого фильтра.

Максимумы:100requests/receipt,131072HTTP bytes,1–30s cooperative timeout каждого GET/validation,1000retained PG operation receipts. Requests идут последовательно. Body читается с byte bound; разрешены200/application-json без content encoding. Redirects/403/429/404/5xx/timeout/invalid identity/invalid JSON/invalid packet не продлевают last_success_at, не удаляют source/listing и не создают success receipt. В guarded row записывается failed check; shared health predicate исключает AI, manual source остаётся active. Подмена source/URL/health stamp во время I/O возвращает stale и не перезаписывает более новое состояние.

Document `synthetic-detail.v1` содержит source/canonical UUID, source name, raw/normalized payload и price text. Existing reviewed builder + `bridge_packet` проверяют response до записи; старый stored payload не переименовывается в новый detail. PG дополнительно измеряет реальный размер JSONB::text, чтобы принятый response оставался доступен существующему bounded snapshot reader.

## Commit и recovery

Network и builder выполняются после закрытия capture/read transactions. Запись использует existing `FactPipeline._anchor`→listing/source authority lock order и snapshot/fingerprint/source-name/canonical/health/freshness CAS. В одной PG transaction обновляются source, existing projection barrier через `_publish` и operation receipt. Operation key связан с durable namespace, exact supervisor receipt digest/revision и source ID. Source payload/URLs в PG receipt не сохраняются.

PG receipt вставляется только после валидного detail; failure INSERT откатывает source и projection. После unknown commit outcome следующий вызов сначала проверяет PG receipt, возвращает already_applied и не делает второй GET/публикацию. Concurrent calls могут выполнить два mock GET до commit, но source/operation locks разрешают только одну запись. Shared advisory lock и явный READ COMMITTED mutation transaction защищают global retained-receipt cap, в том числе при REPEATABLE READ engine default; snapshot до ожидания lock не может разрешить лишнюю запись. Пока нет durable HTTP request claim/budget/lease, это нельзя считать exactly-once fetch или включать для реального источника.

Freshness timestamp берётся из DB observation перед GET, а не из позднего commit: очередь/lock wait не продлевают content age. Действительно неизменившийся detail продлевает last_success_at, но сохраняет fingerprint/content_updated_at. Уже свежий healthy source возвращает already_fresh без GET и продления возраста. Повтор одного уже applied receipt не превращается в периодический refresh: новый sweep выдаёт новый receipt.

После изменения source старые facts/proof не обслуживаются. Existing coordinator должен observe/extract/reconcile/prepare новый snapshot. Успех refresh сам по себе не означает verified coverage. Даже успешный consumer всегда возвращает acknowledged=false: rejected/deferred сигналы того же supervisor receipt относятся к другим обязательствам. Explicit caller может выполнить exact ACK после проверки всех сигналов и downstream результата. ACK не удаляет evidence и не освобождает retention capacity; автоматического pruning/reset нет.

## Оставшиеся эксплуатационные gates

Лимиты числа операций и bytes не являются wall-clock SLO. Async timeout кооперативный, post-return monotonic guard отклоняет synchronous overrun; зависший callback/DB wait требует внешнего process deadline. Hard process boundary из#406 существует для finite supervisor, но lifecycle composition нового consumer, durable pre-HTTP budgets/leases/fences и permanent supervision остаются отдельным следующим rehearsal. В live режиме недопустимо слепо повторять GET после interruption, считая mock operation receipt глобальным spending limit.

До real activation также нужны source authorization/robots/budget/cohort, настоящий reviewed detail decoder, согласованный canonical card/map/price import, data coverage/freshness measurements, erasure/retention и release gates. Legacy `external_import.upsert` здесь не вызывается: он может скачивать media, touch catalog и отправлять notifications. Публичный AI, provider, voice/saved/delivery этим модулем не активируются.

## Проверка

Из backend с existing release-venv и явной owned disposable `AI_FACTS_TEST_DATABASE_URL`:

```text
python -m pytest -q tests/test_ai_fact_refresh.py tests/ai_facts_pg/test_fact_refresh.py
ruff check app tests lab
mypy app lab/ai_fact_refresh.py lab/ai_fact_process.py
```

Existing facts CI включает новый PG module через весь `tests/ai_facts_pg`, unit suite — через whole-tree non-integration collection. Lab остаётся вне production package finder app*.
