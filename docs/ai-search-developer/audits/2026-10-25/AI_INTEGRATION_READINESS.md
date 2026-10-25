# Готовность 112233.es к AI-поиску недвижимости

Дата: 2026-10-25. **Рекомендации, без реализации.** Измеренные факты, SHA, методы и ограничения: [production audit](PRODUCTION_REALITY_AUDIT.md). Ниже ссылки E01–E09 и S01–S15 относятся к его реестру: main M=`1292c6807ece59999238bb31c80e09ef7e2c3212`, planning P=`1ace67b5ae67ab267fdcc37ee499b87bd433fb71`, parser F=`fcae378d9dbbc8447f18df150327180f6f2c8231`. Новые схемы, имена файлов и endpoints — предложения (`INFERRED`), не уже существующий код.

## 1. Решение и границы

Рекомендуется расширять **существующий FastAPI**, сохраняя PostgreSQL/PostGIS, Redis, account/session, поиск, два renderer карточек, галереи, внешний redirect, карту и платный TOP. Не нужен отдельный AI server, vector DB, локальный Whisper или browser-agent на каждый запрос. Новые модули должны иметь отдельные flags и выключаться независимо от обычного поиска.

Основной вариант: завершённая запись → Groq `whisper-large-v3` → подтверждение/правка текста → DeepSeek intent → Pydantic → детерминированный retrieval/matching → существующие cards + короткие текстовые объяснения. Отдельный фоновый pipeline обогащает source snapshots. Резерв ASR — OpenAI `gpt-transcribe`; при недоступности LLM — обычный поиск с сохранёнными фильтрами. Второй LLM-провайдер не объявляется готовым без отдельного тестирования.

Product invariants: только rental search; text-only responses; запись сначала заканчивается; 3/200 успешных пользовательских сообщений в день по Europe/Madrid; text/voice одна квота; failed provider/system request не списывается; saving/alerts требуют registration; обычный поиск доступен всегда. Никаких jobs, POI, routes/travel times, новых карт, live ASR, TTS, LLM SQL, AI-карточек и месячного финансового cutoff. [Решения владельца P; входное задание]

## 2. Scorecard

| Подсистема | Состояние | Основание и граница |
|---|---|---|
| FastAPI/SQLAlchemy/Pydantic orchestration foundation | READY | VERIFIED_CODE_MAIN, S01–S04; не готовый AI orchestration |
| Обычный поиск и card transport | READY | production endpoint работает, E05; AI compatibility semantics отсутствуют |
| Авторизация | READY | persisted JWT sessions/ban checks, S09; AI eligibility надо подключить |
| Карточки/external galleries/TOP | PARTIALLY_READY | S02/S07/S08; сохранение renderer просто, новый relevance обязан учитывать tier |
| Каталожные данные для строгого AI matching | UNKNOWN | counts измерены, coverage/provenance/freshness нет, E05/BLOCKED |
| Parser foundation | PARTIALLY_READY | F/#373, 904 unit + 88 integration passed; не main/production |
| Versioned AI facts/resolver | NOT_READY | в main/F нет persistence/resolver; только docs и offline types |
| Durable enrichment queue/worker | NOT_READY | mail lease pattern есть, AI queue нет |
| Redis availability | READY | PONG, AOF ok, E04; memory cap/AI namespaces ещё нет |
| AI quota 3/200 | NOT_READY | нынешний INCR limiter не подходит, S09 |
| Server-side AI conversation | NOT_READY | URL/UI search state есть, semantic session нет |
| Batch ASR adapter | NOT_READY | нет deps/config/routes; provider keys отсутствуют в backend env |
| Browser recording | NOT_READY | нет MediaRecorder/getUserMedia в source search; policy запрещает microphone |
| Audio upload transport | NOT_READY | generic 256 KiB; audio validation/retention нет |
| DeepSeek intent/extractor adapters | NOT_READY | нет клиентов/промптов/strict validators для provider output |
| Saved searches / alerts | PARTIALLY_READY | auth JSONB + matcher/outbox есть; AI intent игнорируется старым translator |
| Capacity / outbound HTTPS | PARTIALLY_READY | 6 CPU/~16 GiB available, TLS works; peak/network/DB headroom неизвестны |
| Privacy/security для внешнего AI | NOT_READY | F cleaner не полноценный outbound privacy gate |
| CI/release process | PARTIALLY_READY | manual gate и тесты есть; main unprotected/post-merge failures |

READY относится только к существующей переиспользуемой основе. Общий launch verdict: **NOT_READY**, хотя offline разработку можно начать немедленно. Числовой «процент готовности» не даётся: веса не согласованы и измерения каталога отсутствуют.

## 3. Что переиспользовать и что добавить

Переиспользовать `optional_user/current_user`, DB sessions и query builders, `visible_query`, rental price policy, geography functions/INE dictionary, `search_public_cards`, existing DTO/mapping, keyset pagination, `PropertyCard` и `MobileResultCard`, saved-search ownership, notification idempotency и SMTP outbox. Redis пригоден для bounded cache/session state/abuse throttles; authoritative accounting описан отдельно. [VERIFIED_CODE_MAIN S01–S09/S11/S15; VERIFIED_PRODUCTION E03–E05]

Добавить изолированные модули: `schemas/ai_search.py`, provider interfaces с короткими budgets, intent patch validator, conversation state store, quota ledger, audio intake, deterministic compatibility matcher, per-source fact store/resolver, durable enrichment jobs/reconciler, usage metrics. Эти пути предварительные. F input builder и evidence grammar можно принять после review; не дублировать их параллельной реализацией. [S10/S12; INFERRED]

Новый provider client не должен жить в React. В backend уже есть httpx 0.28, python-multipart, Pydantic и Redis; можно начать с небольших HTTP adapters или добавить pinned SDK после выбора. Наличие `python-multipart` означает возможность разобрать форму, но не проверку аудио. Секреты должны оставаться server-side; `VITE_*` публичны. [S03/S09, backend/pyproject.toml:8–35]

## 4. Матрица критериев и семантики поиска

Основание всех existing-столбцов: **VERIFIED_CODE_MAIN M**, [DTO:454](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/schemas/listings.py#L454), [filters:338](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/repositories/listings.py#L338). Предлагаемые столбцы — INFERRED.

| AI-критерий | Backend field | Текущая semantics | Чего нет / интеграция |
|---|---|---|---|
| Цена | minPrice/maxPrice, rentalMode | primary price; долгосрочный global ceiling 1 000 EUR | intent хранит EUR и month/night/week; не сравнивать nightly с monthly |
| Место | municipalityCode/provinceCode/autonomousCommunity/city/query | INE validation, precedence geography; query ILIKE city/area | RU/ES aliases → однозначный INE; неоднозначность уточнять, не угадывать address |
| long/holiday | rentalMode | exact equality, разная price cadence | сохранять режим в intent, подтверждать при двусмысленности |
| Комната/студия | roomType/roomTypes | разрешены individual/shared/studio | реальные one-bedroom apartments тоже есть; расширить taxonomy явно или вернуть unsupported criterion |
| Людей N | roomCapacity | **coalesce(v2,legacy)==N** | AI confirmed_capacity>=party_size отдельным matcher; existing exact filter не менять |
| Свободных мест | minAvailableSpots | capacity-current_room_residents>=N, оба known | число жильцов не максимальная разрешённая вместимость; provenance отдельно |
| Пара | couplesAllowed + acceptedTenantTypes | room_details equality / OR по tenant types | importer couples mapping отсутствует; separate evidenced fact, не выводить из «двое» |
| Дети | childrenAllowed | scalar equality; NULL не проходит | explicit/conditional/age conditions; default false не доказанный запрет |
| Друзья/группа | acceptedTenantTypes ограничен man/woman/couple/family | отдельного group fact нет | добавить факт party composition; не считать couple=friends |
| Животные | petsAllowed | bool equality | species/size/count/conditional/conflict нет; small dog не равно all pets |
| Курение | smokingAllowed | bool equality | indoor/outdoor/only balcony отдельно; «не курю» не обязательно hard nonsmoking property |
| Deposit | deposit enum | 0 / <=primary price / >primary price | unknown, currency, fee/cadence provenance; optional numeric intent переводить проверяемо |
| Amenities | amenities JSONB contains | AND, часть aliases (Balcón/Lavadora) | canonical vocabulary + evidence; `sin wifi` не wifi |
| Балкон/терраса | amenities | balcony aliases; terrace отдельная строка | не объединять два разных пожелания без согласования; hard/soft flags |
| Даты | availableFrom/Until | NULL разрешён как unknown-compatible; known cover dates | в confirmed AI matches unknown дату нельзя назвать подтверждённой доступностью |
| Min stay | maxMinimumStayMonths / maxMinimumNights | known field<=requested threshold | units/date/rentalMode, unknown handling |
| Furnishing/bills | furnished/billsIncluded | bool equality | historical defaults необоснованны; provenance-first |
| Hard/soft | нет | обычные фильтры бинарно сужают | отдельный validated intent + deterministic matcher и explanation codes |

**Нельзя просто отправить roomCapacity=2 в существующий поиск для запроса «нас двое».** Это исключит подтверждённую capacity=3 и пропустит недоказанный default=2. Получение кандидатов должно не накладывать неверный exact predicate, затем применить подтверждённый `>=2` в SQL по подготовленным features. Полный scan в Python и post-filter маленькой страницы дадут неверные total/cursor: filtering/ranking выполнять до pagination.

Цена/location/rental mode — хорошие первые строгие предикаты. Совместимость по pets/couples/children/capacity добавлять только после provenance. Unknown, conditional и conflict не включать в список «точно подходит». Допустима отдельная opt-in группа «нужно уточнить», но без молчаливого ослабления hard constraints. Если подходящих нет — честное объяснение и предложение изменить условия, без выдумывания данных.

## 5. TOP и сохранение карточек

В M TOP — server-owned tier по активной promotion и валидному paid/fulfilled/financial_normal interval либо baseline. **Сортировка начинается `(active_promotion DESC, boosted_at DESC, …)`**, затем requested sort/UUID. [S02:89–137/551–615] Простой `(TOP, relevance)` тоже может нарушить оплаченный boost order: relevance допустим лишь после неизменённых коммерческих ключей либо для непродвигаемого tier в рамках отдельно согласованного алгоритма.

Предлагаемый алгоритм: existing visibility + hard eligibility → существующий TOP/boost order → AI soft score в допустимых tie groups → stable ID. TOP не делает явно несовместимое объявление пригодным. Текущий поиск тоже применяет filters до ranking; этот принцип сохранить. Если бизнес ожидает TOP в том числе вне eligibility, это новое требование, а не разрешение аудита менять правила.

Возвращать existing `ListingCardResponse` и отдельный `explanations: {listing_id: {codes,known,unknown}}`. Пояснение рендерить рядом с существующей карточкой/вторичной строкой, без замены галереи, source labels, внешней ссылки, promotion badge/favorites. На mobile сохранить `MobileResultCard`; desktop — `PropertyCard`. Никогда не восстанавливать весь Listing из выдуманного LLM JSON. Не вызывать LLM на каждую карточку: короткое объяснение строить по проверенным reason codes.

Cursor должен включать normalized intent hash, feature/ranking version и существующие sort components; сортировать только текущую страницу клиентом нельзя. Изменение intent инвалидирует cursor. При изменениях live promotions данные могут сдвигаться и без AI; будущие tests обязаны проверить стабильность переходов, не обещать snapshot-consistency без snapshot mechanism.

## 6. Frontend и микрофон

Интегрировать компактную кнопку AI/микрофона рядом с существующим поиском: desktop SearchForm, mobile search entry в mobile-app-v2, а на results — доступная кнопка уточнения. Assistant — drawer/dialog с текстом, состоянием квоты и editable transcript. На узком экране закрываемая full-height панель; клавиатура не должна перекрывать submit/stop. Положение окончательно проверить в существующих viewport E2E, не менять карту или карточки ради размещения. [INFERRED; архитектура S07/S08]

Состояния: idle → permission pending → recording (видимый таймер/stop/cancel) → stopped → uploading/transcribing → editable transcript → submitting → results/error. Перед upload проверять локальные size/duration, но доверять server validation. Снять tracks при stop/cancel/unmount, revoke ObjectURL; не включать микрофон без действия пользователя. HTTPS уже есть. Текущая `microphone=()` запрещает capture: будущий PR должен согласованно изменить соответствующие Nginx headers и FastAPI headers на разрешение **same-origin**, не `*`. Сегодня ничего не изменено. [VERIFIED_PRODUCTION E03; S01/S07]

Выбирать формат через `MediaRecorder.isTypeSupported`, сначала audio/webm+opus, затем поддерживаемый audio/mp4 или другой проверенный вариант; точную матрицу Safari/iOS/Android/desktop проверить устройствами. Unsupported API, отказ/отозванное разрешение, отсутствие микрофона, пустая/оборванная запись → сохранить текстовый ввод. [MDN API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static), [secure-context requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia). Это возможности браузера, не подтверждённый UX приложения.

Начальные **предлагаемые** limits: 60 s, 8 MiB audio, один активный recording/job на visitor, 2 000 characters текста, общий bounded request budget. Аудио не отправлять через image/video endpoint: у них другие auth, persistence и codecs. Новый multipart route с собственным body limit около 9 MiB, streaming byte cap и duration/container/codec validation под ограниченными ресурсами. Общий JSON body cap оставить 256 KiB. Не доверять filename/MIME; запретить remote URL audio upload (SSRF). Temp file private, удалять в finally/после bounded recovery, не включать в nginx/app/provider logs.

## 7. ASR и проверка провайдеров

Официальные страницы проверены **2026-10-25**; метка provider-spec ниже `DOCUMENTED_ONLY` (документированный внешний контракт), не тест производительности и не подтверждение аккаунта. [Groq speech docs](https://console.groq.com/docs/speech-to-text): `whisper-large-v3`, POST `/openai/v1/audio/transcriptions`, multilingual; flac/mp3/mp4/mpeg/mpga/m4a/ogg/wav/webm; json/verbose_json/text. Таблица указывает 25 MB free и 100 MB dev, отдельно attachment limit 25 MB: для MVP держаться ниже 25 MB. Минимум файла 0.01 s, billed minimum 10 s; universal maximum duration не установлен на прочитанной странице. `prompt` ≤224 tokens, optional ISO language. Цена **$0.111/hour**. Для mixed RU/ES не фиксировать ошибочно один язык; использовать небольшой контекст топонимов, проверить числа/отрицания.

Groq SDK optional (`groq`), можно существующий httpx. Ошибки auth/invalid file — без автоматического повтора; 429/timeouts/5xx — bounded retry с jitter/Retry-After и circuit breaker. [Rate limits](https://console.groq.com/docs/rate-limits) зависят от организации; опубликованный пример whisper: 20 RPM/2 000 RPD, audio-seconds caps. Он **не является лимитом данного аккаунта**. Политика [Groq data](https://console.groq.com/docs/your-data): usage metadata сохраняются; inference content по умолчанию не сохраняется, кроме reliability/abuse exceptions до 30 days; ZDR доступен в Data Controls. Настройки пользователя не проверены. Хранение в США требует проверки договорных параметров проекта.

**OpenAI fallback — именно `gpt-transcribe`.** [Official model](https://developers.openai.com/api/docs/models/gpt-transcribe) сообщает **$0.0045/minute**. [File transcription](https://developers.openai.com/api/docs/guides/speech-to-text): completed file на `/v1/audio/transcriptions`, до 25 MB; mp3/mp4/mpeg/mpga/m4a/wav/webm; prompt, keywords и **languages** для нескольких языков (не singular language). Подсказки не должны навязывать несказанные слова. [Transcription overview](https://developers.openai.com/api/docs/guides/transcription) отмечает deprecation gpt-4o-transcribe/mini и shutdown 26 февраля 2027: новый код не следует проектировать по устаревшему имени. [Data controls](https://developers.openai.com/api/docs/guides/your-data) указывает для `/v1/audio/transcriptions` no training, no abuse-monitoring retention и no application-state retention; не распространять это автоматически на другие endpoints. Region/organization eligibility отдельно неизвестна.

Обязательный будущий ASR gold-set: добровольно предоставленные записи RU/ES/EN/mixed, Adeje/Arona/Guía de Isora и неоднозначные города, 600/700/1 000, двое/трое, «не», собака/маленькая/по согласованию; тишина, шум, короткая запись, accent, iOS format. Считать critical slot error rate (место, бюджет, число жильцов, отрицания), p50/p95 end-to-end latency, error/fallback rate и $/minute. Название модели и WER таблица провайдера не доказывают точность для этого продукта. Платные проверки в рамках аудита не проводились.

## 8. LLM и DeepSeek

Актуальная [официальная pricing/model page](https://api-docs.deepseek.com/quick_start/pricing/) указывает API ID **`deepseek-flash`**, underlying **DeepSeek-V4.1-Flash-1017**, 1M context, max output 384K; thinking default включён. Legacy `deepseek-v4-flash` принят как alias к retired модели с новым backend. Использовать model ID из конфигурации, сохранять returned model, prompt/schema version и дату eval; не считать alias immutable snapshot. Для коротких extraction tasks выбирать documented non-thinking mode и свои малые token caps.

Flash $/1M tokens: input cache miss **0.15 off-peak / 0.30 peak**, cache hit **0.003 / 0.006**, output **0.60 / 1.20**. Peak weekdays 01–04 и 06–10 UTC, исключая Chinese public holidays. Тарифы в документах архитектуры нельзя переносить без этой проверки. [Rate/concurrency docs](https://api-docs.deepseek.com/quick_start/rate_limit/) задают account concurrency 2 500 Flash/500 Pro и 429 сверх лимита; provider может держать соединение whitespace keepalive до inference, закрывая при долгом ожидании. Наш timeout обязан быть существенно короче; provider ceiling не является безопасной concurrency VPS.

[JSON Output](https://api-docs.deepseek.com/guides/json_mode/): `response_format={type:json_object}`, явное слово JSON и образец; возможен пустой content. JSON mode не гарантирует business schema/evidence. Pydantic `extra=forbid`, strict types, enums, numeric/date limits, evidence spans и reject truncated/empty output обязательны. По [error codes](https://api-docs.deepseek.com/quick_start/error_codes/) различать 400/401/402/422 от retriable 429/500/503; не ретраить invalid credentials/balance как сетевой сбой.

Два отдельных интерфейса/промпта: `SearchIntentExtractor` обрабатывает пользовательский текст и предыдущий structured state; `ListingFactExtractor` обрабатывает только минимизированный selected source evidence. Разные schema versions, token limits, flags и workload pools. User text/listing description — недоверенные данные: instruction delimiter, no tools/network/SQL, only allowed fields; утверждение «игнорируй предыдущие правила» не может менять quota/auth/filter policy. Модель не создаёт SQL, URL для fetch или финансовые действия.

[DeepSeek privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) от 10 февраля 2026 прямо отделяет downstream application processing от своей consumer policy. На её основании нельзя объявить API zero-retention/no-training или EU processing. API-specific DPA, subprocessors, retention/training, location, deletion и transfer terms **UNKNOWN**; это gate перед отправкой user/source texts. Юридическое заключение здесь не выносится. Наличие TLS и низкая цена этот пробел не закрывают.

### Сравнение и выбор

| Кандидат | Точность / latency в Ttest | Сложность | Доступность / privacy | Роль |
|---|---|---|---|---|
| Groq whisper-large-v3 | не измерены; multilingual documented | небольшой file adapter | TLS с VPS есть; account limits/ZDR не проверены | основной ASR после eval/privacy |
| OpenAI gpt-transcribe | не измерены; multiple-language/keyword hints documented | похожий endpoint, иная hint schema | TLS есть; endpoint-specific data controls documented | ASR fallback |
| DeepSeek Flash | intent/fact precision не измерены | JSON mode + строгая локальная validation | TLS есть; alias drift и API terms требуют проверки | основной LLM-кандидат |
| Обычный поиск | уже работает по E05 | существующая реализация | без внешнего AI | обязательный доступный fallback |

Не утверждается, что один провайдер точнее/быстрее другого для RU+ES без сравнительного набора. Общий provider fallback обязан укладываться в единый request deadline; каскад бесконечных retries недопустим. Ошибка/полный timeout возвращает пользователя в editable text/обычные filters без списания квоты.

## 9. Quota 3/200: авторитетный ledger и Redis

**Предложение:** PostgreSQL — единственный источник истины для успешных debits/reservations/idempotency; Redis — sessions, throttling и необязательный read-through quota cache. Причина: текущий Redis AOF и Lua INCR не дают транзакционной связи с завершённым user operation; process-local fallback нарушает global limits. Не пытаться сделать два независимо авторитетных счётчика и затем «иногда синхронизировать». [S09/E04; INFERRED]

Минимальные expand-only таблицы:

- `ai_usage_days(subject_key, madrid_date, limit_snapshot, committed_count, reserved_count, updated_at)`, unique subject+date, неотрицательные counters; решения о downgrade eligibility не должны менять уже списанные операции.
- `ai_search_requests(subject_key, idempotency_key, request_hash, madrid_date, status, reservation_token, lease_until, result_ref, provider_usage, expires_at)`, unique subject+idempotency; состояния reserved/transcribing/awaiting_confirmation/processing/succeeded/failed/expired. Hash не содержит raw transcript в логах.

Subject: `u:{server_user_id}` для login; `a:{HMAC(random_visitor_id)}` для гостя. Гостевой random ID выдавать secure HttpOnly SameSite cookie; не использовать supplied user_id из JSON. Никаких browser fingerprint/адресов как личности. Cookie deletion, private mode и разные устройства дают новые guest identities; персону идеально ограничить нельзя. IP/IP-prefix rate limit — дополнительная abuse protection с учётом NAT, не замена identity. После login quota по user ID действует на всех устройствах; недействительный bearer не должен молча давать privileged guest treatment.

Ключи Redis: `ai:v1:session:{opaque_id}`, `ai:v1:abuse:{hashed_network}:{bucket}`, `ai:v1:quota-cache:{subject_hash}:{YYYY-MM-DD}`; никаких emails/transcript/location strings в key. Cache никогда не разрешает запрос вопреки DB ledger. Не переиспользовать importer lock prefix или limiter's `ttest:rate` как бизнес-квоту.

Алгоритм short transactions:

1. Validate auth/input/feature flag/origin, compute subject, canonical request_hash; require Idempotency-Key. Lookup existing operation: same hash+succeeded → replay; different hash →409; in-progress →202/409 with polling/retry hint, без второй reservation/provider call.
2. В короткой транзакции создать daily row при отсутствии, lock row; при `committed+reserved>=limit` вернуть 429 с reset timestamp. Вставить request уникально и увеличить reserved на 1. Никакой provider I/O под DB row lock.
3. Зафиксировать reservation, выполнить ASR/intent/matching в пределах deadline с fencing token. Для voice preview сохранять reservation до bounded edit timeout; transcript можно исправить, не создавая новое debit.
4. При полном успехе **одной транзакцией** записать durable operation result/intent version, reserved−1, committed+1, status succeeded. Только после commit отдавать результат. 0 найденных объявлений — успешная обработка и 1 debit; provider failure — нет. Уточняющий вопрос от assistant, если корректно обработал неоднозначный запрос, считать успешным одним message; его ответ пользователем — новым message. Это надо явно отразить в UX.
5. На подтверждённой ошибке/отмене до success атомарно release ровно один раз по status+fencing token. TTL lease и reconciler чинят crash reservations. Старый/опоздавший worker не может commit после expiry/reassignment. Reconciler не освобождает живой lease без проверки дедлайна/fencing.

Если crash после provider success, но до DB commit: user debit не зафиксирован; повтор может снова стоить провайдеру, но не списывать пользователю дважды. Без provider idempotency невозможно гарантировать exactly-once billing внешней системы. Если DB commit прошёл, а HTTP response потерялся: retry возвращает сохранённый result без вызовов и debit. Обновление query state и success/debit — одна DB unit либо versioned result record; Redis session лишь cache. Успешный debit нельзя вернуть только потому, что браузер закрыл вкладку после commit.

Redis outage: ordinary search работает; AI quota остаётся корректной по DB, но если обязательный abuse/session layer недоступен — AI fail closed 503, без дебита и без local-memory bypass. DB outage →503 до provider call. При утрате Redis cache rebuild из authoritative rows; counter drift не «лечить» двойным INCR.

Voice abuse: ASR-only previews расходуют деньги даже без финальной query. Держать одну bounded reservation, ограничить attempts/ASR seconds per visitor/network, preview TTL и concurrency. Cancel не списывает business quota, но technical abuse budget не обнуляется. Это не месячный spending cap. Max retries 1 дополнительный provider attempt на компонент при достаточном remaining deadline — начальная рекомендация, уточнить по eval.

### Madrid midnight и DST

Расчёт: взять `now_utc`, получить local date через `ZoneInfo('Europe/Madrid')`, построить **следующую календарную local midnight**, затем перевести её в UTC. `TTL=ceil(reset_utc-now_utc)`, а не `86400` и не add-24h в UTC. Дата операции фиксируется при reservation; retry после полуночи того же idempotency key относится к исходной операции, новый message — к новому дню.

Проверочные примеры (timezone database):

| Локальные сутки Madrid | Начало UTC | Конец UTC | Длина |
|---|---|---|---:|
| 2026-03-29 | 2026-03-28 23:00Z | 2026-03-29 22:00Z | 23 h |
| 2026-10-25 | 2026-10-24 22:00Z | 2026-10-25 23:00Z | 25 h |

Redis quota-cache expires at reset (можно вовсе не кешировать display). Request/idempotency records живут дольше midnight, например 48 h, с отдельной privacy retention; expiry cache не удаляет authoritative debit. Sessions имеют собственный TTL, например 30 min idle/24 h absolute; успешные request records не зависят от session eviction. Canarias живёт на час позади Madrid: UI обязан написать «00:00 Europe/Madrid», соответствующее местное время показывать как подсказку; agreed reset timezone не менять.

## 10. Structured conversation state

Предложенный state: `{schema_version, session_id, subject_binding, intent_version, criteria, per_field_status, hard_constraints, soft_preferences, pending_questions, updated_at, expires_at}`. Criteria — location INE, rental mode, EUR budget/cadence, property category, party adults/children/composition, pet species/size/count, smoking scope, amenities, dates/stay, deposit. Per-field status отражает user-confirmed/extracted/ambiguous/unset, а не model confidence=truth.

LLM отдаёт типизированный **patch** (`set`, `unset`, `clarify`) с expected intent_version. Backend валидирует допустимые изменения и ownership; omitted поле сохраняется. «Теперь только с балконом» меняет balcony и hard flag, оставляя Adeje/двое/600; «до 700» меняет maxPrice; «убери условие про животных» удаляет pet constraint. «С собакой» не превращается в pets=false после timeout. Reset-all — явное действие, не интерпретация пустого model output.

Один конкурентный update на session version; stale patch →409 и retry/reload state, без повторного debit за тот же request. На provider отправлять лишь current structured state + текущий message, не дублировать бесконечную историю. Минимизировать household PII; не сохранять полный audio по умолчанию. Смена login/logout требует rebind/new session с очисткой персонального контекста; чужой opaque session ID не даёт доступ без subject binding. [INFERRED на S08/S09]

## 11. Контракты API: минимальный набор

Все endpoints ниже **проект**, не действующий API. Использовать `/api/v1/ai-search`, существующий error envelope и request ID. Provider keys/internal enrichment routes непубличны.

| Endpoint | Запрос / ответственность | Ответ / auth / debit |
|---|---|---|
| `GET /quota` | identity из bearer/cookie; без provider | `{limit,used,reserved,remaining,resets_at,timezone}`; anon allowed; 0 debit; Cache-Control:no-store |
| `POST /transcriptions` | multipart finished audio + operation_id/session_id; reserve один user message, validate/ASR | `{operation_id,transcript,editable:true,expires_at,session_version}`; anon/user; ещё не committed debit |
| `POST /query` | `{text,session_id?,expected_version?,operation_id?}` + Idempotency-Key; direct text либо исправленная транскрипция | `{session_id,intent_version,intent,applied_filters,items,total,next_cursor,explanations,questions,quota}`; success=1 debit, voice использует прежнюю reservation |
| `GET /requests/{operation_id}` | replay/status после lost response/ASR job | только свой operation, redacted bounded status/result; без provider и debit |

Context endpoint не обязателен: query response уже содержит semantic state. Для subsequent page использовать read-only results cursor контракт, связанный с intent version; **просмотр страниц не новый AI message**, provider не вызывается и квота не списывается. Можно расширить existing search transport внутренним validated intent token либо дать `GET /results?cursor=…` под тем же module; решение зафиксировать в contract PR. Прямой opaque token не должен разрешать visibility bypass.

Общий orchestration: validate → identify → idempotency/reserve → optional finished-file ASR preview → user correction → same intent extractor → deterministic SQL features → existing DTO → persist state/result+debit → text response. Для text шаг ASR пропускается. Transcript edit не отдельное user message до submit; follow-up после уже успешного ответа — новое сообщение.

Ошибки: 400 malformed, 401 invalid identity, 403 moderation/origin, 409 idempotency-content mismatch/stale session, 413 bytes, 415 unsupported media, 422 duration/schema/semantic validation, 429 daily quota или отдельный abuse rate code, 502 invalid provider result, 503 unavailable dependencies/feature disabled, 504 deadline. Для system/provider failure release; response содержит `quota_consumed:false` и безопасный code, без provider internals. Повторная replay успешного request содержит исходный debit, а не новый. ASR error/retake оставляет корректируемый text UI; plain search не блокируется.

## 12. AI enrichment и схема

Цель: importer commit → durable snapshot change signal/reconciler → isolated enrichment job → sanitized evidence → external LLM → strict fact validation → per-source versioned facts → canonical resolver → search features. **Provider call никогда не в importer transaction и не в user card loop.**

F уже содержит `ListingEvidenceInput`, sanitization известных contacts/URLs/markup, deterministic hash без IDs/photo-order, bounded evidence grammar, readiness `insufficient_source_data`, audit CLI и synthetic golden fixtures. F **не содержит** live client, durable job, facts tables, worker/DLQ, canonical resolver или полноценную PII classification. Audit CLI использует явный DSN, READ ONLY repeatable-read и 60 s statement timeout, streams batches500; accumulator всё ещё хранит lengths/conflict groups в RAM, поэтому не полностью constant-memory. На production не запускался и туда не копировался. [VERIFIED_BRANCH_ONLY S10/S12]

Минимальная expand-only persistence:

| Сущность | Поля и инварианты |
|---|---|
| `listing_ai_facts` | source_record_id, canonical_listing_id, input_hash, source_observed_at, schema/prompt/extractor/provider/model version, status, facts JSONB, evidence refs, validated_at; unique source+hash+extractor-version |
| `listing_search_features` | canonical listing PK, resolver_version, source-set version/hash, typed capacity/couples/children/pets/smoking scopes, conditions/conflict/unknown, freshness, updated_at; индексы по реальным query plans |
| `ai_enrichment_jobs` | source_record_id/hash/schema+extractor key unique, pending/leased/retry/dead/succeeded, attempts, next_attempt, lease token/expiry, safe error_code; bounded claim SKIP LOCKED |

Импорт сохраняет snapshot; в той же commit unit можно вставить лёгкий job/outbox marker, а **выполнение только после commit**. Периодический reconciler закрывает missed events и historical eligibility, сверяя semantic content hash, не `content_updated_at` (он обновляется и при unchanged). Не отправлять raw_payload/normalized_payload целиком: normalized содержит raw. IDs нужны локальному routing, в provider request достаточно opaque reference или вообще без ID.

Output validator требует source spans/provider field paths, типы, scope и bounded allowed facts; отсутствие evidence →unknown. Conditions как «только маленькие собаки», «курить на балконе», «дети по согласованию» сохраняются условиями. Определённое N occupants не выводится из количества кроватей, household population или «no parejas». Балкон в описании smoking policy не обязательно amenity без корректного контекста.

Resolver: explicit owner assertion с зафиксированным происхождением/manual override приоритетен; legacy owner defaults не приоритетный факт. Только fresh active source votes; равнонадёжные противоречия →conflict. При primary change/removal/retirement/reactivation recompute feature projection и invalidate old content results. Ответ старого worker после source/hash/version change сохранять historical/stale или отбрасывать, но не делать current. Старые valid facts не стирать при provider outage. DLQ/retry UI и alerts только метаданные, без текстов/контактов.

Backfill: dry-run на approved replica → counts eligible/empty/stale по source + sanitized real gold-set → маленький staging pilot → отдельное разрешение production rollout. Первая партия условно 25–50 source records, затем увеличение по измеренной latency/error. Полный размер backfill **не равен 1 163**: это public canonical count, source records могут дублироваться/включать inactive. Empty source descriptions → insufficient_source_data, не платная попытка «додумать»; refetch только отдельный согласованный background importer path, не новый crawl из audit/search.

## 13. Saved searches и alerts

Сохранять intent в существующем JSONB например `ai_search:{version,criteria,hard,soft}` плюс legacy-compatible fields. Новая migration SavedSearch для этого не обязательна; versioned translator и validation обязательны. Запись через существующие authenticated endpoints с ownership; запретить AI guest save/alerts, показать login flow. Guest local search history не является notification registration. [S05/S08/S11]

Matcher alerts должен использовать **тот же compatibility service**, что interactive AI search, иначе saved search по small dog станет просто pets=true. Re-match при newly available facts после enrichment и при reactivation делать идемпотентно. Existing notification recipient+key, mail leases/outbox переиспользовать; не создавать второй engine. На удалённые/closed listings не отправлять «новое подходящее». Решить версионирование ключа: обычный repeat enrichment не создаёт второй new-listing alert; существенное обновление отдельный event type только по явному продуктному решению.

Backend saved-search matcher сейчас перебирает enabled rows и проверяет listing SQL; при 10 000 AI users это потенциальный fan-out/connection bottleneck. Нужны coarse preselection (region/mode/price) и bounded jobs, измерить на staging; не запускать один LLM на saved search или email. Web push advertising waitlist не подменяет общий saved-search transport.

## 14. Стоимость и capacity

**Расчёты, не измеренный usage.** Предпосылки: 1 intent call = 1 200 input + 250 output tokens; 1 enrichment = 2 000 input + 400 output; voice recording=30 s. Без cache discounts, retries, taxes, FX, fees и provider overhead.

DeepSeek intent: off-peak `1200×0.15/1e6+250×0.60/1e6=$0.00033`, peak **$0.00066**. Enrichment: **$0.00054–0.00108/record**. 1 000 enrichment records — **$0.54–1.08**; сколько records пригодны в Ttest, неизвестно. Groq 30 s: **$0.000925**, OpenAI fallback 30 s: **$0.00225**. ASR minimum charge влияет на короткие записи. Цены основаны на официальных страницах разделов 7–8, арифметика INFERRED; сверить перед launch.

Для сценариев ниже: 5 успешных сообщений/user/day, половина voice по 30 s; каждое сообщение один intent call. Это рабочая нагрузка, **не** замена лимиту 200.

| AI users/day | Messages/day | Voice minutes/day | DeepSeek/day off-peak–peak | Groq/day | Всего/day с Groq |
|---:|---:|---:|---:|---:|---:|
| 100 | 500 | 125 | $0.165–0.33 | $0.23125 | $0.39625–0.56125 |
| 1 000 | 5 000 | 1 250 | $1.65–3.30 | $2.3125 | $3.9625–5.6125 |
| 10 000 | 50 000 | 12 500 | $16.50–33.00 | $23.125 | $39.625–56.125 |

При полном ASR fallback добавка вместо Groq: $0.5625 / $5.625 / $56.25 соответственно. При всех 200 сообщениях зарегистрированного пользователя объём в **40 раз** выше предпосылки5; quotas не являются прогнозом потребления. Costs содержат successes: failed attempts/ASR previews/retries также оплачиваются провайдеру и должны попадать в billing metrics отдельно от user debit. Месячный cap не вводится.

Measured headroom: 6 CPU, ~15.6 GiB available, 869 GiB free; importer на одном sample потреблял около одного core. Backend один Uvicorn процесс, DB pool5+5. Это достаточно для небольшого API pilot, но не доказательство 10k users SLA. [E02/E04]

Если все 5 сообщений приходят в 8 peak hours: средний arrival 0.017 / 0.174 / 1.736 requests/s. При **условной** latency8 s concurrent in-flight≈0.14 /1.39 /13.89; burst×5 даёт ~0.7 /6.9 /69.4. При 10k users внешние API limits и очередь существенно важнее размера модели на VPS; ASR sample plan limits могут быть превышены уже на 1k users, поэтому нужны account-specific quota facts.

Начальные рекомендуемые caps: interactive AI in-flight4 (ASR sub-cap2), background enrichment1, одно active сообщение/session, короткий bounded queue и явный busy response; не держать DB connection во время внешнего API. После staging measurements увеличить до8 interactive только при стабильных DB/Redis/API p95 и account limits. Не увеличивать Uvicorn workers/pools автоматически: каждый процесс множит DB pool, а worker/queue тоже используют соединения. SQL max_connections/actual headroom неизвестны.

Рост: `source_records × retained_versions × average_fact_bytes + jobs/requests/indexes`. Иллюстрация 10 000 sources×4 versions×4 KiB≈156 MiB без indexes/raw/history; это **не оценка фактического DB size**. При 8 MiB max и4 active uploads сырой буфер минимум32 MiB плюс decoder overhead; streaming temp files и caps важны. Аудио/transcripts не удерживать бесконечно. Увеличение logs/requests 50k/day требует retention и storage metrics. Bandwidth/IOPS не измерены; тяжёлых нагрузочных тестов на production не было.

Обязательные metrics: requests success/error/debit/replay/reservation_expired, provider calls/tokens/audio_seconds/cost по task/model/status, queue depth/oldest age/retries/DLQ, evidence quality/unknown/conflict/stale, DB pool waits, Redis memory/errors, ASR/intent/search p50/p95. Не добавлять text/user_id/listing_id как Prometheus labels. Исправить отбрасывание allowlisted source counters JsonFormatter отдельно. Технические circuit breakers/limits защищают систему и не являются финансовым cutoff.

## 15. Security/privacy gates

| Область | Конкретная проверка до запуска |
|---|---|
| Identity/authorization | reuse persisted session и bans; no client user_id trust; subject-bound conversation/replay/result |
| CSRF/CORS | bearer API и existing cookie origin guard; новый guest cookie требует SameSite/Origin+fetch metadata policy, CORS не заменяет CSRF |
| Audio | HTTPS, same-origin microphone policy, явное действие, MIME+container+codec+duration+byte bounds; decoder CPU/memory/time cap |
| PII | selected evidence only, contacts/names/address minimization; F regex cleaner недостаточен для general PII |
| Imported prompt injection | no tools/SQL/network, data delimiters, strict output, evidence checking; prompt не security boundary сам по себе |
| SQL | fixed SQLAlchemy predicates/allowlist fields, никаких SQL snippets из provider |
| SSRF | no audio URL intake; existing guarded source HTTP не обходить новым provider adapter; fixed provider hosts |
| Abuse | shared durable quotas + minute/concurrency/audio-second limits; no process-memory quota fallback |
| Duplicate/cancellation | request hash/idempotency/fencing; no double charge по user operation |
| Retention | delete temporary audio; configurable short transcript/operation retention; no content in logs/tracing/error payloads |
| Provider processing | получить API-specific terms/account controls, проверить fallback routing/transfers; audit не даёт legal certification |
| Feature flags | отдельно user AI/ASR/background extraction, по умолчанию off до acceptance |
| Internal jobs | worker private network, server credentials, отсутствие публичного «enrich arbitrary URL/listing» |
| UI | normal search доступен при quota/provider/Redis error; user может править transcript, повторять запись |

Туристические rental legal requirements и source ToS/robots — отдельный review; никакие новые источники/POI/маршруты этим дизайном не подключаются. Публичность исходного объявления не означает допустимость отправки его контактов стороннему AI.

## 16. Стратегия тестирования

Future contract/unit tests: строгая схема и патчи/clear semantics, RU/ES aliases, ambiguous city, currencies/cadence, negation/condition/conflict, owner defaults provenance, source precedence и stale hash. Отдельно current exact capacity=2 vs AI confirmed>=2; preserve unknown dates semantics обычного поиска. Existing parser golden26 cases остаётся synthetic layer, не production accuracy score.

DB integration на disposable PostgreSQL/PostGIS: expand-only migrations/current old-code compatibility, source→canonical lifecycle, primary switch/dedup/retirement, facts/resolver invalidation, queue leases/fencing/crash, quota row race (например100 concurrent запросов на remaining1), same/different idempotency payload, failure release, lost response replay, Midnight/DST23h/25h и cross-midnight retry. Redis outage/restart/cache-loss не должен давать бесплатную новую business quota.

Provider tests сначала mocked adapters: invalid/empty JSON, unsupported enum, timeout/429/5xx, wrong evidence, truncated response, prompt injection, ASR invalid audio. Реальные paid eval — отдельный будущий этап после разрешения, privacy и набора; не часть этого аудита.

Frontend E2E с fake providers: record-stop-upload, deny/cancel/retake, editable transcript, text-only submit, duplicate click, request retry, quotas3/200, restore/reset filters, mobile keyboard, unsupported MediaRecorder, iOS format. Проверить сохранение галерей/source links/TOP badges и обоих renderer.

Обязательный regression envelope: ordinary search/maps, owners/external cards, favorites/saved alerts, rental modes/price cap, Stripe checkout/webhooks/refunds/financial states, TOP expiration/boost sort/pagination, source deactivation/preservation, auth/bans/media. CI уже имеет PostGIS/payment/browser checks; добавить focused AI suites, не маскировать post-merge main failures зелёным PR head. [E08/S14]

## 17. Что действительно блокирует запуск

1. Нет измеренной source coverage/provenance и разрешённого read-only inventory; публичные1 163 не заменяют эти данные.
2. Нет безопасного authoritative quota/state/idempotency и offline compatibility semantics.
3. Нет outbound privacy gate/API terms и approved provider account settings; credentials сами по себе это не решают.
4. Нет voice capture/transport/validation, microphone запрещён.
5. Нужно сохранить existing TOP+boost order, согласовать apartment taxonomy и stale/fresh matching.
6. Нет AI workers/queue/fact storage; main CI имеет непрояснённые failures, source diagnostics неполны.

Не блокируют старт offline ADR: неизвестная ASR latency, точный месячный счёт и будущий peak traffic. Они закрываются до rollout отдельными eval/measurements, а не домыслами в аудите. Конкретные PR и acceptance criteria: [AI_IMPLEMENTATION_SEQUENCE.md](AI_IMPLEMENTATION_SEQUENCE.md).
