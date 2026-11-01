# AI migrations 0077–0079: контролируемое окно

Production rollout этим документом не разрешён. Исторические migration files
не переписаны; 0079 остаётся expand-only. Длинные locks и смена fast-path contract
нельзя устранять отключением freshness/proof/ownership guards.

## Реализованная защита

Alembic online transaction задаёт LOCAL `lock_timeout=5000ms` и
`statement_timeout=60000ms`. При конфликте DDL завершается ошибкой и откатывается,
а не ожидает writer неограниченно. Настройки не меняют pool/runtime defaults и
не сохраняются в роли/БД. Проверяемые override:

```
python -m alembic -x lock_timeout_ms=1000 -x statement_timeout_ms=60000 upgrade 0077_ai_live_inputs
python -m alembic -x lock_timeout_ms=1000 -x statement_timeout_ms=60000 upgrade 0078_ai_live_validity
python -m alembic -x lock_timeout_ms=1000 -x statement_timeout_ms=60000 upgrade head
```

Разрешено 100–30000ms lock /100–300000ms statement, lock<statement. Нулевой,
отрицательный, бесконечный или некорректный timeout отвергается. Приведённые
команды предназначены для согласованного окна, не для запуска на production сейчас.
Ожидание блокировки входит в statement deadline. Несколько revisions в одном
`upgrade head` могут держать locks до конца общей транзакции; разбивка команд
сокращает это окно, но не отменяет locks внутри каждой revision.

## До окна

- Назначить оператора, rollback binary и предел допустимого перерыва записи.
  Подтвердить backup + независимый deletion journal/checkpoint/restore barrier
  по [runbook](AI_RELEASE_ACCEPTANCE_RU.md); recovery не использует downgrade0079.
- Выполнить rehearsal на отдельно разрешённом изолированном snapshot сопоставимого
  объёма. Измерить locks/очередь, длительности, WAL/disk, покрытие proofs и стоимость
  reprepare. Малый synthetic rehearsal не заменяет этот шаг.
- Зафиксировать точный binary/schema, disable AI, остановить/дренировать AI workers
  и согласованные writers. Не объявлять обычную запись zero-downtime:0077 берёт
  SHARE ROW EXCLUSIVE на основных таблицах. Не начинать при долгих транзакциях.
- Зафиксировать counts/coverage/freshness и проверить свободное место. Не писать
  SQL, текст, IDs или DSN в публичные telemetry artifacts.

## Во время и после

- Поэтапно применить revisions с bounded timeouts. При timeout остановить rollout,
  проверить `alembic current` и отсутствие частичного DDL; устранить владельца
  блокировки организационно. Не ставить timeout0 и не запускать бесконечный retry.
- 0078 очищает прежние input signatures и маркирует proofs legacy. Это не удаление
  объявлений. Legacy verification и current-input/freshness guards не отключать.
- Подготовить proofs через настоящий `QueryProofs.prepare` ограниченными пакетами
  на актуальных facts/source checks; preparation не продлевает source freshness.
  Контролировать current/legacy/changed/missing, public/verified coverage и backlog.
- Проверить обычные чтения/записи, owned cards/map, quota/receipt replay и erasure
  recovery. Только после проверки целевых показателей возвращать writers/workers.
  AI включать исключительно по отдельному release решению; текущий public gate BLOCKED.
- При несовместимости оставить AI выключенным и исправлять вперёд. Binary rollback
  допускается лишь для конкретной проверенной пары binary/schema с сохранением данных.

## Воспроизводимая ограниченная проверка

Из `backend`, с Python dependencies и отдельным disposable PostGIS на loopback55479:

```
python -m lab.migration_rehearsal
```

Нужна явная `AI_MIGRATION_REHEARSAL_DATABASE_URL` на `ttest_test`; application DSN
fallback отсутствует. Команда создаёт уникальную `ai_quota_test_migration_*` DB,
сохраняет её и artifacts. Не очищает старые DB/volumes. 250 synthetic listings,
четыре genuine fact/proof fixtures исторического binary, concurrent writer locks,
transaction rollback,0078 invalidation/reprepare и old binary reads на0079.
Это bounded correctness drill, не capacity benchmark или production-sized rehearsal.
