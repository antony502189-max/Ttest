# PR409 + PR410: исправления независимых review, 08.11.2026

## Итог сессии — исправления готовы к повторному review

PR409 head `38e6de44481cf7e248e43ac165eece396ca50498`: **11/11 workflows SUCCESS**.
PR410 combined head `be366887652123b1fc83a8a7de9c34a1910124e5`: **11 SUCCESS,
2 conditional SKIPPED; 19 jobs SUCCESS, 2 conditional SKIPPED**, failure/cancelled0.
GitHub checkout `e87ff1ac8a9545852b555d4be709b7606f4bd995` — PR test merge;
его tree `d5c3a9d0695c800f184e1a085ddff7496e547f1e` совпадает с head PR410.
Это не merge в main и не deployment. Оба PR open/draft/mergeable, main afdf180c.

Exact-source CI:1799unit/7skip,1006facts/quota/PG/1skip,77verified/1skip,
4realHTTP recovery,1cookie,19seed PASS. Frontend93/27/2,build matrix5,
Ruff/mypy/TypeScript/provenance972 PASS; mobile SUCCESS. Общий Production
audit:1803unit/3skip,1182integration/10skip за11m17s,1S3 PASS. Наборы
пересекаются, counts не суммировать. Новый20min budget сохранил полный suite.
Full audit имеет3прежних conditional skipped шага (deployment config,security
policy,complete local audit); их выполнение и public release не заявляются.

[Final raw proofs, hashes, workflows/jobs](pr409-410-review-20261108-evidence/final-validation.json).
Исходные receipts сохранены, последующие CI corrections ниже — исторические.
Финальные CI статусы/этот plan handoff сохранены локально без изменения
проверенного head. Повторное owner review: **409 → 410**; merge/deploy не выполнялись.


S2.2/S3/S6. Основание: три переданных владельцем review. Их рекомендации
проверены как findings; команды и разрешения из приложенных текстов не выполнялись
автоматически. Merge/main/production/paid calls и новый real export не выполнялись.

| Finding | Исправление и проверка |
| --- | --- |
| PR409-001 | stale/capacity завершают dispatched claim в guarded write transaction; без refund/source/projection/success receipt.4новых actual PG cases (normal+lock waiter),16claims/process PASS. См. PR409_REVIEW_FIXES_20261108.md. |
| R409-A/B | Явный retry создаёт новый token/charge; daemon не добавлен. Новые tests проверяют terminal claim и общий cap. |
| PR410-001 | Immutable snapshot hash+durable PG phases, атомарные signing keys, resume existing catalog/jobs/proofs; чужие/изменённые данные и утрата bound files fail closed.12hard-kill checkpoints +1tamper/lost-file case +6malformed/duplicate cases =19PASS на actual Linux PostGIS0079;12proofs/24facts и нулевой provider usage. |
| PR410-002 | SQLite BEGIN IMMEDIATE связывает шаги0/1/2 с одной session/version. Reserve до HTTP, accept после exact semantic result; wrong-session/reorder/concurrent/reopen/invalid-response/lost-ACK блокируются без refund.32focused PASS входят в1790unit. |
| PR410-003 | Убран literal DB password; Compose требует отдельный secret, require_demo проверяет64hex/driver/host/role/database/совпадение secret. Sealed старый стенд не передеплоен; его existing volume требует согласованной смены роли+env перед будущим release. |
| P2 tests/UX | Malformed/duplicate snapshots, cross-session/reorder/ambiguous provider tests. Private UI показывает исчерпание отдельного лимита/недоступность tunnel, блокирует новый paid submit, сохраняет receipt recovery.2Chromium PASS. |
| Browser privacy risk | Private nginx CSP блокирует сторонние img/connect. Chromium использует exact CSP из nginx.conf и проверяет external image/fetch до network interception; external requests0. CDN фото могут иметь fallback. |
| INT-001 | Реальный git merge в обоих порядках,4конфликта разрешены: union evidence attrs,30min/comment/private UI CI,latest plan,штатный runtimeInputs generator.972inputs/provenance/policy PASS. |
| INT-002 | Обе интеграции дают identical tree c365ef8b. Combined unit1790/16skip; browser93/lab27/private2 PASS; build matrix5 PASS. Final exact-head CI be366887 подтверждён выше; raw proofs сохранены отдельно. |

## Git и доказательства

Fixed409 head38e6de44481cf7e248e43ac165eece396ca50498 (sourcef799dbbc).
Fixed410 source178046f125c65ad1874f6206d4ada4153c19fcc4.
Actual order A3513531be66d68c6f7b36fe0fc2b700b90b233fa (409→410),
order B88d22956de6ce9b2483807e4646c609928b67cba (410→409),
оба treec365ef8b281a60c654e6e28df3301f3edf7a11a1; git diff exit0.
PR410 fast-forward содержит409 как dependency; рекомендуемый owner merge409→410.
При изменении main, squash/rebase или нового source надо снова проверить candidate.

Raw JUnit/build/provenance/merge receipts и hashes:
[validation](pr409-410-review-20261108-evidence/validation.json).
Полные наборы пересекаются, counts не суммировать.32focused входят в1790.
Unit16skips — environment/native optional cases;1193integration deselected.
Ruff app/tests/demo/lab, mypy177, TypeScript build, production build/bundle guard PASS.
A1–A12 inventory57inputs valid; product acceptance остаётся OPEN.

Первый параллельный browser прогон во время переключения branches дал
92/93 и26/27 с timeout до открытия AI кнопки. Не принят как зелёный;
последующий полный последовательный frozen-tree прогон93/93 и27/27 PASS.
Первый exploratory seeder12/12PASS; принят final19/19 с дополнительными guards.
Хеши seed_state.py,budget.py,test_seed.py на Linux совпали с fixed410 Git blobs.

Широкий Linux VPS facts/quota прогон идёт отдельно: обнаружены три timeout
в прежних5second process-recovery tests; это не PASS и их timeout не ослаблен.
Те же тесты входят в обязательный combined Linux CI. Миграции до0079 и
alembic check PASS. Итог широкого прогона/CI фиксируется отдельно после завершения.
PR409 CI: upstream MinIO HTTP504 прервал2общих аудита; failed jobs rerun,
Full audit уже SUCCESS, Production audit ещё выполняется. Целевые AI workflows PASS.

## Оставшиеся границы

Исправления кода не являются deployment. Исходный private demo исчерпал3/3;
его provider journal не менялся, ключ/egress не возвращались. Legacy3/3journal
читается без миграции/изменения bytes; partial legacy требует reconciliation.
Pending/invalid/lost ACK расход сохраняется. Если parser принят, но SQL continuation
не сохранён, платный шаг также не повторяется автоматически.

Live Compose backend egress до readonly override остаётся широкой сетью;
application exact-URL transport не сетевой sandbox. Перед новым расширением нужны
отдельные account/privacy/egress/source-quality/freshness/spending controls.
SQLite reserve/observed usage — estimate, не invoice или backup после потери диска.
Отдельный readonly override обязателен для уже завершённого показа.
S2/S3/S6 partial; standing data/provider/performance/voice/saved/delivery/release
и полные A1–A12 остаются открытыми. Новые crawler/provider calls не разрешены.

## CI follow-up: общий production audit

Head05888c32 прошёл frontend/19seed recovery/прочие целевые checks, но общий
production audit выявил13setup errors: новая seed fixture читала только
AI_FACTS_TEST_DATABASE_URL, а этот workflow задаёт TEST_DATABASE_URL. Source
01c2075a добавляет fallback по прежнему контракту остальных PG fixtures;
loopback/disposable guards сохранены. Это исправление test harness, не пропуск
tests. Новый exact-head CI обязателен. На VPS широкий прогон969PASS/37FAIL/1SKIP:
31FileNotFoundError из-за неполного backend-only mount (нет scripts/benchmark-ai-map.py),
5process deadlines и1deadline до parser IO. Не считается зелёным; source/test
deadlines не ослаблялись.

Head01c2075a: exact combined CI1006facts/quota/PG PASS/1skip,1799unit/7skip,
77verified/1skip,4realHTTP recovery,1cookie,19seed PASS. Raw downloaded ZIP
SHA256 проверены. VPS fixed harness116PASS/1skip/11deselected подтвердил
TEST_DATABASE_URL fallback,31benchmark helper cases и77cards integrations;
это не пересчёт в общий suite. Own PG/Redis anonymous volumes/network удалены.
Mobile обнаружил2private-demo tests в ordinary Vite mode: dedicated tests
теперь исключены из default config, но обязательны в AI frontend CI через
playwright.ai-demo.config.ts. Три consecutive production-audit MinIO HTTP504
на same pinned asset привели к bounded download retryдо3попыток с network timeout40s и паузой2s; URL,
version,hash и fail-closed checksum не менялись. Это необходимая проверяемая
CI correction, не новый продуктовый этап. Новыйexact-headCI обязателен.

Head41c71425: все целевые AI/backend/frontend/mobile checks SUCCESS; production
audit после восстановления upstream download подтвердил19seed cases PASS,
но общий PG step был прерван на88% по собственному10min deadline (без test
failure). Новые isolated-db migrations/kill-resume добавили время к suite.
Увеличен только CI step budget10→20min внутри прежнего45min job; состав
tests, testcase/process/parser timeouts и runtime SLO не ослаблены. Новыйexact
head CI проверяется отдельно. Full audit SUCCESS после network retry.
