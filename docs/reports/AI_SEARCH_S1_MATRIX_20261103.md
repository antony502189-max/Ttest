# S1.1–S1.3 — матрица и merged-source проверки, 03.11.2026

База: `ece1632e2872240a36646ddf0b2518a027d67d84`, merged #404.
Ветка: `codex/ai-search-acceptance-matrix` в existing main-integration-audit worktree.
Чистота проверена до switch, root checkout не обновлялся и чужие изменения не включены.

Созданы [A1–A12 matrix](../ai-search-developer/AI_SEARCH_ACCEPTANCE_MATRIX_RU.md), JSON и runner с inventory/unit/mock-browser режимами; inventory включён в существующий frontend CI и artifact upload. Указаны существующие PostgreSQL/HTTP/full-stack/provider/capacity drivers и их пределы; они не запускаются автоматически. Прежний corpus24 не расширялся, gaps по языкам/полям зафиксированы.

Добавлены12 тестов ES/RU/EN × 320/390/768/1440: локализованные accessible names, один POST, empty result, отсутствие overflow, возврат фокуса и обычного фильтра. Код приложения не изменён.

## Evidence

| Проверка | Результат и предел |
| --- | --- |
| Targeted merged-source backend |177 PASS,4.03s; synthetic/MockTransport, до изменения tests/scripts |
| Matrix offline |339 PASS: intent115/facts143/quota15/voice18/saved26/operations22; перекрывается с177 |
| Существующие main browser contracts |63 PASS в первом полном прогоне; новые12 тогда упали на неоднозначном h3 selector в тесте |
| Новые A9 cases после исправления |12 PASS,22.9s; scoped heading и видимый existing manual panel |
| Итоговый единый matrix browser run |75 main +13 pairing PASS на окончательном тестовом source; raw logs/JSON сохранены |
| TypeScript |PASS на изменённом browser source |
| Exact merged-source GitHub |AI frontend [41646696117](https://github.com/antony502189-max/Ttest/actions/runs/41646696117) SUCCESS; combined facts/quota/sessions [41646696119](https://github.com/antony502189-max/Ttest/actions/runs/41646696119) SUCCESS |
| Остальной post-merge CI |Capacity safeguards/security/pages SUCCESS; Full audit IN_PROGRESS на snapshot. Это не итоговый общий PASS |

Runtime: Windows, существующий release-venv Python3.12.14, pytest9.1.1, pydantic2.13.4,httpx0.28.1; Node24.22.1, Playwright1.61.1, установленный Chromium. PYTHONPATH указывает на backend текущего worktree, APP_ENV=test. Первый запуск в `.audit-venv` Python3.13.17 не принят: отсутствовали зависимости. Ничего не устанавливалось.

Локальные логи и JSON: `output/ai-search-s1/`. Сохранённые воспроизводимые результаты/хеши: [evidence](ai-search-s1-20261103-evidence/). Первые ошибки новых тестовых selectors и collection failure не выдаются за дефекты продукта или успешную проверку. Числа пересекающихся прогонов не суммируются.

## Граница результата

S1 завершён как подготовка рабочей базы, инвентаризации и целевых проверок. A1–A12 остаются открытыми в применимых частях. Это не новый LIVE, не публичный выпуск, не capacity или production certification. Настоящий journal не читался/не сбрасывался;52/$0.575120reserved остаётся исторической записью. Не было paid calls, real-user outbound, уведомлений, ingestion/backfill или больших benchmarks.

Далее S2.1 по [единому плану](../ai-search-completion-plan.md).
