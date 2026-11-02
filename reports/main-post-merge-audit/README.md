# Материалы аудита main от 30 октября 2026

Основной отчёт: [MAIN_POST_MERGE_INTEGRATION_AUDIT.md](../MAIN_POST_MERGE_INTEGRATION_AUDIT.md).
Audited application SHA: `7d4c125574927181511c5f1bc7e201e20a8840a8`.

`evidence/` содержит компактную переносимую selection результатов, включая
неуспешные контролируемые воспроизведения. Полные исходные CI logs, PR patches,
JUnit, build logs и Git archive сохранены в `output/main-integration-audit/`
managed worktree. `test-counts.json` не следует суммировать как уникальные tests:
там есть пересекающиеся suites и повторы. Подсчёт завершённых выполнений описан
в `completed-executions.json`; skips и interrupted runs в него не входят.
В переносимой selection удалены только пробелы в концах строк; raw originals
сохранены в output. SHA256 manifest относится к UTF-8 тексту с LF, чтобы checkout
с Windows autocrlf не менял смысл проверки.

`reproduce_migrations.py` создаёт **новую** disposable
`ai_migration_test_main_audit` на local test PostgreSQL и специально не умеет
удалять существующую БД. Запускать только в собственной изолированной среде.
Ожидает exact Git archive в `/audit-src`, pinned dependencies и output mount
`/src/output/main-integration-audit`. Проверяет legacy records, command seed,
повторный upgrade, отказ downgrade и stricter schema-parity canary.

`map_transition.spec.ts` — воспроизведение гонки, которое до исправления
приложения должно падать. Для запуска в exact isolated source snapshot:

```bash
cp /src/reports/main-post-merge-audit/map_transition.spec.ts /audit-src/tests/audit_map_transition.spec.ts
cd /audit-src
VITE_ENABLE_MOCK_MODE=1 VITE_GOOGLE_MAPS_TEST_SDK=1 VITE_E2E_BYPASS_ONBOARDING=1 \
  node node_modules/@playwright/test/cli.js test tests/audit_map_transition.spec.ts --workers=1
```

Используется существующий repository Maps test SDK. Audit test доставляет idle
через microtask после route push, до применения нового React route state.
История URL в evidence показывает push без `dibujar`, затем camera replace с ним.
Application code при воспроизведении не изменён.

`run_fullstack.py` фиксирует использованный изолированный runner и его точные
тестовые настройки. Он предполагает уже подготовленный snapshot/npm/browser
runtime и собственные PostgreSQL/Redis/MinIO; это не universal installer.
Создаёт новую `ttest_fullstack`, не удаляет существующие DB. Negative provider
контролируемо возвращает пустой список; positive использует уже существующий
`scripts/fullstack_test_app.py`. Production validation остаётся одинаковой.

Созданные audit containers остановлены после сбора evidence; данные оставлены
в собственных stopped containers для воспроизводимости. Имена/image IDs —
в `evidence/container-identities.txt`. Shared containers и исходный dirty
checkout не останавливались/не изменялись. Audit network не связан с production.
Никакого deploy, push/merge, включения Pages, AI, ASR или provider не сделано.
