# 02 — Фактическое состояние Ttest / production (снимок от 25.10.2026)

> **NOT LIVE:** здесь зафиксирован результат read-only аудита Codex на 25 октября, а не непрерывный мониторинг. Для нового релиза перепроверить SHA, CI и runtime. Сырые доказательства, методика, неопределённости — в [полном аудите](audits/2026-10-25/PRODUCTION_REALITY_AUDIT.md).

| Участок | Проверенное на 25.10.2026 | Что ещё не доказано |
|---|---|---|
| Production SHA | `1292c6807ece59999238bb31c80e09ef7e2c3212` совпадал с `main`, `current`, публичным `build-info.json` | Будущие изменения после снимка |
| Хост/стек | Contabo; Docker/Traefik/Nginx; React 19/Vite, FastAPI/SQLAlchemy, PG16/PostGIS, Redis, MinIO | Реальная нагрузка под AI |
| Контейнеры | frontend, backend, import worker, mail worker, redis, minio, postgres running/healthy; Traefik running без healthcheck | Состояние каждого за пределами окна наблюдения |
| Публичные карточки | **1 163**: 1 132 long-term, 31 holiday | Полное количество БД, активных source records, backfill eligible |
| Реальные типы | В sample присутствуют квартиры с одной спальней | Полный catalog taxonomy |
| Источники | 6 в effective `EXTERNAL_IMPORT_SOURCES` + Habitaclia hook = 7 adapter objects | Успех/покрытие каждого adapter по данным БД |
| Импортёр | worker healthy; встречались 403/block/error и предупреждения deactivation review | Реальные per-source success/freshness counters без readonly DB |
| AI stack | AI/ASR endpoints, квотных таблиц, enrichment worker, provider clients в проверенном production не было | Аккаунты/права провайдеров |
| HTTP voice | `Permissions-Policy: microphone=()`; общий request body 256 KiB | Корректность будущей audio upload реализации |
| Rate limits | Redis limiter и авторизация работают | Нет 3/200 calendar quota с success-only debit/idempotency |
| Saved searches | SavedSearch/notifications/outbox существуют | Корректность AI extra fields при alerts без новых tests |
| Парсерная база | PR #373 содержит evidence/Fingerprint/audit CLI, но **не слит** | Acceptance после переноса в main |
| CI | В audited main были post-merge full-stack browser failures, в том числе address validation 422 | Повторная проверка на актуальном SHA |
| Branch protection | Снимок фиксировал `protected=false` в main | Результат последующих изменений GitHub settings |
| Железо | ~18 GiB RAM, свободно ~16 GiB; диск ~968 GiB, ~11% занято | p95 под нагрузкой; PG pooling и фоновые AI workers |

## Чего категорически нельзя утверждать

- «1 163 записей в базе» — это **публичная выдача**, не DB total.
- «7 работающих источников» — это **7 сконфигурированных адаптеров**, полезный import каждого не подтверждён.
- «Парсер #373 уже работает» — **не было в production SHA**.
- «Отсутствие описания у X% объявлений» — реальная DB completeness **не измерена**.
- «Все data/API integrations готовы» — не внедрены.
- «Можно запускать backfill» — нет доказанного readonly snapshot coverage и privacy/provider approve.

## Проверки перед началом PR

1. Актуальный `main`/`planning`/PR #373 и checks.
2. Подтвердить отдельную read-only роль/реплику для агрегатов, без app write DSN.
3. Сверить синтетическую матрицу PR #373 с реальными n/status/description/unknown/conflict/capacity.
4. Перепроверить non-AI search, TOP и #372 платежные тесты после любой интеграции.
5. Записать evidence/ref SHA и дату измерения.

## Действующие ключевые участки кода

- `backend/app/services/external_import.py` — import commit/upsert, primary snapshot.
- `backend/app/external_sources.py` и `backend/app/habitaclia_source.py` — source adapters.
- `backend/app/repositories/listings.py` — existing exact filters, TOP order.
- `backend/app/services/notifications.py` — alerts matcher/outbox.
- `backend/app/services/rate_limit.py` — Redis rate limiter, **не** полноценный AI success-only ledger.
- `backend/app/main.py`, `deploy/nginx.conf` — security/body/microphone.
- `docker-compose.production.yml` — service topology и per-service settings.
- `docs/deployment.md`, `docs/production-operations.md` — manual deploy/rollback.
- `docs/ai-voice-search/` в planning branch — более старый архитектурный backlog.

Полные исходные измерения — [аудит Codex](audits/2026-10-25/PRODUCTION_REALITY_AUDIT.md).
