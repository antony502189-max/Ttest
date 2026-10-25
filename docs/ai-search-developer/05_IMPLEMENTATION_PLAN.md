# 05 — План реализации: небольшие PR и зависимости

> Источник: [полный план Codex](audits/2026-10-25/AI_IMPLEMENTATION_SEQUENCE.md) (в нём 13 PR). Таблица ниже — единая рабочая доска. **Ни один будущий AI PR не отмечен как реализованный.** Ссылки на старые planning docs архивированы; scope определён в [01_PRODUCT_SPEC](01_PRODUCT_SPEC.md).

| ID | Задача | Зависимости | DoD / проверка |
|---|---|---|---|
| **BASE-373** | Ревью парсерного PR #373, совместимость с current main и payment #372 | По согласованию владельца | fingerprint/evidence/CLI не ломают importer/gallery/catalog; зелёные тесты |
| **AI-01** | ADR: provenance, facts, compatibility, hard/soft, intent patch, paid TOP contract | **Можно начать сейчас** | Документированные enum/сценарии/контракты, 3/200 Madrid, unknown != deny, без runtime |
| **AI-02** | Read-only audit реальных source records + диагностика импортёра | Reviewed #373, **разрешённая read-only DB роль/реплика** | Измеренные counts/coverage/unknown/freshness; reporter без PII; без crawling |
| **AI-03** | Expand-only models/migrations: per-source facts, materialized search features | AI-01, #373; AI-02 для индексов | PostgreSQL disposable upgrade; status/evidence/index/freshness |
| **AI-04** | Durable queue/reconciler + canonical resolver, без paid provider | AI-03 | idempotency, concurrency, stale hash, owner/source conflicts, fake worker tests |
| **AI-05** | Privacy outbound gate + исправления конкретных адаптеров | AI-01/AI-02 + offline builder PR #373 | evidence sanitizer, structured source facts, no contacts/raw HTML |
| **AI-06** | DeepSeek Flash adapter + worker enrichment | AI-04/AI-05, provider DPA/keys | typed facts, validation, retries, quotas, metrics, controlled staging |
| **AI-07** | Business daily quota ledger 3/200, idempotency and Madrid reset | AI-01 | midnight DST, guest/auth, double clicks, failures, concurrent reservation |
| **AI-08** | Structured conversation state + patch semantics | AI-01/AI-07 | follow-up preserves named constraints, TTL, resets, safety |
| **AI-09** | Text AI query API + server-side matching/search | AI-03/04/07/08; AI-06 for reliable features | existing cards, confidence/unknown, TOP, paging, SQL pre-pagination |
| **AI-10** | Registered-only AI saved searches + existing alerts/outbox | AI-09/AI-06 | delayed enrichment alert, no duplicate notifications, legacy safe |
| **AI-11** | Groq batch speech backend, GPT-transcribe fallback | AI-05/07/08/09, provider/privacy gate | 60s/8 MiB proposal, edit transcript, one debit, failure cleanup |
| **AI-12** | React text panel and voice recorder mobile/desktop | AI-09, voice after AI-11 | cards/gallery/external/Map/TOP 1:1; accessible mobile |
| **AI-13** | Gold evaluation/staging/backfill dry-run/release runbook | all relevant | verified coverage, false-permit quality, costs, no broken non-AI features |

## Рекомендуемая параллельность

```text
             AI-01 (ADR)           review #373
                ├───── AI-07 (quota) → AI-08 (sessions)
                ├───── AI-03 (facts) → AI-04 (queue/resolver)
                └───── AI-02 (real DB audit) → AI-05 (source/privacy)
                                               ↓
                        AI-04 + AI-05 → AI-06 (background DeepSeek)
                        AI-03 + AI-08 + confirmed facts → AI-09 (text)
                                                 ↓
                                   AI-10 (alerts) + AI-11 (ASR)
                                                 ↓
                                      AI-12 (React)
                                                 ↓
                                      AI-13 (staging)
```

**Важно:** real DB read-only audit не блокирует offline ADR, quota ledger или mock frontend. Но **блокирует правдивое утверждение coverage и production backfill plan**. Не придумывать % описаний на основе 4 synthetic source snapshots.

## Первый PR

**AI-01:** документационный ADR совместимости, taxonomy, legacy defaults, conditionals, source conflicts, source freshness, owner override, semantics max capacity >= N, hard/soft, session patch, versioning и commercial TOP order.

Содержимое:
- `docs/ai-search-developer/adr/` с решениями и examples; при необходимости новые standalone Pydantic DTO отдельным PR.
- Тестовые JSON-сценарии: пара из двух, capacity=3, no pets vs dog, balcony follow-up, unknown pets, location fallback, Madrid DST.
- Ни live provider client, ни миграции, ни новые endpoints.
- Обязательно не дублировать уже написанное в #373.

## Актуализация после каждого PR

В [08_NEXT_ACTIONS.md](08_NEXT_ACTIONS.md) фиксировать SHA, PR URL/base, тесты (с ссылкой на run), миграцию/feature flag, что осталось и фактическую среду. В [02_PRODUCTION_BASELINE.md](02_PRODUCTION_BASELINE.md) не переписывать snapshot задним числом; делать новый датированный audit. Когда feature реально смержена, помечать соответствующий ID выполненным со ссылкой на commit/run.

## Release boundary

Кодовые PR сначала маленькие и тестируемые; будущая интеграция должна быть пересмотрена относительно **актуального main**, не заменять его устаревшим planning branch. Production deploy только через существующий ручной GitHub approval pipeline; не запускать из разработки автоматически.
