# Пункт 5: counters, freshness и AI evidence retention

1 ноября 2026, Europe/Moscow. Закрытая offline реализация, без ключей.
Пункт 5 целиком НЕ закрыт: real catalog coverage/freshness не измерены.

Реализованы обязательная явная quality policy, семь отдельных buckets и bounded
read-only audit всей заданной eligible когорты на одном PostgreSQL snapshot.
Overflow/DB failure не становятся partial/zero counts. Existing matcher/verifier
переиспользуются; неподтверждённое свойство не считается mismatch.

Добавлен SQL freshness guard для применения до count/order/LIMIT/aggregate.
Он проверяет live timestamps, а не возраст hash/proof. Отсутствующее или будущее
время исключает подтверждение; retired peer не отменяет active support.
Никакие существующие public/economic/time guards не удалены и не перенесены.
Новый guard явно вызывается в закрытых проверках; production paths автоматически
не включались и согласованных глобальных TTL нет.

Добавлено физическое удаление просроченных AI batches/facts/evidence под обычными
writer locks. В той же транзакции снимаются current pointers, меняется generation,
блокируются старые workers и перепубликуется pending barrier. Существующие DB
механизмы инвалидируют proof; после свежей подготовки нужен новый proof.
Rollback не оставляет частичного удаления. Legacy/raw payload, backup/export и
receipt retention этим методом не очищаются. Scheduler и ingestion отсутствуют.

[Контракт и правила вызова](../docs/ai-search-developer/AI_FACT_QUALITY_POLICY_RU.md).
[Воспроизводимый harness](ai-fact-quality-next-evidence/final-checks.py).
[Проверка Git blobs](ai-fact-quality-next-evidence/verify-blobs.py).

Использован новый git archive с core.autocrlf=false, modes восстановлены из tar.
Linux image pinned sha256:1ff5de84b825934599a53fd69add14bb6784d6399a1464e4a38255b2d234a902.
Собственная PostgreSQL `ttest-fact-quality-next-pg`, network none, без host ports;
runner делит только её loopback namespace, БД `ai_facts_test_quality_next`.
Ни старые audit/capacity DB, ни application DB не использовались.

Проверки охватывают все hard criteria, unknown/legacy/conditional/conflict,
отрицание и scoped permission, отсутствующее/будущее время, TTL boundary,
price TTL, partition counters, SQL count/LIMIT, read-only audit, overflow,
физическое удаление, rollback, новое generation и proof invalidation/reprepare,
retired peer с активным источником. Дополнительно выполняются существующие unit
и bounded PG suites, без browser/capacity переаттестации.

Промежуточные ошибки сохранены отдельно: attempt1 — некорректная synthetic
approval fixture (исправлена на корректный scope case); attempt3 — import order;
attempt4 — mypy Optional для DB scalar (исправлено scalar_one). Они не выдаются
за PASS. Промежуточный b8ee9923 имел 1622 unit PASS /39 SKIP и 288 PG PASS;
точный окончательный source и итог ниже относятся к отдельному прогону.

Реальные записи и внешние provider calls: 0. Ключи не читались. PR #403 остаётся
draft, merge/public AI/deploy не выполнялись. Пункт 3 пропущен; ISSUE-004 OPEN /
capacity BLOCKED. Следующий внешний этап требует конкретного разрешённого export,
права на данные, утверждения payload/retention/freshness и измерения real coverage;
LLM extraction и ключ для него необязательны.

Воспроизведение (из audit checkout, с новыми собственными именами контейнеров):

```powershell
git -c core.autocrlf=false archive --format=tar -o reports/ai-fact-quality-evidence/quality-final.tar 55bafffd557df9e6d745552f863154267885dd0a
docker run -d --name ttest-fact-quality-next-pg --network none --label codex.purpose=fact-quality-next -e POSTGRES_PASSWORD=synthetic-only -e POSTGRES_DB=ai_facts_test_quality_next postgis/postgis:16-3.4
docker exec ttest-fact-quality-next-pg pg_isready -U postgres -d ai_facts_test_quality_next
docker run --name ttest-fact-quality-final-runner3 --network container:ttest-fact-quality-next-pg --label codex.purpose=fact-quality-next -v "${PWD}/reports/ai-fact-quality-evidence:/snapshot:ro" -v "${PWD}/reports/ai-fact-quality-next-evidence:/evidence" ttest-ai-fact-population-tools:20261031 python /evidence/final-checks.py
python reports/ai-fact-quality-next-evidence/verify-blobs.py
docker stop ttest-fact-quality-next-pg
```

Не перезаписывать сохранённую evidence при повторе: для нового запуска указать
отдельный results directory в harness. Выходы final ниже принадлежат этому прогону.

Окончательный проверенный source **55bafffd557df9e6d745552f863154267885dd0a**:
**1622 unit PASS /39 optional-platform SKIP**, **289 PG PASS** (84.82 s),
Ruff PASS, mypy PASS (158 source files). Все **470 backend files /435 Python**
сверены с Git blobs; [attestation](ai-fact-quality-next-evidence/attestation.json).
[Unit](ai-fact-quality-next-evidence/final/unit.log),
[PG](ai-fact-quality-next-evidence/final/pg.log),
[Ruff](ai-fact-quality-next-evidence/final/ruff.log),
[mypy](ai-fact-quality-next-evidence/final/mypy.log).
Собственная PG остановлена; application/shared контейнеры не затрагивались.
CI/browser/performance нового HEAD этими результатами не сертифицируются.
