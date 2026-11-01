# Пункт 6: рабочие правила первого текстового стенда

Дата: 2026-11-01. Ветка: `codex/post-merge-remediation`, существующий PR #403.
База переноса: `544aec333e858cf11fe48d46068a1a8e251d4398`.
Предыдущая изолированная работа сохранена локальным snapshot `8fbb4776`;
каноническая реализация теперь в ветке #403. Main/production не менялись.

## Результат

[Policy v1](../ai-search-developer/OPERATING_PRODUCT_POLICY.md) задаёт допустимые
данные/outbound, сроки хранения, отдельную freshness, восстановление операций,
лимиты и уточнения. Профиль явно включается только закрытым synthetic lab.

- Сессии: idle 24 ч / absolute 7 суток, max 3; bounded cleanup приватных intent
  отдельно от 30-дневных квитанций. Keyed create/reset FK сохраняется минимальной
  закрытой оболочкой; очистка не переоткрывает операцию и не списывает повторно.
- Redis: общий и subject inflight, IP/subject attempts, HTTP/read/bootstrap
  limits, отказ без memory fallback. Deadline text 15 с, HTTP 20 с.
- Prepared-proof age хранится отдельно, с привязкой к точной подписи v2.
  Source age берётся из успешной проверки исходной записи; пересборка proof не
  делает источник свежим. Cards/map/replay используют SQL guard до пагинации.
- При отсутствии проверенного покрытия — terminal unavailable без списания.
  Clarification/no-change/unsupported не меняют intent и квоту; повтор не
  вызывает модель. UI показывает фиксированные причины и неполноту покрытия.
- Обычное и административное удаление очищают также независимые AI saved
  snapshots и commands текущей схемы. Общий порядок блокировок не позволяет
  восстановить приватное состояние незавершённой операцией.
- Независимый зашифрованный deletion journal переживает rollback/restore БД;
  есть проверка цепочки, fresh checkpoint, binding UUID и pre-traffic replay.
  Отсутствующий/подменённый/повреждённый журнал блокирует запуск/restore.
- Maintenance запущен отдельным Compose service с restart policy, ограниченными
  транзакциями и повторными проходами backlog. Отдельный постоянный journal
  volume не входит в PostgreSQL backup. Ключ Compose только синтетический.
- Expand-only migration `0079_ai_operating_policy`; предыдущие миграции,
  оптимизированный proof v2 и утверждённый live intent corpus не переписывались.

## Проверки

Проверки выполнены локально без real provider вызовов и без чтения ключей:

| Проверка | Результат |
| --- | --- |
| Backend unit, без integration/isolated PG | 1657 passed, 17 skipped |
| Isolated PostgreSQL facts/quota/session + Redis | 637 passed, 1 skipped; один устаревший limiter-call assertion исправлен и отдельно прошёл |
| Повтор исправленного HTTP теста + keyed-command retention | 2 passed |
| Полный новый operating-policy файл после добавления decision regression | 17 passed |
| Real PostGIS AI cards/map/saved/HTTP/account suite + journal unit | 84 passed, 5 skipped; два найденных дефекта исправлены и перепроверены следующим запуском |
| Account erasure + source/proof freshness + saved review + journal после исправлений | 19 passed |
| Chromium AI home + saved collections, frontend с API mocks | 45 passed |
| Python mypy | 168 файлов, без ошибок |
| Ruff; TypeScript; production frontend build; i18n source guard | passed |
| Полная цепочка миграций в отдельной disposable PostGIS DB | head 0079 |

Числа отдельных запусков пересекаются, их нельзя складывать как уникальные тесты.
В исходном широком прогоне исправлены: ожидание дополнительного subject gate;
удаление независимых AI snapshots при admin erase; ожидаемый migration head.
Browser-моки не считаются end-to-end проверкой реального backend.
Пропущенные DB/browser cases требуют отдельного browser dist/config; это не
доказательство их прохождения. Проверка Compose запуска отмечается отдельно ниже.

## Что осталось до публичного продукта

Пункт 7: приёмка и инфраструктурные drills на точном release SHA, наблюдаемость
без приватного содержимого, подтверждённые backup/journal retention и restore
barrier в целевом окружении, binary rollback и быстрое отключение AI. ISSUE-004
остаётся OPEN: большой capacity этап пропущен владельцем, SLO gate не пройден.
Real-user outbound требует проверенной политики конкретного provider account;
узкое разрешение на synthetic intent eval и Flatio pilot её не заменяет.
Merge/main checks и публичное включение — отдельные решения.

Пункт 8: voice/ASR/microphone и rematch/delivery/уведомления — отдельные этапы,
не условие первого текстового стенда. До их приёмки capabilities остаются false.
