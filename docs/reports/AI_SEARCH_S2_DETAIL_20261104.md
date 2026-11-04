# S2.2 — synthetic receipt→detail→facts/proof, 04.11.2026

Исторический initial-source отчёт. После внешнего review#407 исправлены JSONB type semantics, header compatibility, CI typecheck и неоднозначный mock binding contract; актуальные результаты — [PR407_REVIEW_FIXES.md](PR407_REVIEW_FIXES.md). Старый validation.json сохраняет local pre-CI статус: subsequent b256f95f прошёл11workflows SUCCESS, но эти results не сертифицируют новый d797e68a.

Base: merged main **1990638d61ada0960a864e34568db306151f442b**, PR#406 merged владельцем04.11 в12:46:54Europe/Moscow; GitHub и fetch совпали. Existing worktree переиспользован на `codex/ai-search-detail-refresh`; собственные локальные итоги предыдущего review сохранены, чужой старый root checkout не переключался.

Runtime source: **716ae9fa2298c4455ceb6d4392e937a1b8457748**, initial increment822f0ef5. Это локальный source-only synthetic contract A3/A11, не real catalog coverage и не production importer.

## Реализовано

`backend/lab/ai_fact_refresh.py` явно принимает exact retained supervisor receipt, explicit source→canonical cohort, source policy и reviewed MockTransport bundle. Разрешены только synthetic source, HTTPS на одном `.invalid` host и owned loopback fixture schema, hash которой связан с supervisor catalog identity. Real network transports/subclasses, redirects, proxies/env transport routing и выход за cohort исключены из consumer API. Доверенный mock callback не является sandbox.

Используются existing capture/bridge/builder, source-check health predicate, lock order/authority, projection publish и next coordinator tick. Новый disposable PG operation receipt коммитится вместе с guarded source write и projection barrier. В existing owned SQLite добавляется только immutable refresh config/namespace row. DDL вызывается явно через initialize; production metadata/migrations не меняются.

Проверены:

- Mock valid detail меняет source, старый proof исключён; настоящий следующий coordinator tick получает новые факты и current proof. Refresh не подменяется presence/reprepare и не продлевает stale payload без нового detail.
- Exact receipt replay/unknown commit outcome/reopening не повторяют GET или publication после durable PG receipt. Concurrent pre-commit GETs допустимы только в synthetic contract, но durable effect один.
- Payload/fingerprint/URL/source/canonical/retirement/deletion/visibility/check-stamp races не перезаписываются. HTTP403/429/404/redirect/5xx, timeout/invalid JSON/identity/packet/encoding/oversize не делают content fresh и не удаляют manual source.
- Retained-operation cap не pruning/reset; concurrent distinct-source writes соблюдают cap при READ COMMITTED и REPEATABLE READ engine defaults. Mutation transaction явно READ COMMITTED, чтобы count после advisory lock видел завершившиеся commits.
- Source write/projection/receipt rollback атомарен. Already-fresh source не вызывает GET и не продлевает возраст. Unchanged valid detail продлевает successful detail check, сохраняя fingerprint/content_updated_at.
- Freshness берётся из DB observation перед GET: lock/commit delay не делает контент моложе. Проверяются HTTP bytes и фактический размер stored JSONB::text против existing snapshot-reader bound.
- Cooperative cancellation и synchronous overrun не записывают свежесть. Consumer и actual coordinator binding перепроверяются после I/O и до завершения mutation transaction.
- ACK не вызывается автоматически: rejected/deferred сигналы того же receipt остаются обязанностью explicit consumer/caller. Retained supervisor evidence сохраняется после explicit exact ACK.

Обнаруженный при self-check coordinator-policy drift воспроизведён RED на822f0ef5 и исправлен в716ae9fa; [raw reproduction](ai-search-s2-detail-20261104-evidence/configuration-drift-red.xml). Это source-specific seam, не новые activation hooks или конкурирующий roadmap.

## Проверки и ограничения evidence

**Финальные результаты:** **150targeted PASS и1752backend unit PASS/16skip на716ae9fa**, финальный targeted повтор полностью выполнен на свежем owned PG; XML/source caveats в validation.json/final-targeted.xml. Ruff app/tests/lab PASS; mypy app+два lab modules —175files PASS; runtime manifest946inputs/provenance PASS, historicalEvidenceAppliesToCurrentRuntime=false. Наборы пересекаются, counts не суммируются.

Ранние63,147и149targeted и1752unit прогоны имеют source caveats: до final coordinator binding recheck и/или READ COMMITTED guard. Initial development failures с asyncpg UUID subtype и SQLAlchemy colon-bind в literal исправлены до финального source. Исторические raw artifacts не переписаны; текущие XML и hashes находятся [отдельно](ai-search-s2-detail-20261104-evidence/validation.json).

Один targeted run был прерван из-за преждевременного удаления owned test PG до окончания pytest; он не считается PASS. Owned pytest processes остановлены, создан свежий disposable container, весь targeted набор повторён без переноса частичных результатов. Результаты финального повтора отделены от interrupted run.

Existing Python3.12.14 release-venv, pytest9.1.1, Windows spawn; PG `ttest-s2-detail-pg`, loopback55441/`ai_facts_test_detail`, actual image `sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5`. Redis не требовался; текущие application/closed-lab containers и настоящие journals не тронуты. Оба owned containers и их anonymous volumes удалены; финальный cleanup выполнен после полного150PASS и завершения pytest/teardown.

Post-merge main1990638d на13:23:36Europe/Moscow:5/6workflows SUCCESS, Full audit ещё in_progress — [snapshot](ai-search-s2-detail-20261104-evidence/main-1990638d-ci.json). Это не certification нового716ae9fa или deployment. Exact-head CI нового increment проходит отдельно.

## Оставшееся

До standing/real refresh нужны durable pre-HTTP claims/leases/fences/budgets и process-lifecycle composition нового consumer. Нельзя переносить exactly-once PG effect на число запросов или spending cap: до commit два callers могут сделать два GET, прерванный до commit GET может повториться. Requests здесь только MockTransport; реальных provider/source calls нет.

Также открыты S2.1 source/cohort/authorization/robots/canonical-import policies, реальные coverage/freshness measurements, permanent supervision, erasure/retention и release gates. Legacy upsert/media/notifications не активированы. S0–S1 сохраняют границы, S2 partial, S3–S7/B2–B6 OPEN, voice/saved/delivery обязательны. Следующий шаг — exact-head CI/review этого S2.2 increment, затем следующий bounded durability/lifecycle rehearsal по единому плану.
