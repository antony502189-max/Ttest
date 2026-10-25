# Архив аудита Codex от 25 октября 2026

Эти три отчёта скопированы из предоставленного пользователем `ai-production-readiness-2026-10-25.zip` без смысловой переработки и размещены здесь для удобного чтения в GitHub:

1. [PRODUCTION_REALITY_AUDIT.md](PRODUCTION_REALITY_AUDIT.md)
2. [AI_INTEGRATION_READINESS.md](AI_INTEGRATION_READINESS.md)
3. [AI_IMPLEMENTATION_SEQUENCE.md](AI_IMPLEMENTATION_SEQUENCE.md)

Также: [audit-summary.json](audit-summary.json) — **сокращённая безопасная редакционная сводка на основе отчётов**, не оригинальный `audit-summary.json` из ZIP. Отдельный `evidence/observations.json` из исходного архива в этот публичный репозиторий **не переносился**: подробные операционные доказательства держать в контролируемом приватном хранилище, не публиковать без повторной security/privacy проверки. Оригинальные JSON и SHA-256 manifest остаются в предоставленном пользователем исходном ZIP.

**Не считать сводку machine-identical оригинальному JSON.** Для формальных выводов читать оригинальные 3 MD и использовать evidence labels/refs E01… из них; при необходимости запросить у владельца архив в закрытом канале.

Полные отчёты содержат ссылки на соседние исходные JSON, которых в публичном handoff может не быть. Это ограничение deliberate, а не отсутствие проверок исходного автора.

## Как читать статусы

- `VERIFIED_PRODUCTION`: моментное read-only измерение 25.10, **не** мониторинг.
- `VERIFIED_CODE_MAIN`: код на SHA audited main.
- `VERIFIED_BRANCH_ONLY`: находится только в незлитом PR/ветке.
- `DOCUMENTED_ONLY`: утверждение в документации.
- `INFERRED`: архитектурный вывод.
- `BLOCKED / UNKNOWN`: реальных измерений нет.

**Особенно важно:** public listings count 1 163 != строкам БД; configured 7 sources != successful 7 sources; 4 active synthetic parser fixtures != production coverage; UTC timestamps и платежи имеют собственную свежесть.

## Безопасность

В GitHub не добавлять full prod env, закрытые snapshots, пароли, webhook signing keys, raw cookies/logs/HTML и транскрипты реальных пользователей. Тесты из аудитных файлов выполнять только после code review и в разрешённой среде.
