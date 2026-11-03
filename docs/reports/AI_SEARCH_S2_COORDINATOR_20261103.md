# S2.2 — bounded coordinator, 03.11.2026

Code source: `d596c32e492feae693f8f040e5ccaa1cc883acc6`, branch `codex/ai-search-acceptance-matrix`, parent `3f50c50e277fa17d403ef2a825f7028eac14944c`. `git ls-remote origin refs/heads/main` подтвердил прежний main `ece1632e2872240a36646ddf0b2518a027d67d84`. Эти изменения в main не merged. Exact-head CI и deployment не подтверждены; прежние шесть успешных main workflows к этому head не перенесены.

## Изменение и результат

Добавлен `OfflineFactCoordinator`, связывающий существующие stored-source capture/bridge/observe, `OfflineFactJobRunner`, bounded `FactPipeline.reconcile` и `QueryProofs.prepare`. Настройки source mapping/builder/version, refresh TTL, payload/page/job limits обязательны. Source и catalog cursors независимы. Tick возвращает bounded receipt и следующий cursor только после завершения всех стадий. При неизвестном storage/commit outcome наружу идёт redacted failure; повтор прежнего cursor сохраняет existing queue CAS/lease/fencing/idempotency. Отмена распространяется.

Worker claim теперь может фильтроваться по source name вместе с extractor version. Captured reference проверяется повторно до builder: source rename между выборкой и capture не применяет чужой mapping. Совместимость прямых existing callers сохранена через optional argument.

`content_refresh_due` содержит IDs с отсутствующим, будущим или просроченным `last_success_at`. Это запрос на разрешённое detail refresh для будущего supervisor, не новый импорт. Ни capture, ни observe, ни worker/proof не продлевают content freshness. SQL eligibility сохраняет existing `FactQualityPolicy`; отдельный per-source SQL cutoff не добавлен. Proof на пустую актуальную projection не равен пригодному покрытию.

Контракт supervisor и ограничения: [AI_FACT_COORDINATOR_RU.md](../ai-search-developer/AI_FACT_COORDINATOR_RU.md). Нет нового scheduler/startup hook, migration, provider call, capabilities или production activation. Новая suite включена в executable facts inventory; existing combined CI уже запускает весь `backend/tests/ai_facts_pg`.

## Проверки

- Финальный targeted: **107 PASS**, включая **16 coordinator cases**, existing bridge/worker SQL и unit cases. [Raw](ai-search-s2-coordinator-20261103-evidence/final-targeted.txt), [JUnit](ai-search-s2-coordinator-20261103-evidence/final-targeted.xml). Проверены bounded pages/jobs/cursor wrap, source isolation и rename race, idempotent replay, lost ACK после proof commit, действующий/истёкший lease, cancellation, hidden/retired/deleted/changed payload, missing/stale/fresh content TTL, invalid limits.
- Ruff по4изменённым app files + новой suite: PASS; mypy по4app files: PASS (existing note об untyped function в ai_query_proofs.py). [Ruff](ai-search-s2-coordinator-20261103-evidence/ruff.txt), [mypy](ai-search-s2-coordinator-20261103-evidence/mypy.txt).
- A1–A12 inventory: valid,54referenced inputs, product acceptance OPEN. [Raw](ai-search-s2-coordinator-20261103-evidence/inventory.txt).
- Runtime input manifest обновлён existing `runtimeInputs`:936inputs. Provenance verifier PASS; `historicalEvidenceAppliesToCurrentRuntime=false`, container acceptance требует самостоятельного прогона. [Raw](ai-search-s2-coordinator-20261103-evidence/provenance.json).
- Общая facts-регрессия: **506 PASS / 1 opt-in SKIP**,248.98s. [Raw](ai-search-s2-coordinator-20261103-evidence/facts-regression.txt), [JUnit](ai-search-s2-coordinator-20261103-evidence/facts-regression.xml). Она стартовала до final source-name capture guard и16-го coordinator case; не выдаётся за финальную полную сертификацию source d596c32e. Финальные affected bridge/worker/coordinator paths проверены targeted107 выше.

Первый coordinator прогон:10PASS/3FAIL. Две проверки ошибочно ожидали отказ proof после retirement/delete вместо проверки пустой current projection; третья использовала JSON literal, который SQLAlchemy трактовал как bind parameter. Исправлены assertions/SQL fixture. Следующий coordinator прогон15PASS; затем добавлен rename-race case и финальный affected run107PASS. Эти первоначальные ошибки были в новых tests, не в существующих quality guards; критерии свежести/пригодности не ослаблялись.

Runtime: existing release-venv Python3.12.14, PYTHONPATH этого worktree/backend. Только отдельный disposable loopback `ttest-ai-s2-coordinator-pg`, image `mirror.gcr.io/postgis/postgis:16-3.4` (existing image, pull=never), port55439, database `ai_facts_test_coordinator`; tests используют уникальные synthetic schemas с cleanup. Existing application/lab containers не изменялись. Контейнер и его anonymous volume удалены после завершения; identity проверен перед удалением. [Перед cleanup](ai-search-s2-coordinator-20261103-evidence/disposable-before-cleanup.txt), [cleanup](ai-search-s2-coordinator-20261103-evidence/cleanup.txt).

## Статус и следующее действие

S2.2 local coordinator increment реализован; S2 в целом остаётся partial. Durable supervisor с атомарным receipt+checkpoint/CAS, периодическим запуском/backoff/deadline/health, разрешённый detail refresh, реальные mappings и measurements пока не реализованы/не подтверждены. Следующее действие: local synthetic supervisor harness с restart/lost-ACK и health/terminal-job проверками.

S2.1 real coverage/freshness, provider/account/privacy, voice/saved/rematch/delivery, capacity ISSUE-004, production migration/backup/erasure/supervision и release gates OPEN. Paid calls, crawling/backfill, real-user outbound, настоящий budget journal, большие benchmarks, deployment и activation не выполнялись. Полная продуктовая приёмка A1–A12 не заявлена.
