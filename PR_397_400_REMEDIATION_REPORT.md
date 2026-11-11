# Исправления по ревью PR #397–400

28 октября 2026, Europe/Moscow. Репозиторий: [Ttest](https://github.com/antony502189-max/Ttest).

**Статус: R-01–R-05 исправлены; актуальная цепочка #402 → #397 → #398 → #399 → #400 имеет свежий зелёный CI и готова к повторному owner review как выключенная основа.** Merge, deploy и публичная активация не выполнялись. Все PR сохранены draft.

## Изменение исходного плана

При повторной проверке обнаружено, что #396 уже merged в main: merge commit `883a03c64edd8e1a5da7e4df49deeaeb2fe7488b`, исходный HEAD `21f1f0ef3c0177d87cf6ff60e27ddcfdb01fd8bb`. Поэтому исправление наследуемого R-02 вынесено в новый [корректирующий PR #402](https://github.com/antony502189-max/Ttest/pull/402) от актуального main. Закрытый #396 не переписывался, main не менялся. #397 retargeted на #402.

Фактический порядок будущего review/merge: **#402 → #397 → #398 → #399 → #400**. После каждого будущего merge/retarget необходима повторная проверка актуальных refs/checks; текущий результат не разрешает merge или активацию.

## Точные ревизии

| PR | Предыдущий HEAD | Новый HEAD | Актуальный parent |
|---|---|---|---|
| [402](https://github.com/antony502189-max/Ttest/pull/402) | Новый corrective PR после merged #396 | `d1a33ab940a33385af02ad777cfafa2c1b8ab0da` | main `883a03c64edd8e1a5da7e4df49deeaeb2fe7488b` |
| [397](https://github.com/antony502189-max/Ttest/pull/397) | `bc9b8b1de6012e70f138f1d6d591ee93cce87fd3` | `8cee67a2d2c6c75b8a2ff2a1cc88c8e2a91f0f53` | #402 |
| [398](https://github.com/antony502189-max/Ttest/pull/398) | `02d7029161677a7a1076899c2f678e912cf6f35b` | `0859453d7d37e2023652e2e6a58bbe48517c9119` | #397 |
| [399](https://github.com/antony502189-max/Ttest/pull/399) | `5d3a2a362d384e3a6af1e3884d5e9a273251366c` | `d91f3bb03c4c39510fad0e0e99307a2cd3848f39` | #398 |
| [400](https://github.com/antony502189-max/Ttest/pull/400) | `df9653aaa8ee95658a6ad56a74b91f773c676fd9` | `0682c990c690ee1455b6810d155952bac99dd313` | #399 |

Новые production/test commits: `d1a33ab9` (terminal recovery), `0859453d` (unused seeds), `d91f3bb0` (voice budgets), `0682c990` (same-connection snapshot read). Обновление стека выполнено обычными merge commits, без force-push и без замены child tree целиком.

## Что исправлено

**R-02 — terminal recovery (#402, адаптация нормализованной metadata в #398).** Подтверждённый terminal operation очищает pending независимо от GET editable session. Недоступный диалог показывает явное действие начала нового диалога; старые text/session/version/key не отправляются автоматически. При ambiguous network failure и reserved/running ответах сохраняется точный replay key/payload; reset и редактирование до разрешения неопределённости заблокированы. Успешные original cards не зависят от refresh editable session. В #398 committed metadata по-прежнему проверяется по result ref/hash/session/version/count: ошибка metadata не показывает неправильно подписанные новые cards и не восстанавливает terminal pending. Новый диалог очищает старые results/map/mode/text и требует нового явного mode choice. Счётчик quota не обнуляется.

Регрессии: terminal SESSION_EXPIRED, expired guest (GET404), successful replay после lost response с истёкшей editable session, истёкшая committed-result metadata, новый session ID/key/version0 после явного reset; прежние running/ack-loss, original-result labels и metadata mismatch tests сохранены.

**R-03 — abandoned initial seeds (#398).** cleanup_unused принимает только version0 и известные ai-search.v1/rental.v1 с точным criteria {}, либо единственным hard rental_mode long/holiday. Произвольные nonempty/soft/edited criteria не удаляются. Сохранены aware past cutoff, лимит 1–1000, сортировка, skip-locked, NOT EXISTS quota requests и results. Не добавлялся worker или новая retention policy.

Новый настоящий PG regression охватывает empty/long/holiday, active rows, версии/редактирование/soft seeds, reserved/running/failed/succeeded audit references, отдельную result-reference защиту, batch и locked rows. Для независимой проверки result guard используется явно синтетическое альтернативное session binding audit row; audit/result rows не удаляются cleanup.

**R-04 — voice total deadline (#399).** Собственный monotonic deadline охватывает reserve/claim, replay reads, providers, candidate query, cleanup и atomic finalize. HTTP deadline может только сократить бюджет. Failure/cancellation cleanup получает лишь оставшийся бюджет. При его исчерпании вызов выдаёт TimeoutError либо сохраняет external CancelledError; durable reservation/fence остаются для штатного recovery. Отдельного неограниченного cleanup allowance нет. Finalize и ack uncertainty остаются вне speculative-release handler, транзакционная атомарность session/result/debit сохранена.

Настоящие PG tests удерживают quota-day FOR UPDATE после ASR/intent timeout и cancellation с/без HTTP budget, требуют завершения до снятия блокировки, затем проверяют recovery, stale fence и exact-key replay без повторных provider calls/debit. Дополнительные tests: finalize timeout до commit и после committed debit/lost ack — release не вызывается в обоих случаях. Сервис остаётся offline/injected; public voice HTTP endpoint не добавлен.

**R-05 — nested checkout (#400).** SearchSessions.result делегирует общему result_in_transaction reader. RegisteredAISearches.save использует его на том же AsyncSession/connection, где уже взяты collection lock и cap. Общими остались ownership, session expiry, schema/vocabulary, intent session/version/hash проверки; cap/write transaction не разделялась.

Регрессии: pool_size=1/max_overflow=0; pool_size=2 с одним занятым connection; SQLAlchemy checkout instrumentation подтверждает один checkout на save. Три конкурентных разрешённых AI saves проходят на обоих размерах. Конкурентные AI/manual saves при cap=1 дают ровно один успех. На pool1 проверены foreign owner, expired session, blocked/deleted user, corrupt hash/schema/version binding; отсутствие новых saved rows/ledger rows при отказе.

**R-01 — актуальный stack и конфликт.** Последовательно включены новый corrective parent и финальные #395 fixes e68a47e8. Сохранены private422 MapView bounds, одна компиляция hard plan, общий public verified_intent_predicate API, dense/unverified additions и все saved/card/map parity tests. Конфликт helper в backend/tests/integration/test_ai_verified_cards.py разрешён объединением параметров vocabulary, count и positions. AST-проверка подтвердила, что все имена тестов из исходного #400 и исправленного parent сохранены (18 named tests в файле).

## Локальная проверка

Работа выполнена в новой managed worktree:
`C:/Users/HONOR/.codex/worktrees/ai-stack-remediation/Ttest`, локальная ветка `codex/ai-stack-remediation-review`, HEAD соответствует #400.

PostgreSQL16/PostGIS3.4: только disposable loopback container `ttest-pr397-400-audit-db`, порт 127.0.0.1:55479. PG/facts tests создавали случайные schemas в ttest_test. Для полной исторической migration chain создана отдельная новая `ai_quota_test_remediation`. Application/staging/production DB не использовались.

Python: существующий audit-venv Python3.13.17 с pinned backend constraints, код текущей worktree задан через PYTHONPATH. Frontend: успешный **npm ci** с неизменённым package-lock.json; React19.2.7, Vite8.3.5, Playwright1.61.1, TypeScript6.0.3 — installed versions совпадают с lock. Ограничение зависимостей предыдущего аудита устранено.

| Проверка | Результат | Лог в C:/Users/HONOR/AppData/Local/Temp/ttest-remediation-npm/ |
|---|---|---|
| Sessions/HTTP после R-03 | 32 passed | sessions-fixed.log |
| Voice/ASR после R-04 | 110 passed | voice-fixed.log |
| Saved/session focused | 55 passed; затем усилен small-pool cap test до cap=1 и пройден в расширенном прогоне | saved.log, combined-pg.log |
| Все backend units, not integration | 1403 passed, 15 skipped, 864 deselected | units.log |
| ai_search_pg + ai_facts_pg + HTTP/ASR/saved boundary | 528 passed, 1 optional Redis skip, 1 Windows setup error; ошибочный тест отдельно повторён успешно | combined-pg.log, pg-error-rerun.log |
| Повтор ошибочного старого minPrice test | 1 passed | pg-error-rerun.log |
| Полная историческая migration chain до0072 + alembic check | Success; No new upgrade operations detected | migration.log, migration-check.log |
| Полная PostGIS schema: verified cards, HTTP, saved parity, gallery | 59 passed | fullschema.log |
| Финальные AI/ordinary-map Playwright contracts | 25 passed | browser-final.log |
| Настоящий loopback Chrome guest-cookie/CORS | 1 passed | real-browser.log |
| Ruff app/tests, mypy app, pip check | Success; 153 source files; requirements consistent | mypy.log и вывод команд |
| TypeScript, mock и production Vite build | Success | build-398.log, build-production.log |
| Production bundle security, i18n, dependency audit | Success | dependency-security.log и вывод команд |
| Frontend lint | Exit0, существующие warnings вне исправленных путей | frontend-lint.log |
| Git diff check, ancestry, migration immutability, сохранность обоих test sets | Success | Вывод команд/refs/remediation |

Counts пересекающихся suites не суммируются в число независимых проверок. Расширенный PG run **не назван полностью зелёным**: Windows Proactor/asyncpg setup одного существующего minPrice test получил OSError WinError121 (semaphore timeout), без assertion failure. Изолированный повтор того же node дал 1 pass. Первый small targeted PG test при разработке ошибочно пытался удалить request, защищённый FK; regression исправлен так, чтобы audit row сохранялся. Первый voice regression использовал слишком малый общий бюджет30ms для нового reserve-inclusive контракта; исправлен на validated allocation с достаточным временем входа в query. Итоговые targeted/CI runs проверяют исправленные тесты.

Первый pinned Playwright запуск не смог стартовать отсутствующий bundled Chromium. Финальные локальные tests выполнены установленным Chrome с pinned Playwright через static mock preview; это не проверка настоящего Google Maps SDK/сети. Временный preview config сохранён рядом с логами. Linux CI отдельно использует pinned Chromium и npm ci.

## GitHub CI на новых HEAD

Все нижеперечисленные runs созданы после исправлений для новой комбинации head/base, а не унаследованы из старого аудита.

| PR | Checks | Runs |
|---|---|---|
| #402 | 8 success, 2 intentional visual skips | [Frontend40661457263](https://github.com/antony502189-max/Ttest/actions/runs/40661457263), [Security40661457291](https://github.com/antony502189-max/Ttest/actions/runs/40661457291), [Payment40661457253](https://github.com/antony502189-max/Ttest/actions/runs/40661457253), [Full40661457519](https://github.com/antony502189-max/Ttest/actions/runs/40661457519), [Production40661457269](https://github.com/antony502189-max/Ttest/actions/runs/40661457269), [Mobile40661457493](https://github.com/antony502189-max/Ttest/actions/runs/40661457493), [Source40661457355](https://github.com/antony502189-max/Ttest/actions/runs/40661457355), [Capacity safeguards40661457268](https://github.com/antony502189-max/Ttest/actions/runs/40661457268) |
| #397 | 3 success | [Frontend40661511962](https://github.com/antony502189-max/Ttest/actions/runs/40661511962), [Security40661512005](https://github.com/antony502189-max/Ttest/actions/runs/40661512005), [Payment40661511970](https://github.com/antony502189-max/Ttest/actions/runs/40661511970) |
| #398 | 5 success | [Combined40661967816](https://github.com/antony502189-max/Ttest/actions/runs/40661967816), [Quota40661967849](https://github.com/antony502189-max/Ttest/actions/runs/40661967849), [Frontend40661967841](https://github.com/antony502189-max/Ttest/actions/runs/40661967841), [Security40661967873](https://github.com/antony502189-max/Ttest/actions/runs/40661967873), [Payment40661967834](https://github.com/antony502189-max/Ttest/actions/runs/40661967834) |
| #399 | 4 success | [Combined40662752281](https://github.com/antony502189-max/Ttest/actions/runs/40662752281), [Quota40662752229](https://github.com/antony502189-max/Ttest/actions/runs/40662752229), [Security40662752445](https://github.com/antony502189-max/Ttest/actions/runs/40662752445), [Payment40662752241](https://github.com/antony502189-max/Ttest/actions/runs/40662752241) |
| #400 | 5 success | [Combined40663674376](https://github.com/antony502189-max/Ttest/actions/runs/40663674376), [Quota40663674421](https://github.com/antony502189-max/Ttest/actions/runs/40663674421), [Frontend40663674706](https://github.com/antony502189-max/Ttest/actions/runs/40663674706), [Security40663674360](https://github.com/antony502189-max/Ttest/actions/runs/40663674360), [Payment40663674403](https://github.com/antony502189-max/Ttest/actions/runs/40663674403) |

GitHub run metadata подтверждает актуальные HEAD/base пары. Fetched live merge refs дополнительно сравнены по Git tree с review HEAD; все пять совпадают:

| PR | Live merge ref SHA |
|---|---|
| #402 | `5e7045010a83e4fdf17b0824aee35f16864e53b4` |
| #397 | `85bf4c24267e4ecb8fc85e4363d445c309825de8` |
| #398 | `cc346d64e37b81b4c6ee231da5a95436914b0b21` |
| #399 | `a8a17097390e301825e06d92598ffd0656d084a4` |
| #400 | `85639c5fad47865764183950167d6310f15ab280` |

## Готовность и оставшиеся ограничения

#402/#397/#398/#399/#400: исправления готовы к повторному owner review как выключенная основа; все актуальные workflows завершились success (для #402 два специализированных visual jobs ожидаемо skipped). Draft сохранён. Green CI и этот отчёт не являются отправленным GitHub approval/review.

No-op downgrade0072 сохранён как существующая binary rollback policy. Ни одна released migration и ни один snapshot ради downgrade roundtrip не изменены. Rollback должен использовать прежний binary при сохранённом migration stamp; физический downgrade→upgrade roundtrip не заявляется.

Представительные SQL EXPLAIN/load/cancellation измерения и approved capacity budgets (R-01 из #395), реальная source freshness/coverage, privacy/consent/retention, настоящие providers/ASR, production ingress/logging/abuse, DDL lock rehearsal на репрезентативных данных и будущая notification delivery lifecycle остаются отдельными gates. Функциональные tests и capacity smoke safeguards их не закрывают. Реальные Google SDK/network, физические устройства, screen readers и полный DB TCP-disconnect matrix не проверялись. Local Redis не запускался; его проверка выполняется в CI.

Исходный checkout C:/Users/HONOR/Documents/Codex/Ttest не переключался. Пользовательское deploy/manual-production-runner.sh и старые untracked artifacts/build directories сохранены и не включены в commits. Старый полный audit report не изменялся. Новый remediation report — отдельный локальный artifact. Комментарии/сообщения людям и GitHub reviews не публиковались; обновлены только разрешённые PR descriptions/refs и создан corrective draft402. Ничего не merged и не deployed; публичные AI/provider/ASR/notifications не включались.


Финальная проверка refs/checks: main остался 883a03c6; описания всех пяти рабочих PR обновлены. Тестовый контейнер остановлен, данные сохранены. Изолированная worktree чистая; результаты и логи доступны по указанным путям.


Финальный combined CI #400 (job122732686643) фактически checkout live merge ref85639c5fad47865764183950167d6310f15ab280, дерево которого совпадает с HEAD0682c990. В полном скачанном логе: 1411 units passed / 7 skips, 719 focused PG/contracts passed, 59 full PostGIS passed, 1 real Chromium passed; Ruff, mypy153 и migrations/alembic check success. Эти suites пересекаются. Лог сохранён в C:/Users/HONOR/AppData/Local/Temp/ttest-remediation-npm/github-job-122732686643.log; snapshots CI/head/base — github-remediation-evidence.json в той же папке. Local WinError121 на Linux CI не повторился.


## Уточнение полного порядка с учётом #401

Повторно проверено 28 октября 2026 по live GitHub metadata, heads, merge refs и CI. #401 (Avoid full-catalog source scans in AI proof verification, HEAD11fb5f40700850a0a13432463904ee2d99c9edfa) — отдельная ветка codex/ai-map-capacity с target main. Она не является parent #402–400 и не включена в итоговый #400. Её сохранённый merge ref0a88f7fb2053e855efffdc7634d29aa74c7cfd9a ещё построен на старом main e50f96a5, до merge #396. Git merge-tree с live main883a03c6 и с новым #400 конфликтов не показал; это проверка слияния, не функциональная проверка объединённого дерева.

Полный рекомендуемый порядок интеграции: **#402 → #397 → #398 → #399 → #400 → #401**. Жёсткие зависимости задают первые пять PR; размещение независимого #401 последним сохраняет подготовленный зелёный stack и позволяет отдельно проверить SQL-оптимизацию на полном объединённом main. После каждого merge ребёнок должен быть retargeted на main с актуальными refs/checks. #401 технически может идти раньше, но тогда нужно обновить и перепроверить зависящий от main stack.

#401 сейчас не готов считать зелёным: 9 workflow success, Mobile validation40655842612 failure. Job122706550742: 164 passed, 1 failed; tests/mobile-location-map.spec.ts:179, сценарий320px, timeout60000ms при закрытии occupant dialog на строке187. Причина флаки/регрессии не установлена этим read-only уточнением. Перед слиянием #401 нужны обновление от будущего актуального main, устранение/диагностика сбоя и свежий полный CI. Ранее написанное в его description Fresh CI pending устарело.

Capacity gate остаётся открытым: масштабные измерения после SQL fix отсутствуют; большие тесты ранее остановлены владельцем и этим уточнением не возобновлялись. Код/PR refs/descriptions в этом уточнении не менялись, merge/deploy не выполнялись.
