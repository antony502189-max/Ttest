# 08 — AI-01 execution log, 2026-10-26

Этот файл — новый execution log на `main`, где handoff folder отсутствовал. [Исторический журнал #374](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/08_NEXT_ACTIONS.md) сохраняется в своей ветке; при merge #374 объединить оба журнала, не заменять историю. Остальные handoff документы не копируются.

## Выполнено

- [x] Fetched current main `1292c6807ece59999238bb31c80e09ef7e2c3212`, подтверждён payment #372.
- [x] Прочитаны утверждённый Product, рабочее ТЗ, PR plan и next actions на handoff `d086fec3f0c4286d66493082982e2ac55a14d174`.
- [x] Сопоставлены planning `f203807d4507f68b34cd4407e326b3bc671a3552` и #373 `fcae378d9dbbc8447f18df150327180f6f2c8231`; #373/#374/#375 открыты. BASE-373 human review этим не выполнен.
- [x] Подготовлены AI-01 ADR, versioned ListingFact/SearchIntent/IntentPatch/operation/cursor examples, synthetic negative scenarios и DST fixtures.
- [x] Определены provenance/conflicts/legacy defaults, hard compatibility, available capacity, current TOP, cursor invalidation, quota lifecycle и crash/fencing semantics.
- [x] Разделены owner-approved правила и **предложения** для clarification debit, background alerts, guest transfer, TTL/leases/audio limits и owner precedence.
- [ ] Human review и принятие AI-01 contracts; статус **PROPOSED**, runtime этап не завершён.

## Delivery record

Ветка: `codex/ai-01-search-contracts`, base `main` на `1292c680`. Final SHA и PR URL — в GitHub PR, который содержит этот файл (самоссылочный final SHA не записывается в собственный commit). Итоговый отчёт в [AI-01_VALIDATION.md](AI-01_VALIDATION.md); все файлы под `docs/`, application source/CI/deploy не меняются. Миграции/feature flags/API before→after: отсутствуют. Среда — только локальный offline checkout.

## Следующие отдельные PR

1. Review ADR/DTO: согласовать taxonomy, owner/source resolver precedence, clarification/alerts business policy, guest transfer/retention/anti-abuse limits. Не считать рекомендации утверждёнными решениями владельца.
2. После review AI-07: authoritative PG reserve/finalize/release, DST/concurrency/idempotency/failure tests на disposable PG; затем AI-08 CAS sessions. Ни paid API, ни real production DB для этого не нужны.
3. BASE-373: human review и selective port parser foundation на current main, включая payment #372/import/gallery regressions. Не merge planning целиком.
4. AI-03/04: additive facts/projection + durable fenced queue/resolver, fake providers. Индексы/backfill требуют реального AI-02 audit.
5. DBA: отдельный approved read-only role/replica для coverage/source health/SQL plans. Реальные проценты, свежесть и ёмкость пока **UNKNOWN**.
6. Privacy/DPA/provider account gates перед outbound; AI-09+ query/UI только после зависимостей. AI-13: approved goldset и staging browser p95<=10s с error rate, separate zero-result latency, TOP/Stripe/cards/map/media/favorites/saved-search regressions.

Manual production search остаётся текущим кодом. AI runtime/10s SLO **не реализованы и не измерены**. Merge, live staging, paid pilot и production deployment требуют отдельных разрешений из ТЗ.
