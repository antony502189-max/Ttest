# 06 — QA, критерии готовности и регрессии

## Матрица доказательств (обязательные категории)

| Тема | Контрольные кейсы |
|---|---|
| Источник факта | permit/deny/unknown/conditional/conflict/legacy_unverified, evidence exists, fake LLM evidence rejected |
| Pets | cat/dog, size, number, conditional only small dogs, no blanket yes, explicit no |
| Smoking | indoors vs balcony/outside; tenant "не курю" не означает landlord bans |
| Occupancy | 1,2,3,4,7,10; `confirmed_capacity>=N` и existing exact legacy filter unchanged |
| Relationship | couple != two friends, adults/children separate, no-parе запрет != capacity=1 |
| Data lifecycle | source changed content; stable content digest, source removed/retired, primary promotion, duplicate conflicts |
| Parser | no description; photo gallery integrity; fingerprint updates optional facts; no stale snapshot |
| Intent | RU/ES/EN/mixed toponyms Adeje/Arona, price 650 vs 850, negative clauses, hard vs soft, budget preferred/max |
| Follow-up | "теперь только балкон" preserves all other constraints, unset field, reset, stale cursor |
| Ranking | existing TOP/boost positions, hard ineligibility filter, unknown warning, stable server pagination |
| Quota | guest3, user200, login transition, concurrent last request, idempotent replay, provider failure refund, DST Madrid 00 |
| Voice | click permission, completed ASR, **one submit triggers automatic search without confirmation gate**, editable transcript after initial search, Safari mp4, WebM, corrupt audio, oversize, silence, cancellation |
| Security | secret never in React, uploads size/codec checks, raw HTML/PII not outbound, injection, SSRF, rate-limit bypass |
| Alerts | auth required, existing SavedSearch, delayed enriched data triggers only one alert, no duplicate SMTP |
| UI | desktop/mobile property cards, external redirects, galleries, favorites, existing map, Back, 320px, keyboard, screen reader |
| Production | safe feature off, old API still works, migrations expand-only, no automatic deploy |

## Regression suites and files

- Existing FastAPI pytest, PostGIS integrations + Alembic compatibility.
- Existing frontend Playwright and mobile tests; inspect React desktop `PropertyCard` vs mobile `MobileResultCard`.
- Existing Stripe, paid promotion, normal listing search, external worker lifecycle.
- Parser PR #373: 26 synthetic policy fixtures, fingerprint regression and read-only CLI; **только synthetic**.
- CI полный зелёный на **конечной** кодовой ревизии, не только на более раннем хеше. Post-merge fullstack failures из snapshot надо диагностировать отдельно (часть address validation 422).

## Обязательный пользовательский SLO после голосовой записи

**p95 ≤10 секунд** от Send **уже завершённой** записи до **отрисованных первых подходящих/проверенных карточек** в браузере при репрезентативной нормальной мобильной сети и исправных provider APIs (не включать время самой записи). 95% успешных запросов должны достигнуть 10s, **но измерять и публично учитывать все 429, timeouts, fallback и ошибки**, не исключать провалы из реальной картины. Отдельно p50/p99. Skeleton/транскрипция/200 OK не являются success. Нельзя делать обязательный transcript confirmation click. Показатель **не измерен**, он принят владельцем как новый release gate.

Нужны интеграционные и browser E2E измерения стадий: audio upload, Groq ASR, DeepSeek intent, indexed SQL/filter, API, React paint. Типовые записи 5–20s на RU/ES/EN/mixed и 4G-like uplink/WiFi; отдельно slow links, 60s recordings, provider timeout, 0 matches, stale/external ads и invalid media. Невозможно гарантировать 10s при любой сети/сбое — показывать понятный fallback/error без списания квоты за сбой. Настройки budget и полная методология: [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md).

## Оценка распознавания речи

Оценить на добровольно записанном наборе ~100+ репрезентативных фраз RU/ES/EN/mixed. Измерять **critical slot error**, а не только generic WER:
- Цена €600/€650/€850/€1000.
- Количество 2/3/4, дети/пара/друзья.
- Отрицания "не", "no".
- Tenerife топонимы, говоры, шум, телефонные микрофоны.
- Паузы/сжатие и разные codecs.
- p50/p95 latency, err rate, fallback provider, фактические расходы.
Groq chosen initially, OpenAI fallback. Provider names/цены перепроверять по официальным docs перед включением. Платные прогоны требуют отдельного операционного разрешения.

## Оценка DeepSeek fact extraction

Ручная обезличенная реальная выборка + synthetic regression. Основной риск — **ложное явное разрешение** (например, маленькая собака допускается → любая собака допускается). Отдельно precision для explicit_allow, conflict detection, evidence correctness, unknown coverage. Отсутствующий источник не восполнять AI-догадкой. На достаточном goldset задать quality gate; не объявлять «ноль ошибок в мире» по 26 synthetic cases.

## Минимальное соответствие для feature rollout

- Real catalog read-only matrix и проверенный backfill dry-run.
- Unit, database integration и browser E2E проходят на актуальном main+AI branch.
- Стабильные source facts/derived features при retry/restart/promotion.
- Quota 3/200/сброс midnight корректны, ошибочные запросы не расходуют лимит.
- Нет PII/сырого HTML в outbound AI; DPA/retention проверены.
- Search/filter до pagination, ни один hard-deny не выдаётся как compatible.
- TOP/Stripe/cards/external/photo/map без регрессий.
- Monitoring provider cost/429, queue backlog, failure/no-crash fallback и release off switch.
- **Staging** проверен; production rollout вручную и по флагам, без auto merge/deploy.

Источники и детали: [readiness](audits/2026-10-25/AI_INTEGRATION_READINESS.md), [original implementation sequence](audits/2026-10-25/AI_IMPLEMENTATION_SEQUENCE.md).
