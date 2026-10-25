# 07 — Эксплуатация, безопасность и интеграция с production

> **Этот runbook — инструкция по проверке и выпуску после отдельного разрешения владельца.** Само появление файла в GitHub не разрешает изменения VPS/данных.

## Production topology из audited state

Сайт `https://app.112233.es`, Traefik публичный HTTPS, Nginx frontend/API reverse proxy, FastAPI, PostgreSQL/PostGIS, Redis, MinIO, external import worker, mail/outbox worker. Production release выбирается через `/srv/112233.es/current` и immutable SHA. `main` может отличаться от active release; доверять `build-info.json` и текущему symlink, а не README.

Релиз 25.10: `1292c6807ece59999238bb31c80e09ef7e2c3212`; Docker health/память — моментный снимок. Не считать этот SHA вечным.

## Правильный процесс

1. Feature branch и PR, tests & code review.
2. Проверка всех обязательных CI checks, expand-only DB migration compatibility.
3. Merge в **актуальный** `main` только после разрешения.
4. Только оператор: `Actions → Production deployment (manual approval)`, `main`, confirm checkbox + GitHub environment review.
5. Release metadata, `current` SHA, `build-info.json` и browser smoke QA должны совпасть.
6. В случае ошибки отключить AI features через утверждённые flags; не делать автоматический destructive rollback данных.

Не запускать deploy с планировочной ветки и не пытаться перенести её целиком поверх main.

## Безопасное read-only наблюдение

- Подтвердить server current SHA, health backend, status контейнеров, importer heartbeat, disk/Redis/PostgreSQL readiness.
- Анализировать только агрегированные метрики, no raw logs/PII.
- Для DB statistics только отдельная авторизованная read-only роль/реплика с bounded statement timeout. Не использовать production app write DSN в целях аудита.
- Инструмент `audit_ai_listing_data.py` содержится **в PR #373**, не считайте его установленным в production; сперва ревью source code и permissions.
- Source adapters могут быть configured, но не полезно работавшими. Нужно отличать все effective 7 от healthy/imported source count.
- Не запускать importer/crawl вручную ради проверки, не обходить CAPTCHA/403.

## Secrets/provider keys

Server-side only. Keys Groq/DeepSeek/OpenAI не размещать в `VITE_*`, React, GitHub issues, docs и JSON-аудитах. Подключение через existing secret-management process, least privilege. API clients общаются только из backend/worker. В каждом запросе не логировать transcript/audio/raw listing contacts; structured metrics без PII.

### Privacy

- Никогда не отправлять в DeepSeek whole `raw_payload` или nested `normalized_payload`.
- Минимальный evidence envelope: очищенные selected public text and structured allowlisted fields; independently verified PII gate.
- Audio ephemeral, private temporary storage with cleanup, no default transcript retention. Провайдерские DPA/region/retention проверить до включения.
- Source ToS/legality и tourist publication rules отдельно с юристом. Старое ТЗ не служит юридическим заключением.

## Operational safeguards (даже без месячного cap)

Technical controls: guest3/registered200 daily, per-operation audio <= согласованный limit (proposal 60s/8MiB), concurrency, request timeout, token cap, bounded retries, circuit breaker, per-IP bot defense, E2E telemetry on costs (USD/day, USD/1k requests), DLQ queue. **Месячного денежного cutoff нет**.

Worker обязан иметь отдельные ресурсовые ограничения от importer, продавливать backlog не должен. Невозможность внешнего LLM не должна закрывать объявления и нарушать основной поиск.

## Скорость выдачи после отправки голоса

Ключевое пользовательское acceptance: **browser-measured p95 ≤10s** от завершённой отправки аудио до **видимых актуальных карточек** при обычной сети/работающих API. Учитывать audio upload + Groq batch ASR + DeepSeek intent + indexed PG query + React painting. Нельзя блокировать на обязательной коррекции транскрипта или получать данные повторным crawl. Не ухудшать проверку актуальности ради скорости. Подготовить tracing per stage, p50/p95/p99, ошибки/timeout/429, quota refunds и критерии аварийного fallback. Полный SLO: [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md).

## Monitoring after rollout

- AI quota accepted/completed/refunded, remaining, 429s, timezone bucket.
- Transcriptions latency/failure, ASR critical slot error on test only.
- DeepSeek intent/fact invalid JSON/evidence rejected.
- Enrichment queue depth/deadletter, stale jobs, retry, fact coverage, conflict rate.
- Existing backend p95, 4xx/5xx, DB pool/slow SQL, importer healthy vs useful sources.
- Real user costs and abnormal traffic without sensitive text.

## Запрещено без отдельного одобрения

Деплой, SQL migration/backfill на production, изменять `EXTERNAL_REMOVAL_CHECK_ENABLED`, удалять данные/галереи, mass reimport/crawl, пробивать 403, менять TOP/Stripe, restart контейнеров/секретов, платный eval. Не обходить release lock и не удалять volumes/backups.

Оригинальные эксплуатационные правила: `docs/deployment.md`, `docs/production-operations.md`, `docs/manual-production-cicd.md`, `docs/production-monitoring.md` в текущем репозитории.
