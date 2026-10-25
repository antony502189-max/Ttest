# Итоговый аудит оставшихся пробелов AI-поиска

Дата наблюдений: **2026-10-25**. Только исследование и документация. Production, приложение, данные, Redis, парсеры, платежи и настройки не изменялись; платные API, crawling, backfill, нагрузочные прогоны, merge и deploy не выполнялись.

## Решение

**Разработку можно начинать. Production запускать нельзя.** Доступной информации достаточно для ADR, строгих DTO, ledger квот, session patch, mock provider adapters, схемы фактов и проектирования индексированного retrieval. Неизмеренные production coverage и нагрузка не блокируют эти работы, но блокируют утверждение о пригодности всего каталога, размер production backfill и включение полного AI. Staging с mocks можно строить; staging с настоящими провайдерами и данными требует privacy/account gates и отдельного разрешения на платные вызовы. [R01–R04, C01–C12, D01; вывод INFERRED]

Для голоса: **FEASIBLE_WITH_SPECIFIC_CHANGES**, уверенность средняя в архитектуре и низкая в достижении численного SLO до прототипа. **p95 ≤10 секунд не доказан.** Рекомендован один multipart request с автоматическими ASR → intent → SQL → прежними карточками. [P01–P03, C01/C02/C08/C09; подробности в [VOICE_10S_FEASIBILITY.md](VOICE_10S_FEASIBILITY.md)]

Первый следующий PR: **PR-AI-01 — ADR provenance/compatibility, versioned intent/patch и quota/operation contract, без runtime и миграций**. Следующий первый кодовый поток после ADR — AI-07, quota ledger с concurrency/DST/replay tests на disposable PostgreSQL. Review/перенос #373 на текущую кодовую базу и DBA evidence идут отдельно. [R02/R03, C03–C07, INFERRED]

## 1. Граница проверки и актуальность материалов

Использованы README, 01–09 и CODEX_START_HERE из developer handoff, три прошлых аудита и parser audit #373. Исторические отчёты не переписаны. Это целевой разбор оставшихся вопросов A–I, а не повтор инвентаризации серверов. Исторические SSH/контейнерные наблюдения не выдаются за новый runtime check. [R03/R04]

| Ref | Точный SHA | Состояние при повторной проверке |
|---|---|---|
| M / main | `1292c6807ece59999238bb31c80e09ef7e2c3212` | GitHub branch API и свежий clone; PR #372 merged |
| H / developer docs | `85fa9ad7ebff15634b34bd341882d302398b6dfc` | PR #374 open, base main; новый аудит направляется в эту ветку |
| F / parser foundation | `fcae378d9dbbc8447f18df150327180f6f2c8231` | PR #373 open, base planning; не production |
| P / planning | `1ace67b5ae67ab267fdcc37ee499b87bd433fb71` | `main...planning`: 1 commit только main, 10 только planning |
| Публичный frontend build | M | HTTPS `/build-info.json` в 20:19 UTC; не доказательство hash всех backend-файлов |

Сравнение H с M по `backend/`, `src/`, `deploy/`, compose не выявило различий. Поэтому анализ исполняемых файлов в checkout H соответствует M. Исходный E:/task с изменёнными изображениями не использован как baseline и не исправлялся. [R01–R03]

**Устаревшая рекомендация исправлена решением, а не редактированием истории:** в старом AI_INTEGRATION_READINESS есть этап обязательного подтверждения транскрипта. Прямое требование владельца и 09_PERFORMANCE_SLO выше: первый поиск запускается автоматически после Send. Старые состояния `awaiting_confirmation` не включать в обязательный happy path. Старое предложение направлять кодовые PR по умолчанию в planning также не является разрешением заменить current main; новые implementation branches строить на актуальном main после интеграционного review. [R03/R04, INFERRED]

## 2. Что закрыто и что осталось неизвестным

| Вопрос | Итог | Что это означает |
|---|---|---|
| Актуальные PR/main | Закрыт: R01–R03 | #373/#374 не слиты; #372 уже в M |
| Публичный build и microphone policy | Закрыт в окне P01 | build M; capture всё ещё запрещён |
| Capacity и порядок TOP | Закрыт по коду C03/C04 | legacy exact equality; TOP/boost после eligibility |
| Назначение source timestamps | Закрыт по коду C05/C06 | discovery, successful fetch и content change нельзя смешивать |
| Достаточность #373 | Закрыт по F, C07 | исправляет часть потерь обновлений, не весь evidence pipeline |
| Saved AI JSON replay | Закрыт по коду C10 | JSON хранить можно; старый matcher AI-поля не понимает |
| Текущий CI | Закрыт для конкретных runs R05 | main full audit failed; H full audit passed, H mobile failed |
| Total DB, usable coverage, actual source success | **BLOCKED D01** | нет подтверждённой выделенной read-only роли/реплики |
| Индексы/планы/пулы в runtime | **BLOCKED D01** | есть migration/code evidence, нет live DB measurement |
| Groq/DeepSeek latency, качество RU/ES/EN | **UNKNOWN** | paid calls запрещены заданием, feature отсутствует |
| Account limits/DPA/retention settings | **UNKNOWN** | официальная документация не показывает настройки аккаунта |
| Фактический browser SLO | **NEEDS_MEASUREMENT** | три HTTP sample не являются голосовым E2E |

## 3. A/B — каталог и полезность источников

Полная матрица, определения знаменателей и SQL-процедура: [REAL_CATALOG_EVIDENCE.md](REAL_CATALOG_EVIDENCE.md). Новые public measurements: long=**1134**, holiday=**31**, сумма **1165**, запросы последовательные, не один DB snapshot. Исторические 1163 сохраняются как исторические. Изменение +2 не доказывает происхождение новых объявлений или успешность адаптера. [P02/P03]

В выбранных первых страницах есть Pisos и Fotocasa: long page — 16 Pisos, 1 Fotocasa, 3 без `primarySource`; holiday — 19 Pisos, 1 без `primarySource`; Adeje≤700 — 1 Fotocasa, 5 без `primarySource`. Это **наличие отображаемых карточек**, не свежий успешный import этих площадок. Страницы пересекаются; их нельзя складывать как unique inventory. Полнота описаний/условий по этим источникам и всем остальным — null. [P02/P03]

В коде зарегистрировано 8 базовых source types; Habitaclia добавляется production hook вне обычного списка. Compose default включает Fotocasa, Milanuncios, PisoCompartido, Pisos, AlquilerDocenteCanarias, Flatio; старый runtime snapshot подтверждал эти шесть плюс Habitaclia. Текущая worker-specific effective configuration повторно не прочитана. Configured ≠ healthy process ≠ useful fresh data. [C05/C06, R04; DOCUMENTED_ONLY для старого runtime]

`ExternalImportRun` хранит result/counters/discovery/http_status/challenge/next_check; это лучше worker heartbeat для source health. `accepted_rentals` увеличивается до upsert и является числом событий, а не уникальных сохранённых usable dwellings. Полезный источник должен одновременно иметь свежие successful/partial runs, persisted accepted records, видимые canonical и проверяемое evidence. Все эти production пересечения пока не измерены. [C05/C06]

`JsonFormatter` выбрасывает `source`, `sources`, `run_id`, counters/result из `extra`. Часть explicit message summaries сохраняется, но обычного `external_import_finished` или healthy worker недостаточно для per-source success rate. Не запускались audit CLI, worker healthcheck или live source contract commands без проверки side effects. [C06, D01]

## 4. C — критический путь и инфраструктурные ограничения

Один внешний intent call и один ASR в обычном голосовом запросе; enrichment заранее, вне user path. PostgreSQL connection/transaction не удерживать во время provider await. В существующей базе уже async SQLAlchemy, httpx и multipart; это снижает объём интеграции, но не даёт SLO. [C01/C02/C08]

Уточнение прежнего аудита: **256 KiB подтверждено как общий Nginx limit**, `client_max_body_size 256k`. В просмотренном FastAPI `main.py` нет самостоятельного общего middleware с таким byte cap. Upload endpoints имеют собственные ограничения. Новый audio route требует собственного streaming byte/duration/codec cap на backend и scoped Nginx location. Нельзя переносить формулировку «FastAPI ограничивает все body 256 KiB» без отдельного доказательства. `/api/` proxy timeout в M — **60 s**, public-page proxy — 30 s; ни то ни другое не является AI deadline. [C01/C02]

Compose default pool5+5 на процесс, ожидание30s, SQL60s, lock10s; Settings defaults10+20, не путать с compose/runtime. Один Uvicorn процесс по Dockerfile и историческому audit; текущее число процессов не проверено SSH. Без `max_connections`, активных соединений importer/mail и pool wait нельзя оценить headroom. До реализации нужны короткие AI-specific acquisition/query deadlines. [C02, R04, D01]

API JSON сейчас без gzip в трёх samples: 32 931 / 37 582 / 8 985 body bytes. Nginx `/api/` явно `gzip off`; включение только для проверенного JSON route — возможная оптимизация, которую нужно измерить и отдельно проверить с учётом безопасности сжатия приватных ответов. Не менять всё proxy config ради предположения. [P02/P03, C01]

Frontend уже умеет показать карточки до восстановления неполных native galleries; сохранить progressive callback. Без него helper ожидает gallery hydration. Desktop/mobile имеют независимые state/request paths; AI response должен передавать готовые items и query token, не запускать повторный legacy search с потерей AI-критериев. Mobile intersection observer может сразу запросить следующую страницу; отложить его до первого результата и не считать pagination новым AI message. [C08/C09]

## 5. D — свежесть и фактическая доступность

`published` — public lifecycle state, не подтверждение, что объект сейчас свободен. `visible_query()` проверяет published, price ceiling, deleted/blocked owner и активные ограничения; он не соединяет source current status и не доказывает availability. Temporarily unavailable не выделен как самостоятельный canonical enum: source error/check result и listing closed/hidden — разные уровни. `expires_at` не входит отдельным условием в этот query; нельзя добавлять его от имени существующей semantics. [C03/C11]

Повторное обнаружение URL обновляет `last_discovered_at/last_seen_at` до fetch. `last_success_at` означает успешный fetch/active-state observation по конкретному пути; не гарантию vacancy. `last_checked_at` может означать неуспешную попытку. `content_updated_at` обновляется и без semantic change. `last_synced_at` canonical — применение metadata, не первичный источник проверки. [C05/C06/C11]

Preserve-existing guard может подавить deactivation/purge; compose default preserve=1, removal=0. Это объясняет, почему старое объявление может оставаться visible при отсутствии свежего подтверждения. Текущее effective значение не перепроверялось, и аудит его не меняет. [C06/C11, R04]

**Предлагаемая policy для ADR, не активированная политика:**

1. Существующая visibility остаётся обязательной. Подтверждённый removed/expired/not_found/retired source не голосует за текущие AI facts; canonical с живой альтернативой пересчитывается. Сбой/403/redirect без доказанного identity не равен удалению.
2. Разделить `source_content_observed_at`, `availability_observed_at`, `last_attempt_at`, `source_status`, `verification_method`, `input_hash/source_version`, `resolver_version`. Имеющиеся timestamps переиспользовать с точной semantics, новые поля добавлять лишь для отсутствующих различий. Source status/check evidence и fact freshness не смешивать.
3. До измерения реальных интервалов не задавать глобальную TTL, скрывающую каталог. Для каждого source согласовать content/availability confidence window по реальному расписанию, сбоям и ручной gold-проверке. Числа этих окон пока **не определены**.
4. Старые записи могут оставаться в обычном поиске. В AI они не называются «доступность проверена»: видимое «Последняя проверка …; наличие нужно уточнить». Для обязательной verified availability они не confirmed matches. Отдельная группа «нужно уточнить» — только явно выбранная policy, не скрытое ослабление hard constraints.
5. После изменения/исчезновения source stale facts не используются как current permit. При временном LLM outage можно хранить историю, но не подтверждать факт с несовпадающим content hash. Unknown freshness явно отражать в UI.
6. Alert использует freshness в момент matching и повторно перед отправкой; stale/closed/withdrawn не становится «новым подходящим». Сама публикация или новая дата import не повод повторить alert. [C03/C05/C06/C10/C11, INFERRED]

## 6. E — полная матрица совместимости

Во всех строках «сейчас» — **VERIFIED_CODE_MAIN M**, «AI/изменение» — **INFERRED proposal**. Дата 2026-10-25, метод: чтение точных исходников; production coverage неизвестна во всех строках. `L` означает `listings`, `RD` — `listing_room_details`. Источник scalar: owner form/default или primary imported snapshot; исторический explicit origin не восстановлен. Ссылки C03/C04/C05/C11 дают SHA+строки.

| Критерий | Поле / происхождение | Сейчас: semantics и строки | Желаемая AI-semantics / изменение | Риск и acceptance |
|---|---|---|---|---|
| Цена/период | L.monthly/nightly/weekly_price, source_price_period; primary source/owner | primary_price; min/max, rentalMode; repo:338–381; price policy:79–88 | typed EUR/month/night/week, hard vs preferred; не сравнивать месячную с ночной | 700€/month не пропускает 700€/night; long≤1000 остаётся |
| Тип | L.room_type, bedroom_count; parser/owner | equality/in; repo:382–393; DTO allowed enum | явный room/shared/studio/one-bedroom contract; imported apartment не превращать в studio | новые DTO не ломают старый enum; actual apartment sample P02/P03 |
| Режим | L.rental_mode | exact long/holiday, repo:376–377 | same predicate; ambiguity→уточнение | holiday не получает скрытый monthly cap |
| Место | province_code/city/area/location | municipality→province→community→query priority, repo:343–375 | existing INE/aliases, без новых геосервисов; не угадывать точный адрес | Adeje/Arona не смешаны, unknown geography явна |
| Максимум людей | coalesce(RD.room_capacity_v2,L.room_capacity); legacy/default/snapshot | **==N**, repo:433–434; importer 1–10, legacy≤2 | отдельный evidenced confirmed_capacity **>=party_size** до paging | N2 + confirmed3 включён; default3 не verified; currentResidents не capacity |
| Свободные места | RD.current_room_residents | capacity-current≥N, оба known, repo:463–470 | только подтверждённые capacity/residents с датой; отдельный от maximum criterion | unknown residents не становится0; capacity3/resident2 не даёт2 свободных |
| Пары | RD.couples_allowed, accepted_tenant_types | equality / list OR, repo:483–490 | evidence couple permission отдельно от capacity; importer не хранит полный couple provenance | no couples при capacity3 исключает пару, но не доказывает запрет друзей |
| Друзья/группы | accepted_tenant_types; отдельного group fact нет | enum man/woman/couple/family, DTO:576–579 | typed party composition и explicit/conditional group policy | «пара» не равно двум друзьям; unknown не permit |
| Дети | L.children_allowed, defaults/primary | scalar equality, repo:439–446 | evidence + возраст/число/conditions; legacy false unverified | no children vs family; «по согласованию» conditional |
| Животные | L.pets_allowed | scalar equality, repo:439–446 | species/size/count/conditions per-source; новый indexed projection | small dog allowed подходит small dog; cats only запрещает dog; no policy unknown |
| Вид питомца | отдельного scalar нет | не фильтруется отдельно | dog/cat/other + evidence, species exclusivity | no cats не значит all dogs allowed |
| Размер/число | отдельных scalar нет | bool теряет qualifiers | typed qualifiers; неизвестный вес пользователя не удовлетворяет≤5kg | small dog не означает large dog; conditional хранится |
| Курение | L.smoking_allowed | scalar equality | indoor/outdoor/balcony scopes; user «не курю» не landlord ban | только terrace не all smoking; explicit indoor ban отдельно |
| Мебель | L.furnished, исторический default true | equality, repo:413–414 | evidence true/false/unknown, не доверять default | «sin amueblar» не furnished |
| Депозит | L.deposit_amount/text, default0 | 0/≤price/>price, repo:417–422 | сумма+currency/period/evidence; unknown !=0 | absent deposit не «без залога»; deposit1month при monthly price |
| Счета | L.bills_included/text, default false | equality, repo:415–416 | included/excluded/partial с составом и evidence | agua included не all bills included |
| Балкон | L.amenities JSONB | contains, alias Balcón/Balcón disponible, repo:495–502 | canonical balcony + evidence; qualifier smoking не всегда собственный балкон | balcony != terrace; hard vs soft preserved |
| Терраса | L.amenities JSONB | точная строка contains | отдельный terrace token и контекст | общая терраса != private при strict private |
| Прочие удобства | amenities/bathroom/kitchen/RD | AND JSON containment; booleans/equality | allowlist vocabulary, scope/unit provenance | «sin wifi» не wifi; owner/shared/private не теряются |
| Min stay | minimum_stay_months/minimum_nights | known≤max threshold, repo:399–402/435–436 | единицы и rentalMode; unknown остаётся unknown | 3months не подходит1month; nights отдельно |
| Даты и vacancy | available_from/until, source checks | NULL совместим с запрошенной датой, repo:394–398/437–438 | conservative confirmed dates + source freshness; availability не из published | no date не verified available; removed source не проходит |
| Иные условия | tenant_requirement/restrictions/empadronamiento/RD | equality/contains и enum | только подтверждённые разрешённые criteria, unsupported→явное состояние | «только студенты», регистрация и household не домысливаются |

Не менять legacy `roomCapacity` на >= глобально. Для AI передавать только безопасный subset старых filters, добавлять strict predicates к **тому же filtered SQL**, затем count/order/seek/limit. Не фильтровать 20 полученных карточек Python/React: total и страницы будут ложными. Не подавать AI extra JSON в старый DTO: неизвестные поля по умолчанию могут быть проигнорированы. [C03/C04/C10]

### TOP и pagination

Текущий pipeline уже filters→commercial ordering→pagination. Promotion valid по starts/ends и paid+fulfilled+financial_normal либо baseline; одинаков для native/external. **Жёстко несовместимый sponsored listing может быть исключён по тому же принципу, что сейчас цена/location исключают TOP.** Код не даёт TOP bypass всех filters. Юридическая формулировка оплаченной гарантии отдельно не исследована; это вывод о кодовом контракте, не изменение договора. [C03/C04]

Коммерческие keys `(active_TOP DESC, boosted_at DESC)` сохранить перед пользовательской сортировкой. На первом этапе не добавлять soft score, меняющий текущую сортировку; reason codes уже полезны. Если позже нужен relevance, явно согласовать его положение после всех обещанных keys и добавить его в cursor components. Нельзя sort только страницу на клиенте. [C04, INFERRED]

Card cursor — base64 JSON, query fingerprint и sort tuple; он **не подписан и не является snapshot**. Валидатор проверяет fingerprint, типы/finite numbers/UUID. Каждый page снова проверяет visibility. AI cursor должен bind normalized intent hash/version, facts/resolver version, sort и subject при приватных result/session; opaque server token либо MAC. При изменении query/facts/promotion live данные могут сдвигаться: для стабильности snapshot token/expiry или явный restart при version mismatch. Один `CatalogState` не гарантирует, что clock-driven TOP expiry пойман; тестировать истечение promotion и boost между страницами. Это будущий контракт, не обещание нынешней snapshot consistency. [C04/C08/C12, INFERRED]

Конфликт pets двух source records одной dwelling: unknown не голосует; fresh explicit owner assertion с доказанным origin может иметь согласованный приоритет, но owner default не override. Равноправные allow/deny → conflict, отдельно по species/size/smoking scope; «последний primary победил» неприемлемо. Retired/stale evidence хранится как история. Identity conflict/сомнительный dedup — не объединять автоматически AI permissions. [C05/C07, INFERRED]

## 7. F — квоты, транзакции и сессии

Existing limiter — Redis INCR/EXPIRE с process-memory fallback; это технический fixed-window limiter, не durable business accounting. Для AI он не может быть источником 3/200 success-only. [C12]

**Предлагаемый контракт реализации AI-07/08:**

1. `ai_usage_days(subject, madrid_date, limit_snapshot, committed, reserved)`, unique(subject,date), nonnegative checks; `ai_search_requests(subject,idempotency_key,request_hash,day,status,lease_token,lease_until,result_ref,session_version,expires_at)`, unique(subject,key). Дневная row и operation меняются в одной короткой PG transaction.
2. Identity: authenticated user из существующей persisted auth; visitor — random signed HttpOnly Secure SameSite cookie. Не принимать user ID из body. Сервер проверяет Origin/fetch metadata для cookie endpoints; CORS не заменяет CSRF. IP — дополнительный anti-abuse, не business identity. Удаление cookies не решается обещанием «3 на человека».
3. Validate auth/size/type/feature/session version → lookup idempotency → lock/create day → reserve при committed+reserved<limit → commit. **Reservation до любого платного ASR**, но это ещё не debit. Provider I/O без row lock и без удержания session connection. Same key+hash replay; другой hash→409; in progress→bounded status response без второго вызова.
4. ASR→intent→Pydantic→SQL→bounded result serialization. Успех, включая валидный zero-match, одной transaction сохраняет result/session CAS и переводит reserved−1/committed+1. Только после commit отдаётся success. Follow-up — новое сообщение; ASR+intent — один debit. Успешное уточнение при неоднозначности: решение о debit явно закрепить в AI-01, владелец отдельно это не определил.
5. Failure/cancel до commit → atomic release по status+lease token, один раз. Expiry/reconciler с fencing не позволяет позднему worker commit. Lease охватывает максимальный execution deadline и cleanup grace; продление контролируемое. Crash после provider response до PG commit может стоить повторного provider call; exactly-once provider billing без его idempotency недоказуем.
6. Потерян ответ после success commit → retry/status возвращает сохранённую operation без debit/LLM. При replay проверять текущую auth/visibility/freshness карточек; удалённое/hidden не возвращать только ради byte-identical replay. Хранить результат или ID/query reference кратковременно, свежие cards разрешать по прежним visibility rules; изменение выдачи пометить.
7. Cancellation после commit не возвращает debit автоматически. Race release/finalize разрешает один CAS. Статус запроса доступен только его subject. Неизменяемый operation день фиксируется при reserve; retry после midnight относится к старому дню. Session patch `set/unset/clarify`, expected version; omitted сохраняется, foreign session запрещена.
8. `Europe/Madrid` local calendar date и следующая local midnight→UTC; не `now+86400`. 2026-03-29 —23h, 2026-10-25 —25h. UTC timestamps и актуальная tzdata обязательны. Идемпотентные операции живут дольше сброса day; UI показывает reset timezone.
9. Guest→login: **предлагается**, новые requests идут в account 200/day; уже завершённые guest requests не списываются повторно с account. In-flight guest завершается под исходным subject; затем одноразовая авторизованная передача только normalized conversation state с CAS. Guest idempotency не переносить слепо в account namespace. Использованные guest technical attempt tokens не обнулять при login/logout. Правило не увеличивает утверждённые daily limits и требует ADR.
10. DB unavailable→AI503 до paid call. Redis technical protection unavailable→AI fail closed либо заранее утверждённый durable PG technical limiter; никаких per-process unlimited retries. Ordinary search доступен. [C12/C10/C04, INFERRED; реализации пока нет]

**Защита от бесплатного ASR:** reservation сама по себе недостаточна, потому что failure/cancel освобождает business slot. До ASR тратить отдельный **не возвращаемый technical attempt token** и audio-second budget; per visitor/account/network, one in-flight/session, global bounded concurrency, token/output limits, bounded provider attempts, cooldown/Retry-After, circuit breaker. Эти budgets учитывают cancel/invalid/failed attempts и сохраняются вне business refund. Для distributed reliability хранить critical attempt gate в PG или отказать при Redis outage. Предварительно один ASR attempt + максимум один fallback только в оставшемся deadline. Численные minute/audio-second caps выбрать по staging и аккаунту, не менять 3/200 и не вводить monthly financial cutoff. [C12/V01–V06, INFERRED]

## 8. G — SavedSearch и уведомления

JSONB SavedSearch сохраняет filters, owner endpoints уже authenticated и update/delete scope=user. Но `_saved_search_payload` вручную выбирает legacy keys: AI species/scope/evidence/freshness будут проигнорированы. `notify_saved_search_matches` вызывается при imported/restored published, а не при любом updated/enrichment completion. Existing key `saved-search:{search}:{listing}` предотвращает повтор базового alert, но не различает revision preferences. [C05/C10]

Рекомендуемый контракт AI-10, **не новая notification система**:

- `filters.aiSearch={schemaVersion,criteria,hard,soft,unknownPolicy,freshnessPolicyVersion,preferenceRevision}`; валидация и отдельный versioned dispatcher legacy/AI. Unknown schema fail closed с диагностикой, не fallback на урезанный legacy matcher.
- Interactive и background используют один deterministic compatibility predicate/resolver. Ни LLM на каждую подписку, ни повторного ASR. Coarse region/mode/price preselection, durable bounded re-match jobs после publication, first valid enrichment, meaningful source/fact status change и preference update.
- До enrichment — pending compatibility, не отправлять ложное «подходит с собакой». После enrichment — ещё раз visibility/freshness/ownership/alerts_enabled. Stale/removed evidence инвалидирует pending matches. Уже доставленное уведомление нельзя «отправить назад»; по ссылке всегда текущая карточка.
- Dedup по recipient+savedSearch+preferenceRevision+canonical identity+event kind; **не по extractor run/hash**. Re-enrichment/неизменный reimport не создают новый new-match alert. При dedup canonical merge нужна сохранённая identity mapping, иначе новый UUID даст duplicate. Значимое изменение prefs создаёт revision; предложение уведомлять один раз для новой revision закрепить отдельно. Миграция event key additive, без массового переотправления истории.
- Notification insert и existing mail outbox — одна PG unit; resend/SMTP lease reuse. Проверять eligible recipients при dispatch; не рассылать удалённым/заблокированным, не раскрывать чужой search/session.
- **Предлагаемое решение: фоновые matching/notifications не расходуют interactive AI quota**, в том числе при used=200. Это рекомендация владельца в задании, ещё не утверждённое бизнес-правило. Создание/редактирование поиска обычной формой и pagination не AI message; новое сообщение AI для изменения preferences расходует quota при успехе. [C10/C05, INFERRED]

## 9. H — провайдеры и outbound privacy

Официальные страницы проверены 2026-10-25 без inference. Все provider-specific claims — **DOCUMENTED_ONLY**, SHA=null (внешние документы), среда public vendor documentation; высокая уверенность в прочитанном контракте, account entitlement/quality/latency неизвестны. Подробный register V01–V08 ниже. Не заменять названия моделей похожими устаревшими aliases.

| Провайдер | Документированный контракт | Неподтверждённое / действие |
|---|---|---|
| Groq `whisper-large-v3` | multilingual file transcription; flac/mp3/mp4/mpeg/mpga/m4a/ogg/wav/webm; json/verbose_json/text; $0.111/audio-hour, min billed10s; direct attachment≤25MB, higher tier отдельно; prompt224 tokens | конкретный RU/ES/EN code-switch, max duration/SLO и account RPM/audio limits не измерены; безопасный локальный cap60s/8MiB — proposal, ниже attachment ceiling [V01/V02] |
| OpenAI `gpt-transcribe` | completed-file transcription; $0.0045/min; multilingual/context/keyword hints; guide25MB, общий пересекающийся набор mp3/mp4/mpeg/mpga/m4a/wav/webm | response/MIME/limits проверить именно выбранной моделью; не подменять `gpt-4o-transcribe`; fallback account/deadline/качество не проверены [V03/V04] |
| DeepSeek `deepseek-flash` | текущая documented версия DeepSeek-V4.1-Flash-1017; JSON object mode, не доказанная JSON Schema гарантия; thinking по умолчанию включён, для intent явно disabled; input cache miss $0.15/$0.30, hit $0.003/$0.006, output $0.60/$1.20 за1M off/peak; documented concurrency2500/account | Pydantic strict + evidence обязательны; empty/truncated JSON ошибочен. Настроить малый output/context cap, recording model/prompt version; quality и latency ещё неизвестны [V05/V06] |

Все три — обоснованные **кандидаты**, не проверенная production интеграция. Mixed language, топонимы/цены/отрицания требуют gold eval; ASR hints не гарантируют правильность. Audio MIME проверить capability detection и container decoder; filename/extension не доказательство. Точные device codecs протестировать на iOS Safari/Android Chrome/desktop. [V01/V03/V08, INFERRED]

Ошибки: malformed/auth/unsupported media/413 — не повторять вслепую; 429 учитывать Retry-After; timeout/5xx — только bounded remaining-deadline retry/fallback. DeepSeek дополнительно documented402 balance/422 invalid parameters; долгий server keep-alive не означает начало inference, application wall deadline обязателен. Billing provider failure и business debit — разные счётчики. [V02/V06, INFERRED]

Groq: inference обычно без сохранения content, исключения reliability/abuse до30days; ZDR configurable, retained data US. OpenAI `/audio/transcriptions`: таблица no training/no abuse retention/no application state, ZDR eligible; data residency требует условий аккаунта. DeepSeek опубликованная privacy policy описывает China и не задаёт точный API retention для downstream user content. Это **не** договорное подтверждение no-training/ZDR для этого приложения. Для всех нужны API-specific terms/DPA, фактические account controls, региона/transfer review; не делать правового заключения по consumer policy. [V02/V04/V07]

### Минимальная граница отправки в DeepSeek

`normalized_snapshot(asdict(item))` включает nested raw; generic raw включает HTML/embeddedJson, контакты, потенциально exact address. В canonical есть external phone/email/whatsapp, street/postcode/exact_location; private/moderation tables отдельно. Полные raw/normalized/ListingResponse передавать нельзя. F cleaner удаляет ряд контактов/links/markup, но не полноценный PII detector и не address classifier. [C05/C07/C11]

Разрешённый будущий envelope: `{schemaVersion, publicTitleClean, publicDescriptionClean, propertyCategory, rentalMode, coarseMunicipalityCode?, providerFacts:[{allowlistedField,typedValue,cleanEvidence}]}`. Оpaque request correlation допустим без stable internal/user/source-record UUID; локальная mapping хранится сервером. Только подтверждённо public selected descriptions, без точного адреса, имён/телефонов/email, cookies/tokens, private notes, raw HTML, media, moderation comments. Неизвестный field reject. Sanitize до hash/evidence extraction; offsets относятся к очищенному тексту. Exact units/условия сохраняются. [C07, INFERRED]

Privacy gate должен отдельно проверить названия/адреса в свободном тексте, обфускацию контактов, вложенные payloads, quoted instructions/prompt injection и возможную потерю отрицаний при очистке. Safe fail → insufficient_source_data, не отправка «на удачу». Intent также минимизирует personal narrative до необходимых rental constraints; audio transient/private, cleanup всегда, no raw transcript в logs/traces. Никаких paid tests в этом аудите. [C07/V02/V04/V07, INFERRED]

## 10. I — реальные development/release gates

| Finding | Классификация | Точное решение |
|---|---|---|
| #373 ещё не в M | Не блокирует contracts/quota; блокирует зависимую parser/enrichment integration | отдельный reviewed перенос на current main, 16-file scope не заменяет #372; регрессии import/gallery/payments [R02/C07] |
| Planning расходится с M | Не блокер offline; integration gate | не merge whole stale branch вместо main, проверить patch с payment baseline [R01/R02] |
| #372 payments | Уже разрешён факт включения в M | AI не меняет payment/TOP rules; backend/frontend payment regressions до rollout [R01/C04] |
| Main fullstack address422 | Rollout regression gate; не блокер DTO | run40138694278 failed; H full-audit40228259640 даёт23passed/7skipped. Код H/M одинаков, значит нельзя объявить фикс без воспроизводимости/environment diagnosis [R05] |
| H mobile municipality | Новый проверенный CI риск location UX | run40228259650 mock-e2e(4):1failed/155passed, municipality-search:49, ожидался Adeje, пустая строка. Диагностировать отдельно, не изменять код в этом аудите [R05] |
| Branch protection | Не блокер разработки; governance before rollout | branch endpoint protected=false, rulesets=[], protection detail403. Проверить с admin scope; не выдавать403 за отсутствие правил [R06] |
| Manual deployment | Существующий workflow подтверждён кодом | workflow_dispatch checkbox/exact main/merged PR checks/production environment. Текущие required reviewers/self-approval не прочитаны; исторические настройки не current proof [C13/R04] |
| Alembic | Схему проектировать можно | AST66 migrations: один code head0066_complimentary_ads; live alembic_version неизвестен. Additive revision после актуального head, disposable old/new compatibility; не выполнять `alembic current` через write DSN [C14/D01] |
| Feature flags | NEEDS_IMPLEMENTATION | отдельно AI text, voice, saved matching, enrichment, fallback; default off, server gate авторитетен. Kill switch не ломает manual search; флаг не защита квоты сам по себе [C01/R03, INFERRED] |
| Read-only DB | Mandatory для real measurements/backfill/launch; не для mocks | DBA plan в отдельном отчёте. Переданный server password не устанавливает разрешённую read-only DB identity [D01] |
| Source observability | Gate truthful freshness; bounded diagnostics improvement | stored runs + snapshot aggregates и fixed safe log labels; не включать broad arbitrary extra [C05/C06] |

Ни один исторический UI/CI failure сам по себе не доказывает поломку production поиска. Необходимо закрыть релевантные regressions и документировать остаточные failures на финальном code SHA, не менять security validation ради зелёного теста. Pages failure — отдельная preview проблема, не production AI blocker. [R05/C13, INFERRED]

## 11. Прямые ответы на 20 вопросов

| № | Ответ |
|---:|---|
| 1 | **Да, достаточно для начала разработки** ADR/DTO/quota/session/mock adapters/schema. Не для активации полного AI. |
| 2 | Нет DB inventory, per-source freshness/coverage/provenance/conflicts, live plans/pool headroom, provider settings/DPA, real accuracy/latency и browser E2E. Конкретный доступ/план — REAL_CATALOG_EVIDENCE. |
| 3 | База обслуживает обычный поиск и подходит архитектурно. Надёжность рекомендаций по всем условиям **не доказана**; strict subset возможен только на подтверждённых facts. |
| 4 | Trust coverage неизвестна для occupancy/couples/groups/children/pets/species/size/smoking scopes/furnishing/deposit/bills/amenities/stay/dates. Default не evidence; поля и gaps в §6. |
| 5 | В sampled visible cards есть Pisos/Fotocasa. Какие sources сейчас стабильно доставляют fresh usable data — **не установлено** без runs+source snapshot. |
| 6 | **Да, с дополнениями:** post-commit durable marker/reconciler, semantic hash, isolated queue/fenced worker и source resolver. Сейчас этого нет; import не должен ждать LLM. |
| 7 | **Да, Groq Large V3 разумный кандидат** для completed multilingual audio; качество/скорость Ttest и account limits ещё проверить. |
| 8 | **Да, DeepSeek Flash подходит как кандидат** для typed extraction с JSON/Pydantic/evidence; не выбирать ему SQL или final truth. Privacy/quality gates открыты. |
| 9 | **FEASIBLE_WITH_SPECIFIC_CHANGES**; 10s статистически правдоподобен, численно не доказан. |
| 10 | Scoped audio route/caps/mic headers, one request, bounded async clients/deadlines, quota before ASR, precomputed facts/indexes, release DB connections, reuse progressive cards, tracing/capacity isolation. |
| 11 | Сейчас: кодовые limits/filters/cursors, три safe HTTP samples/bytes, CI. После прототипа: ASR+intent distributions, correctness, mobile upload/paint E2E, concurrent DB/provider behaviour. |
| 12 | **Да:** strict eligibility до unchanged TOP+boost; несовместимый TOP исключается по принципу существующих filters. Soft rank не переупорядочивает коммерческие keys. |
| 13 | **Да:** reuse repository/card DTO/renderers; AI predicates перед paging, отдельный versioned envelope/query token. Нельзя свести все AI criteria к legacy JSON. |
| 14 | PG ledger short reserve/finalize/release, subject+idempotency+CAS/fencing, Madrid calendar, Redis technical budgets; failure release, success including0=1debit, no double ASR debit. |
| 15 | **Да:** versioned SavedSearch JSONB, shared matcher, delayed enrichment rematch, existing Notification+outbox/dedup. Background no quota — proposed decision. |
| 16 | Data provenance/freshness, privacy, quota/session races, upload/codec abuse, stale enrichment, TOP/cursor regression, source telemetry, real capacity/SLO и CI/manual approval. |
| 17 | После AI-01 параллельно: AI-07→08; AI-03→04 с mocks; AI-02 DBA evidence→05; provider contract fakes; UI recording/text shell с mocks. Общие DTO сначала фиксируются. |
| 18 | **PR-AI-01** с ADR и JSON scenarios, docs-only. Первый кодовый независимый PR после него — **AI-07 ledger**, не paid Groq demo. |
| 19 | Новый общий аудит не нужен. Нужны только адресные closure checks: DBA aggregates, sanitized gold eval, final CI/release checks, staging browser performance после интеграции. |
| 20 | **READY_FOR_DEVELOPMENT**; готовить staging с mocks можно; live staging NEEDS_IMPLEMENTATION/MEASUREMENT/privacy; **production rollout BLOCKED** перечисленными gates. |

Ответы — INFERRED на основании реестра ниже; неизвестные показатели сохранены null в [JSON](final-gates-summary.json). Не выдан ни процент «готовности», ни обещание общей catalog accuracy.

## 12. Реестр доказательств

Правило ссылок: M/H/F/P раскрыты в §1 точными40-символьными SHA. Ниже path:line относится к указанному SHA, а не плавающей ветке. Для внешнего провайдера SHA=null. Дата всех проверок **2026-10-25**; historical runtime отдельно помечен. Уверенность высокая в чтении конкретного кода/API, ограниченная для production-экстраполяции. Новые proposals помечены INFERRED и не являются evidence реализации.

| ID | Тип / среда / SHA | Источник, строки и метод | Граница |
|---|---|---|---|
| R01 | VERIFIED_CODE_MAIN / GitHub / M,P | [main API](https://api.github.com/repos/antony502189-max/Ttest/branches/main), PR372 API; fresh git refs, rev-list main...planning | snapshot refs, не runtime |
| R02 | VERIFIED_BRANCH_ONLY / GitHub / F | [PR373](https://github.com/antony502189-max/Ttest/pull/373), точные blobs/diff M→F | open, не main |
| R03 | VERIFIED_BRANCH_ONLY / GitHub / H | [PR374](https://github.com/antony502189-max/Ttest/pull/374); docs/ai-search-developer/README.md:1, 01–09, CODEX_START_HERE:1; diff executable paths H/M | документы, не реализованные возможности |
| R04 | DOCUMENTED_ONLY / historical audit / H, о M | [PRODUCTION_REALITY_AUDIT:24](https://github.com/antony502189-max/Ttest/blob/85fa9ad7ebff15634b34bd341882d302398b6dfc/docs/ai-search-developer/audits/2026-10-25/PRODUCTION_REALITY_AUDIT.md#L24); E01–E09/S01–S15; два companion reports | использованы как прошлые выводы; новый SSH не выполнялся |
| R05 | VERIFIED_CI / GitHub Actions / M,H,F | M [40138694278/job121005614722](https://github.com/antony502189-max/Ttest/actions/runs/40138694278); H [40228259640](https://github.com/antony502189-max/Ttest/actions/runs/40228259640), [40228259650](https://github.com/antony502189-max/Ttest/actions/runs/40228259650); F [40136990342](https://github.com/antony502189-max/Ttest/actions/runs/40136990342). GET runs/jobs/existing logs | no reruns; F904passed/7skipped+88integration не data coverage |
| R06 | VERIFIED_CI / GitHub settings / M ref | [branch](https://api.github.com/repos/antony502189-max/Ttest/branches/main), [rulesets](https://api.github.com/repos/antony502189-max/Ttest/rulesets): protected=false, []; protection detail403 | ограничение integration scope; env policy current UNKNOWN |
| P01 | VERIFIED_PRODUCTION / public HTTPS / build M | GET/build-info.json и GET/ в20:19:17–20:19:19UTC; commit и selected headers | frontend build identity; no backend binary attestation |
| P02 | VERIFIED_PRODUCTION / public search behind build M | POST/api/v1/listings/search/cards: long20/holiday20,20:19UTC; urllib full body timing/byte count, response immediately reduced to aggregates | n=1 на query; отдельные snapshots; no p95/SQL timing |
| P03 | VERIFIED_PRODUCTION / public search behind build M | тот же route, long/query=Adeje/maxPrice700/limit20,20:19UTC | page sample, не pet/capacity-compatible AI results |
| D01 | BLOCKED / production DB / runtime SHA null | не предоставлен явно авторизованный RO role/replica; нет DB connector/session с доказанными grants. Server password не использован | total/coverage/freshness/plans/live schema неизвестны |
| C01 | VERIFIED_CODE_MAIN / source / M | [nginx.conf:60](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/deploy/nginx.conf#L60),69–79,172–180,184–249,274–289 | source config, не новый effective settings read |
| C02 | VERIFIED_CODE_MAIN / source / M | [main.py:118](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/main.py#L118),136–143,224–318; db/session.py:8–28; core/config.py:25–31; docker-compose.production.yml:6–12; backend/Dockerfile:31 | defaults/runtime различать |
| C03 | VERIFIED_CODE_MAIN / source / M | [repositories/listings.py:272](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/repositories/listings.py#L272),338–518; schemas/listings.py:454–607; services/rental_price_limit.py:79–88 | filter semantics, не provenance/count |
| C04 | VERIFIED_CODE_MAIN / source / M | [repositories/listings.py:89](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/repositories/listings.py#L89),110–137,551–615,634–721; api/v1/listings.py:217–239 | TOP/seek/count/DTO; no snapshot guarantee |
| C05 | VERIFIED_CODE_MAIN / source / M | [external_import.py:594](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/external_import.py#L594),606–668,671–702,755–774,925–984,1387–1426,1504–1572 | stored snapshots/lifecycle/event counters |
| C06 | VERIFIED_CODE_MAIN / source / M | [workers/external_listings.py:217](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/workers/external_listings.py#L217),243–365; external_sources.py:2376–2394; habitaclia_source.py:527–544; core/observability.py:27–64 | config/health/log distinction |
| C07 | VERIFIED_BRANCH_ONLY / source / F | [listing_evidence.py:16](https://github.com/antony502189-max/Ttest/blob/fcae378d9dbbc8447f18df150327180f6f2c8231/backend/app/services/listing_evidence.py#L16),27–56,65–100; ai_listing_input.py:45–193; commands/audit_ai_listing_data.py:228–287; external_sources.py:675–697,808–827; docs/ai-voice-search/PARSER_DATA_AUDIT.md:16–140 | grammar partial, cleaner not general privacy gate |
| C08 | VERIFIED_CODE_MAIN / source / M | [SearchPage.tsx:205](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/pages/SearchPage.tsx#L205),217–248,250–297,773/820; src/api/listings.ts:256–283,348–386 | no browser paint measurement |
| C09 | VERIFIED_CODE_MAIN / source / M | [mobile-search-results-v2.tsx:245](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/components/mobile-search-results-v2.tsx#L245),248–334 | separate mobile session, observer |
| C10 | VERIFIED_CODE_MAIN / source / M | [notifications.py:46](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/notifications.py#L46),143–221,251–285; api/v1/saved_searches.py:20–53; services/search_state.py:260–314 | existing auth/outbox; AI dispatcher отсутствует |
| C11 | VERIFIED_CODE_MAIN / source / M | [models/__init__.py:126](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/models/__init__.py#L126),138–203,206–287,324–334; models/room_details.py:13–43; models/moderation.py:22–50; external_removal.py:76–96,273–290; external_import.py:1031–1052,1131–1154 | наличие полей не говорит о качестве stored values |
| C12 | VERIFIED_CODE_MAIN / source / M | [rate_limit.py:19](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/rate_limit.py#L19),47–101; main.py:118–163,241–273; api/dependencies.py:17; api/v1/listings.py:185–192 | fixed window; GET catalog-version может писать при отсутствии singleton, не использован как audit probe |
| C13 | VERIFIED_CODE_MAIN / source / M | [manual-production-deploy.yml:1](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/.github/workflows/manual-production-deploy.yml#L1),23–74; docs/production-operations.md | workflow не запускался |
| C14 | VERIFIED_CODE_MAIN / static graph / M | [0066 migration:6](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/alembic/versions/0066_complimentary_advertisements.py#L6); AST revision/down_revision всех66 файлов; 0050_spain_search_indexes.py:15–35; 0029_external_import_run_retention.py:17–32 | один code head; live migrations/index validity неизвестны |
| V01 | DOCUMENTED_ONLY / public provider / null | [Groq speech](https://console.groq.com/docs/speech-to-text), headings Supported Models/Audio File Limitations/Parameters | прочитан официальный контракт; no inference |
| V02 | DOCUMENTED_ONLY / public provider / null | [Groq limits](https://console.groq.com/docs/rate-limits), [errors](https://console.groq.com/docs/errors), [data](https://console.groq.com/docs/your-data) | account plan/settings неизвестны |
| V03 | DOCUMENTED_ONLY / public provider / null | [OpenAI file transcription](https://developers.openai.com/api/docs/guides/speech-to-text), [gpt-transcribe](https://developers.openai.com/api/docs/models/gpt-transcribe) | model-specific integration нужно проверить |
| V04 | DOCUMENTED_ONLY / public provider / null | [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [data controls](https://developers.openai.com/api/docs/guides/your-data), endpoint table | не account settings/DPA |
| V05 | DOCUMENTED_ONLY / public provider / null | [DeepSeek pricing/models](https://api-docs.deepseek.com/quick_start/pricing/), [thinking](https://api-docs.deepseek.com/guides/thinking_mode/) | mutable alias/price; response version записывать |
| V06 | DOCUMENTED_ONLY / public provider / null | [JSON](https://api-docs.deepseek.com/guides/json_mode/), [rate limit](https://api-docs.deepseek.com/quick_start/rate_limit/), [errors](https://api-docs.deepseek.com/quick_start/error_codes/) | JSON не гарантия наших semantic constraints |
| V07 | DOCUMENTED_ONLY / public policy / null | [DeepSeek privacy, Feb10 2026](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html?os=___) | downstream/API-specific terms не установлены |
| V08 | DOCUMENTED_ONLY / browser API / null | [MDN isTypeSupported](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static) | capability может не гарантировать recording; device QA впереди |

Связанные deliverables: [каталог](REAL_CATALOG_EVIDENCE.md), [10 секунд](VOICE_10S_FEASIBILITY.md), [gates/порядок PR](IMPLEMENTATION_GATE_MATRIX.md), [санитизированный JSON](final-gates-summary.json).
