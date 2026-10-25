# 10 — Техническое задание на реализацию AI Search для 112233.es

> **Рабочее ТЗ разработчику. Версия 2026-10-25 (после заключительного аудита Codex, PR #375).**
>
> **Статус:** `READY_FOR_DEVELOPMENT` — можно писать код в отдельных PR. `PRODUCTION_ROLLOUT_BLOCKED` — запуск для пользователей запрещён до прохождения перечисленных ворот. Ни одна новая AI-функция не считается реализованной только потому, что здесь описана.
>
> **Приоритет документов:** прямые решения владельца и [01_PRODUCT_SPEC.md](01_PRODUCT_SPEC.md) → это рабочее ТЗ → [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md) → [05_IMPLEMENTATION_PLAN.md](05_IMPLEMENTATION_PLAN.md) → новые аудиты [PR #375](https://github.com/antony502189-max/Ttest/pull/375) → исторические материалы. При конфликте старого текста с утверждёнными решениями не реализовывать устаревшее без нового согласования. Технические варианты в данном документе явно помечены как **рекомендация / ADR**, а не как новая продуктовая договорённость.

## 1. Назначение и границы проекта

Встроить в существующий Ttest голосовой и текстовый помощник, который преобразует запрос пользователя в точные критерии **аренды жилья**, ищет по уже сохранённому каталогу и показывает **существующие карточки**, объясняя подтверждённые причины соответствия. Повторные сообщения уточняют отдельные критерии без сброса предыдущих условий. Никакого отдельного поискового сайта, переписывания React/cards, новой карты, вакансий, POI, маршрутов, TTS, live-ASR, live scraping на пользовательском пути или локальных моделей.

**Нельзя ломать:** native/external карточки и source redirect, галереи, избранное, карту, сохранение поиска, notification/outbox, paid TOP/promotions, Stripe, допустимые rental modes, price ceilings, модерацию и парсеры. Устаревшая planning-ветка НЕ подменяет current `main` с платежными изменениями #372.

## 2. Реальный пользовательский сценарий

1. Пользователь открывает текущий поиск и выбирает **текст** или **запись голоса**.
2. Голос: start record → говорит → stop → **один Send**; *запись должна закончиться до ASR*. Нет обязательного preview/«подтвердить транскрипт» перед первой выдачей.
3. FastAPI проверяет авторизацию, feature flag, техническую защиту от спама и бизнес-квоту, **резервирует единственную операцию до платного ASR**.
4. Для аудио Groq Whisper Large V3 транскрибирует завершённый файл; text bypasses ASR. При необходимости OpenAI GPT-Transcribe — резерв после отдельного eval/approval.
5. DeepSeek Flash извлекает **strict JSON intent patch**; сервер проверяет Pydantic схемы, обрабатывает совместимость и сохраняет нормализованное состояние разговора.
6. Existing SQL/PostGIS filters + **предварительно вычисленные verified facts** строят кандидатов; hard-условия проверяются **до count/order/seek/pagination**; current TOP/boost sorting сохраняется.
7. Backend возвращает прежний `ListingCardResponse`, короткий **детерминированный** текст/reason codes, transcript для добровольной правки, остаток квоты, session/version и cursor.
8. Frontend **показывает первые подходящие существующие карточки** и доступное объяснение без дополнительных кликов. После Send результат должен появляться **p95 <=10 сек** для согласованной типовой сети/нагрузки. Затем пользователь может исправить текст или уточнить запрос новой фразой.

Пример: «Мы вдвоём, пара, с маленькой собакой, до 650 евро, Адехе» → карты/карточки по допустимому каталогу с указанными подтверждёнными фактами. Follow-up «теперь только с балконом» добавляет balcony и оставляет состав, животных, географию и потолок цены неизменными. Follow-up «до 700» заменяет только предел бюджета.

При нераспознанном критическом параметре (цена, отрицание, место) нельзя угадывать. Запросить уточнение либо сообщить о проблеме, не выдавать неподходящие карточки как точные matches.

## 3. Обязательная скорость, UX и измерение

**Согласовано владельцем:** быстрое появление объявлений — примерно **10 секунд после отправки завершённой голосовой записи**.

**Engineering acceptance:** browser-observed `p95 <= 10,000 ms` от `Send` до первого paint **содержательных и действительно подходящих** карточек **текущей** операции, при поддерживаемой типовой сети/нагрузке и исправных провайдерах. Время записи исключено, upload включён. Skeleton, старый список, transcript и HTTP 200 не равны результату. Для честного `zero-results` отдельно измерять `Send→verified empty state`: это successful business request, но **не** результат card-render SLO. Публиковать error/timeout/429, p50/p95/p99 и долю **всех** валидных обращений, вовремя получивших корректный результат; не исключать неуспехи ради красивого p95.

**Рекомендация:** один multipart `POST /api/v1/ai-search/query` с audio → batch ASR → intent → SQL/cards; text проходит через тот же orchestrator. Не создавать публично доступный unlimited free-transcriptions endpoint. Асинхронные deadline-bound HTTP clients, без DB connection во время ожидания Groq/DeepSeek. Ресурсный budget — upload 1.5s, ASR 3s, intent 2.5s, SQL 1s, finalize/serialize/render+reserve 2s; **пока только гипотеза**. При плохом мобильном upload, long-audio/provider outage целевой срок не гарантирован: progress/error/fallback без ложного обещания. Реальное выполнение 10 секунд подтвердить **staging browser E2E**, не из трёх имеющихся HTTP samples (0.596/1.799/0.927 сек).

Запрещены синхронное LLM enrichment каждого найденного объявления, внешний crawl, geocoding/Places API, LLM SQL и тяжёлые галереи в blocking request. Картинки подгружаются существующим renderer независимо от первого осмысленного paint.

## 4. Провайдеры / данные / безопасность

| Задача | Кандидат | Реализация |
|---|---|---|
| ASR завершённого аудио | Groq `whisper-large-v3` | server-side, MIME/codec/duration/bytes checking, timeout, error/retry budget |
| ASR fallback | OpenAI `gpt-transcribe` | только при утверждённом provider config и сравнительном тестировании |
| Search intent | DeepSeek Flash | один bounded structured output request, строгий Pydantic, no tools/SQL |
| Source facts enrichment | DeepSeek Flash | **отдельная долговечная асинхронная очередь** по сохранённым sanitized snapshots |
| Search and ranking | Existing FastAPI + PostgreSQL/PostGIS | SQL predicates и commercial TOP, без inference on query-per-card |
| Sessions / anti-abuse | Redis + PostgreSQL | ephemeral state Redis допустим, quota truth в PostgreSQL |

Перед любым платным или персональным outbound вызовом: подтверждённые настройки account/DPA/retention и privacy approval. Внешней модели **не передавать** контакты, полный HTML, raw payload, email/phone, точный приватный адрес, токены или внутренние примечания. Server-side ключи; never `VITE_*`. Prompt injection в source content не должен давать полномочий на tools/SQL.

## 5. Source evidence, качество фактов и свежесть

Разработать typed per-source facts с provenance: `source_record_id`, `canonical_listing_id`, `status` (`explicit_allow/explicit_deny/conditional/unknown/conflict/legacy_unverified`), `typed_value`, `qualifiers`, `evidence`, `origin`, `observed_at`, `content_hash`, `schema/extractor_version`. Для чисел хранить подтверждённое значение, единицы измерения и происхождение, не «allow».

Между `source snapshots` и `canonical listing_search_features` — явный resolver. При равнозначных противоречащих условиях статус `conflict`, а не «последний импорт победил». Old defaults `pets_allowed=false`, `furnished=true`, `deposit=0` и `room_capacity=1` не являются доказанным указанием владельца. Отсутствие сведений → `unknown`. «Маленькие собаки по согласованию» не означает «все питомцы разрешены». «Курить на балконе» не означает «курить в доме».

Поддержать: long/holiday, EUR и monthly/nightly/weekly, room/shared/studio/one-bedroom и подтверждённые типы из каталога, INE geography/Adeje/Arona, подтверждённая вместимость `>= N` (НЕ меняя legacy `roomCapacity==N`), состав жильцов/пара/друзья/дети, pets species/size/count, smoking scope, furniture, bills, deposit, balcony/terrace, duration/dates, amenities, freshness. Hard mismatch исключается; unknown/conditional показываются только по согласованной логике и **не** маркируются гарантированным совпадением. Не показывать выдуманные проценты соответствия.

Freshness: published/active — не гарантия актуальности во внешнем источнике. Использовать source status/last successful check/last content change/evidence age; не считать refresh timestamp «описание изменилось». Не вводить глобальный скрытый TTL на каталог без измерений. Не проверять сторонние сайты на request path.

**Ключевой внешний блокер:** реальный DB inventory/coverage/source-health не измерен. Публичные примеры показывали Pisos/Fotocasa; нельзя утверждать, что семь настроенных адаптеров стабильно поставляют свежие объекты. Отдельная разрешённая DBA read-only роль/реплика обязательна для source coverage, SQL plans и production backfill planning. Без неё — только mocks/документы/isolated tests, не реальные проценты.

## 6. Квота — утверждённая бизнес-семантика

| Вопрос | Правило |
|---|---|
| Гость | **3** успешных user AI сообщения / calendar day |
| Авторизованный | **200** успешных user AI сообщения / calendar day |
| Сброс | **00:00 Europe/Madrid**, DST-aware, НЕ фиксированные 24 часа |
| Каналы | Голос и текст используют **общий** лимит |
| Списание | **Ровно 1** на успешное пользовательское обращение, включая корректный zero-result |
| Ошибка сервиса | Не списывать при ASR/LLM/backend/system failure |
| Follow-up | Каждое новое сообщение пользователя = новый запрос |
| Обычный поиск | Без AI quota |
| Сохранённый поиск/уведомления | Сохранять/включать только авторизованным |

**Рекомендуемый, ещё не реализованный контракт:** PostgreSQL authoritative `ai_usage_days` + `ai_search_requests`; short atomic reserve/finalize/release transaction с idempotency key, request hash, leases/fencing и CAS session. Резерв **до** Groq; сетевые вызовы не держат PG lock. Retry same key+same hash возвращает тот же result/status без второго платного вызова/debit. Двойное нажатие и параллельный последний слот не обходят лимит. Падение провайдера release, crash/recovery корректно завершает операции. Отдельный технический лимит попыток/audio seconds до ASR предотвращает расход API при бесконечных бесплатных повторах. Гость — signed HttpOnly Secure SameSite identifier, IP только дополнительный anti-abuse (не обещать уникального физического человека).

**Открытые решения для ADR, не выдавать за утверждённые:**
- AI-подсказка «уточните условие» как successfully processed AI reply: считать одним обращением или нет? Зафиксировать одинаковое правило для voice/text.
- Фоновые matched SavedSearch alerts **рекомендуется** не учитывать в интерактивных 3/200 — требуется формальное согласование.
- Guest→login quotas/session ownership, технический ASR attempts budget, grace/fence durations — детали контракта, тестировать.

## 7. Search, TOP, cursor, карточки

Existing `/api/v1/listings/search/cards`, DTO, `PropertyCard` и `MobileResultCard` — **переиспользовать**. В одном SQL query применить AI-predicates, visibility и confirmed matching **до** `count/order/seek/limit`. Не фильтровать уже пагинированные 20 карточек на frontend/Python.

Коммерческие sort keys `active_TOP DESC, boosted_at DESC` и существующий tier/rules не менять. Сначала eligibility/hard criteria, потом текущие commercial sort keys; мягкий AI score не должен перекидывать неподходящее объявление вперед, нарушать paid priority или делать rerank только внутри страницы. Исключить confirmed-incompatible TOP можно по тому же принципу, по которому текущий поиск исключает TOP по цене/месту, но договорные promises TOP подлежат review.

Cursor bind к normalized intent/session version, filter/query hash, relevant facts/resolver version и promotion state (expiry between pages), subject если private; не считать текущий cursor immutable snapshot. При смене hard criteria/версии запросов restart pagination. Deterministic reason codes из validated evidence, а не сгенерированные LLM тексты «дом точно подходит».

## 8. Saved searches и уведомления

Не писать новую систему. Использовать существующие `SavedSearch`, ownership, JSONB filters, notifications/outbox, dedup. AI extra fields старый matcher может просто игнорировать: нужен единый typed compatibility matcher для interactive query и background saved-search triggers.

После асинхронного enrichment ранее опубликованное объявление может впервые стать подходящим. Нужен delayed rematch event с revision/dedup, чтобы отправить подходящее уведомление **один раз**. Учитывать source retirement, пользовательскую редакцию saved filters, race между publish/enrichment. Auth required. Решение о фоновых AI quota — см. ADR выше.

## 9. Декомпозиция и зависимости

**Не пытаться реализовать всё одним PR.** Точный план — [05_IMPLEMENTATION_PLAN.md](05_IMPLEMENTATION_PLAN.md).

| Этап | Что делать | Статус / вход |
|---|---|---|
| **AI-01 — первый** | ADR: vocabulary, source provenance/conflicts, hard/soft, typed intent/patch, cursor, TOP, quota operation | **READY**, без runtime/migrations/paid APIs |
| **BASE-373** | Human review незлитого parser PR #373 и безопасный перенос на current main, payment #372 regressions | Review отдельно, не replace planning→main |
| **AI-02** | Real catalog/source coverage с DBA read-only, source telemetry | **BLOCKED** по доступу, logging QA можно отдельно |
| **AI-07 → AI-08** | PG quota ledger + Redis anti-abuse; диалог/session CAS | Независимый кодовый поток после AI-01, disposable PG |
| **AI-03 → AI-04** | Additive AI facts tables, indexed projection, durable queue/resolver | После ADR; индексы и rollout уточнить по AI-02 |
| **AI-05 → AI-06** | Sanitize/privacy gate, source adapter improvements, DeepSeek enrichment worker | Провайдерные live вызовы только с одобрением |
| **AI-09** | Text AI query/matching, reuse cards/TOP/cursors | После facts + sessions/quota; сначала mock |
| **AI-10** | Saved search/matcher/alerts | После AI-09 и events AI-06 |
| **AI-11 → AI-12** | Groq batch backend + React text/voice mobile/desktop | UI shell/mock параллельно; real provider после privacy |
| **AI-13** | Gold evaluation, staging E2E p95, CI/payments/TOP regressions, rollout gates | Production только отдельно по manual approval |

До AI-01 не дублировать parser foundation #373; не писать бизнес-SQL, не используя согласованный typed taxonomy. Допустимые параллельные потоки **после согласования DTO**: quota/session, facts/queue, DBA/source/privacy, provider mocks и React UI shell. Новый multi-agent/worker не должен самостоятельно выдумывать отличающиеся статусы, DTO, idempotency или quota rules.

## 10. Release gates (definition of done)

**Development разрешён** без real DB access для ADR, disposable DB/mocks/schema design. **Live staging** требует отдельного разрешения, provider/privacy account settings, approved sanitized goldset и технических лимитов. **Production запрещён**, пока не доказано следующее:

- [ ] Реальные per-source данные, provenance, usable coverage, freshness из одобренного read-only DB audit; backfill dry-run/capacity planned.
- [ ] Human review #373 и регрессии importer/gallery + платежного #372, main compatibility.
- [ ] Strict facts/resolver, stale-job fencing, durable queue, no raw PII outbound.
- [ ] Quota 3/200 shared text+voice, midnight Madrid DST, successful-zero, failure refund, idempotent retries, guest abuse gates.
- [ ] One Send → automatic audio ASR→intent→SQL→cards, no mandatory transcript confirm, mobile/desktop codecs and UI.
- [ ] Production-like browser end-to-end card-render **p95≤10s** на согласованной normal workload, **плюс** error/timeout rates, отдельно zero-result latency и bad-network behavior; не считать 0.596/1.799/0.927s показателем p95.
- [ ] Goldset RU/ES/EN/mixed проверяет числа, отрицания, Adeje/Arona, pets scopes, tenancy и unknown/conflicts, без fake matches.
- [ ] TOP/boost/Stripe/listing search/map/photos/external redirect/favorites/saved alerts не имеют регрессий на финальном SHA.
- [ ] CI стабилен: существующие 422 address validation и mobile municipality failure исследованы/исправлены без ослабления валидации.
- [ ] Provider retention/DPA и external-source privacy/ToS review, operator-only keys, flags/kill switches, metrics/cost tracing, recovery/rollback plan.
- [ ] Staging release проверен, отдельное разрешение на `main` merge и **только ручной** production deployment с текущим approval process.

## 11. Что разработчик должен сдавать по каждому PR

**Шаблон отчёта:**
1. PR number/title, base branch, head SHA, paths/files.
2. Какие утверждённые requirements covered, какие design choices являются предложением.
3. Реальный код vs docs-only vs mock/staging/production status.
4. Schema changes, миграции, feature flags, before/after API contract.
5. Unit+PostGIS integration+frontend/Playwright test list, сколько pass/fail/skipped, GitHub CI URL **на финальном SHA**.
6. Data quality/security/PII/provider/performance evidence, где измерено, где unknown.
7. Rollback/fallback и подтверждение, что не выполнялись запрещённые действия.
8. Обновление [08_NEXT_ACTIONS.md](08_NEXT_ACTIONS.md), ADR и общего QA при изменении контракта.

## 12. Источники и реальные доказательства

- [Первый production audit](audits/2026-10-25/PRODUCTION_REALITY_AUDIT.md) — host, SHA, worker, public listings; без DB read-only inventory.
- [Первый readiness audit](audits/2026-10-25/AI_INTEGRATION_READINESS.md) — gaps по API/ASR/quotas/alerts.
- **Заключительный аудит [PR #375](https://github.com/antony502189-max/Ttest/pull/375), head `fe59df7fcda852bdea39c4c6c9a26b91ff95ac2e`** — [FINAL_GAP_CLOSURE_AUDIT.md](https://github.com/antony502189-max/Ttest/blob/fe59df7fcda852bdea39c4c6c9a26b91ff95ac2e/docs/ai-search-developer/audits/final-gap-closure-2026-10-25/FINAL_GAP_CLOSURE_AUDIT.md), [REAL_CATALOG_EVIDENCE.md](https://github.com/antony502189-max/Ttest/blob/fe59df7fcda852bdea39c4c6c9a26b91ff95ac2e/docs/ai-search-developer/audits/final-gap-closure-2026-10-25/REAL_CATALOG_EVIDENCE.md), [VOICE_10S_FEASIBILITY.md](https://github.com/antony502189-max/Ttest/blob/fe59df7fcda852bdea39c4c6c9a26b91ff95ac2e/docs/ai-search-developer/audits/final-gap-closure-2026-10-25/VOICE_10S_FEASIBILITY.md), [IMPLEMENTATION_GATE_MATRIX.md](https://github.com/antony502189-max/Ttest/blob/fe59df7fcda852bdea39c4c6c9a26b91ff95ac2e/docs/ai-search-developer/audits/final-gap-closure-2026-10-25/IMPLEMENTATION_GATE_MATRIX.md), JSON. На момент подготовки рабочее ТЗ находится **в ветке PR #374**; отчёт #375 — **открытый отдельный docs PR** на эту ветку. **Не считать пять отчётов уже слитыми**, пока GitHub не подтвердит merge.
- [Исторический parser #373](https://github.com/antony502189-max/Ttest/pull/373).

**Итог:** никаких новых общих аудитов. Начать AI-01, затем код по независимым PR. Никаких production-интеграций/merge/deploy в рамках только этого обновления документации.
