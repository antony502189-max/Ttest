# S2.2 — bounded process lifecycle rehearsal, 04.11.2026

Source: `c4b32cb4d15f4d8bb6dc767618c86ef1f2f750e3`, base merged main `20435c2e36cabac5608780fe01ab75e47efe152c`. Scope: локальная synthetic часть A3/A11, не продуктовая приёмка и не production activation.

`backend/lab/ai_fact_process.py` добавляет конечный явно вызываемый process boundary над существующим supervisor. Spawn создаёт engine и journal внутри child; внешний deadline убивает процесс, даже когда синхронный builder блокирует asyncio. Caller interruption также вызывает kill/join. После bounded reap функция возвращает PID/outcome/exitcode только для завершённого child; если reap не удался — redacted error. Доверенная factory не создаёт descendants; постоянный supervisor/OS service, startup/importer/scheduler/capabilities не добавлены. Parent не меняет durable claims от имени child и не принимает exitcode вместо receipt.

## Проверенные faults

| Точка принудительного kill | Durable состояние до restart | Recovery |
| --- | --- | --- |
| Синхронный builder worker после настоящего PG claim | SQLite revision0, прежний cursor, нет receipt; PG running/attempt1/lease/fence | До lease expiry новый poll deferred; после explicit synthetic expiry job succeeded/attempt2/fence+1; старый PG claim отвергнут |
| После PG job publication и proof, до SQLite receipt | PG succeeded/attempt1; SQLite revision0 без receipt | Повтор старого cursor создаёт receipt; повтор extraction/publication отсутствует, rematch event count неизменен |
| После атомарного SQLite receipt/checkpoint до return | Revision1, непустой source cursor, pending refresh и digest receipt сохранены | Новый process читает checkpoint; старый receipt/digest не меняется, PG attempts/fence и events не растут |

Каждый fault подтверждается marker из исполняющего coordinator child, принудительным ненулевым exitcode и join/reap; PID отсутствует в active children. После recovery отдельный replay снова проверяет отсутствие повторных publications. Отдельный unit test прерывает controlling join через KeyboardInterrupt при реально живом child и проверяет kill/reap до close; пять invalid-limit cases и factory-failure redaction также покрыты.

SQLite clock ускорен явным fixture clock1000→1031, PG lease expiry — SQL только в owned unique schema. Hard kill действительно выполняется по wall clock5s; тест не ждёт естественные30/60s leases и не сертифицирует production timing. Factory bundle/catalog digests — synthetic fixture constants, не attestation реального источника. Никаких provider calls, ingestion/backfill, реальной lab/application БД, budget journal, outbound или больших benchmarks.

## Проверки и воспроизведение

Existing Python3.12.14 release-venv, Windows spawn, owned `ttest-s2-process-pg`, loopback55439/`ai_facts_test_process`, image digest `sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5`. Existing tests создают и удаляют отдельные schemas; journal/markers находятся в pytest temp directory. Redis не нужен.

```text
PYTHONPATH=<worktree>/backend
AI_FACTS_TEST_DATABASE_URL=<owned disposable loopback ai_facts_test_* URL>
python -m pytest backend/tests/ai_facts_pg/test_fact_process.py backend/tests/ai_facts_pg/test_fact_coordinator.py backend/tests/ai_facts_pg/test_fact_supervision.py backend/lab/test_synthetic_fact_supervisor.py backend/tests/test_ai_fact_process.py -q --junitxml=<evidence>/targeted.xml
python -m ruff check lab tests/test_ai_fact_process.py tests/ai_facts_pg/test_fact_process.py
python -m mypy lab/ai_fact_process.py
node scripts/verify-ai-lab-provenance.mjs
```

Ruff/mypy выполняются из backend; provenance — из root. Финальные результаты, hashes и source caveats: [evidence](ai-search-s2-process-20261104-evidence/validation.json). Первый общий root-run без PYTHONPATH сохранил87PASS/1FAIL: прежний subprocess `python -c` не видел lab. Код не менялся; корректный повтор с документированным PYTHONPATH сохраняется отдельно. Ранние3process/7unit PASS пересекаются с final targeted, не суммируются. Промежуточные ошибки отсутствующей psutil в начальном тесте и lint/import/indentation исправлены до указанного source, dependency не добавлялась.

Manifest обновлён через `runtimeInputs`:943inputs; historicalEvidenceAppliesToCurrentRuntime=false. Исторические raw artifacts не переписаны. Existing CI автоматически собирает новые unit tests и весь ai_facts_pg; Linux exact-head CI рассматривается отдельно. Post-merge CI main20435 на11:52:42Europe/Moscow:5/6SUCCESS, Full audit in_progress — [snapshot](ai-search-s2-process-20261104-evidence/post-merge-ci.json). Эти results не сертифицируют новый source и не доказывают deploy.

S0–S1 сохраняют прежние границы. S2 partial: локальный hard process lifecycle gap закрыт этими проверками; S2.1 реальные measurements, permitted detail refresh и постоянная supervised chain остаются OPEN. S3–S7 и B2–B6 OPEN; voice/saved/delivery обязательны. Следующее действие: exact-head CI/review этого S2.2 increment перед продолжением source-specific refresh chain, без production activation.
