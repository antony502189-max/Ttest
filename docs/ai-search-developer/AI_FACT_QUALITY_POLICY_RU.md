# Закрытый контроль качества фактов без ключей

1 ноября 2026. Это явно вызываемые offline primitives; public runtime не включён.
Сроки передаются обязательным `FactQualityPolicy` (строгие положительные секунды,
до года), согласованных production defaults нет. Наличие ключа ничего не включает.

`repositories.ai_fact_quality.audit_catalog(pipeline, eligibility=..., plan=...,
policy=..., limit=...)` читает один REPEATABLE READ / READ ONLY snapshot.
Вход eligibility — серверный SQL predicate для полного необходимого public,
economic и time eligibility. Дополнительно всегда проверяются published/deleted.
Когорта ограничена 1000; overflow вызывает ошибку, а не неполный отчёт. Каждый
eligible listing относится к одному bucket: match, mismatch, unknown, conditional,
conflict, stale, source_error. Сумма buckets равна eligible. Текст и IDs не возвращаются.
Ошибки DB не превращаются в нулевые counts.

Currentness проверяет существующий pipeline verifier; matcher используется
повторно. Mismatch — подтверждённое несовпадение значения при проверенной форме
и scope. Missing/legacy/неподходящий scope/duplicates не считаются mismatch.
Если критерии одновременно неизвестны и не совпадают, неопределённость имеет
приоритет (conflict → conditional → unknown → mismatch). Это консервативная
диагностика, не полный multi-label разбор причин. Party означает состав жильцов,
а не разрешение вечеринок; отдельного extraction party rule по-прежнему нет.

Freshness использует реальный `last_success_at` действующих источников;
пустое или будущее время не подтверждает свежесть. Граница max_age включительна.
Для price/availability/available_spots применяется меньший из двух TTL; для
остальных — policy TTL. Unknown/unavailable source не становится healthy;
retired peers исключаются, но один отсутствующий источник не создаёт свежесть.
Равенство hash и время вычисления projection не обновляют возраст источника.

`source_freshness_predicate(Listing.id, plan, policy)` — отдельный SQL guard:
добавляется вместе с existing currentness, hard matching и всеми eligibility
условиями ДО count/order/seek/LIMIT/aggregate. Время берётся заново через
statement_timestamp; prepared proof сам по себе TTL не продлевает. Guard не
заменяет currentness. Он не подключён автоматически к public/runtime query paths:
первое применение — закрытый explicit audit и synthetic SQL checks.

`FactPipeline.purge_expired_evidence(listing_id, retention_seconds=...)` — явный
вызов очистки AI evidence, без scheduler и real-content ingestion. Срок считается
от observed_at (новая проверка источника не продлевает хранение старого текста).
Просроченные batches и связанные facts/evidence физически удаляются в одной
транзакции; current pointers очищаются, generation увеличивается, running/pending
jobs fenced, projection перепубликуется через существующий pending barrier.
Прежние workers не восстанавливают удалённые факты; повторная подготовка требует
нового поколения. Proof инвалидируется существующими DB зависимостями.
Rollback восстанавливает evidence и proof. Более 1024 batches на listing вызывает
отказ без частичного удаления. Метод не является удалением legacy raw payload,
backup/export/copy, receipt или всех следов записи; для real pilot это отдельный
инвентарь хранения и физического удаления. Job receipts сохраняют hash и metadata,
но не evidence text. Общее удаление receipt/idempotency state здесь не включается.

Проверки и exact source: [отчёт](../../reports/AI_FACT_QUALITY_NEXT_20261101.md).
Настоящий каталог, coverage, source health, права на экспорт и утверждение сроков
остаются необходимыми для закрытия пункта 5. LLM extraction необязателен.
