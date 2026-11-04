# S2.2 — durable synthetic supervision, 03.11.2026

Code source: `f76d99a25bbb3800621f97079474985f397a90ba`; parent/checkpoint `8656c823efdaf787cea9db75c110d53853e887f8`. Existing branch `codex/ai-search-acceptance-matrix`. Live GitHub main остаётся `ece1632e2872240a36646ddf0b2518a027d67d84`; [raw](ai-search-s2-supervisor-20261103-evidence/origin-main.txt). Создан draft [PR #405](https://github.com/antony502189-max/Ttest/pull/405) с accumulated S1–S2 changes. Новые изменения не merged/deployed; точные результаты CI следует сверять отдельно по текущему PR head. Прежние main workflows не являются проверкой этого кода.

## Реализовано

`backend/lab/ai_fact_supervisor.py` добавляет явно вызываемый finite harness над существующим coordinator. Отдельный disposable SQLite journal атомарно фиксирует receipt с refresh IDs и cursor/revision; CAS owner/fence/lease запрещает устаревшему процессу перезаписать нового владельца. Crash до commit оставляет прежний cursor для replay после lease; потеря ACK после commit сохраняет подтверждённый checkpoint. Existing queue/worker/proof idempotency используется без новой реализации fact primitives.

Заданы interval, lease, cooperative deadline, capped durable backoff, stale threshold, receipt capacity и bounded health sample. Отмена не подтверждает успех. Async timeout и monotonic post-return check не дают признать deadline-overrun своевременным успехом. Journal хранит только stable failure codes. Receipt capacity останавливает новые claims до внешнего решения, не теряя refresh IDs.

Binding включает фактическую coordinator/worker policy, catalog destination, builder bundle и catalog/schema digest. Loopback `ai_facts_test_*` обязателен; обычные budget paths, symlink journal и чужой SQLite отвергаются. Health отражает sampled terminal/pending/retry jobs, expired queue leases, truncation, failures/staleness, rejected/deferred/refresh outcomes и receipt capacity. Successful tick не скрывает failed job; health storage errors redacted.

Нет app startup/import hook, migration, provider, autonomous daemon или refresh/delivery consumer. Конфигурация не выдаёт source/privacy/outbound разрешения. Подробный [контракт и воспроизведение](../ai-search-developer/AI_FACT_SUPERVISOR_RU.md).

## Проверки финального source

- **153 PASS**: final targeted unit + actual PG bridge/worker/coordinator/quality/supervision. Включает28новых harness unit cases и10новых PG supervision cases. [Raw](ai-search-s2-supervisor-20261103-evidence/final-targeted.txt), [JUnit](ai-search-s2-supervisor-20261103-evidence/final-targeted.xml).
- **100 PASS / 1 opt-in SKIP**: existing lab composition/boundary/parser/review + new harness suite, [raw](ai-search-s2-supervisor-20261103-evidence/lab-regression.txt), [JUnit](ai-search-s2-supervisor-20261103-evidence/lab-regression.xml). С targeted пересекается; counts не суммируются.
- Ruff всего lab + new PG suite PASS; mypy new harness PASS, existing untyped-body note в query proofs не является новой ошибкой. [Ruff](ai-search-s2-supervisor-20261103-evidence/ruff.txt), [mypy](ai-search-s2-supervisor-20261103-evidence/mypy.txt).
- A1–A12 inventory valid,56referenced inputs; product acceptance OPEN. [Raw](ai-search-s2-supervisor-20261103-evidence/inventory.txt). PG suite автоматически включена existing CI через directory; unit suite добавлена в explicit lab CI step.
- Runtime manifest939inputs + existing provenance verifier PASS; historical Docker evidence не применяется к новому runtime. [Raw](ai-search-s2-supervisor-20261103-evidence/provenance.json).

Проверены SQLite atomic rollback при fault между insert receipt/update checkpoint, reopen, два journal owners, stale fence/expired lease, capped backoff, terminal job и queue attempt exhaustion, lost ACK после настоящего PG job/proof и после SQLite commit, bounded health/truncation, receipt-capacity alert, configuration drift, refused non-disposable destination, чужой SQLite без изменения его bytes, graceful cancellation и hard process exit после claim (`os._exit` в отдельном child). Process-exit test проверяет durable claim recovery, а не принудительное завершение работающего coordinator по deadline.

Первый unit прогон дал15PASS/5fixture errors: mock pipeline не содержал sessions. Fixture исправлена; subsequent20, combined27/33 и intermediate151 отмечены только как промежуточные. Финальные153 и100/1skip выполнены после добавления overrun/config-drift checks. Общий full facts/all-backend/browser suite в этой сессии не запускался. Набор506/1skip из предыдущей сессии остаётся историческим промежуточным evidence, не exact-final certification.

Runtime: existing release-venv Python3.12.14; PYTHONPATH текущего backend. PG: owned `ttest-ai-s2-supervisor-pg`, existing PostGIS16-3.4 image с pull=never, port127.0.0.1:55439, БД `ai_facts_test_supervisor`, unique synthetic schemas. Identity проверен; контейнер и anonymous volume удалены. [До cleanup](ai-search-s2-supervisor-20261103-evidence/disposable-before-cleanup.txt), [cleanup](ai-search-s2-supervisor-20261103-evidence/cleanup.txt). SQLite создавались только в owned pytest temp directories. Existing app/lab containers и настоящий budget journal не затронуты.

## Остаток и следующее действие

S2.2 synthetic supervision harness реализован. **S2 остаётся partial.** Async cancellation не может убить заблокированный synchronous builder, постоянный OS supervisor не установлен, detail refresh не выполняется. Следующее действие S2.2: bounded process-isolated synthetic rehearsal этого coordinator/journal с принудительным deadline/kill и restart после interruption; не подключать production hooks. Это проверка недостающего lifecycle, не новая реализация queue/pipeline.

S2.1 real source coverage/freshness, разрешённый importer/источники, постоянная supervised цепочка и S3–S7 остаются открытыми. S0–S1 не пересертифицировались. Provider/account/privacy, voice/saved/rematch/delivery, capacity ISSUE-004, production migration/backup/erasure и release gates не закрыты. Paid calls, real-user outbound, crawling/backfill, большие benchmarks и production activation не выполнялись.
