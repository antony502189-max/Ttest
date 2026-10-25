# Последовательность внедрения AI-поиска

Дата: 2026-10-25. Этот документ — **план будущих PR**, не разрешение изменять production. В рамках текущего задания реализованы только отчёты. База анализа: main/production `1292c6807ece59999238bb31c80e09ef7e2c3212`, planning `1ace67b5ae67ab267fdcc37ee499b87bd433fb71`, parser #373 `fcae378d9dbbc8447f18df150327180f6f2c8231`. Все новые компоненты ниже — INFERRED/proposed, существующая база проверена в [production audit](PRODUCTION_REALITY_AUDIT.md) и [readiness](AI_INTEGRATION_READINESS.md).

## 1. Первый безопасный PR

**PR-AI-01: «ADR совместимости, provenance и versioned AI intent — без runtime-интеграции».** Его можно начать немедленно: он не требует provider credentials, production DB или закрытия старых вопросов, на которые владелец уже ответил. Он не дублирует код parser foundation и фиксирует опасные различия `== capacity`/`>= capacity`, unknown/default, hard/soft и неизменяемый TOP/boost order до создания новых таблиц.

Одновременно отдельно провести human review #373 и добавить read-only измерения, когда появится разрешённая replica/роль. **Не сливать #373 автоматически**, не переносить feature branch в main wholesale. Planning отстаёт от main в изменениях #372; перед будущим кодовым переносом проверить payment integrity и сохранить новые main изменения.

Первые implementation PR по умолчанию направлять в planning; будущий production integration PR — отдельный reviewed перенос на актуальный main. Только отчётная ветка настоящего аудита уже создана локально: `audit/ai-production-readiness-2026-10-25`.

## 2. Зависимости

```text
AI-01 contracts / ADR
  ├─ AI-02 read-only evidence + observability
  ├─ AI-03 facts schema ─ AI-04 queue/resolver ────────┐
  ├─ AI-05 privacy + selected source evidence ────────┤
  │                                                 └─ AI-06 enrichment worker
  └─ AI-07 quota ledger ─ AI-08 session/patch ─ AI-09 text matching API
                                                   ├─ AI-10 saved alerts
                                                   ├─ AI-11 batch ASR backend
                                                   └─ AI-12 frontend text/voice
AI-02/06/09/10/11/12 ─ AI-13 staging eval + controlled rollout plan
```

AI-09 strict compatibility требует AI-03/04 и доказанных features; mocked development может идти раньше. AI-12 text shell может идти до ASR, но voice acceptance требует AI-11. AI-02 access limitations не блокируют DTO/ADR, однако реальные coverage/backfill/launch gates без них не закрываются.

## 3. PR-AI-01 — договориться о проверяемых контрактах

- **Цель:** ADR на fact provenance, conditional/conflict/unknown/legacy_unverified, occupancy/party composition, intent patch/unset/clarify, taxonomy и TOP ordering. Убрать противоречивые stale вопросы/cost-cutoff из документов.
- **Зависимости:** текущие решения владельца; статический review S02/S03/S05/S10. #373 можно ревьюить параллельно, не дублируя его builder.
- **Компоненты:** `docs/ai-voice-search/adr/`, IMPLEMENTATION_PLAN/FINAL_ROADMAP; JSON examples schemas в docs. При необходимости executable DTO вынести отдельным follow-up, чтобы этот первый PR остался offline/documentation-only.
- **Миграции:** нет.
- **Проверки:** согласованные примеры RU/ES с отрицаниями/conditions, «двое» при capacity3, one-bedroom apartment, late follow-up «только балкон», successful zero matches, quota/DST/idempotency examples.
- **Риски:** ошибочно принять legacy defaults за явные ответы; объявить unknown permission; менять TOP boost priority; забыть квартиры из настоящего каталога.
- **Acceptance:** фиксированы поля/статусы и единицы, отсутствие LLM SQL, отсутствие silent relaxation, 3/200 Madrid, shared text/voice, owner requirements выше старых docs; перечень действительно нерешённых technical decisions короткий.
- **Совместимость/результат:** существующие DTO/поиск/карта/платежи не меняются; reviewable ADR и API draft с examples. **Именно этот PR безопасен сейчас**, не требует paid API.

## 4. PR-AI-02 — реальные агрегаты и диагностика источников

- **Цель:** закрыть N/A для source coverage и улучшить наблюдаемость без ручного импорта.
- **Зависимости:** отдельно reviewed #373; approved staging/read-only replica/роль. Если доступа пока нет, начать только safe formatter regression; не создавать DB users в production в этом PR.
- **Компоненты:** `backend/app/commands/audit_ai_listing_data.py`, `core/observability.py`, worker diagnostics tests, docs audit appendices. Export fixed source labels/numeric counters/statuses, не arbitrary extra и не descriptions/IDs.
- **Миграции:** нет, если данные читаются из существующих источников; query-only DBA access provisioning отдельная operator task.
- **Проверки:** реальные роли/permissions и read-only transaction, statement timeout, bounded queries; memory на большом snapshot set; no env fallback; sensitive-field negative tests; formatter сохраняет только разрешённые source/result/counters.
- **Риски:** all-source scan/large accumulator, PII в JSON extra, ложный успех по `external_import_finished`, refresh timestamps без content change.
- **Acceptance:** source matrix n/active/canonicals/published/freshness/description p50/p95/policies/defaults/conflicts; separate public geography mismatch check; численные знаменатели; fixture results помечены synthetic; raw text/HTML не экспортируются.
- **Совместимость/результат:** ни crawler, ни deactivation, ни gallery не запускаются; отдельный evidence report, anonymized gold-set при разрешённом доступе, измеренный eligible/backfill estimate. Без доступа PR не должен утверждать закрытый coverage gate.

## 5. PR-AI-03 — expand-only схема фактов

- **Цель:** хранить per-source versioned facts и canonical feature projection независимо от legacy scalar defaults.
- **Зависимости:** AI-01; #373 accepted foundation; измерения AI-02 для выбора индексов.
- **Компоненты:** новые models `listing_ai_facts`, `listing_search_features`, typed fact schemas/repository; новая Alembic revision **после актуального main head**, не редактировать старые migrations.
- **Миграции:** additive tables/indexes. Номер определить после повторной проверки remote head, не резервировать слепо `0067` в старой planning history.
- **Тесты:** upgrade на disposable PostGIS, прежний app release продолжает читать/писать, null/false/0 provenance, source FK/history lifecycle, unique content/version key, query plans на production-like fixtures.
- **Риски:** FK/cascade потеряет необходимую историю; JSONB без query design; blocks при index build; модель capacity включает bed count/current residents вместо max occupants.
- **Acceptance:** confirmed/conditional/unknown/conflict различимы; owner explicit vs default различимы; features не читаются старым search автоматически; idempotent versioned writes; migration guard проходит.
- **Совместимость/результат:** legacy Listing/room DTOs, map and TOP untouched; схемы+repository+integration evidence. При feature off новая таблица не меняет выдачу.

## 6. PR-AI-04 — durable очередь и canonical resolver

- **Цель:** безопасный offline execution lifecycle и согласованная canonical projection без provider calls.
- **Зависимости:** AI-03, решения conflicts/freshness AI-01.
- **Компоненты:** `ai_enrichment_jobs`, lightweight commit marker/reconciler, claim/lease/fencing service, resolver; tests интеграции `services/external_import.py`. Reuse SKIP LOCKED/mail lease pattern, не mail payload/table.
- **Миграции:** отдельная additive jobs/outbox table с unique source+hash+extractor/schema version, next_attempt/lease indexes.
- **Тесты:** crash до/после commit, missed marker healed by reconciler, duplicate events, concurrent claims, lease loss, primary switch, source removal/reactivation/retirement, current hash mismatch, owner override, DLQ без provider.
- **Риски:** provider I/O внутри importer transaction, broad fingerprint churn, source primary переопределит более надёжный факт, новая очередь заблокирует scraper/media.
- **Acceptance:** importer latency не зависит от model latency; stale result не становится current; одинаковый input не создаёт второй job; failures не меняют listing visibility/gallery; resolver сохраняет conflict вместо произвольного разрешения.
- **Совместимость/результат:** обычный import lifecycle unchanged except durable marker; isolation flags; queue/resolver ready с fake extractor и bounded admin diagnostics.

## 7. PR-AI-05 — outbound privacy и адресное качество evidence

- **Цель:** ограничить отправляемые тексты и исправить только доказанные потери выбранных adapters.
- **Зависимости:** AI-01, реальные дефекты AI-02, offline input builder F.
- **Компоненты:** `ai_listing_input.py`, privacy validator, source-specific fixtures; один adapter improvement на отдельный небольшой PR при разных причинах. Сначала route-ID/full-description selection и structured facts allowlist, затем другие источники по измеренному приоритету.
- **Миграции:** обычно нет; additive source evidence envelope/version в JSONB. Поля raw history не переписывать массово.
- **Тесты:** contacts/email/handles/name/precise address minimization, nested DOM, page chrome/unrelated JSON object, prompt injection, negation retained, content hash stable при фото/contact-only change и меняется при semantic change.
- **Риски:** regex cleaner выдаётся за универсальную PII защиту; удаление отрицания; full HTML уходит провайдеру; guessed Habitaclia coordinates; обход access controls источника.
- **Acceptance:** selected minimal evidence, no raw payload routing, unknown when insufficient; actual API terms/retention/processing reviewed отдельно до live calls; measured coverage improvement на обезличенном наборе; не только synthetic example.
- **Совместимость/результат:** price cadence/IDs/URLs/location/gallery/dedup сохранены; tested outbound packet boundary и source defect evidence. Нового crawling в PR validation нет.

## 8. PR-AI-06 — DeepSeek adapter и изолированный enrichment worker

- **Цель:** асинхронное извлечение фактов с typed output и стоимостью, независимое от поиска.
- **Зависимости:** AI-03/04/05; API-specific privacy/account gate. Live provider pilot — отдельное разрешённое действие после offline tests.
- **Компоненты:** provider protocol/DeepSeek adapter, `ListingFactExtractor`, validated prompt/version, worker, safe usage metrics, feature flag off; deployment service definition только после review в отдельном rollout change, не фактический deploy.
- **Миграции:** нет поверх jobs/facts, при необходимости отдельный additive provider usage ledger; не новые поля в cards.
- **Тесты:** HTTP mocks JSON empty/truncated/type mismatch, evidence mismatch, 429/5xx/timeouts, no retry401/402, dead-letter/requeue, stale responses, hash/model version, PII log scans, concurrency1 initial.
- **Риски:** alias drift deepseek-flash, thinking latency, provider cost при retries, untrusted instructions, workers конкурируют с importer.
- **Acceptance:** model/prompt/schema/usage сохранены; no SQL/tools/browser output; job failures не ломают importer; bounded retries/deadline/circuit breaker; staging quality metrics по false explicit permits и coverage.
- **Совместимость/результат:** separate process/flag, existing listing rendering unchanged; adapter+worker+metrics/runbook; никаких production backfill в PR.

## 9. PR-AI-07 — дневная quota и idempotency ledger

- **Цель:** 3 anon /200 registered успешных user messages, общий text/voice budget, exact calendar reset.
- **Зависимости:** AI-01 и существующая auth S09; provider можно fake.
- **Компоненты:** `ai_usage_days`, `ai_search_requests`, quota service, anonymous cookie issuer, retry/replay/fencing; Redis только cache/abuse, DB authoritative.
- **Миграции:** additive daily/request ledger tables с uniqueness и минимальными indexes; retention strategy; no user quota mutation существующих данных.
- **Тесты:** concurrent remaining1, duplicate Idempotency-Key same/different hash, crash/provider failure/release/replay, lost HTTP response, Redis unavailable, DB unavailable, 23h/25h Madrid day, cross-midnight retry, login/logout/multi-device, invalid bearer, disabled/banned account.
- **Риски:** double debit, abandoned reservations permanently exhaust quota, local memory gives free allowance, anonymous cookie rotation, unbounded quota keys.
- **Acceptance:** successful zero results =1; failures=0; 201st/4th rejected without model calls; retries одного success=0 новых debits; provider cost ≠business count; normal search available; no monthly spending cutoff.
- **Совместимость/результат:** existing rate limiter/auth behavior unchanged; отдельный quota API и proof through concurrent DB tests.

## 10. PR-AI-08 — structured session и intent patches

- **Цель:** сохранять прошлые критерии и менять лишь запрошенные поля.
- **Зависимости:** AI-01/07; fake IntentExtractor вначале, реальный DeepSeek client может reuse AI-06 transport, но отдельный prompt/schema.
- **Компоненты:** `schemas/ai_search.py`, session repository/state cache, typed patch validator, owner/session binding; Redis TTL+durable successful result version.
- **Миграции:** если authoritative semantic state не помещается в request ledger, отдельная additive session table; raw conversation history не нужна.
- **Тесты:** Adeje/2 people/600 → balcony →700; explicit unset/clear-all; ambiguous municipality; duplicate context; concurrent version409; provider invalid patch; session expiry/logout; no unexpected loosening.
- **Риски:** LLM memory считается реальной server state; patch from stale version; session ID как bearer secret без subject check; PII retention.
- **Acceptance:** omitted поля сохраняются, unset различим от unknown и false; server version/subject обязательны; bounded context; no raw text logs; anonymous и authenticated flows одинаково корректны.
- **Совместимость/результат:** contract/service with mocked eval, no change ordinary filter semantics; upstream intent layer готов к query orchestration.

## 11. PR-AI-09 — текстовый query API и deterministic matching

- **Цель:** один shared pipeline выдаёт existing cards и evidence-backed explanations.
- **Зависимости:** AI-03/04/07/08; strict policy filters только при готовых facts; AI-02 query/coverage baseline.
- **Компоненты:** `api/v1/ai_search.py`, orchestration service, matcher/repository composition, existing DTO, pagination/results replay; clear unsupported type behavior или отдельный reviewed taxonomy follow-up.
- **Миграции:** при необходимости additive features indexes по measured plans, не менять Listing.status/price constraints.
- **Тесты:** native/external/moderation/price/rental-mode/location preservation, capacity>=party отдельно exact standard, unknown/conditions/conflicts, ranking TOP+boost+relevance+UUID, pagination/filter hash, no per-card model calls; corrupted provider output fails safely.
- **Риски:** post-filter small page даёт неправильные totals; pure relevance нарушает paid boost; apartment mapped to studio; SQL из model; blocking DB connection на provider await.
- **Acceptance:** POST/query success debit1; pages/cursor не списывают quota; explanations из facts/reason codes; 0 matches честно; ordinary routes byte-compatible по contracts; read-only SQL query semantics сохранены.
- **Совместимость/результат:** server API+tests+documented errors, reusable `ListingCardResponse`; не новый search server и не изменение TOP.

## 12. PR-AI-10 — saved AI criteria и existing alerts

- **Цель:** зарегистрированные сохраняют AI intent и получают уведомления по тем же правилам matching.
- **Зависимости:** AI-08/09; source enrichment completion AI-06 для delayed-fact alerts.
- **Компоненты:** existing SavedSearch JSONB validation/translator, `services/notifications.py`, existing outbox, enrichment re-match marker; auth UI trigger.
- **Миграции:** не обязательны для versioned JSONB; новая event idempotency index/table только если обоснована, additive.
- **Тесты:** ownership/auth/registration, legacy filter restoration, unknown AI fields не теряются, delayed enrichment match, duplicate import/re-enrichment no duplicate email, removal/closed, alert opt-out, ban/user deletion, stale source.
- **Риски:** JSON сохраняется, но ignored matcher; guest sees false promise; N saved searches ×N listings; push waitlist ошибочно используется как общий notification engine.
- **Acceptance:** один same matcher для interactive/alerts; bounded background preselection, no LLM per saved search; existing recipient+idempotency/outbox reuse; user registration обязательна для AI save/alerts.
- **Совместимость/результат:** legacy saved searches/notifications/favorites intact; end-to-end fake-provider alert lifecycle, не отдельная система рассылок.

## 13. PR-AI-11 — ASR backend с редактированием транскрипта

- **Цель:** завершённый audio file → preview → query в той же reservation; Groq primary, OpenAI gpt-transcribe fallback.
- **Зависимости:** AI-05/07/08/09, privacy/provider account controls; no paid eval до отдельного разрешённого этапа.
- **Компоненты:** ASR interface и два adapters, scoped multipart route, byte/container/codec/duration validator, temporary storage cleanup, provider budgets; scoped Nginx route/config tests как reviewed source change.
- **Миграции:** request ledger states reuse; постоянная audio table не нужна по умолчанию.
- **Тесты:** webm/mp4/wav fixtures, MIME spoof/too large/long/corrupt/silence, partial upload/cancel, fallback deadline/429, hidden retries, edit preview, operation expiry/fence, SSRF URL refused, delete temp after every failure.
- **Риски:** generic256KiB reject, inference blocks30s proxy, ASR preview abuse, gpt-4o deprecated name, wrong language vs languages field, audio PII в logs.
- **Acceptance:** ASR только после stop; max60s/8MiB initial; transcript editable/retake; single debit only final success; bounded ASR technical budget; no TTS/live streaming; no changes global JSON cap.
- **Совместимость/результат:** tested upload contracts and adapters; feature off initially. Никакого install ПО на VPS/production deploy в рамках code PR.

## 14. PR-AI-12 — frontend, сначала текст, затем голос

- **Цель:** встроить assistant без замены карточек/карты.
- **Зависимости:** AI-09; voice acceptance AI-11. При большом diff разделить **12a text panel** и **12b MediaRecorder**.
- **Компоненты:** SearchForm/HomePage/mobile-app-v2, новый isolated panel/hook, app-context+URL adapter, `src/api/ai-search.ts`, explanation adjunct; существующие PropertyCard/MobileResultCard менять только минимальным optional integration.
- **Миграции:** нет.
- **Тесты:** 375/390/768/1024/1440 layouts, mobile keyboard, focus/Escape/return focus, permission denied/missing/revoked, record/stop/cancel/retake, text editing, quotas3/200/reset display, Back/map/list/filter restore, double click/stale response, external redirects/gallery/TOP/favorites.
- **Риски:** два независимых mobile/desktop filter state, скрытый default сбросит hard constraints, sticky dialog перекроет controls, new full cards потеряют external behavior.
- **Acceptance:** API credentials отсутствуют в JS; normal search доступен после exhaustion/error; text fallback работает на unsupported device; no map feature changes; cards/galleries/source labels/TOP сохранены; text-only answer.
- **Совместимость/результат:** screenshots/E2E и реальные supported-browser observations; same-origin microphone permission policy согласована с backend/Nginx, без wildcard relaxation.

## 15. PR-AI-13 — staging eval, эксплуатация и rollout plan

- **Цель:** доказать quality/capacity/privacy/compatibility до включения production.
- **Зависимости:** AI-02/06/09–12, actual provider terms/account limits и approved test corpus; отдельное разрешение на платный pilot.
- **Компоненты:** обезличенные eval sets/results, runbook/metrics/dashboards configs, flags/concurrency config, backfill dry-run и staged rollout checklist. Не менять production при принятии документа.
- **Миграции:** новые только если показана необходимость и пройдена compatibility guard; no destructive cleanup/backfill-as-migration.
- **Проверки:** ASR critical-slot accuracy RU/ES/mixed, fact false-permit rates, latency/cost/retries, quota reconciliation/crash drills, realistic query plans, background backlog recovery, DB/Redis memory and pool headroom, ordinary payment/search/import regression envelope.
- **Риски:** synthetic4 snapshots выданы за coverage,1 163 canonical=backfill source count, работающие healthchecks выданы за SMTP/provider performance; uncontrolled costs при retry storms.
- **Acceptance:** измеренные и согласованные threshold values вместо произвольного «95% accuracy»; source eligibility/freshness; provider costs visible; no monthly cutoff; business quotas корректны; known failures main разобраны; rollback выключает AI consumption без потери старого поиска.
- **Совместимость/результат:** go/no-go report, маленькая staging партия25–50, план увеличения; production только отдельный manual dispatch/approval согласно существующему процессу, не автоматический merge/deploy.

## 16. Отдельные эксплуатационные задачи

Это будущие actions оператора, **не выполненные этим аудитом**: approved read-only replica/роль; branch protection policy; investigation post-merge main10 browser failures; source diagnostics rollout; provider account privacy/limits; Redis memory/retention budget; scraping permissions/source freshness; documented tourist-rental review.

Ни одна из них не требует присылать пароль/API key в чат. Read-only DB evidence должно приходить через безопасный согласованный механизм. Успешный SSH и наличие write-capable app role не снимают требование отдельной DB-роли.

## 17. Ответы на финальные 14 вопросов

| № | Вопрос | Конкретный ответ и evidence |
|---:|---|---|
| 1 | Что реально работает сегодня? | M на vmi3640228: frontend/backend/importer/mail, PostgreSQL16.4, Redis, MinIO, Traefik; 7 app/data services healthy, Traefik running без Docker healthcheck. E02–E04 |
| 2 | Чем production отличается от main? | SHA совпали; public build-info/current/main=M. Пять backend Git blobs совпали с runtime SHA-256. Полная файловая/DB/data equivalence не утверждается. E01–E04 |
| 3 | Что в parser foundation не слито? | Весь #373 open: policy evidence grammar, optional scalar fingerprint, audit CLI, offline typed sanitized hash input, fixtures/regressions/CI. F не production. E07/S10/S12 |
| 4 | Какие реальные ограничения данных опасны? | Публично1 163; regional sum967 (разница196, причина не установлена); реальные one-bedroom apartments вне3 exact DTO types; policy coverage неизвестна; defaults/snapshot/fingerprint/conflicts риски подтверждены кодом. E05/S03/S05/S06 |
| 5 | Что переиспользовать? | FastAPI/SQLAlchemy/Pydantic, visibility/price/geography/card DTO+cursor, auth, Redis infrastructure, оба renderer/галереи/TOP, SavedSearch/notifications/mail leasing. S01–S09/S11/S15 |
| 6 | Что до Groq? | Batch upload/capture, same-origin microphone policy, scoped body/timeout validation, reservation/idempotency, privacy+account limits, ASR adapters/eval; в backend GROQ_API_KEY не настроен. E03/E04/S07 |
| 7 | Что до DeepSeek? | server adapter по актуальному deepseek-flash, separate intent/fact prompts, strict output/evidence, durable jobs/facts, privacy gate/API-specific terms и eval. Сейчас client/key/worker отсутствуют. S10/S12/E04 |
| 8 | Как обеспечить3/200? | Authoritative DB daily+request ledger, atomic short reserve/finalize/release, user/guest binding, Idempotency-Key, Madrid next-calendar-midnight UTC, fenced recovery; Redis cache/abuse, не local quota fallback. Readiness§9 |
| 9 | Достаточен ли existing search API? | Для price/location/rental/type подмножества да; confirmed>=party, conditions/conflicts/hard-soft и apartment taxonomy требуют additions. Exact roomCapacity semantics оставить. S02/S03 |
| 10 | Как сохранить cards/TOP? | Existing ListingCardResponse + PropertyCard/MobileResultCard, отдельные explanation codes, same external/gallery/favorite behavior; hard eligibility перед неизменёнными TOP/boost keys; no client per-page reranking. S02/S07/S08 |
| 11 | Главные ops/privacy риски? | PII из source snapshots/audio, provider terms неизвестны, false permits, quota retries/crash, source errors/потеря diagnostics, Redis no cap, DB peak unknown, main unprotected/post-merge failures. E04/E06/E08/E09 |
| 12 | Какой PR первым и почему? | **AI-01 ADR/versioned evidence+intent contracts**, docs-only offline: безопасен сейчас и предотвращает неверные semantics до DB/provider work; #373 review отдельно. §3 |
| 13 | Что действительно блокирует? | Production launch: data provenance/coverage, privacy/provider permissions, quota correctness, safe voice transport, TOP/taxonomy compatibility и quality/regressions. Offline ADR и mocks этим не заблокированы. |
| 14 | Чего нет из-за доступа? | Полный DB/source inventory, policy/description coverage, conflicts/freshness, live Alembic/PostGIS/indexes/plans/connections/outbox backlog; provider accounts/privacy/limits не доступны. SSH доступен, DB read-only доступ не установлен. |

Ни merge, ни deploy, ни migration, ни paid API, ни импорт/backfill в этом аудите не выполнялись. [Машинное резюме](audit-summary.json) сохраняет null для неизмеренных величин.
