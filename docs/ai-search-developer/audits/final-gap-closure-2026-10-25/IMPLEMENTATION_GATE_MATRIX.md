# Ворота реализации и последовательность PR

Дата: **2026-10-25**. Main M=`1292c6807ece59999238bb31c80e09ef7e2c3212`; docs H=`85fa9ad7ebff15634b34bd341882d302398b6dfc`; parser F=`fcae378d9dbbc8447f18df150327180f6f2c8231`; planning P=`1ace67b5ae67ab267fdcc37ee499b87bd433fb71`. R/C/P/V/D — [реестр evidence](FINAL_GAP_CLOSURE_AUDIT.md#12-реестр-доказательств): точные SHA, paths/lines, классификация, среда, метод и ограничения. Статусы ниже относятся к конкретной области, не к платформе целиком.

`VERIFIED_READY` — подтверждена существующая основа в указанном scope; `READY_FOR_DEVELOPMENT` — можно писать offline/mock/disposable code; `NEEDS_IMPLEMENTATION` — нужной функции нет; `NEEDS_MEASUREMENT` — есть конкретный будущий эксперимент; `BLOCKED` — конкретное отсутствие прав/обязательной зависимости; `UNKNOWN` — нельзя установить доступными данными. Числовой процент готовности не рассчитывается.

| Area | Status | Evidence | Blocker | Recommended action | Priority |
|---|---|---|---|---|---|
| Актуальные refs и PR | VERIFIED_READY | R01–R03: #372merged, #373/#374open | нет для docs | audit PR→ветка H; runtime branches→current main после review | P1 |
| Scope/3–200/Madrid/one Send | VERIFIED_READY | прямое задание, H01/09, R03 | нет | сохранить как product invariants, не возвращать historical confirmation gate | P0 |
| ADR и versioned DTO | READY_FOR_DEVELOPMENT | C03/C07/C10/C12 | согласование оставшихся semantics | **AI-01 первым**, docs schemas/examples без runtime | P0 |
| Обычный listing search/card API | VERIFIED_READY | C03/C04, P02/P03 | AI extra semantics пока нет | reuse query builders/card DTO, separate envelope | P0 |
| Полная инвентаризация production DB | BLOCKED | D01 | явно разрешённая RO-role/replica не установлена | DBA reviewed plan, не app DSN/root | P0 |
| Data coverage по source/type/criteria | BLOCKED | D01; public sample не denominator | те же права и controlled projection | AI-02; numerator/denominator/date/status, real gold subset | P0 |
| Какие sources дают fresh usable data | BLOCKED | C05/C06; P02/P03 только visible sample | source runs+snapshots/config runtime | matrix configured/process/useful, no crawl | P0 |
| Source telemetry | NEEDS_IMPLEMENTATION | C06 formatter теряет extra | safe field allowlist | отдельный log/metrics patch с negative PII tests; read-only aggregates | P1 |
| Parser foundation integration | NEEDS_IMPLEMENTATION | F/#373, R02/C07; CI904+88 | open PR, planning diverges | reviewed minimal перенос на main с #372 regressions | P0 |
| AI facts schema | READY_FOR_DEVELOPMENT | C07/C11/C14 | ADR для semantics; actual DB для rollout | AI-03 additive tables; offline design/disposable upgrade сейчас | P0 |
| Canonical resolver/queue | NEEDS_IMPLEMENTATION | C05/C07/C11 | facts schema/ADR | AI-04 lease/fencing/durable signal/reconciler, no network в import txn | P0 |
| Confirmed occupancy/pet/smoke filters | NEEDS_IMPLEMENTATION | C03/C07, main§6 | current facts/provenance | indexed predicates before count/seek/limit; legacy equality сохранить | P0 |
| Paid TOP compatibility design | READY_FOR_DEVELOPMENT | C03/C04 | integration regressions | eligibility→unchanged TOP/boost/order; no page rerank | P0 |
| Apartment taxonomy | NEEDS_IMPLEMENTATION | P02/P03/C03: apartment в выдаче, старый DTO ограничен | explicit enum mapping contract | additive AI category, no studio remap; legacy tests | P1 |
| Cursor version/stability | NEEDS_IMPLEMENTATION | C04: query hash+tuple, без snapshot | intent/facts/sort version design | MAC/opaque binding, restart policy, promotion expiry tests | P1 |
| Freshness policy | READY_FOR_DEVELOPMENT | C05/C06/C11, actual ages null | source windows требуют AI-02 | ADR unknown/stale/retired; не глобальная скрывающая TTL | P0 |
| Daily quota ledger | READY_FOR_DEVELOPMENT | C12/approved requirements | нет DB production dependency для disposable tests | AI-07 PG reserve/finalize/release+idempotency+Madrid | P0 |
| ASR attempt abuse prevention | NEEDS_IMPLEMENTATION | C12, current limiter не business ledger | технические thresholds/identity | separate nonrefunded attempt/audio-second gate до ASR | P0 |
| Conversation/session patch | READY_FOR_DEVELOPMENT | C10/C12, handoff | AI-01 contract; ledger для wiring | AI-08 CAS/version/subject/TTL, explicit unset | P1 |
| Guest→login semantics | READY_FOR_DEVELOPMENT | main§7 proposal | решение AI-01 | no double debit; in-flight original subject, one-time state transfer | P1 |
| Provider fake adapters | READY_FOR_DEVELOPMENT | V01–V06 | нет для mocks | contracts timeout/429/invalid JSON/codec errors; no paid calls | P1 |
| Live provider account/limits | UNKNOWN | vendor docs не account state | authorized account inspection | operator safe checklist entitlement/concurrency/retention, без ключей в repo | P0 |
| API-specific privacy/DPA | BLOCKED | C07/V02/V04/V07 | processing settings/terms review | outbound allowlist, sanitize, transfer/retention approval перед live data | P0 |
| Voice transport/mic/recorder | NEEDS_IMPLEMENTATION | C01/C02/C08/C09; P01mic blocked | quota/privacy/ASR для live path | AI-11/12 scoped caps, actual codecs, one multipart query | P1 |
| UI mock shell/recorder | READY_FOR_DEVELOPMENT | C08/C09/V08 | нет live provider dependency | reuse desktop/mobile cards; no mandatory confirmation, real paint marks | P1 |
| SavedSearch storage/auth | VERIFIED_READY | C10/C11 | AI dispatcher ещё нет | reuse JSONB/current_user/ownership | P1 |
| Saved AI matching/notifications | NEEDS_IMPLEMENTATION | C10 fixed legacy keys | same matcher/facts/event jobs | AI-10 delayed rematch+revision dedup+existing outbox | P1 |
| Background alerts не расходуют200/3 | UNKNOWN | предложение в задании, main§8 | явное product decision AI-01 | предложено0interactive debit; quota exhaustion не останавливает background | P1 |
| Existing HTTP baseline | VERIFIED_READY | P02/P03, n=1/query,0.596–1.799s | статистики нет | использовать как samples, не p95 | P1 |
| Live indexes/PG headroom | BLOCKED | C02/C14 code defaults/indexes, D01 | разрешённая DB metadata | preflight+EXPLAIN без ANALYZE, runtime pool metrics | P1 |
| ASR/intent quality+latency | NEEDS_MEASUREMENT | V docs, вызовов нет | working integration+paid/privacy authorization | gold RU/ES/EN/mixed, critical slot/evidence quality | P0 |
| Browser10s voice SLO | NEEDS_MEASUREMENT | VOICE_10S_FEASIBILITY | implementation/staging/account gates | trace all stages, p50/p95/p99+errors/correctness/freshness | P0 |
| Main address422 CI failures | NEEDS_MEASUREMENT | R05 Mfull audit failed; Hfull audit passed | reproducible root cause/environment | separate scoped investigation, не ослаблять validation | P1 |
| H municipality mobile failure | NEEDS_IMPLEMENTATION | R05 exact run/location49 | диагностика причины до fix | отдельный UI/test PR, feature audit остаётся docs-only | P1 |
| GitHub protection | UNKNOWN | R06protected=false/rulesets[]/detail403 | admin settings access/policy | owner/admin проверяет approved protection до release | P1 |
| Manual deploy workflow | VERIFIED_READY | C13 код workflow_dispatch/exact main/checks/environment | current reviewers policy не проверена | сохранить ручной gate; не запускать в аудите | P0 |
| Code Alembic lineage | VERIFIED_READY | C14 static66files, head0066_complimentary_ads | live version неизвестен | новые revisions после актуального head, upgrade old/new app tests | P1 |
| Live Alembic/index validity | BLOCKED | D01 | RO metadata | SELECT alembic_version/pg_indexes с DBA, без migrations | P1 |
| AI kill switches | NEEDS_IMPLEMENTATION | C01/R03, feature отсутствует | server config/UI wiring | independent default-off text/voice/enrichment/saved/fallback | P0 |
| Production full AI rollout | BLOCKED | перечисленные P0 gates | данные+quota+privacy+voice+quality/SLO | closed gates на release candidate, manual approval отдельно | P0 |

`NEEDS_IMPLEMENTATION` у existing UI failure не означает доказанную production ошибку: пока доказан CI symptom; сначала diagnosis, затем при необходимости source/test fix. `VERIFIED_READY` у code migration lineage не означает, что migration применена в production.

## Порядок реализации с зависимостями

1. **PR-AI-01, docs-only ADR/contracts.** Versioned fact statuses/qualifiers/evidence, group/capacity≥N, taxonomy, freshness, unchanged commercial order, intent set/unset/clarify, cursor version, quota success/clarification semantics, guest login и background quota proposal. Удалить из активных contracts необходимость confirmation; исторические аудиты сохранить. Review examples:2people+capacity3;small dog/cats-only/unknown;conditional smoke;two sources conflict;zero results;lost response;Madrid DST. Не включать migration/client/endpoints.
2. **BASE-373 review/интеграция**, независимо от AI-07. Review fingerprint/input-builder/grammar/CLI на current main, проверить importer/gallery, source identity и payment/TOP #372. PR#373 не сливать автоматически и не заменять main веткой planning.
3. **AI-07 quota → AI-08 conversation**: первый независимый кодовый поток после AI-01. Disposable PostgreSQL, concurrency последнего slot, cross-midnight replay, failure/cancel/fence, signed guest identity, technical attempt gate до ASR. Без live provider/production DB. Можно параллельно с facts/parser review.
4. **AI-03 schema → AI-04 queue/resolver** после AI-01 и accepted parser contract; design/mocks можно раньше фактического merge. Additive migrations на current head, durable marker/reconciler, late hash/status rejection, source retirement/owner explicit precedence. Индексы окончательно выбирать по AI-02/SQL plans.
5. **AI-02 targeted real data evidence → AI-05 source/privacy boundary**, как только DBA разрешит RO. Safe formatter improvement можно до DB доступа. Объём backfill, source eligibility/quality и freshness windows до получения evidence не утверждать. Никаких crawls/changes active sources.
6. **AI-06 DeepSeek facts worker** после AI-04/05, сначала mocks. Реальное enrichment только после provider/privacy permission; user search не ждёт его. **AI-09 text retrieval** после03/04/07/08, сначала с controlled facts; strict predicates+TOP+cursor+cards до pagination.
7. **AI-10 existing SavedSearch/alerts**, после09 и enrichment event contract06: shared matcher, first-enrichment notification, dedup повторов/reimports/preference revision, stale-source recheck. Background business quota решение сначала AI-01.
8. **AI-11 completed-file ASR → AI-12 React voice integration**, после07/08/09/05, provider contracts и privacy. Mock adapters и recorder UI можно разрабатывать параллельно раньше. Production mic headers менять только будущим reviewed PR; не открывать free-ASR preview loop.
9. **AI-13 staging evidence/release runbook**, после работающих06/09/10/11/12. Gold quality+real browser10s+bounded concurrency/recovery+non-AI regressions. Отдельный release check current main/source flags/DB head/privacy/CI и manual approval; audit PR не является разрешением deploy.

Параллельные команды разработки не должны независимо изобретать DTO/provenance/operation keys. После AI-01 независимы quota/session, facts/queue, DBA/source/privacy, provider mocks и UI shell. Hard SQL matching зависит от facts+semantics, live ASR от quota+privacy, notifications от shared matcher; эти зависимости не сокращаются созданием дополнительных агентов.

## Что закрыть до какого этапа

| Этап | Разрешено начинать | Что ещё обязательно |
|---|---|---|
| Offline development | ADR/DTO, quota tests, session fakes, schema design, mock clients, recorder shell | current code baseline и agreed contracts; не требуются production counts/keys |
| Disposable/staging mocks | migration compatibility, transactional races, UI full flow с fakes | реализованные части, isolated infrastructure; fake speed не provider acceptance |
| Live staging | small authorized sanitized corpus, real providers, performance traces | privacy/DPA/account/paid authorization, working feature, quota/attempt caps |
| Catalog backfill | сначала dry-run на RO replica, затем separately approved batch | real eligible source counts/evidence/freshness, outbound minimization, queue recovery |
| Production activation | только после всех material gates | real quality/SLO+errors, safe current data, final CI, flags/rollback, manual approval |

Общий development verdict — **READY_FOR_DEVELOPMENT**. Статус live staging — **NEEDS_IMPLEMENTATION / NEEDS_MEASUREMENT** с отдельным privacy/access blocker. Production verdict — **BLOCKED**. Дополнительный общий аудит не нужен: достаточно перечисленных адресных closure checks с датой/методом/точным release candidate SHA.
