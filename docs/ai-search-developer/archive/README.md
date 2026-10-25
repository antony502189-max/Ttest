# Исходные parser/AI планы и аудит (историческая копия)

- [IMPLEMENTATION_PLAN_2026-10-25.md](IMPLEMENTATION_PLAN_2026-10-25.md) — полный первоначальный backlog parser/data/enrichment, включая ещё не согласованные исторические предложения.
- [PARSER_DATA_AUDIT_2026-10-25.md](PARSER_DATA_AUDIT_2026-10-25.md) — матрица 9 адаптеров, fingerprint/regression/evidence/CLI, тесты PR #373.
- [fixture-data-audit.json](fixture-data-audit.json) — **синтетический** отчёт на 4 active / 5 total snapshots, не измеренные production данные.
- [Parser PR #373](https://github.com/antony502189-max/Ttest/pull/373) — источник реализации, проверить актуальный merge/CI. Snapshot parser audit на дату PR, не production coverage.
- [Основная ветка planning](https://github.com/antony502189-max/Ttest/tree/planning/ai-voice-search-architecture/docs/ai-voice-search) — исторические заказчик/архитектура документы.

Эти материалы **справочные**, не меняют более поздние решения владельца в [../01_PRODUCT_SPEC.md](../01_PRODUCT_SPEC.md): убрать вакансии, карты/маршруты, live ASR, TTS; сохранить cards/TOP; 3/200 midnight Madrid, no monthly spending cap.

Нельзя автоматически отмечать старые [ ] выполненными только потому что материал скопирован в GitHub. Реальные реализации проверять по SHA, коду и тестам.
