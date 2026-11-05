# S2.2 — durable reservation перед synthetic detail HTTP, 05.11.2026

Base merged main `afdf180c922da65de8f0fbdf3e89005e30faf481`. Владелец слил#408; GitHub подтвердил merge05.11 в14:25:34UTC, fetch origin/main совпал. Existing worktree переиспользован на `codex/ai-search-refresh-claims`; два намеренных docs changes сохранены. Старый root checkout не переключался. Source первого increment: `2859b4444edc209888a2b932eff8e5870e803e5a`, [draft PR409](https://github.com/antony502189-max/Ttest/pull/409).

## Изменение

Existing MockTransport detail consumer получил отдельные owned PG request budget/claim tables. Setup только через explicit initialize в schema `ai_facts_<uuid>`, связанной с supervisor catalog digest; production metadata/migrations не меняются.

- До mock GET коммитится reservation с monotonic used counter, namespace maximum, exact operation/source, UUID fence и DB-clock lease. `max_total_requests` и `request_lease_seconds` обязательны; lease превышает HTTP timeout. Максимум относится к одному owned namespace, не ко всем операторам/аккаунтам сайта.
- `reserved→dispatched` коммитится до создания клиента. Повторное использование той же reservation для GET отвергается. Unknown claim/dispatch outcome не приводит к refund. Прерванный до отправки запрос может израсходовать reservation, даже если HTTP фактически не начался.
- Exact operation и другой активный lease того же source в namespace возвращают in_progress без нового GET. После lease нужен новый token и новая reservation; exhausted cap возвращает request_capacity. Reopen/initialize не сбрасывает счётчик.
- После DB await перед client construction повторно проверяется binding/exact MockTransport. HTTP/builder не держат DB transaction/locks. Старый token проверяется до dispatch, под row lock до source write и финальным fence check внутри mutation transaction.
- Successful source CAS, projection barrier, operation receipt и finish request коммитятся вместе. Expired/replaced owner не может применить late response. После ожидания request row повторно читается operation receipt, чтобы завершённый writer не вызывал лишний GET у waiter.
- Finite `SyntheticDetailRefreshTick` использует existing spawn/kill boundary. Protocol typing отражает уже существующий run_once contract; module-function/scalar-input/pickle/IPC/reap guards сохранены. No automatic ACK. Даже committed protocol reply требует проверки durable effect и retained pending signals.

## Проверки

Local source checks:1758unit PASS/16skip,55targeted policy/process PASS (входят в1758), Ruff app/tests/lab PASS, mypy175PASS, runtime input policy/provenance949PASS. Historical container acceptance не переносится на новый source. Фронтенд не менялся; его новые browser/build результаты учитываются отдельно в GitHub CI.

Новые PG tests: durable cap после403/reopen, shared cap двух sources/callers, exclusion другого receipt для того же source, lost claim ACK до dispatch, expiry до GET, one reservation/one dispatch, late old response после нового owner, final fence rollback и waiter, ожидающий чужой commit. Старый two-overlapping-GET test заменён single-flight contract; rollback/recovery tests явно ожидают lease expiry после unknown effect outcome.

Три actual process tests останавливают consumer после reserved, внутри synchronous mock GET и после PG commit; marker подтверждает достижение соответствующей точки, child reaped, parent проверяет used/status/receipt. Restart до expiry deferred; после expiry тратит новую reservation; unknown commit с retained operation receipt не повторяет GET/effect. Следующий actual coordinator tick должен восстановить current proof; ACK не вызывается.

**Actual Linux CI на source2859b444:** [combined facts run42049048343](https://github.com/antony502189-max/Ttest/actions/runs/42049048343), job127319847731 SUCCESS. По job log:1767unit PASS/7skip (Linux/Python3.13 отличается от local Windows/Python3.12),112schema tests PASS,1002combined facts/offline/quota/PG PASS/1skip,77verified integrations PASS/1skip,4real-HTTP recovery и1cookie boundary PASS. Эти наборы пересекаются. Artifact13426512749 скачан, SHA256 совпал с GitHub digest `09c0b614b6909d8cc8a17ee3baf4fdc8b71de4b9406db0931ce8f7d748f8b0d9`; JUnit подтверждает все12новых cases (9claims+3process) PASS, без skip. Это реальные Linux SQL/spawn/kill проверки, **не** локальный запуск и не real-source/provider acceptance. Финальный head с документацией требует своих current checks.

**Local PostgreSQL/process-consumer PASS отсутствует.** Docker daemon остановлен, Docker Desktop и CLI start завершаются missing installation registry key. Обычный hidden launch был предпринят, установка/registry не менялись. New PG/process cases только собраны локально и должны пройти actual Linux combined facts CI. Нельзя переносить прежние65PG PASS из#408 на эти изменения.

Финальный local unit повтор первоначально остановился примерно на20%; остановлены только проверенные PID этого pytest, затем полный verbose/faulthandler повтор завершился1758PASS/16skip за73.99s. Interrupted log не считается PASS. Первый1758PASS до final dispatch guard также исторический; принят final verified run на текущем application source. New code не требует локального ремонта Docker: actual SQL/process acceptance выполняется в существующем CI с owned PostgreSQL.

Raw local logs/XML, sanitization и source caveats — [evidence](ai-search-s2-claims-20261105-evidence/validation.json). GitHub CI текущего PR head — [checks](https://github.com/antony502189-max/Ttest/pull/409/checks); датированный exact-head итог публикуется отдельно в PR description. Local tests не выдаются за PG или CI certification.

## Границы и продолжение

### CI timeout follow-up

На head86f4ab2b combined facts job127330452219 завершён SUCCESS:1767unit/7skip,112schema,1002combined/1skip,77verified/1skip,4HTTP и1cookie PASS. Frontend job127330452789 отменён на общем15min deadline: после установки Chromium/build успели пройти72из93 browser cases без failures; pairing/build-mode/provenance steps не выполнялись. Это не frontend PASS. Лимит только общего CI job поднят15→30min; все suites и test timeouts сохранены. Manifest949 обновлён, policy/provenance PASS. Backend/src не менялись; source2859 evidence сохраняет свои границы. Новый head требует собственного CI.

Транспорт только exact trusted dynamic MockTransport, один synthetic `.invalid` host/cohort. Bundle label не аттестует handler/closure/response bytes и не является sandbox. Обязательные packet/identity/size/source CAS проверки сохранены.

Это synthetic request cap, **не** настоящий provider budget journal, global account/USD cap, permission на crawling или exactly-once HTTP. После неопределённого dispatch GET может повториться после lease, с новой reservation; физическое число requests может быть меньше charged reservations. Claim/write fencing относится к этому consumer/namespace и проверяется по DB state, не по одному child exit.

Нет scheduler/daemon/standing activation, автоматического ACK, изменений site design/runtime capabilities, source importer/media/delivery, paid provider/source calls, реального backfill, больших benchmarks, merge/deploy. S2 остаётся partial: source authorization/coverage, постоянный supervised refresh, retention/erasure, provider/data/performance/release gates и S3–S7/B2–B6 OPEN. Voice/saved/delivery обязательны. Следующее действие — exact-head CI/review409; затем S2.1 concrete source/cohort/authorization/measurement package как dependency standing refresh, без новых synthetic harness вместо реального data gate.
