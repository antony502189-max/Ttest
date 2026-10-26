# AI-01 — Контракты AI Search v1

Дата: 2026-10-26. Статус: **PROPOSED / REVIEW_REQUIRED**. Документационный этап AI-01 подготовлен; технические решения ниже требуют review перед зависимыми runtime PR. Runtime, миграции и provider clients этим ADR не вводятся.

## Основание и совместимость

Прямые решения владельца и [Product spec на handoff SHA](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md) выше этого ADR. [Рабочее ТЗ](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/10_IMPLEMENTATION_TZ.md) определяет границы. Указаны immutable ссылки, поскольку #374 ещё открыт; его документы здесь не копируются и не объявляются слитыми. [Матрица сценариев](../contracts/acceptance-v1.json) синтетическая, не оценка реального каталога.

База реализации: `main` **1292c6807ece59999238bb31c80e09ef7e2c3212**, включая платежи #372. На 26.10.2026 #373/#374/#375 открыты. Planning `f203807d4507f68b34cd4407e326b3bc671a3552` отстаёт по платежам; переносить planning вместо main нельзя. #373 head `fcae378d9dbbc8447f18df150327180f6f2c8231` содержит offline evidence/input builder; здесь он только сопоставлен с будущим контрактом, не перенесён и не прошёл human review BASE-373.

Проверенные anchors текущего main:

| Контракт | Существующий код | Граница AI |
| --- | --- | --- |
| Карточки и count | [repositories/listings.py](../../../backend/app/repositories/listings.py), `search_public_cards` | Reuse `ListingCardResponse`; дополнительные reasons рядом с cards, без изменения DTO карточки |
| Capacity | Там же, `apply_search_filters` | `roomCapacity == N` остаётся legacy; новый verified available-capacity predicate `>= party size` |
| TOP | Там же, `apply_search_order`, `_card_sort_components` | Полная существующая коммерческая сортировка перед AI soft preferences |
| Intent geography | [schemas/listings.py](../../../backend/app/schemas/listings.py), [municipalities](../../../backend/app/data/spain-municipalities.json) | INE `38001` Adeje, `38006` Arona; aliases только через локальный справочник |
| Saved searches | [services/notifications.py](../../../backend/app/services/notifications.py), [services/search_state.py](../../../backend/app/services/search_state.py) | Старый matcher не знает AI extra fields; несовместимые версии не понижаются молча до legacy |

Ни один пример ниже не является действующим публичным API.

## 1. Typed vocabulary и evidence

Версии независимы: `schema_version=ai-search.v1`, `extractor_version`, `resolver_version`, `taxonomy_version`. Неизвестная major version отвергается, не преобразуется в пустой поиск. Pydantic DTO будущего PR: strict, `extra=forbid`, bounded arrays/strings, finite numbers, никакого coercion `"false"→true`, `true→1`, NaN или model-generated SQL. Примеры: [dto-examples-v1.json](../contracts/dto-examples-v1.json).

`ListingFact` — per-source observation, не canonical projection:

| Поле | Тип / правило |
| --- | --- |
| `schema_version`, `taxonomy_version` | Версия контракта / словаря |
| `fact_id`, `source_record_id`, `canonical_listing_id` | UUID; source record для external обязателен; для native допустим null только с `origin=owner_explicit` |
| `key` | Один из typed keys в таблице ниже |
| `status` | `explicit_allow`, `explicit_deny`, `conditional`, `unknown`, `conflict`, `legacy_unverified` |
| `typed_value` | Discriminated union по `kind`; unknown/conflict/legacy = null |
| `qualifiers` | Typed scope: species, size, max_count, smoking_scope, approval_required; только поля, допустимые для данного key |
| `evidence` | Array sanitized spans: source field, exact quote, start/end offsets в sanitized snapshot; никакого raw HTML/контактов |
| `origin` | `owner_explicit`, `source_structured`, `source_text`, `model_extracted`, `legacy_default`; origin не даёт автоматической истинности |
| `observed_at`, `content_hash` | UTC instant и SHA-256 sanitized content; hash не равен legacy import fingerprint |
| `extractor_version` | Версия extraction rules/model prompt; server-owned |

Статусы сохраняют названия из ТЗ. Для policies `explicit_allow` / `explicit_deny` означают доказанное разрешение/запрет. Для value facts `explicit_allow` означает только **подтверждённое значение**, не разрешение; `explicit_deny` для numeric/money/type/date факта запрещён. Условный факт может хранить scoped typed value, но без безусловного permit. Conflict не имеет победившего value и ссылается на все конфликтующие observations. Unknown: null, пустые qualifiers/evidence; legacy_unverified: null, ссылка на legacy origin, без fabricated quote.

| Key | `typed_value.kind` / содержимое |
| --- | --- |
| `pets`, `smoking`, `couples`, `children`, `tenant_groups` | `policy`: `allowed: bool`; группы из supported tenant vocabulary; smoking scopes `indoors/outdoors/balcony/terrace` |
| `capacity_total`, `current_room_residents`, `available_spots` | `quantity`: nonnegative integer, `unit=persons`; total/available положительные; scope `rented_unit`, не площадь всего дома |
| `price`, `deposit` | `money`: decimal amount **строкой**, `currency=EUR`, `period=monthly/nightly/weekly/one_off`; deposit months — отдельный `quantity`, `unit=months`, не ноль евро |
| `furnished`, `bills_included`, `balcony`, `terrace`, `amenity` | `boolean`: строго bool; `amenity` qualifier содержит supported catalog code |
| `rental_mode`, `accommodation` | `category`: `long/holiday`; либо `room/shared_room/studio/one_bedroom/catalog_other` с обязательным подтверждённым catalog code |
| `geography` | `geography`: INE municipality/province, optional supported zone ID; не private address |
| `availability` | `date_range`: ISO dates, end > start, explicit inventory scope |
| `minimum_stay`, `maximum_stay` | `quantity`: положительное значение, `unit=nights/months`; без неявного пересчёта месяцев в 30 ночей |

`catalog_other` не разрешает LLM придумывать тип: сервер разрешает только действующий catalog code. Нормализованный AI vocabulary проецируется через reviewed mapping текущих `roomType/rentalUnit/bedroomCounts`; one-bedroom не сводить к studio. Неизвестный код → unsupported/clarification, не удаление ограничения.

### Bridge к #373

#373 `PolicyFact(status=explicit, value=true/false)` → allow/deny только при проверенном evidence/span. Для integer `room_capacity` → `capacity_total` со статусом confirmed value, unit persons, только после проверки scope. `conditional`, `conflict`, `unknown` сохраняются; scalar fallback ничего не доказывает. #373 `explicit` не новый статус v1; adapter переводит его однократно. Дефолты `pets_allowed=false`, `furnished=true`, `deposit=0`, `room_capacity=1` → `legacy_unverified`, не evidence. Builder #373 — minimization helper, не одобренный privacy gate. Повторять его parser/cleaner в AI-01 нельзя.

## 2. Resolver и freshness

Resolver читает observations текущего content hash/schema/extractor, не меняет imported listing scalars. Projection хранит `feature_revision`, `resolver_version`, supporting fact IDs, freshness metadata и matchable value/status по каждому key+scope. Job ключ: source record + content hash + extractor version; запись результата — CAS с текущим hash/generation. Старый job после изменения snapshot, удаления или retirement не восстанавливает facts. Смена resolver запускает отдельный rematch event.

Рекомендованная precedence (требует review): проверенный explicit owner override для **того же canonical listing, key и scope** выше source observations; override хранит автора/время/superseded facts и снимается явно. Imported listing не считается owner-controlled без подтверждения ownership. Unverified/legacy/model confidence не повышают authority. Внутри равного authority: равные значения объединяются; несовместимые значения/permissions → conflict. `last observed` не разрешает конфликт. Owner override также не отменяет moderation, source retirement и publication visibility.

Условие про маленьких собак не включает кошек/всех собак; count/size/species проверяются совместно. «По согласованию» всегда unresolved до отдельного разрешения. Балконное smoking permission не подтверждает indoor smoking. Отрицание сохраняется в span; regex presence слова «pets» ничего не доказывает.

Freshness хранит отдельно `source_status`, `last_successful_check_at`, `last_content_change_at`, `evidence_observed_at`, `last_check_error_at`. Check без изменения не сдвигает content-change timestamp. Failure не считается check success. Retired/unavailable source не supporting evidence; при других активных sources resolver пересчитывает canonical, а не обязательно удаляет его целиком. Если последний supporting source retired, listing не может оставаться verified match по его старым фактам. Новый глобальный TTL не вводится: limits/coverage требуют AI-02 и отдельного review. «Verified» означает совпадение с доступным сохранённым evidence, а не обещание, что жильё ещё свободно на внешнем сайте. Никаких external checks на request path.

## 3. Compatibility и hard/soft

Matcher выдаёт по критерию `satisfied/incompatible/unresolved/not_requested`. Все hard критерии обязаны быть `satisfied` для exact list. `unknown/conditional/conflict/legacy_unverified` не проходят hard predicate, без reasons вида «питомцы разрешены». Противоречащие TOP также исключаются до сортировки. Relaxed alternatives потребуют отдельного UX/product review: v1 не смешивает их с exact cards. Неназванный критерий `not_requested` не исключает карточку.

Состав: `party={adults, children, relationship: couple/friends/family/unspecified}`. Численность = adults+children; relationship нельзя вывести из «двое». Для пары нужны и вместимость, и явное couples permission; для детей — соответствующее разрешение; friends не равнозначны couple. Подтверждённый `capacity_total=3` подходит двоим при полной аренде свободного unit. Для shared room нужна verified `available_spots>=2` либо доказанные total/current residents одного scope/revision; `3 total - 2 current` даёт только одно место. Legacy exact `roomCapacity` не использовать для AI minimum-capacity.

Hard по умолчанию: явно названные budget+period, location, mode/type, party, pets, smoking scope, dates/duration, «только/обязательно» amenity. «Желательно балкон» → soft; soft не делает incompatible hard-кандидата допустимым. Фраза «без питомцев» описывает party.pets=[], не требует объявления с запретом на животных. «Не курим» также не требует smoking ban.

Цены сравнивать в EUR и одном period. Monthly €650 не равно weekly €650; никаких FX/30-day пересчётов без согласованного правила. Long monthly cap €1000 и существующие price/visibility/moderation правила действуют независимо от model output. Запрос long €1200 сохраняет потолок пользователя, но каталог всё равно ограничен текущим €1000; сообщить о действующем ограничении. Holiday не получает long cap. Неясные период/отрицание/география → clarification, без выдачи несовместимых карточек. Нераспознанное Adeje не заменять silently на Arona или Spain; postcode/aliases проверять локально.

Reason codes — server templates с supporting fact IDs: `PRICE_WITHIN_BUDGET`, `GEOGRAPHY_CONFIRMED`, `CAPACITY_CONFIRMED`, `COUPLES_EXPLICIT`, `PETS_SCOPE_CONFIRMED`, `SMOKING_SCOPE_CONFIRMED`, `AMENITY_CONFIRMED`, `DATES_CONFIRMED`. Нельзя добавлять неподтверждённый reason, raw source quote или процент match. UI локализует templates ES/EN/RU; legacy card/media/redirect/favorites/map renderer сохраняется.

## 4. SearchIntent и IntentPatch

`SearchIntent`: `schema_version`, `taxonomy_version`, `session_id` UUID, `version` integer >=0, `criteria`. Criteria — typed object с optional `rental_mode`, `budget`, `geography`, `accommodation`, `party`, `pets`, `smoking`, `furnished`, `bills_included`, `deposit`, `balcony`, `terrace`, `amenities`, `dates`, `stay`. Каждый criterion = `{strength: hard|soft, value: <typed value>}`. Null не равно «снять»; отсутствие = не задано. Pets — array `{species, size, count}`; smoking — requested scope; dates — check-in/out, stay — value+unit. Budget — amount+currency+period, geography — локально подтверждённый code. `species=dog/cat/other`, `size=small/medium/large/unspecified`; unspecified size не соответствует small-only policy. V1 count 1–10, adults 1–10, children 0–10, party total <=10 — технический proposal по текущему API; >10 не clamp, а unsupported/clarification до расширения catalog/API. Amount — неотрицательная decimal string с максимум двумя знаками после точки; dates — строгие ISO dates; amenities — unique supported codes, максимум 100. Unsupported qualifier сохраняет uncertainty и не превращается в allow. Эти границы ещё должны стать standalone strict DTO в следующем PR.

`IntentPatch`: `schema_version`, `session_id`, `expected_version`, `set`, `remove`. `set` содержит целиком typed criterion; `remove` — unique names из того же allowlist. Произвольные JSONPath, tools, SQL, session owner, quota, sort/promotion поля запрещены. Поле одновременно в set/remove → invalid. Max 20 changed criteria; nested merge отсутствует: замена party должна быть полной и проверенной. LLM получает только минимальное нормализованное состояние, не весь архив диалога.

Правила:

1. «Теперь только с балконом» устанавливает только hard balcony=true. Budget, pets, party и geography сохраняются.
2. «До 700» при известном EUR/monthly заменяет amount, сохраняя currency/period в **полном** budget value; если period неизвестен — clarification.
3. «Балкон не важен» явно remove balcony; пустое set не снимает остальные критерии.
4. «Начнём заново» — явный reset/new session command, не эвристическое удаление предыдущих критериев.
5. Session subject проверяется сервером, не моделью. CAS `(subject, session_id, expected_version)`; два patch v7 не становятся v8 и v9 молча. Второй получает `SESSION_VERSION_CONFLICT` и release без debit. Committed session version/state хранится в PostgreSQL для атомарного finalize с ledger; Redis только cache/ephemeral progress. Иначе PG success и Redis session CAS нельзя обещать как одну транзакцию.
6. Patch проходит schema + cross-field checks до CAS: nights/months, dates, party totals, geography consistency, budget period, enums. Ambiguity оставляет прежнее committed state и возвращает clarification.
7. TTL — technical proposal 24h inactivity, не quota day; expired → `SESSION_EXPIRED`, без автоматического нового поиска с потерей criteria. Retention pending privacy review; raw transcripts/audio не сохранять в профиле.

## 5. SQL, TOP и cursor

Порядок: существующая visibility/moderation/price policy → verified hard predicates в SQL → count → **весь** текущий commercial sort → seek → limit. Никакого Python/frontend filter после страницы, LLM SQL, live geocoding/crawl или per-card enrichment. AI soft score v1 не вводится; при будущем review разрешён только после сохранения существующего commercial contract. Native/external cards и marker path должны использовать одинаковую eligibility policy.

`CursorBinding v1`: subject hash (если private), session_id/version, normalized intent hash, filter hash, taxonomy/resolver version, monotonic facts/catalog revision, promotion revision, sort, last sort tuple+listing ID, expiry, server MAC. Hash строится сервером из canonical JSON, не model string. На первой странице фиксируется `as_of`; promotion expiry horizon — минимум ближайшего окончания активных TOP, вошедших в matching candidate set. Следующая страница после horizon, boost/activation/expiry, relevant fact или intent change → `CURSOR_STALE`, UI начинает страницу 1. Это invalidation, не immutable SQL snapshot. Консервативная глобальная catalog/promotion revision допустима до измерений; hash выбранных карточек недостаточен — новый matching объект тоже влияет на выдачу.

Текущий base64 cursor связывает только filters/sort и не является signed AI cursor. Не принимать его как новый контракт и не менять legacy endpoint побочным эффектом. AI-09 должен добавить отдельную обёртку/версию, проверять подпись/subject/version **до** seek. GET/POST страницы той же операции не вызывают AI, не тратят новую единицу квоты; pagination не новая user AI message.

## 6. Квота и operation lifecycle

Утверждено: guest 3 / auth 200 успешных user messages в календарный день **Europe/Madrid**, общий voice+text, ровно один debit, valid zero-results списывает 1; ASR/LLM/system/backend failure — 0. Manual search без AI-квоты. Никакого monthly spending cap. Guest identity — signed HttpOnly Secure SameSite cookie; IP дополнительный rate limit, не уникальная личность.

PostgreSQL authoritative: `ai_usage_days(subject, madrid_date, used, reserved)` и `ai_search_requests(subject, idempotency_key, request_hash, day, status, lease_until, fence, result_ref, expected_session_version)`. Unique subject+key, check nonnegative counts и `used+reserved<=limit`. Redis — attempts/audio seconds/inflight/short session cache, не источник бизнес-квоты. Если PG/anti-abuse gate недоступен — fail closed до providers, manual search доступен.

`QueryOperation`: один text **или** один завершённый audio файл, subject/session/version, client idempotency UUID; server request hash включает channel, SHA-256 bytes или canonical text, session/version, transport contract. Текст не пропускать через ASR. Retry обязан повторять тот же key/body; изменённый transcript/follow-up — новый key. Технический content hash/audio limits/codec/duration/bytes проверяются до paid call. Если загрузку нужно временно spool для hash/codec — bounded temporary storage с cleanup, не долговечное хранение голоса.

| Состояние | Переход / транзакционная гарантия |
| --- | --- |
| absent → reserved | Короткая атомарная reserve под day-row lock; сравнить used+reserved с 3/200, создать unique request, reserved+1 **до ASR** |
| reserved → running | Claim lease, monotonic fence; сеть вне PG transactions/connections. Attempt budget применяется независимо от business debit |
| running → succeeded | Одной транзакцией CAS session, сохранить result envelope, used+1, reserved-1; fence/status/lease должны совпасть |
| reserved/running → failed | Terminal release reserved-1 ровно один раз, reason code; session patch не commit |
| running → clarified | Отдельный terminal outcome, прежняя session не меняется; debit/release policy только после решения clarification ADR |
| running → recovering | Lease истёк: старому worker запрещён finalize по fence; crash-reconciler исключает повторный debit |
| recovering → failed/succeeded | По persisted validated result/finalize evidence; без результата release, без автоматического второго paid provider call |

Same key+hash: terminal replay тот же result/status без inference/debit; inflight status/retry-after без второго worker. Same key+different hash → `IDEMPOTENCY_CONFLICT` до provider. Не переоткрывать failed row тем же key; новая пользовательская попытка с новым key ограничена technical budget. При provider timeout неизвестно, был ли внешне billed первый вызов: обещать exactly-once **внешний billing нельзя**. Retry после неопределённого исхода не повторяет provider автоматически; можно завершить failed и дать explicit user retry. Fence предотвращает stale commit, не отменяет уже отправленный HTTP.

Дата bucket фиксируется при reserve; завершение после midnight debit относится к reservation day. Новый запрос после midnight идёт в новый day. `reset_at` — следующая local midnight → UTC по IANA tzdata, не now+24h. DST fixtures: 2026-03-29 — 23h; 2026-10-25 — 25h. При HTTP disconnect после committed success retry возвращает persisted result с тем же debit; при crash до finalize recovery либо атомарно commit известный result, либо release. Коммит success нельзя откатить только потому, что браузер не получил response.

Result envelope хранится с ограниченным retention; техническая рекомендация — idempotency tombstone не короче 48h и всей жизни inflight operation, review до реализации. Для ограничения dedup retention key привязан к server-validated creation window: после его истечения старый key отвергается как `IDEMPOTENCY_KEY_EXPIRED`, а не считается новой операцией; окно/формат в AI-07. Если cards уже retired, replay не выдаёт новые private/stale cards: сохранить operation identity/intent/count/reasons, повторно проверить visibility и вернуть `RESULT_EXPIRED_REQUERY_REQUIRED` без нового debit/paid call. Session не применяет patch второй раз.

### Открытые решения, не утверждённая бизнес-логика

| Вопрос | Предложение для review | До решения |
| --- | --- | --- |
| Успешное clarification | **Не списывать**, no-card outcome; отдельный technical attempts budget | Enum outcome `clarification` отделён от success; production disabled до выбора единого voice/text правила |
| Background saved alerts | Не списывать interactive quota | AI-10 не запускать до подтверждения; не применять implicit default |
| Guest → login | Auth subject использует свои 200, прежний guest bucket не сбрасывается; sessions только explicit transfer с ownership check | Transfer ADR перед AI-08; без автоматического объединения и переноса replay на другого subject |
| Lease/limits | Deadline-bound 15s initial lease, 30s recovery grace; max 60s audio/8 MiB — технические гипотезы | Настроить/измерить offline/staging после privacy, не считать обещанием 10s |

## 7. Saved searches, события и безопасность

AI-10 сохраняет в существующий JSONB filters versioned `ai_search` с normalized intent, matcher/taxonomy version и saved_filter_revision. Auth/ownership обязательны и при создании, и при delayed delivery. Interactive SQL builder и background matcher используют один typed compatibility contract. Unknown version не превращается в legacy широкий запрос: skip alert+diagnostic, предложить обновить поиск.

Durable enrichment event: canonical ID, old/new feature revision, resolver version; создаётся атомарно с projection update. Outbox/rematcher при доставке читает **текущие** saved filters/ownership/enabled и listing visibility/source state. Revisions дедуплицируют jobs, а notification unique key на `(saved_search_id, saved_filter_revision, canonical_listing_id)` предотвращает повтор при новом enrichment той же подходящей карточки. Publish/enrichment race converge в один alert; после реальной правки filters новая revision может дать новый alert. Retirement/disable/edit во время обработки проверяются перед enqueue/delivery; никакого duplicate mail при retry. Уведомление не выдумывает новые факты при устаревшей projection.

Outbound до одобрения DPA/retention/privacy выключен. Только allowlisted sanitized spans, minimum normalized intent; без email/phone/private address/PII из transcript, raw payload, HTML, internal notes, credentials. Audio само может содержать PII: ASR требует отдельного privacy gate, текст до intent также проходит minimization/critical-value preservation check. Prompt injection остаётся данными; модель не имеет tools/SQL/network/ownership authority. Логи — operation ID, стадия, latency, redacted errors, cost counters; raw audio/text/evidence не логировать по умолчанию.

One Send после stop record автоматически выполняет ASR→patch→SQL→existing cards. Transcript editing добровольное, без обязательного второго клика. Error/clarification не рисует старые cards как новый успех. Browser p95 <=10s Send→first **current matching card paint**, включая upload; zero-result latency отдельно. Error/429/timeout rate и доля корректных своевременных результатов считаются по всем валидным обращениям. Метрики/порог ещё не измерены.

## 8. Приёмка и следующие PR

AI-01 предоставляет DTO examples и 12+ негативных сценариев. Они **не runtime tests** и не доказательство PostgreSQL concurrency/coverage/SLO. [Validation report](../AI-01_VALIDATION.md) описывает выполненные offline проверки. [Next actions](../08_NEXT_ACTIONS.md) фиксирует ветку/статус.

После review taxonomy/DTO/ADR: AI-07 ledger → AI-08 sessions на disposable PostgreSQL; BASE-373 отдельно review/port; AI-03 facts → AI-04 queue без provider. AI-02 требует отдельной DBA read-only роли; AI-05/06/11 требуют privacy approval до любого paid/personal outbound; AI-13 — browser+load+payments/TOP regressions на final SHA. Реальные coverage/freshness/SQL plans неизвестны.

Rollback AI-01 — revert только добавленных docs. В будущих PR flags/kill switches отдельно для query/ASR/enrichment, additive migrations и manual fallback; не удалять legacy filters/cards. Merge main, live staging и production deployment требуют отдельных разрешений из ТЗ.
