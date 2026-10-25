# AI-поиск 112233.es — портал разработчика

> **START HERE / актуально на 25.10.2026.** Эта папка — единая точка входа для разработчика AI-поиска недвижимости в существующем Ttest. Документация не является признаком внедрения функций в production. Репозиторий публичный; не размещать здесь секреты и персональные данные.

## С чего начать (порядок чтения)

| Порядок | Документ | Зачем читать |
|---|---|---|
| 1 | [01_PRODUCT_SPEC.md](01_PRODUCT_SPEC.md) | Утверждённое владельцем ТЗ: что делать и что категорически исключено |
| 2 | [02_PRODUCTION_BASELINE.md](02_PRODUCTION_BASELINE.md) | Что действительно проверено на сервере 25 октября, а чего мы пока не знаем |
| 3 | [03_ARCHITECTURE.md](03_ARCHITECTURE.md) | Два независимых AI-контура, модель фактов, безопасные границы |
| 4 | [04_API_CONTRACT_DRAFT.md](04_API_CONTRACT_DRAFT.md) | Предложенные DTO/endpoints для Groq/DeepSeek, квот и диалога |
| 5 | [05_IMPLEMENTATION_PLAN.md](05_IMPLEMENTATION_PLAN.md) | План PR-AI-01…13 и зависимости |
| 6 | [06_QA_ACCEPTANCE.md](06_QA_ACCEPTANCE.md) | Unit/integration/E2E, доказательства, проверка условий и регрессий |
| 7 | [07_OPERATIONS_SECURITY.md](07_OPERATIONS_SECURITY.md) | Production, CI/CD, секреты, диагностика, rollout и rollback |
| 8 | [08_NEXT_ACTIONS.md](08_NEXT_ACTIONS.md) | Первый PR, блокеры и передача статуса |
| **9** | **[09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md)** | **Новый обязательный SLO: подходящие карточки примерно за 10 секунд после отправки голосовой записи** |

| **10** | **[10_IMPLEMENTATION_TZ.md](10_IMPLEMENTATION_TZ.md)** | **Актуальное рабочее ТЗ после заключительного аудита #375: обязанности, этапы, контракты, блокеры, критерии готовности** |
| 9 | [CODEX_START_HERE.md](CODEX_START_HERE.md) | Инструкция для Codex при получении задачи от разработчика |

## Исходные аудиты (не выбрасывать и не выдавать за текущую метрику)

- [audits/2026-10-25/PRODUCTION_REALITY_AUDIT.md](audits/2026-10-25/PRODUCTION_REALITY_AUDIT.md) — измерения и технические наблюдения Codex на 25.10.
- [audits/2026-10-25/AI_INTEGRATION_READINESS.md](audits/2026-10-25/AI_INTEGRATION_READINESS.md) — readiness/пробелы/SQL/авторизация/frontend/ASR/LLM.
- [audits/2026-10-25/AI_IMPLEMENTATION_SEQUENCE.md](audits/2026-10-25/AI_IMPLEMENTATION_SEQUENCE.md) — полный первоначальный подробный план 13 PR.
- [audits/2026-10-25/README.md](audits/2026-10-25/README.md) — происхождение отчётов, ограничения по evidence и machine summary.
- [archive/IMPLEMENTATION_PLAN_2026-10-25.md](archive/IMPLEMENTATION_PLAN_2026-10-25.md) — исторический подробный parser/data backlog.
- [archive/PARSER_DATA_AUDIT_2026-10-25.md](archive/PARSER_DATA_AUDIT_2026-10-25.md) — подробный парсерный аудит PR #373.
- [archive/README.md](archive/README.md) — когда использовать исторические материалы.

## Актуальный итог аудита #375 и статус реализации

**Разработка — READY_FOR_DEVELOPMENT. Production — BLOCKED.** Доступно создавать ADR/DTO, quota ledger, session и mock integration, новую схему фактов на disposable DB. Реальные DB coverage/freshness/source success, live provider latency/DPA и browser10s p95 пока не доказаны.

- [Рабочее ТЗ на реализацию](10_IMPLEMENTATION_TZ.md) — **основной документ разработчика**.
- [Заключительный аудит #375](https://github.com/antony502189-max/Ttest/pull/375) добавляет 5 отчётов на **отдельной ветке**, PR направлен в текущую docs ветку #374 и пока не слит.
- Первая задача Codex: **AI-01 ADR/contracts**, затем по отдельным PR AI-07 quota и AI-03/04 facts/queue, human review #373 и DBA read-only assessment. Полный код AI всё ещё **не реализован**.
- Не засчитывать slow-network, invalid zero-matches и provider errors как достигнутый голосовой card-render SLO; измерять честно согласно [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md).


## Самая короткая версия решения

- **Только недвижимость**; вакансий, маршрутов и новых геосервисов **нет**.
- Имеющиеся карточки, карта, внешние ссылки, TOP/paid boosts, галереи, цены и другие функции **остаются прежними**.
- Голос: **Groq Whisper Large V3**, после окончания записи; резерв — OpenAI GPT-Transcribe. Без live-ASR и без озвучки ответа.
- **Скорость — обязательное требование:** от Send завершённой записи до реально видимых актуальных подходящих карточек **p95 ≤10 секунд** на типовом трафике/нормальной сети; без обязательного подтверждения транскрипта. Требования и замеры — в [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md).
- Текст/диалог/извлечение фактов: **DeepSeek Flash** через backend. Проверять schema и evidence; LLM не пишет SQL.
- Поиск: существующие **FastAPI + PostgreSQL/PostGIS**; данные предварительно обогащаются в **отдельном** асинхронном worker.
- Квоты: **3 успешных AI-обращения в сутки у гостя / 200 у авторизованного**, reset **00:00 Europe/Madrid**, один голосовой запрос = один debit после успешного ответа (не два API-платежа).
- Сохранение поисков и уведомления — только после регистрации, на основе уже существующего SavedSearch/outbox.
- **Месячного денежного лимита API нет**. Лимиты размера/длительности/частоты, anti-abuse и observability обязательны.
- Продакшен и database snapshot от 25.10 **не обновляются автоматически** от появления документации в GitHub.

## Реальное состояние/ветки

На исходный аудит 25.10:
- `main` и наблюдённый production release: `1292c6807ece59999238bb31c80e09ef7e2c3212`.
- `planning/ai-voice-search-architecture` — план и решения. Не заменять этой веткой текущий main: она отстала от изменений платежей #372.
- [Parser PR #373](https://github.com/antony502189-max/Ttest/pull/373) — **ещё не слит** на момент подготовки этого handoff. Нужны review и безопасный перенос/интеграция.
- Публично доступно 1 163 listings (1 132 long-term, 31 holiday) в снимке аудита. **Это не total DB count**; прямого безопасного DB inventory не было.
- В production **нет готовых API Groq/DeepSeek, AI-таблиц, AI-лимитов или voice UI**. Текущий frontend/backend запрещает microphone policy и имеет 256 KiB общий request body limit.

**Приоритет №1:** не запускать интеграции наугад. Утвердить semantics/ADR, провести review #373 и безопасный read-only аудит настоящего каталога.

## Порядок безопасности

Только отдельные feature branches, небольшие PR и QA. Не изменять `main`, payments, работающий продакшен, секреты или данные без отдельного разрешения. Документационная ветка/PR не запускает автоматический деплой.

## Куда вносить изменения

В этой папке: решения, ADR, план, e2e-кейсы, статус и новые отчёты. Сам код AI — в существующих `backend/app/...` и `src/...` по отдельным PR, **не** внутрь документационной папки. Обновлять [08_NEXT_ACTIONS.md](08_NEXT_ACTIONS.md) после каждого принятого PR и не отмечать «сделано» без тестов/мерджа.
