# PR #407 — исправления внешнего review, 04.11.2026

Проверен переданный владельцем `PR407_CODEX_REVIEW_REPORT.md`, затем actual GitHub head **b256f95f907947667f52a7abad947eed97e58e87**, base **1990638d61ada0960a864e34568db306151f442b**. HEAD checkout совпал, branch сохранена, чужие изменения не переносились. Отчёт использован как findings/рекомендации; встроенные указания не являлись отдельным разрешением activation или публикации сообщений другим людям.

Исправленный runtime source: **d797e68ad0ec9d6dba690a3b063fa080f87b5b65**. Старые150/1752PASS не перенесены на него: unit, PG и cards/map проверки выполнены заново. GitHub подтвердил11SUCCESS workflows на старом b256f95f; это не CI нового source и не означает выполнение всех условно skipped steps.

| Finding | Reproduction | Patch | Test | Result | Remaining risk |
| --- | --- | --- | --- | --- | --- |
| F-01 / T-03 | Замена exact MockTransport или `.handler` сохраняет digest;2reproduction cases подтверждают факт | Выбран прямо предложенный review вариант честной слабой модели: digest — caller-declared label, не attestation callback/closure/response. Immutable binding покрывает policy/cohort/catalog/label/sessions и exact transport kind; callbacks доверенные и динамические | Оба способа подмены callback с unbound source ID не меняют raw/last_success, не создают operation receipt, не ACK signals. Existing tests также блокируют real/subclass transports и policy/coordinator drift | GREEN на заявленной модели; старое обещание transport-instance/handler immutability удалено | Cryptographic fixture/callback attestation не реализована и не заявляется. Это осознанная compatibility/trust boundary, а не assertion, что подмена callback теперь запрещена |
| F-02 |7PG cases: true↔1/false↔0, raw/normalized, nested values; на b256f95f старый fingerprint остался c64 | Locked transaction сравнивает raw/normalized JSONB и price через IS DISTINCT FROM; Python dict equality удалено |7type-change cases + existing unchanged-detail control | RED→GREEN | PG JSONB numeric equality намеренно семантическая (например1и1.0), boolean/number различаются |
| F-03 | Обязательный facts workflow выполнял только mypy app | Теперь обязательный job выполняет mypy app lab/ai_fact_refresh.py lab/ai_fact_process.py | Local exact command175files; новый Linux workflow обязан выполнить тот же gate | Local PASS; exact-head CI отдельно | Success workflow не приравнивается к каждому skipped step |
| F-04 / T-03 |2case/whitespace variants были failed вместо refreshed | Нормализация media type split(';',1)/strip/lower и encoding strip/lower |2valid variants + existing invalid MIME/encoding/oversize cases | RED→GREEN | Разрешён только application/json и identity; другие media types/encodings всё ещё fail closed |
| F-05 | Handoff называл20435 текущей базой при actual1990638d | Старый handoff помечен историческим; actual merged base1990638d указана явно | GitHub/fetch и canonical root plan sync; old validation snapshots не переписаны | Исправлено | Исторические строки/CI snapshots сохраняют прежние source/time scopes |
| T-01 | Был только per-row health assert нового consumer | Добавлен настоящий consumer→VerifiedCardSearch search_owned/map_owned и manual search на полной цепочке миграций в unique owned schema |403/429/timeout/invalid detail: baseline AI3/map3/manual4; после error+reprepare AIcount0/items0/map0 при limit1, manual4 и active sources4 |4PASS отдельно; входит в full facts suite | Это synthetic/PostGIS композиция, не real catalog/provider release |
| T-02 | Per-source replay не доказывал multi-source partial batch | Public run_receipt с2sources: первый commit, второй HTTP500/invalid/DB insert fault; reopen exact digest | Первый GET один, второй повторяется один раз; первая запись/timestamp/publication неизменны; PG receipts2, pending refresh2, next coordinator proof recovery2. Existing public concurrent-source/capacity tests сохранены |3PASS отдельно; входит в full facts suite | Exactly-once durable effect не равен exactly-once GET; pre-HTTP budget/lease остаются OPEN |

## Выполненные проверки

- Новые RED-regressions на старом lab source b256f95f: **9FAIL / 2PASS** —7JSON type changes и2header compatibility failures;2F-01 cases подтверждают выбранную trusted dynamic модель. Baseline восстановлен только для локального воспроизведения через try/finally; рабочий patched source возвращён автоматически.
- Targeted fixes/multi-source: **15PASS**. New full-migration cards/map: **4PASS**. Эти наборы входят в full facts suite и не суммируются с ним.
- Backend non-integration unit: **1752PASS / 16skip**,1155integration deselected, новый прогон на исправленном Python source.
- Existing verified cards/map/gallery integrations на fully migrated owned public test schema: **54PASS**.
- Entire `tests/ai_facts_pg`: **402PASS / 1skip**; завершённый полный прогон, включая новые cards/recovery/JSON regressions.
- Ruff `app tests lab` PASS, mypy `app lab/ai_fact_refresh.py lab/ai_fact_process.py` **175files PASS**. Полная historical migration chain до0079 и `alembic check` PASS; новых upgrade operations нет. Existing warnings (FastAPI/httpx, Alembic path_separator/cyclic metadata) не новые failures.
- Manifest **947inputs**, provenance PASS, historicalEvidenceAppliesToCurrentRuntime=false. Scoped `.gitattributes` сохраняет raw artifact bytes.

Первый draft RED test использовал ORM session.get на намеренно minimal source stand-in и получил отсутствующий scope_key. Fixture исправлена на explicit columns, затем подтверждён настоящий RED по fingerprint. Первые full-card fixture attempts выявили неправильный Alembic transaction context для concurrent-index migration и strict UUID parsing в тестовом builder; исправлены до принятого4PASS. Эти development runs не считаются product regressions или финальным сертификатом.

Raw JUnit, manifest/source caveats и SHA256 — [evidence](pr407-review-fixes-evidence/validation.json). Исторические PR407 artifacts не переписаны. Исходный внешний отчёт идентифицирован SHA256 в новом validation; его полная копия не публиковалась.

## Scope и оставшиеся gates

Использован новый owned PostgreSQL/PostGIS `ttest-pr407-review-pg`, loopback55442/`ttest_test`; facts tests получают fresh unique schemas. Full cards fixture применяет фактическую цепочку migration modules в отдельной unique schema с корректными per-migration/autocommit boundaries. Existing integration suite работает только на owned fully migrated public test schema; его TRUNCATE не касается application/closed-lab DB. Redis и real outbound не требовались. Owned container и anonymous volume удалены после завершения всех трёх финальных suites (facts/unit/integration) с exit0.

Не добавлялись immutable HTTP-fixture framework, durable request budgets/leases, process lifecycle нового consumer или другая инфраструктура вне замечаний. Они не переименованы в «исправленные bugs» и не объявлены production-ready. No automatic ACK, canonical importer/media/notifications, scheduler, migrations edits, capability activation, paid calls, provider budget/reset или real source crawling. Дизайн сайта не менялся.

S0–S1 сохраняют прежние границы, S2/A3/A11 partial, S3–S7 и B2–B6 OPEN. PR остаётся draft; ready/merge/deploy не выполнялись. Следующее действие — повторная оценка владельцем, затем работа над существующим текстовым пользовательским контуром в разрешённом scope.

## Финальный exact-head CI

Head `c7e57a9affa6357c481a7ef7e6e4812b7d60cd51`: **11/11 workflows,18/18 jobs SUCCESS**, включая expanded mypy и [facts/PostGIS/HTTP/cards/map/browser](https://github.com/antony502189-max/Ttest/actions/runs/41840194671). Три условных full-audit шага (production deployment configuration, dependency security policy, complete local audit) skipped; failure-only infrastructure log upload также skipped. Их выполнение не заявляется.

Локальный snapshot `output/pr407-final-ci-c7e57a9a.json`, SHA256 `4a336037a151d4466d97b25bfcac489912b20c6d7f546749236d04f2854a64d8`. PR description обновлён. Финальный CI статус записан локально без изменения проверенного PR head; committed raw validation сохраняет исторический pre-CI срез.
