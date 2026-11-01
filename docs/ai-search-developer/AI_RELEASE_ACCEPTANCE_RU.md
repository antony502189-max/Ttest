# Приёмка и управление закрытым AI-стендом

Новый закрытый режим UI/provider adapter описан в
[отдельном отчёте](../reports/AI_PARSER_UI_COMPOSITION_20261101.md).
`./scripts/ai-text-lab.ps1 start -Parser decision-transport-fixture` запускает
общий strict decision adapter с MockTransport только на границе модели.
`-Parser finite` (по умолчанию) сохраняет прежний стенд для старых drivers.
Для нового режима использовать `node scripts/accept-ai-parser-ui.mjs`, а не
старый release driver: семантические no-op и provider deadlines различаются.
[Real-user outbound review](DEEPSEEK_OUTBOUND_POLICY_RU.md) остаётся BLOCKED.

Область: только synthetic localhost lab, PR #403. Команды выполняются из
существующего `main-integration-audit/Ttest`, без merge/main/production.
Точный проверенный runtime и результаты: [отчёт пункта 7](../reports/AI_RELEASE_ACCEPTANCE_20261101.md).

## Повторяемая проверка

В PATH добавить Docker Desktop `resources/bin`; для browser driver установить
`PLAYWRIGHT_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe`.
Стенд запускается только из чистого immutable archive текущего HEAD:

```powershell
./scripts/ai-text-lab.ps1 start
node scripts/ai-text-lab-control.mjs seed
node scripts/accept-ai-release.mjs
node scripts/accept-ai-release-ops.mjs
docker exec ttest-ai-text-lab-backend python -m lab.release_status
```

Первый driver использует настоящие HTTPS UI/API/PostGIS/Redis. Только конечный
parser инъецирует failure/cancel/delay/timeout; commit-ack hook срабатывает после
настоящего SQL finalize. Browser disconnect удаляет только ответ после фактического
запроса к backend. API responses не подменяются. Артефакты в `output/ai-release/`.
Нужен seeded acceptance account из `lab.acceptance`; его данные синтетические.
Гостевые issuance buckets, дневные quota и журналы не сбрасываются ради теста.
Повтор ограничен текущим техническим бюджетом; 429 надо дождаться или расследовать.

Ops driver временно заменяет backend предыдущим проверенным image `f9282957`,
проверяет exact receipt replay и обычный SQL search на schema 0079, затем возвращает
текущий image. Он использует только существующие label-owned контейнеры и mounts.
Это совместимость двух конкретных binary/schema, не разрешение отката на любую
старую версию. Downgrade expand-only 0079 запрещён; при несовместимости выключить AI,
сохранить schema и исправлять вперёд. Не применять `down -v`, volume rm или prune.

Для настоящего отдельного backup/restore drill явно установить
`AI_RELEASE_TEST_DATABASE_URL` на disposable `ttest_test` в loopback:55479,
с тестовыми ai_lab credentials. Затем из `backend`:

```powershell
python -m lab.release_restore
```

Команда отказывается от другого адреса/порта/DB, создаёт две новые уникальные
`ai_quota_test_release_*` DB, выполняет полную migration chain, pg_dump/pg_restore
и restore barrier. Существующие DB не очищает. Журнал независим от dump. Артефакты
и DB сохраняются для проверки; backup содержит только созданные synthetic данные.
Это проверка механизма, не подтверждение production encryption/retention/permissions.
Для реального восстановления нужны доверенный backup manifest и актуальный
checkpoint авторитетного журнала по [policy](OPERATING_PRODUCT_POLICY.md).

## Быстрое выключение и возврат

```powershell
./scripts/ai-text-lab.ps1 disable-ai
./scripts/ai-text-lab.ps1 enable-ai
```

Состояние сохраняется в `output/ai-text-lab/source.json`, применяется к backend
через явную synthetic-only Compose настройку и переживает следующий `start`.
Backend заменяется, nginx обновляет адрес upstream. Проверять capabilities.text=false,
AI 503 `AI_SEARCH_DISABLED` и 200 обычного `/api/v1/listings/search/cards`.
Возврат обязан сохранить квитанцию/квоту и те же Postgres/journal mounts.
Операция с неопределённым commit повторяется точным ключом и payload; выключение,
disconnect и отмена ожидания не доказывают rollback и не дают права переинферировать.

## Наблюдаемость и действия оператора

Метрики доступны только внутри backend; nginx не публикует `/metrics` наружу:

```powershell
docker exec ttest-ai-text-lab-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())"
docker exec ttest-ai-text-lab-backend python -m lab.release_status
docker logs --tail 10 ttest-ai-text-lab-maintenance
```

- `ttest_http_request_duration_seconds` и `ttest_http_requests_total`: private AI
  route свёрнут в фиксированную категорию, включая невалидные URL.
- `ttest_ai_execution_seconds`, `ttest_ai_parser_seconds`: wall time, включая
  ошибки/отмену. `ttest_ai_execution_total{status,replay,failure}`: только конечные
  фиксированные labels. Это число ответов/uncertain исходов, не число списаний;
  replay не прибавляет provider calls или фактический debit.
- `lab.release_status`: pending/running/failed jobs, возраст oldest pending,
  overdue recovery, отдельные source/proof ages и public/verified coverage через
  тот же live SQL predicate. Только aggregates, statement deadline 3 секунды.
- Provider calls/cost равны нулю только для этого конечного parser без transport.
  Real account cost/usage/coverage помечаются unverified; закрытый live intent
  journal и его бюджет не изменяются этой приёмкой.

Локальные пороги расследования: отсутствие maintenance heartbeat >15 секунд;
`recovery_overdue>0` в двух последовательных проходах; pending age >60 секунд;
любые новые 503/504 или sustained error growth; verified coverage=0 либо резкое
падение source freshness. Проверить здоровье зависимостей и supervisor, не
ослаблять guards/quotas; при необходимости выключить AI. Периодические recovery
проходы каждые 5 секунд, GC после idle — ежечасно. Не выдавать единичные latency
samples за p95/p99 SLO: ISSUE-004 OPEN / capacity BLOCKED.

Запрещены text/criteria/evidence/IDs/token/SQL/DSN в labels/logs/error export.
Метрики process-local и обнуляются при смене binary; durable truth — PostgreSQL
receipts и независимый journal. Production scraper, alerts, supervisor и retention
должны быть проверены в целевом окружении до реальных пользователей.

## Release gate

Локальная synthetic приёмка не открывает публичный AI. До выпуска остаются:
capacity/SLO, policy конкретного real-user provider account, законченная UI
композиция с настоящим parser и подтверждённая инфраструктура backup/journal.
Merge #403, main checks, deployment и public activation — отдельные решения
владельца. Voice/ASR и rematch/delivery относятся к пункту 8.
