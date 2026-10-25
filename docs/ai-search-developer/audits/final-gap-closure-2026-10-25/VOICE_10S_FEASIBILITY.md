# Голосовой поиск за 10 секунд: инженерная реализуемость

Дата: **2026-10-25**. Итог **FEASIBLE_WITH_SPECIFIC_CHANGES**, SLO **НЕ ДОКАЗАН**. Архитектурная уверенность средняя; latency/quality внешних вызовов Ttest пока неизвестны. Провайдеры не вызывались. Изменений runtime, нагрузочных тестов production и голосового прототипа в задании нет.

Baseline M=`1292c6807ece59999238bb31c80e09ef7e2c3212`, handoff H=`85fa9ad7ebff15634b34bd341882d302398b6dfc`, parser F=`fcae378d9dbbc8447f18df150327180f6f2c8231`. C/R/P/V/D ниже — [точный реестр доказательств](FINAL_GAP_CLOSURE_AUDIT.md#12-реестр-доказательств) с path:line, SHA, средой, датой и границей применимости. Все новые design choices в этом отчёте — **INFERRED proposals**, не внедрённые возможности.

## 1. Измеряемая цель

T0 — click Send завершённой записи (или auto-send on Stop, если это отдельно выбрано продуктом). T1 — первый browser paint содержательных **подходящих** существующих карточек текущей operation, с правильными hard constraints и честной свежестью. Recording time исключён, но upload и всё после Send включено. Skeleton/transcript/HTTP200/старые карточки предыдущего запроса не считаются результатом.

Цель: **p95(T1−T0)≤10.0s** на заранее описанном supported workload/network/browser. Ошибка не даёт быстрого success. Помимо conditional latency успешных positive-result searches считать долю всех valid eligible submissions, получивших правильные карточки≤10s; timeout/5xx/429/failed ASR не вырезать из service picture. Численный availability/error-budget threshold согласовать до acceptance, не выбирать после результатов.

Valid zero-result search считается успешной обработкой и расходует1 business request, но **не доказывает card-render SLO**. Для него отдельно измерять Send→paint честного verified empty state и публиковать count/долю. Старый09 допускает empty outcome в overall completion; в новой проверке вести обе метрики раздельно, чтобы zeros не улучшали карточный p95. Unknown-only candidates также не превращать в confirmed matches. [R03, требования владельца; INFERRED operational definition]

## 2. Что измерено сейчас

**VERIFIED_PRODUCTION P01–P03**:20:19UTC,25.10.2026, один Windows HTTPS-клиент. Без connection reuse, с DNS/TLS/network и серверным временем; urllib timers до headers и полного body, не браузерный paint и не чистое SQL время. Один запрос на query,limit20. Accept-Encoding:gzip отправлен, API samples вернулись без Content-Encoding. Никаких personal fields/карточных текстов в таблице.

| Query | n | До headers,ms | Полный body,ms | Получено cards / public total | Wire=decoded body bytes |
|---|---:|---:|---:|---|---:|
| long | 1 | 547.67 | **596.40** | 20/1134 | 32931 |
| holiday | 1 | 1740.70 | **1798.99** | 20/31 | 37582 |
| long,Adeje,maxPrice700 | 1 | 849.39 | **927.30** | 6/6 | 8985 |

Разность body complete−headers включает transfer/read ~48.73/58.29/77.91ms, не JSON parse/render. Три разнородных samples не дают p50/p95/p99, устойчивый throughput, ASR budget или95% гарантию. Holiday1.799s нельзя интерпретировать как SQL>1s: сеть и backend не разделены. Это безопасный baseline сигнал для будущего profiling, не доказанная production capacity. Raw catalog count/freshness отдельно **не измерены**. [P02/P03/D01]

Public build M и microphone=() подтверждены новым GET. Backend source/runtime hash вновь не аттестован; C-code facts описывают M. Точные request bodies приведены в строках таблицы: rentalMode,long/holiday; limit20; у Adeje query и maxPrice700. Повторить только после изменения/в staging, не превращать audit probe в production load test.

## 3. Проверенные ограничения критического пути

| Компонент | Проверенный факт | Последствие / необходимое изменение |
|---|---|---|
| Nginx | общий body256KiB; body idle15s, header15s; `/api/` connect5/read60/send60; microphone запрещён; API gzip off [C01] | отдельная audio location≈9MiB при file cap8MiB; общий JSON limit оставить; same-origin mic на document и backend; свои deadlines |
| FastAPI | нет найденного общего256KiB middleware; existing multipart dependency, отдельные image/video rules [C02] | audio byte counter до/во время parse, bounded spool/decoder, reject oversized chunked uploads; не считать Nginx единственной защитой |
| Uvicorn | Dockerfile один процесс без--workers; historical runtime то же [C02/R04] | await async providers; не CPU decode/event-loop blocking; число процессов не увеличивать без PG budget |
| PostgreSQL pool | compose5+5/process, wait30s, SQL60s, lock10s; Settings10+20 [C02] | AI-specific acquisition/search deadlines; соединение release до provider wait; worker connections учитывать отдельно |
| Индексы | migration0050: partial created keyset, city/area trigram; geography GiST упомянут; run retention indexes0029 [C14] | наличие/validity/plans runtime неизвестны; confirmed-capacity/pet/scope features понадобятся новые по real plans |
| Search SQL | count отдельным запросом, затем card query limit+1; TOP/boost correlated expressions и gallery subquery; filters до paging [C03/C04] | измерить count и retrieval отдельно; не подтягивать full descriptions, не реранжировать маленькую страницу |
| Redis | Lua limiter roundtrip, sockets1s; memory fallback [C12] | quota PG authority; anti-abuse failure policy; не budget «1s overhead» без измерения, cache loss не бесплатный AI |
| Serialization | card description SQL left240, images≤MAX_LISTING_PHOTOS, Pydantic card projection [C04] | bounded20cards, no full-detail hydrate before first paint; pure serialization отдельно не измерена |
| Desktop UI | request cancellation/progressive gallery, server list используется без legacy full filter [C08] | AI items подавать прямо в существующие renderers; исключить duplicate fetch effects |
| Mobile UI | отдельная request session,20cards, sentinel rootMargin1600px [C09] | следить за premature load-more и desktop/mobile двойным request; не блокировать initial paint |
| Browser audio | MediaRecorder.isTypeSupported capability check, runtime recording может fail [V08] | actual iOS/Android codec tests; text fallback; не навязывать webm всем устройствам |

Runtime live indexes, pool headroom/max_connections, peak resource utilisation и staging URL не доступны/не подтверждены. Нет оснований заявить, что железо уже выдержит заданную concurrency. В текущем задании frontend проверен статически, без нового paint benchmark; production browser route мог бы запускать дополнительные effects, включая stateful catalog-version. Поэтому исходники и HTTP samples оставлены разными классами evidence. [D01/C08/C09/C12]

## 4. A против B: выбор request orchestration

| Свойство | A: один multipart query | B: transcribe→query, автоматическая цепочка |
|---|---|---|
| Browser round trips | один POST normal path; subsequent pages без AI | два последовательных POST и дополнительные headers/cookies/tracing |
| Подтверждение transcript | не требуется; редактирование после первого результата | также не требуется, frontend обязан автоматически продолжить |
| Business quota | одна operation/reservation/finalize | единый operation token через оба routes, иначе double-debit/ASR bypass |
| Идемпотентность | request hash completed audio+normalized session/version | shared operation ownership/hash; query token одноразово bound, transcript tampering проверяется |
| Recovery | статус/replay operation после lost response | можно повторить stage2 без ASR, но orphaned stage1 требует expiry/cleanup |
| Реализация | orchestration сложнее серверу, проще согласовать state | больше client/server intermediate states и races |
| Browser formats | одинаковая intake validation | разделение endpoints не исправляет codec compatibility |
| Tracing | один trace с spans, requestId→paint | общий trace на два HTTP spans и gaps frontend |
| Риск для10s | меньше последовательных RTT/разрывов, предпочтительно | дополнительный RTT и orchestration overhead без обязательной пользы |

**Рекомендация: A** — `POST /api/v1/ai-search/query` multipart для audio, text equivalent в том же service. API возвращает transcript, versioned intent, existing cards/explanations, quota/session и result cursor. Один authenticated/guest operation до вызова ASR; transcript correction после успешного ответа — новое user message. Никакого промежуточного обязательного preview click. [C02/C04/C10/C12, INFERRED]

`GET/status` или idempotent replay — recovery, не mandatory extra roundtrip перед каждым результатом. Progress необязателен; не вводить live ASR/TTS. Нельзя ждать backend HTTP-запросом к своему existing search route: reuse SQL/repository functions напрямую, сохраняя auth/visibility. B допустим при существующем доказанном преимуществе клиента, но этого преимущества сейчас нет. Не создавать публичный free-ASR endpoint без общего reservation+attempt budget.

## 5. Latency budget: гипотеза

| Stage | Проектный бюджет,s | Что измерено |
|---|---:|---|
| Upload/routing | 1.5 | audio upload не измерен |
| Groq file ASR | 3.0 | не вызывался |
| DeepSeek compact intent | 2.5 | не вызывался |
| Indexed match/retrieve | 1.0 | SQL-only не измерен; HTTP samples выше |
| Quota/validation/serialize/network/render/remaining | 2.0 | этапы отдельно не измерены |
| Итого design allocation | **10.0** | не measured E2E |

Это allocation одной цепочки, **не сумма доказанных p95**. Даже если каждый этап укладывается в свой p95,95% всего пути не следует: tails/корреляция/load/разные populations требуют фактического E2E распределения. Нельзя вычесть0.596s из10 и объявить остаток доступным providers p95.

Аудио payload — расчёт, не measured sample:20s×64kbit/s÷8≈160000B;60s≈480000B. PCM16kHz×mono×16bit —32000B/s,20s≈640000B,60s≈1920000B плюс header. Битрейт MediaRecorder advisory/variable, контейнер/MIME/decoded duration проверять сервером. При uplink1Mbit/s один160KB upload≈1.28s без TLS/RTT;640KB≈5.12s. Значит размер/формат важен, а разрешённые8MiB не обещают upload≤1.5s. Не ухудшать слышимость цифр/отрицаний чрезмерным lossy compression. [V08; INFERRED арифметика]

Один request normal path, до одного ASR и одного intent. Фоновое enrichment и source verification не в critical path. No per-card LLM, no live crawl, no vector DB prerequisite. Compact structured state вместо бесконечной conversation history. DeepSeek mode/JSON specs см. [provider section](FINAL_GAP_CLOSURE_AUDIT.md#9-h--провайдеры-и-outbound-privacy); качество важнее prompt/cap, который режет обязательные поля.

## 6. Предлагаемые deadlines и fallback

Все числа здесь — стартовая конфигурация **для staging calibration**, не provider SLA и не изменение current Nginx. Разделять idle socket timeout и absolute wall deadline: keep-alive bytes не продлевают operation бесконечно.

- Client сохраняет monotonic T0;10s — порог SLO, а не автоматическая имитация success. На10s честно показывает задержку. Предложение:15s общий пользовательский hard deadline для завершения/error, с AbortController и проверкой статуса operation при неопределённом исходе.
- Server: bounded upload wall time≤5s в normal route, общий absolute request ceiling≤15s, processing после upload≤8s и не дольше оставшегося общего deadline. Лимит файла8MiB/recording60s — технический cap, не «supported normal10s» для любых файлов.
- Normal ASR stage cap3s, intent2.5s, SQL match≤1s плюс короткие pool/reserve/finalize budgets. Остаток определять по monotonic deadline и фактическому времени, а не на каждый stage начинать полный15s заново. Это может повысить early errors: quality и error rate измерять вместе со speed.
- Groq→OpenAI fallback только при recoverable failure/circuit-open и достаточном remaining time для ASR+intent+SQL+paint. Не ждать сначала полного3s, затем запускать ещё unbounded ASR. По умолчанию не hedged dual calls: повторная стоимость и privacy routing требуют отдельного решения.
- 401/403/402/config error — circuit/операторская диагностика без retry storm; invalid/unsupported media→понятная ошибка.429/5xx/timeouts→одна bounded попытка fallback при разрешённой маршрутизации; если Retry-After не помещается, отказ/текстовый ввод. Не наказывать пользователя business debit за failure.
- DeepSeek invalid/empty/truncated JSON → строгий отказ или один bounded repair только если весь путь ещё помещается; не guessed SQL/filters. Нельзя молча убрать pet condition ради получения карточек. Provider outage не запрещает обычный поиск.
- Success0matches остаётся success; no system failure refund как «нет подходящих»; lost response replay сохраняет ровно один debit. Если deadline cancellation успел после commit, статус authoritative; не делать автоматический refund завершённой operation. [C12/V02/V06, INFERRED]

Provider SDK defaults/retries отключить или явно ограничить. Async pooled HTTP clients lifecycle-managed; connect/read/write/pool timeout отдельно, absolute cap поверх них. Decoder вынести в bounded worker/thread/subprocess при необходимости; CPU/memory/duration/file header sniff caps. Temp file private и finally cleanup, ни записи в MinIO, ни JSON/base64 audio в обычный route.

## 7. Instrumentation до performance claims

Reuse existing `X-Request-ID` и Prometheus C02/C06; добавить safe trace correlation без transcript/audio/user IDs в labels. Nginx сейчас может переопределять incoming request ID своим `$request_id`; browser должен брать возвращённый ID либо binding operationId, а не предполагать неизменность произвольного client header. Session/result status subject-bound; trace ID не authorization token.

Client performance marks: send, upload start/end где измеримо, response headers, parsed JSON, React commit, first qualifying card paint. React commit сам по себе не гарантирует paint: instrument matching result container с operation/query version, rAF/следующий кадр и проверкой, что видны price/location/title и карточка не skeleton. Playwright screenshot/DOM assertion подтверждают критерий. Image decoding всей галереи не ждать; cover loading не должен оставлять пустой неинформативный блок.

Server spans: intake bytes/duration validation; identity; idempotency lookup; quota reserve; queue/admission wait; ASR upload/TTFB/complete; intent HTTP/parse/Pydantic; pool wait; count SQL; match+cards SQL; serialization; atomic result/session/quota finalize; response bytes. Отдельно cleanup/release/fence failure. `Server-Timing` может показать безопасные stage durations; для same-origin не нужен новый сторонний collector.

Измерять low-cardinality task/model/outcome/mode/client class: p50/p95/p99, histogram buckets около1/2/3/5/7.5/10/15s; provider429/timeouts/retries/fallback; committed/released/expired/replay; queue age; PG pool saturation; result0; confirmed/uncertain freshness. Текущий catalog duration не включает browser render и все middleware/serialization. Количество provider attempts/seconds/tokens/cost и user debits — разные metrics; без monthly cutoff. Никаких phone/name/raw prompt/source URL/ID labels. [C02/C04/C06/C12, INFERRED]

## 8. Staging план и p50/p95/p99 методика

1. Изолированный staging PostgreSQL/PostGIS+Redis, актуальный main+reviewed AI revisions, current payment/card contracts. Mocks только для orchestration/timeout/cancellation/quota; mock latency не доказательство real-provider SLO.
2. Детерминированный sanitized gold corpus и реальная разрешённая catalog projection после AI-02. RU/ES/EN/mixed, цены/числа/negations/Adeje-Arona, small dog/cats/unknown/conflict, positive и zero outcomes. Не передавать raw source payload. Для live provider eval — отдельное разрешение владельца и privacy gates.
3. Supported normal workload заранее зафиксировать:5–20s recordings, выбранный bitrate/container, normal mobile/WiFi profiles с явными RTT/uplink/downlink/loss; реальная iOS Safari/Android Chrome и desktop.60s/maxsize/slow uplink/degraded provider — отдельные robustness strata, публиковать их результаты, не скрывать вне benchmark.
4. Начать single request, затем2/4/8 concurrent sessions с pacing в staging; background enrichment off/on separately. Не растить concurrency вслепую: stop conditions по DB saturation/error/queue deadline. Стартовые interactive4,ASR2,enrichment1 — proposal, не доказанная capacity. Open-loop arrival schedule для проверки очередей, иначе closed-loop клиент скрывает перегрузку (coordinated omission).
5. Предложение sample plan:≥1000valid normal submissions суммарно, достаточно наблюдений в основных strata; не менее100 в значимых client/language/network groups для baseline и дополнительный сбор для устойчивого tail. Warm/cold path отдельно; setup/warm-up заранее помечены, не удалять неудобные samples после измерения. Public report n/selection/duration/build/provider version/limits/region/network/machine.
6. Для каждого запроса одна browser-observed duration. Не усреднять p95 по подгруппам. Для sorted durations quantile nearest rank index ceil(p×n); p99 при малом n нестабилен. Показывать bootstrap/другой выбранный confidence interval и uncertainty для порога10s; тождественный метод зафиксировать до acceptance.
7. Отдельные denominators: allsubmitted, valid/admitted, succeeded-positive, succeeded-zero, providerfail, technicalreject, dailyquota429, timeout/cancel, fallback. Отчёт включает good-card-within10s/allvalideligible и latency distribution success; rejected quota не служит быстрым результатом. Error/availability acceptance threshold утвердить до live run.
8. Параллельно correctness: critical slots match gold, zero false verified permits в обязательных test scenarios, freshness labels правдивы, no duplicate debit, source/hash races safe; ошибки контента не проходят speed gate. Реальная статистическая accuracy threshold требует достаточного gold sample и решения, не выдуманного «95%AI accuracy».
9. Документировать adverse tests: lost connection после commit, double submit, one quota remaining, midnight25h/23h, cancel/expiry, provider latency tails/429, Redis down, pool exhausted, delayed enrichment, source retirement, TOP expiry/boost и cursor movement, stale session response. Production никогда не используется для этого load plan.

## 9. Проверяемый критерий готовности

Считать10s доказанным только на working integration, когда одновременно: live providers разрешены и использованы; правильные current cards измерены настоящим browser; normal population заранее определена; p95≤10s с достаточным n и описанной uncertainty; all-request errors/fallbacks опубликованы и проходят согласованный reliability threshold; freshness/strict compatibility/TOP/quota/privacy tests прошли на точном release candidate SHA.

Сейчас доказана только существующая HTTP основа и кодовые точки интеграции. Не измерены аудио upload→provider latency, mobile codecs в этом приложении, staged concurrent SQL/pool tails, React paint и итоговый voice E2E. До live prototype никакого performance «PASS» быть не может. [P01–P03/D01/R03]

10s нельзя гарантировать при любом uplink, maxsize recording, provider queue/outage/rate limit, cold device, DB saturation или отсутствии достаточного evidence. Недостаток evidence решается честным unknown/empty и фоновым data pipeline, а не live crawl или ложными быстрыми рекомендациями. Статистическая архитектурная достижимость сохранена; нужны конкретные изменения выше и последующая проверка.
