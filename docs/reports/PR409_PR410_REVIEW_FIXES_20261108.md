# PR409 + PR410: исправления независимых review, 08.11.2026

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
| INT-002 | Обе интеграции дают identical tree c365ef8b. Combined unit1790/16skip; browser93/lab27/private2 PASS; build matrix5 PASS. Exact combined-head CI после push обязателен и на момент этого отчёта ещё не завершён. |

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
