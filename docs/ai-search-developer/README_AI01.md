# AI Search — AI-01 contracts

Это отдельный **документационный PR AI-01**, подготовленный от актуального `main` с платежами #372. AI Search ещё не реализован. Статус контрактов **PROPOSED / REVIEW_REQUIRED**; rollout **BLOCKED**.

Начать с [ADR/contracts](adr/AI-01_CONTRACTS.md), затем [DTO examples](contracts/dto-examples-v1.json), [acceptance scenarios](contracts/acceptance-v1.json), [validation](AI-01_VALIDATION.md) и [next actions](08_NEXT_ACTIONS.md).

Основной handoff живёт в ещё открытом [PR #374](https://github.com/antony502189-max/Ttest/pull/374): [README](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/README.md), [Product](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md), [Implementation TZ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md), [план AI-01…AI-13](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/05_IMPLEMENTATION_PLAN.md).

Не импортировать planning branch вместо current main; [parser #373](https://github.com/antony502189-max/Ttest/pull/373) и [gap-closure #375](https://github.com/antony502189-max/Ttest/pull/375) остаются отдельными review. Не переносить сюда исторические audits и их измерения как новые результаты.

Ни migrations, ни endpoints, ни paid APIs, ни production/staging integrations этим PR не вводятся. После review ADR следующий независимый кодовый этап — AI-07 quota ledger на disposable PostgreSQL, далее AI-08 sessions. Real catalog inventory, privacy и staging browser SLO требуют собственных gates.
