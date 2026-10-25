# Инструкция для Codex / разработчика

## Правила до любой реализации

Прочитать [README.md](README.md) и полностью [01_PRODUCT_SPEC](01_PRODUCT_SPEC.md), [02_PRODUCTION_BASELINE](02_PRODUCTION_BASELINE.md), [03_ARCHITECTURE](03_ARCHITECTURE.md), [05_IMPLEMENTATION_PLAN](05_IMPLEMENTATION_PLAN.md).

**Single source of truth:** прямые решения владельца в `01_PRODUCT_SPEC.md` выше старых customer review/AI-roadmap вопросов. Аудит датирован; проверять актуальный GitHub and production независимо.

## Обязательная актуальная точка входа

**Сначала прочитать [10_IMPLEMENTATION_TZ.md](10_IMPLEMENTATION_TZ.md)** и [заключительный аудит PR #375](https://github.com/antony502189-max/Ttest/pull/375). Статус `READY_FOR_DEVELOPMENT`, **не** `READY_FOR_PRODUCTION`. Установить actual main/PR #373/#374/#375 HEAD прежде чем писать код. Ни один новый общий audit не нужен.

Первый PR **AI-01 ADR**: версии intent/facts/patch, provenance, unknown/conditional/conflict, occupancy>=N (старое equality нетронуто), unchanged TOP, session/cursor, 3/200 Europe/Madrid transactional quota (включая успешные 0 matches), idempotency/fencing, UX one Send→cards и отдельные metrics zeros/errors. Background alerts не списывать с interactive quota — **предложение**, требующее ADR/одобрения. Нет read-only DB — не мешает DTO/mocks/disposable ledger, но запрещает утверждения об истинном coverage/backfill/readiness.

Все кодовые изменения потом малыми PR от **актуального main**, не от устаревшей planning в обход payment #372. Никаких production миграций/merge/deploy/provider calls без разрешения.


## Безусловное требование по скорости и UX

От Submit завершённой голосовой записи до **нарисованных подходящих и актуальных карточек** — целевой **p95 ≤10 секунд**, проверять настоящим browser E2E, включая upload, Groq, DeepSeek, PostgreSQL и рендер; статус **не реализовано**. Не заставлять пользователя дополнительно подтверждать распознанный текст перед первой выдачей; исправление текста должно оставаться возможным без этого препятствия. Нельзя делать live crawling или LLM-per-card ради «актуальности». Если сеть/провайдер плохие — transparent timeout/fallback/error, без списания quota при system failure. Обязательно изучить [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md) до разработки API/frontend.

## Каждый новый таск

1. Пересверить актуальный `main`, feature/planning HEAD и CI. PR #373 мог изменить состояние с 25.10.
2. Точно определить scope одного PR и затрагиваемые компоненты.
3. Проверить существующую реализацию прежде чем писать новую (особенно importer, ListingRoomDetails, Redis, SavedSearch).
4. Уточнить подтверждённые DB факты только через специально разрешённый read-only канал.
5. Сначала regression tests, потом минимальное изменение.
6. Не ломать existing card DTO, map, TOP, Stripe, auth, price cap, promotions, gallery и imports.
7. Код, миграции и docs — только в отдельной ветке. CI запускать по необходимости; не деплоить автоматически.
8. Отчёт: реальные команды/tests/result, commit SHA, PR, blocker/unknown, что изменилось в поведении.

## Нельзя

- Продакшен deployment / merge без явного запроса.
- Изменять секреты, env, Redis/DB production, run crawler/backup/rollback/clear.
- Писать DeepSeek output напрямую как подтверждённый факт без evidence.
- Пропускать ₽/€ цифры, отрицания и условные разрешения.
- Доверять deprecated/docs-only assumptions.
- Автоматически ограничивать monthly provider spend суммой.
- Добавлять вакансии, маршруты, POI, live-ASR или TTS.
- Отправлять raw HTML/контакты арендодателей в внешние модели.

## Где искать доказательства

[Основной архив аудита](audits/2026-10-25/README.md), [внешний исторический parser план](archive/README.md), GitHub PR #373 и текущее `backend/app/...`.

## Первое действие

PR-AI-01 — ADR/data intent contracts, без runtime. После этого — DBA readonly coverage и code PRs, разделённые по таблице в [05_IMPLEMENTATION_PLAN](05_IMPLEMENTATION_PLAN.md).
