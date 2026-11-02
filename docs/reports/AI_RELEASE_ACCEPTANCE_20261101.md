# Пункт 7: общая приёмка и подготовка выпуска

Дата: 1 ноября 2026, Europe/Moscow. Существующая ветка
`codex/post-merge-remediation`, draft [PR #403](https://github.com/antony502189-max/Ttest/pull/403).

## Вердикт и точные источники

**Закрытый synthetic текстовый стенд функционально принят. Публичный выпуск BLOCKED.**
Проверенный и работающий runtime: `ed1f9f96360e2ead47c8a8b6b2c186f4319f7bd3`,
`https://localhost:9443`. Полные frontend/backend/PostGIS/Redis/maintenance,
schema `0079_ai_operating_policy`, конечный SyntheticParser. Внешние provider calls — 0.
Приёмочные drivers: `6e99bc58104b5d324d715803c40f8a5a0520f564`.
[Source/validation attestation](../../reports/ai-release-evidence/source-and-validation.json).
После runtime SHA изменены только drivers и документы/evidence; исходники backend,
frontend и Compose/launcher сверяются отдельно. Ни один cancelled/pending CI не
считается successful. Checks конечного опубликованного evidence HEAD проверяются
после публикации в самом PR; evidence не переносит CI между SHA.

Merge/main mutation, production deploy, public AI, payments, notifications,
Pages и новые реальные данные не выполнялись. Исходный грязный checkout не менялся.
Старые lab PG v1/v2 и independent erasure volumes не удалялись. Capacities и
большие benchmarks не возобновлялись. DeepSeek journal/budget не читался и не сбрасывался.

## Что принято

Настоящие HTTPS/browser проверки на указанном runtime, без API mocks:

**16 проверок PASS**, включая privacy assertions реального metrics payload:
[browser/HTTP evidence](../../reports/ai-release-evidence/browser-http.json),
[метрики](../../reports/ai-release-evidence/metrics.prom).

- Guest create/query, Secure cookie, owned reload на 390px, квота 3 successful
  operations, отказ четвёртой, exact receipt replay с одним parser call/debit.
- Настоящий UI login, quota contract auth200, отсутствие переноса guest state,
  auth refresh и owned result recovery. Обновлённый access token используется
  после настоящей ротации refresh; старый bearer сервер отвергает.
- Model failure и cancellation — terminal, без debit; lost SQL commit ACK —
  первоначальный 503, затем прежний succeeded receipt и одно списание.
- Timeout исполнения 15 секунд — HTTP504/uncertain; maintenance освобождает
  истёкший lease, exact retry читает failed, reserved0/без debit/повторного parser.
- Browser disconnect после настоящего commit и «перестать ждать» во время parser:
  точный payload/key сохранён в памяти вкладки, retry не вызывает повторный inference.
- Реальные остановки Redis и PostGIS: 503/no-store/fail closed, после запуска
  used/reserved не изменились. Maintenance сам перезапустился по restart policy
  после DB outage; aggregate heartbeat возобновился, overdue recovery0.

После одного DB restart новая операция получила `BACKEND_FAILURE` без списания;
следующий явный новый запрос и последующие rollback/replay проверки прошли.
Transient сохранён в локальном `output/point7-ops.log`. Ошибки во время fault drill
не являются прохождением capacity/SLO.

Отдельный rollback/disable drill — 4 проверки PASS:
[ops evidence](../../reports/ai-release-evidence/operations.json).

- Реально запущен предыдущий backend image `f9282957` на текущей schema0079;
  обычный SQL search и AI exact replay работают, receipt/used совпали. Переключение6с.
- Возврат текущего backend сохранил receipt/used; SQL downgrade не делался.
- `disable-ai` применился за9с: capabilities.text=false, AI503 `AI_SEARCH_DISABLED`,
  обычный `/api/v1/listings/search/cards`200 с тем же count.
- `enable-ai` восстановил capability и exact receipt; PG/journal mounts совпали.

Эти длительности — единичный локальный drill, не SLO или production RTO.
Совместимость доказана для этой пары binary/schema, не для произвольного rollback.

## Migrations, настоящий backup/restore и независимое удаление

`python -m lab.release_restore` создаёт новые disposable DB, проходит полную
цепочку до0079, делает настоящий pg_dump custom-format и SHA256 manifest.
После backup принимается deletion intent в независимом AES-GCM journal,
исходный аккаунт удаляется. Настоящий pg_restore возвращает pre-deletion
аккаунт/приватную сессию в отдельную изолированную DB. Затем restore barrier:

| Сценарий | Результат |
| --- | --- |
| Нет independent journal | отказ |
| Валидный пустой replacement с другим UUID | отказ по DB binding |
| Backup старше30дней | отказ |
| Journal head изменился после checkpoint | отказ |
| Свежий authoritative checkpoint + replay | restored account deleted, private sessions0 |
| Повтор того же replay | идемпотентно, sessions0, schema0079 |

7 сценариев PASS. Точный source, имена новых disposable DB и backup hash:
[restore evidence](../../reports/ai-release-evidence/restore.json).
Сам encrypted journal, synthetic dump и manifest сохранены локально в
`output/ai-release/restore-c563e084b0b7/`; они не заменяют production backup policy.
Политика expand-only0079 и запрет downgrade сохранены. Production retention,
encryption, доступность отдельного ключа/журнала и реальный restore isolation
должны быть подтверждены владельцем целевого окружения.

## Наблюдаемость и исправления

Добавлены bounded `ttest_ai_execution_total{status,replay,failure}`,
`ttest_ai_execution_seconds`, `ttest_ai_parser_seconds`; используются существующие
HTTP latency/status metrics с private route category. Uncertain commit не
маркируется failed debit. Нет raw exception labels, текста, критериев или IDs.
Unit canary подтверждает подавление произвольного failure label.

`lab.release_status` выдаёт только read-only aggregates, SQL deadline3с:
14sources, 13source checks≤24h, 11prepared proofs≤24h, 13public/11verified listings,
13succeeded fact jobs, pending age0, overdue recovery0. Source age и proof age
разделены; реальное покрытие и стоимость provider account остаются unverified.
В этом конечном parser нет provider transport, поэтому calls/cost=0.
Метрики process-local; PostgreSQL/journal остаются durable authority.

Исправлены ошибка timedelta в новой status-команде, ожидание асинхронного mobile
onboarding в driver, использование свежего bearer после refresh и выбор доступного
PowerShell7 для ops driver. Политики безопасности и quotas не ослаблялись.
В runbook исправлены устаревшие числа active sessions/TTL/Redis budgets и перечень
resources; добавлены отключение/возврат, rollback/restore, метрики и пороги расследования.

## Локальная регрессия

| Проверка | Результат |
| --- | --- |
| Полный backend unit без integration/isolated PG |1668 passed / 17 skipped |
| Targeted execution/policy/journal/transport + metric canaries |161 passed / 3 skipped без Redis env |
| Real PostGIS HTTP/browser/account/freshness + Redis operating gates |18 passed / 1 skipped |
| Отдельный Redis distributed-gate повтор с явным DB15 |3 passed |
| Python mypy |169 файлов, success |
| Ruff изменённых Python; node syntax; git diff check |PASS |

Числа пересекаются, их нельзя складывать. В integration18 действительно выполнены
все4 `test_ai_browser_recovery.py` с built dist и настоящим Chrome. Пропущен
отдельный ASGI bridge, которому нужен `AI_UI_TEST_URL`; он не объявляется пройденным.
Launcher выполнил TypeScript и production Vite build из immutable archive runtime SHA.

Исходный HEAD6195a807 после failed-only rerun:11исполнявшихся workflows success,
2conditional skipped. Первоначальный Mobile shard упал с workerSIGTRAP без
failed assertion,167прочих tests прошли; повтор того же SHA завершился success.
CI последующих SHA отслеживается отдельно, отменённые новым push runs не принимаются.

## Блокеры выпуска

| Gate | Состояние |
| --- | --- |
| Закрытая synthetic functional/fault/restore/rollback приёмка |PASS на указанном runtime |
| Capacity/SLO, ISSUE-004 |BLOCKED / OPEN, этап3 пропущен владельцем |
| Real-user provider account privacy/outbound |не подтверждено; прежний synthetic eval не разрешает user text |
| UI composition с настоящим parser |не завершена; текущий UI понимает конечный набор synthetic фраз |
| Production backup/journal retention/encryption/supervisor/alerts |не подтверждены synthetic drill |
| Merge/main CI, production deploy/public activation |не разрешены; отдельное решение владельца |

Voice/ASR и rematch/delivery остаются пунктом8, capabilities=false.
Пункт7 даёт конкретный закрытый результат и подготовленный release runbook;
выпуск продукта остаётся заблокирован указанными gates.

[Воспроизведение и действия оператора](../ai-search-developer/AI_RELEASE_ACCEPTANCE_RU.md).
