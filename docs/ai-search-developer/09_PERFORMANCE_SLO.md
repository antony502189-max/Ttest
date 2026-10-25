# 09 — Быстрый AI-поиск: результаты после отправки голоса ≈10 секунд

> **Утверждено владельцем 25.10.2026:** пользователь закончил голосовую запись, нажал «Отправить» и **примерно в течение 10 секунд** должен увидеть **реальные, актуальные и подходящие объявления** в существующей выдаче. Это ключевое требование к продукту, а не факультативная оптимизация. **НЕ означает** потоковую расшифровку во время записи, глобальную 100% гарантию при плохой связи или обещание проверять весь интернет синхронно.

## 1. Однозначная метрика SLO

**Target:** `p95 time_to_results <= 10.0 s` после окончания записи и нажатия «Отправить» на типовом поддерживаемом клиенте и сети, при исправных внешних провайдерах.

- **T0:** пользователь инициировал отправку **уже завершённой** голосовой записи (клик Send / подтверждённая передача; если продукт выберет auto-send on Stop — Stop=Send). Время самой речи/записи **не входит** в 10 секунд.
- **T1:** в текущем списке действительно нарисованы **первые подходящие карточки**, полученные из backend после проверки видимости/актуальности и hard constraints, . При отсутствии подходящих объявлений должен отображаться честный verified empty state — **отдельная latency-метрика, не карточный p95**. Спиннер, транскрипт, toast, голый skeleton, HTTP 200 и пустой placeholder **не считаются** появлением результатов.
- **Метрика:** `T1 - T0`, browser-observed end-to-end; включает upload, очередь, batch ASR, intent DeepSeek, Postgres/PostGIS, API response и frontend render. Замер p50/p95/p99, timeout/error rates.
- **Acceptance:** минимум **95% успешных voice requests с ожидаемыми подтверждёнными карточками** на репрезентативной normal network/workload должны отрисовать первые действительно подходящие карточки за <=10с. **Нулевые результаты учитывать отдельно** по Send→verified empty state, они расходуют одну бизнес-квоту, но не улучшают p95 карточек. Отдельно измерять success-within-10s как долю **всех** валидных входов и error/timeout/429 rates, чтобы не «добиться p95» исключением неудачных запросов. Quality и data-freshness gates обязательны одновременно.
- **Scope теста:** короткие типовые бытовые записи (~5–20 секунд), RU/ES/EN + смешанные топонимы, обычные mobile/desktop browsers и репрезентативный реальный mobile uplink. Отдельно тестировать долгую запись до максимального лимита, медленную сеть и provider degradation: **для них нельзя обещать гарантированные 10 секунд**, но нужно корректное уведомление/отказ и возможность повторить.
- Нельзя считать SLO выполненным без staging/browser measurements. Значение в 10 секунд — целевое требование, а не уже измеренная возможность Groq+DeepSeek.

## 2. UX: **одна отправка → сразу объявления**

```text
нажал Record → сказал условия → Stop → Send (T0)
                    ↓
             короткий «Ищу варианты…»
                    ↓
    batch Groq ASR → DeepSeek intent → indexed DB lookup
                    ↓
  реальные existing listing cards + короткий текст (T1 <=~10s)
```

**Никакого обязательного второго клика «подтвердить распознанный текст» между Send и выдачей.** Иначе время будет зависеть от действий пользователя, а обещание «через 10 сек» — невыполнимо.

- Распознанную фразу можно показать/отредактировать **не блокируя** первый поиск: в компактной строке результата, с возможностью «Исправить запрос»/«Повторить поиск».
- Изменение пользователем распознанного запроса **после** первой выдачи — новое осознанное сообщение, расходует новый дневной AI запрос по действующему правилу.
- Если backend физически использует `/transcriptions` и затем `/query`, клиент должен автоматически запустить второй этап без интерактивного подтверждения и измерять **оба** в одном SLO; предпочтительно один backend orchestration `POST /ai-search/query` с multipart audio, чтобы избежать лишних сетевых RTT/двойной quota reservation. Поля/маршруты являются draft и должны соответствовать общему API.
- Не показывать AI-догадки как факты, не выдавать старые/скрытые/закрытые объявления за актуальные и не скрывать непригодные условия ради скорости.
- Проблемы распознавания важных чисел/отрицаний: лучше явная понятная просьба исправить текст, чем уверенно показать неподходящие варианты.

## 3. Предварительный инженерный latency budget (ориентир, не гарантия провайдера)

| Участок полного цикла | Проектный бюджет |
|---|---:|
| Browser upload + маршрутизация | <= 1.5s |
| Groq Whisper V3 batch ASR | <= 3.0s |
| DeepSeek intent (один компактный JSON вызов) | <= 2.5s |
| PostgreSQL candidate search + compatibility & rank | <= 1.0s |
| Ответ API + rendering + запас | <= 2.0s |
| **Итого целевой p95** | **<= 10s** |

Это **budget по цепочке**, а не самостоятельные SLA поставщиков. Реальное распределение пересмотреть по tracing. Upload большого файла по медленной сети не помещается в стандартный бюджет.

**Оптимизации для 10s:**
1. **Предварительно обработанный каталог**: AI enrichment, evidence, dedup, freshness, canonical resolver и индексированные `listing_search_features` подготовлены **фоновым worker**, а не при пользовательском запросе.
2. **Никаких** live crawling, LLM per listing/card, фонового backfill внутри запроса, vector DB на критическом пути.
3. Один ASR вызов **после конца записи**, максимум один intent LLM вызов в обычном happy-path. Ограниченная длина prompt/history; структурированный patch к нормализованному session state.
4. Ограниченный candidate pool и server-side SQL filters/indexes **до** пагинации, существующий search/card DTO и TOP sorting.
5. Дедлайны на операции, bounded retries (не подрывать 10 секунд повторными вызовами), concurrency/circuit breakers, worker isolation, capacity/load testing, tracing.
6. Не забирать изображения/видео в AI API: existing frontend cards сами загружают media; для T1 считать реальные отображённые карточки с читаемыми основными данными, не дожидаться полной загрузки тяжёлых галерей.
7. Redis quota/session / PG ledger не должен делать ненужные медленные запросы; idempotency и quota finalize без дополнительного heavyweight network round trip к провайдеру.

## 4. «Актуальные объявления» означает проверяемые правила

- Выдавать **только** соответствующие существующим production правилам публичности и жизненного цикла (`published/active`, rental mode, price <=1000€ для long-term, география и ограничения аренды; source/owner status).
- Для импортированных источников учитывать **последнюю успешную проверку**, source status, доступный evidence и provenance. Если свежесть **не подтверждена**, не подписывать как «актуально проверено» — показывать appropriate uncertainty/last checked и не делать unsupported claim.
- **Не вызывать парсер в user-request** ради актуальности: это нарушит SLO и ограничения источника; freshness обеспечивается отдельно существующим импортёром + периодическими задачами.
- Не вводить молча TTL, который выбрасывает большую часть каталога; политику freshness настраивать по source и доказательствам, согласовать в ADR.
- Релевантность = проверенные **hard rules** + сортировка с сохранением TOP + soft score только там, где это не ломает коммерческую логику. Не генерировать fake `96% match`.
- Обязательные атрибуты животных/курения/пары/вместимости учитывать как `allow/deny/conditional/unknown/conflict`, не заявлять неизвестное разрешённым.

## 5. Timeout/fallback, без скрытого нарушения

- Если запрос превысил целевой бюджет, показать информативное состояние: «Поиск занимает больше времени…» и, где возможно, штатный поиск **без ложного AI-подтверждения**. Нельзя оставлять бесконечный spinner.
- При сбое ASR или DeepSeek можно предложить повторить/ввести текст, но **не** скрыто переключаться на случайные результаты, выдавая их за соответствующие голосу.
- Ошибки не расходуют business quota (гость 3/сутки, зарегистрированный 200/сутки; календарь Madrid). Успешный fallback, признанный пользователем самостоятельным AI-ответом, требует явной семантики debit/idempotency.
- Поставщик может быть недоступен: SLO — статистический целевой показатель, **не абсолютное обещание**, без ухудшения безопасности/качества.
- Независимо от времени соблюдать privacy: no PII in logs/third-party outbound beyond approved minimization.

## 6. Обязательные тесты перед release

| Испытание | DoD |
|---|---|
| E2E мобильный голос: 5–20 секунд, RU | cards + short explanation from Send within 10s p95 |
| E2E ES/EN/mixed toponyms and € / negation | critical slots correct; no invented policies |
| Same audio under normal 4G-like uplink & WiFi | real browser p95 with upload included |
| Saved session follow-up «теперь с балконом» | no unnecessary LLM enrichment, fast cards |
| Search returning zero verified matches | honest validated empty state within target |
| Stale/closed/unpublished source entry | excluded or clearly marked per approved freshness/visibility rules |
| Concurrent voice traffic under bounded pilot load | p95 <=10s in target scenario, stable error rate, no double charge |
| Missing/slow Groq or DeepSeek | bounded timeout, clear fallback/error, no consumed request on failure |
| Long audio/slower network beyond benchmark | clear progress, cancel/retry, no fake hard SLA |
| Desktop/mobile existing UI | cards/TOP/redirects/gallery/map remain unchanged |

Measure/report: `client_time_to_first_results_ms`, `audio_upload_ms`, `asr_ms`, `intent_ms`, `db_search_ms`, `serialization_ms`, `render_ms`, `search_success`, `fallback_type`, `data_freshness_status`, `query_mode`, provider 429/timeouts, business quota charged/refunded. Redact text/transcript.

## Обновление после специализированного аудита #375

Вердикт: `FEASIBLE_WITH_SPECIFIC_CHANGES` — **не** измеренное достижение. Прямые public HTTP samples существующего card API `596.40 / 1798.99 / 927.30 ms` были **по одному запросу на 3 разные query** и не являются ни p95, ни ASR/LLM, ни browser-render timing. Выбранная рекомендуемая схема — **один multipart request**, без ручного второго шага. Подробности: [VOICE_10S_FEASIBILITY.md в PR #375](https://github.com/antony502189-max/Ttest/blob/fe59df7fcda852bdea39c4c6c9a26b91ff95ac2e/docs/ai-search-developer/audits/final-gap-closure-2026-10-25/VOICE_10S_FEASIBILITY.md) и [10_IMPLEMENTATION_TZ.md](10_IMPLEMENTATION_TZ.md).


## 7. Ownership

- Backend engineer: API orchestration, provider adapter timeouts, SQL/index/fast search, quota/idempotency, freshness.
- Data/parser engineer: asynchronous facts/freshness/provenance; no live crawl.
- Frontend engineer: submit→results without another confirmation, actual paint timing, responsive UI, progressive images.
- QA/SRE: browser E2E performance tests (normal network), tracing and ongoing p95 alerts.

**Сначала добиться качества данных и правильных карточек, затем оптимизировать критический путь.** Быстрый, но ложный ответ не проходит acceptance.
