# Main acceptance и подготовка ограниченного LIVE UI smoke

3 ноября 2026, Europe/Moscow. Existing audit checkout, новая ветка
`codex/closed-live-ui-preparation`. Исходный грязный checkout не изменялся.

**Main принят; LIVE UI подготовлен, но не запускался.** Новых provider calls=0,
ключи и настоящий eval journal не читались. Production/merge/public AI, реальные
данные, capacity benchmark и внешние публикации приложения не выполнялись.

## Проверенный main

Актуальный origin/main — `4a60e1632d3b234f4b5321d224b3abfd041769a3`.
GitHub API дал6 push workflows, все completed/success; дополнительный scheduled
external-source audit тоже success. Это проверки merge SHA, не старого PR head:
[Full audit](https://github.com/antony502189-max/Ttest/actions/runs/41422753884),
[AI facts/quota/sessions](https://github.com/antony502189-max/Ttest/actions/runs/41422753956),
[private frontend](https://github.com/antony502189-max/Ttest/actions/runs/41422754038).
Остальные ссылки — в [CI snapshot](ai-closed-ui-preparation-20261103-evidence/main-ci.json).

Лаборатория пересобрана из clean git archive **точно этого main**; архив SHA256
`75356689dbe276e80dbf5c758ad368d45613de1414537663d162c9432daeb950`.
Старые volumes/DB/evidence сохранены, backend network internal=true.

Из отдельного процесса обычного `app.main` с настоящей lab PG:
capabilities все false; POST query503; обычный GET listings200 и13 synthetic items.
[Aggregate evidence](ai-closed-ui-preparation-20261103-evidence/main-default-disabled.json).
Lab UI composition сама включена только явно и не меняет этот default.

Все **15 real HTTPS/UI/backend/PG/Redis** regression scenarios PASS:
карточки/карта, оба режима аренды, exclusive map/list, hard criteria, quota,
clarification/no_change/unsupported, failure/cancel/timeout, lost commit ACK,
ownership/stale version, hard reload operation recovery, отмена ожидания,
metadata read failure после commit и приватность metrics.
Model completion в этих проверках synthetic, настоящей модели нет.
[Raw acceptance](ai-closed-ui-preparation-20261103-evidence/main-browser-acceptance.json).

## Выполненный пакет

Отдельный `ClosedUIParser` использует общий strict decision adapter, точный
трёхфразовый subset прежнего corpus24 и UI-compatible deadline10s/one attempt.
Identity/version остаются server-owned. ExistingSmokeBudget не создаёт journal:
проверяет прежнюю binding/history, резервирует до IO и атомарно останавливается
при cumulative54 attempts. Baseline51 не сбрасывается, global56/$0.75 не повышен.
Retry transport выключен; неопределённый outcome сохраняет reservation.

Подготовлены отдельная explicit factory и Compose override, который обычный
launcher не подключает. Реальный ключ доступен только backend через file mount,
SAME budget directory сохраняет общий SQLite locking. Конфигурация проверена
без запуска override и без открытия ключа/настоящего journal; frontend/maintenance
не получают secret/budget/egress, backend не публикует порт.
[Compose validation](ai-closed-ui-preparation-20261103-evidence/compose-validation.json).
Docker bridge не объявляется сетевым allowlist: финальный egress review остаётся
явным условием активации.

UI dialog и общий lab banner различают настоящую модель с synthetic каталогом
и simulated replies. Отдельная LIVE-labelled frontend build проверена offline;
она не подключалась к сервисам и ничего не активировала.

Точный предлагаемый smoke:3 свежие owned sessions, `ru-balcony`, `es-monthly`,
`en-negation`, пустые criteria, до3 новых HTTP attempts, локальный дополнительный
резерв33180 microUSD. Exact retry/reload должны вернуть owned receipt без новой
модельной попытки. [Машиночитаемый план](ai-closed-ui-preparation-20261103-evidence/live-smoke-plan.json),
[контракт запуска и5 оставшихся gates](../ai-search-developer/AI_CLOSED_UI_SMOKE_RU.md).
Старое разрешение synthetic eval24/24 не разрешает этот новый платный запуск.

## Новая offline проверка

Runtime **fb1877d3fc2aac7c7776bdb384b43d90c4022bf8** собран из clean archive,
`https://localhost:9443`, mode `decision-transport-fixture`.

- **Backend composition3/3:** настоящая новая factory/parser/budget и PG/Redis,
  подменён только HTTP model transport. Собственный disposable journal с явно
  искусственными51 baseline rows;3 новых fixture attempts и3 настоящих debits,
  exact retry не добавляет attempt. Настоящий eval journal не открывается.
  [Результат](ai-closed-ui-preparation-20261103-evidence/backend-composition-rehearsal.json).
- **Browser3/3:** точные предлагаемые фразы через обычный UI, typed criteria,
  cards/map hash, exact retry и reload с одним fixture attempt на case. Raw text
  отсутствует в durable browser storage. В unfurnished case подтверждён нулевой
  результат; это допустимый результат synthetic каталога.
  [Результат и hash driver](ai-closed-ui-preparation-20261103-evidence/browser-rehearsal.json),
  [скриншот](ai-closed-ui-preparation-20261103-evidence/en-negation.png).

Backend и browser rehearsals — разные наборы. Ни один не является LIVE model
приёмкой; browser rehearsal использует LocalDecisionParser, а backend rehearsal
проверяет именно ClosedUIParser и cumulative metering.

Первые локальные прогоны выявили ошибки drivers: отсутствие identity bootstrap
до session create и слишком быструю выдачу третьего guest identity (штатный429,
limit2/min). Bootstrap исправлен, новые browser contexts разделены35s. Квоты,
issuance counters и budgets не сбрасывались. Неуспешные raw logs сохранены в
`output/closed-ui-package-20261103/`, а browser partial evidence —
`output/ai-closed-ui-rehearsal/402ce3d3-3de8-4908-b08a-ac46902d8f03/`.
Успешный browser run — `acbbe326-de04-4e5a-9bec-c83e8c3d8abe`.

## Остальная верификация

| Проверка | Результат |
| --- | --- |
| Полный backend unit, app/tests совпадают с merge |1683 passed,16 skipped,397 deselected |
| Closed provider/UI/lab targeted |52 passed,8 subtests |
| HomeAI browser contracts до lab-label-only изменения |56 passed |
| Backend mypy |172 files, success |
| Ruff app/tests/lab |PASS |
| TypeScript, Vite production и отдельная LIVE-labelled offline build |PASS |
| i18n source guard, driver syntax, diff check |PASS |

Числа пересекаются, не суммировать. Новые lab regressions включены в CI.
Raw результаты и hashes опубликованных Git blobs находятся в
[evidence](ai-closed-ui-preparation-20261103-evidence/SHA256_GIT_BLOBS.json).
Исходный Windows-byte manifest сохранён отдельно; отличие CRLF/LF описано в
[README](ai-closed-ui-preparation-20261103-evidence/README.md).
Этот отчёт не объявляет CI новой ветки успешным: он проверяется отдельно для
опубликованного HEAD.

Real-user outbound остаётся BLOCKED до account review/минимизации; актуальный
реальный каталог требует нового разрешения. Production-sized migration
rehearsal OPEN. ISSUE-004 OPEN / capacity BLOCKED / прежний SLO FAIL; stage3
пропущен владельцем, нового benchmark не было. Voice/ASR и delivery — этап8.
