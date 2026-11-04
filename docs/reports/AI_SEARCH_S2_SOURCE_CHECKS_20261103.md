# S2.2–S2.3 — source check, freshness и proof, 03.11.2026

Рабочая база `471843e8c68ff13ef8ff29421ac70dbb70a936c0` поверх main `ece1632e2872240a36646ddf0b2518a027d67d84`.
Изменения связаны с A3/A11 (текущие данные) и A4 (нет пригодного покрытия — нет debit).

## Исправленное поведение

1. После 403/blocked,429/timeout/temporary_error или unknown direct check оставляет manual source active.
   Раньше AI freshness учитывал только ещё недавний last_success_at и мог считать такой источник пригодным.
   Теперь last_checked_at новее последней успешной проверки блокирует AI evidence до успешной перепроверки.
   Audit и SQL guard согласованы; guard действует перед count/LIMIT и агрегацией карты.
2. Положительный presence probe прежде продлевал last_success_at без захвата/сравнения detail payload.
   Теперь он обновляет last_seen/state health, а возраст сохранённого содержимого продлевает detail import.
   Presence probe может снять отказ source health, но не оживить stale content. Reconcile/QueryProofs.prepare
   также не продлевают source freshness. Схема БД и публичные capabilities не менялись.

SQL regression сначала воспроизведён на старом guard:3 expected FAIL (blocked/temporary_error/unknown).
После исправления он проходит. Полная PostGIS integration использует наследуемый реальный HTTP status
classifier с fixture-only URL policy и MockTransport, настоящий reconcile_source и сохранённые metadata:
403/429/timeout/unknown → manual cards4, AI cards/map0, SOURCE_COVERAGE_UNAVAILABLE, ledger без debit;
active recheck при свежем content → AI3; устаревший content +active recheck +proof prepare → AI0/manual4.

## Проверки

| Проверка | Результат / применимость |
| --- | --- |
| Исходные queue/worker/quality/proof tests |100 PASS до исправлений |
| Весь ai_facts_pg |296 PASS /1 opt-in pilot SKIP; до окончательного отделения presence от content |
| Verified cards/map +freshness +external removal |78 PASS; до окончательного presence/content изменения |
| Окончательный SQL quality module |8 PASS, включая все3 новые regression cases |
| Окончательные full-schema freshness/removal |32 PASS, включая4 новых HTTP/error/recovery/stale cases |
| Unit quality/import lifecycle/source classifier |114 PASS /1 opt-in real-source SKIP; наборы пересекаются |
| Ruff, mypy, CI selection |Ruff changed files PASS; mypy172 перед presence split, финальные2 app files PASS; CI YAML/selection PASS |

Полная historical migration chain применена только к новой disposable loopback БД, head0079.
Изолированные facts tests создают/удаляют свои схемы. Прежний закрытый lab и другие контейнеры не изменялись.
Runtime: Windows/Python3.12.14/pytest9.1.1/SQLAlchemy/asyncpg+psycopg, PostgreSQL16/PostGIS3.4.
JUnit warning о record_property/xunit2 сохранён; это предупреждение reporter, assertions прошли.
Пропущены только явно opt-in реальный source smoke и Flatio pilot dataset — они не разрешались и не запускались.
Ошибка первого нового integration fixture (несуществующее map.total) исправлена на map.items до принятого финального прогона.
Суммировать overlapping/промежуточные counts нельзя; точные результаты, input hashes и исходные JUnit/logs — в
[evidence](ai-search-s2-checks-20261103-evidence/validation.json).

Новый integration file включён в существующий combined facts CI и A1–A12 matrix. Main ece1632e:
все6 post-merge workflows теперь SUCCESS, включая Full audit; это проверка прежнего main, не новых изменений.
CI нового head и deployed runtime не подтверждены этим отчётом.

## Незакрытая часть

S2 не завершён. Нужны разрешённое реальное покрытие/измерения, source-specific content refresh,
bounded coordinator для existing observe/worker/reconcile/proof primitives, supervision и эксплуатационная проверка.
Исторический last_success_at мог быть продлён старым presence probe; новые изменения не переаттестуют эти timestamps.
Перед приёмкой реального каталога нужен новый разрешённый detail snapshot. Автоматический backfill не включён.
При отсутствии content refresh AI закономерно исключает источник после TTL; успешная проверка существования
объявления больше не скрывает этот пробел. Provider/data/performance/release gates остаются открытыми.

Нет paid/model calls, real source requests, outbound пользователям, чтения/сброса настоящего budget journal,
production изменений, crawling/backfill или больших capacity benchmarks.
Далее S2.2 по [единому плану](../ai-search-completion-plan.md).
