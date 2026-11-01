# Исправления по независимому review PR403

1 ноября 2026. Исходный пользовательский отчёт
`PR_403_FULL_SECURITY_CODE_REVIEW_20261101.md` относится к
`fbcb2fab9385b932edd15ee1e757ef7ca9515c4e`. SHA256 исходного файла сохранён в
[attestation](ai-review-remediation-final-evidence/attestation.json). Его рекомендации
рассматривались как входные данные review; разрешения на merge, production,
real-user outbound или большие capacity benchmarks не расширялись.

Runtime исправленного UI: **331bbcc74be1eb6c19ef95b8b6c7804cedd73078**,
`https://localhost:9443`, `decision-transport-fixture`, API mocks=false.
После runtime менялись только docs/evidence; app/migrations/src/
Compose/launcher hashes совпадают с итоговой веткой. Старые evidence не переписаны.

## Диспозиция всех пяти находок

| Finding | Изменение | Проверка / оставшаяся граница |
| --- | --- | --- |
|001 reload незавершённой операции | FIXED: synchronous operation marker до POST; после reload owned GET status → receipt → metadata/cards | Настоящий commit → потерянный ACK → hard reload восстановил исходный receipt/cards, model calls1. Running/reserved/неизвестный404 не запускают новый inference; failed требует нового явного текста. Negative owner/TTL tests |
|002 противоположный rental mode отсутствует | FIXED: обе long/holiday опции доступны независимо от modeChoice/homeMode | Browser проверяет обе опции и фактический rental_mode запроса |
|003 карта не скрывает список | FIXED: список hidden/display:none в map mode; возврат восстанавливает список |390/1440 browser tests, настоящий synthetic coordinate map с SQL markers |
|004 потеря receipt при metadata failure | FIXED: terminal receipt locator отделён от hydration; raw pending очищается, locator остаётся до успешной binding-проверки | Mocked HTTP metadata503→200 и настоящее удаление ответа после GET metadata; read-only retry без второго POST/inference/debit. Hash mismatch fail-closed |
|005 migration locks/invalidation | HARDENED + bounded rehearsal PASS: LOCAL lock/statement deadlines, staged runbook, реальные конфликтующие writers/rollback/reprepare | Production-sized snapshot/WAL/availability rehearsal остаётся OPEN; маленький synthetic набор этого не доказывает |

001/004 теперь воспроизведены собственными browser fault drills, а не только
статическим чтением.002–004 были pre-existing; происхождение не переобозначается
как новая regression PR403. В первом новом driver прогоне исправлялся selector:
Vite synthetic mode использует coordinate map, а не production `.ai-result-map`.
Карта на скриншоте работала; дополнительный дефект высоты не подтвердился.

## Recovery и privacy

В sessionStorage только session/result UUID и operation `{key, expectedVersion,
createdAt}` с TTL≤24h, scoped к текущей auth/guest identity. Нет raw text, criteria,
cards, bearer, provider response или SQL. Дополнительные поля, неверные UUID,
version, будущий/истёкший timestamp отвергаются. Запись marker до POST синхронна:
reload не зависит от того, успел ли выполниться React effect.

GET operation проверяет владельца на сервере. UUID из storage не даёт доступа.
Running/reserved, transport failure/429/5xx и OPERATION_NOT_FOUND не считаются
доказательством rollback; UI предлагает только статусное чтение.401 владельца
очищает старый locator, не переотправляет операцию под новой identity. Status
failed снимает блокировку для нового явного ввода. Status succeeded восстанавливает
receipt; session/version/count/ref/hash сверяются с metadata/cards. Metadata failure
не превращает успешный debit в новый model request. Несовпадение binding не
переименовывает и не показывает прежние карточки как новый результат.

Исходный payload после reload отсутствует; он не восстанавливается из storage и
не переотправляется. В той же вкладке прежний exact payload retry сохраняется.
При истечении marker очищается также in-memory locator: новый запрос не может
унаследовать прежний key. Concurrent refresh отменяется перед recovery; повторные status GET в React
StrictMode безопасны и не имеют model/debit side effects.

## Migration rehearsal

Точный source **fcdf037943bba117baf8bba46db87e6b7974727b**;
backend/app и migrations совпадают с runtime выше. Новая disposable DB
`ai_quota_test_migration_6db6effea812` в разрешённом loopback PostGIS55479,
сохранена. Application/lab DB, старые restore DB и volumes не очищались.

[Шесть checks PASS](ai-review-remediation-final-evidence/migration.json):

- Полная цепочка до0076, 250 synthetic listings, writer держит RowExclusive.
  Upgrade0077 с lock300ms завершается именно lock timeout; revision остаётся0076,
  частичная ai_live_input_versions отсутствует. После освобождения writer upgrade
  проходит. Wall times3.633с/3.880с включают startup Python/Alembic, это не чистая DDL latency.
- Исторический source **b65c70af75be9bef204c032e1db4f10111acf5b8** (родитель0078)
  создаёт ещё четыре listings с настоящими facts/proofs через старый pipeline.
  Это не fake signatures и не production snapshot.
- Настоящий0078 body в транзакции блокирует concurrent proof writer: SQLSTATE55P03
  при300ms lock deadline. После commit обычная запись доступна, четыре прежних
  fast-path bindings очищены и помечены legacy. Wall sample0.531с включает writer wait.
- Полная цепочка до0079, настоящий QueryProofs.prepare восстанавливает четыре
  current proofs; owned SQL query возвращает три карты. Исторический binary source
  читает те же три карты на0079. Schema downgrade и production binary deploy не делались.

В Alembic online transaction теперь LOCAL lock5s/statement60s; разрешены только
bounded числовые override. Нулевые/инъекционные/некорректные значения отвергаются.
Released migration files0077–0079 не менялись; governance tests прошли.
[Поэтапный runbook и pre/post gates](../ai-search-developer/AI_MIGRATION_ROLLOUT_RU.md).

## Проверки и evidence

| Набор | Результат |
| --- | --- |
| Полный backend unit |1683 passed /16 skipped /1041 deselected |
| Полный Home AI browser contracts, настоящий Chrome |56 passed; API mocked |
| Дополнительный targeted recovery/privacy |12 passed; пересекается с56 |
| Настоящий HTTPS/UI/backend/PG/Redis |15 passed, только model transport fixtures и network response loss |
| Bounded populated migration/locks/reprepare/old-source |6 passed |
| Migration timeout/governance unit |11 passed, пересекается с backend unit |
| Mypy / Ruff |172 app files success / app+tests+новый lab driver PASS |
| TypeScript/Vite immutable build, syntax, diff |PASS |

Числа не суммировать. [Browser/HTTP](ai-review-remediation-final-evidence/browser.json),
[validation](ai-review-remediation-final-evidence/validation.json),
[снимок recovery](ai-review-remediation-final-evidence/auth-recovery.png).
CI точного опубликованного HEAD отслеживается отдельно в PR; локальные результаты
не объявляют pending CI успешным. Непрошедшие начальные driver artifacts сохранены
в локальном output, не подменяют успешный итог.

## Оставшиеся release gates

Production-sized migration rehearsal с отдельно разрешённым snapshot/объёмом,
WAL/disk/lock-queue и доступностью в целевом окружении не выполнен. Также остаются
capacity ISSUE-004/SLO, account-specific DeepSeek privacy/минимизация, LIVE UI smoke
по отдельному разрешению и production backup/journal/supervisor/alerts. Эти gates
не являются исправленными кодом багами и не закрываются зелёным CI.

Новых paid calls, чтения реальных ключей, изменения eval budget/journal, новых
реальных данных, merge/main/production mutation или public activation нет.
PR остаётся draft. Этот отчёт не является заявлением «все возможные уязвимости
исключены» и не заменяет независимый targeted re-review итогового SHA.
