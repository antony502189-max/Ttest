# Фактическое состояние production 112233.es

Дата: **25 октября 2026**. Репозиторий: `antony502189-max/Ttest`. Проверки production: 14:07–14:16 UTC (17:07–17:16 Europe/Minsk). Это аудит и рекомендации; изменений приложения, инфраструктуры и данных не выполнялось.

## 1. Резюме для владельца

| Вопрос | Ответ | Подтверждение |
|---|---|---|
| Какая версия реально стоит в production? | `1292c6807ece59999238bb31c80e09ef7e2c3212` | VERIFIED_PRODUCTION, E01–E03 |
| Совпадает ли production с main? | Да, на момент проверки; совпадают main, current и публичный build-info | E01–E03; пять файлов backend дополнительно сверены по SHA-256 с Git blobs |
| Какие контейнеры работают? | frontend, backend, external-listings-worker, mail-worker, Redis, PostgreSQL, MinIO, Traefik | VERIFIED_PRODUCTION, E02; minio-init завершён с кодом 0 |
| Работают ли парсеры? | Worker healthy; семь эффективных адаптеров. Есть ошибки и 403; успех каждого источника не установлен | E04, E06 |
| Сколько реальных объявлений? | В публичной доступной выдаче **1 163**; long **1 132**, holiday **31**. Число всех строк БД неизвестно | VERIFIED_PRODUCTION, E05 |
| Насколько полны данные объявлений? | Проценты описаний/доказанных правил не измерены. Есть подтверждённые риски defaults, snapshots и описаний | BLOCKED для данных; VERIFIED_CODE_MAIN S03/S05/S06 |
| Какие возможности AI уже есть? | В main нет ASR/LLM/AI quota/session/enrichment. В #373 — offline foundation | E07, S10–S12 |
| Готов ли сервер к внешним AI API? | Ресурсный запас и TLS-доступ есть; полноценная готовность не доказана | E02/E04; ключи трёх провайдеров в окружении backend не настроены |
| Готов ли frontend к голосовому вводу? | Нет; записи нет, микрофон запрещён Permissions-Policy, общий body limit 256 KiB | E03, S01/S07/S08 |
| Можно ли переиспользовать существующий поиск? | Да, фильтры, visibility, DTO карточек, keyset pagination и TOP. Для AI нужны дополнительные semantics | S02–S04 |
| Готовы ли Redis и авторизация к лимитам 3/200? | Частично. Identity и Redis есть; дневных успешных запросов, reserve/finalize/release нет | S01/S09, E04 |
| Что мешает начать разработку? | Начать offline ADR/контракты можно сейчас. Для запуска нужны provenance, quota ledger, privacy, voice transport и реальные данные | INFERRED на основе E01–E09/S01–S15 |

**Решение:** существующий FastAPI пригоден как основа. Начинать с небольшого PR контрактов и семантики доказанных фактов, одновременно закрывая доступ к безопасным агрегатам. Запуск пользовательского AI сейчас преждевременен. Покупать VPS для локальных моделей не требуется: inference предполагается внешним.

## 2. Методика и границы доказательств

Использованы все восемь меток задания: `VERIFIED_PRODUCTION`, `VERIFIED_CODE_MAIN`, `VERIFIED_BRANCH_ONLY`, `VERIFIED_CI`, `DOCUMENTED_ONLY`, `INFERRED`, `UNKNOWN`, `BLOCKED`. Метки применяются к конкретному наблюдению, а не автоматически ко всему подсистемному разделу.

Точные SHA: main/production **M=`1292c6807ece59999238bb31c80e09ef7e2c3212`**; planning **P=`1ace67b5ae67ab267fdcc37ee499b87bd433fb71`**; parser **F=`fcae378d9dbbc8447f18df150327180f6f2c8231`**; base PR #373 **B=`f203807d4507f68b34cd4407e326b3bc671a3552`**. Ссылки S ниже фиксированы на SHA. Дата всех проверок — 2026-10-25, если прямо не указана дата исторического CI.

SSH: `root@169.58.147.65`, существующий pinned known_hosts, без отключения проверки ключа. Предоставленный пароль использован через скрытый ввод процесса, не сохранён. Полный env, DSN, private keys, raw logs, HTML и тексты объявлений не выгружались. Вывод логов отфильтрован на сервере до агрегатов. Поисковые запросы проверены по коду как read-only; `items` с описаниями отбрасывались на сервере до возврата аудиторскому клиенту.

**DATABASE_READ_ONLY_ACCESS: NOT AVAILABLE / NOT ESTABLISHED.** Явно разрешённая replica/выделенная read-only роль не предоставлена; проверенные имена `AI_AUDIT_DATABASE_URL`, `READONLY_DATABASE_URL`, `DATABASE_READONLY_URL` отсутствуют в backend env. Это не доказывает отсутствие такой роли вообще. Root SSH не использован как обход требования отдельной DB-роли. Прямые SQL-инвентаризации, audit CLI на production и `alembic current` через application DSN не запускались. Health endpoint выполняет свою штатную проверку зависимостей; это не DB inventory.

Локальная исходная копия E:/task была на старом SHA `6c51324f…` и содержала изменённые изображения. Для анализа созданы отдельные checkout main/planning/parser. Ошибка fetch из-за повреждённой локальной checkpoint-ref не исправлялась удалением refs; точные объекты были доступны, их SHA сверены с GitHub. Незавершённые пользовательские изменения сохранены.

## 3. Ветки и фактический GitHub

| Объект | SHA / состояние | Что действительно есть | Метка |
|---|---|---|---|
| main | M | действующая платформа, реклама/платежи #372, поиск/импорт/уведомления | VERIFIED_CODE_MAIN |
| production | M | current + build-info + success metadata; 5 backend-файлов совпадают с Git blobs M | VERIFIED_PRODUCTION |
| planning | P | три архитектурных документа, решения 3/200 и Madrid; история основана на `083c928b…` | VERIFIED_BRANCH_ONLY |
| #373 | open, не draft, mergeable=true по ответу API; base planning/B; head F | evidence grammar, fingerprint fix, audit CLI, input builder, fixtures/tests | VERIFIED_BRANCH_ONLY |
| release/* / releases/* | удалённые refs по этим двум шаблонам не найдены | факт выкладки F не обнаружен; произвольно названные ветки целиком не исследованы | UNKNOWN для иных release-веток |

`main` содержит новые изменения #372 после общего предка с planning, включая payment integrity. Обычный diff main→planning показывает и отсутствие этих изменений в planning, и добавление AI-документов. **Нельзя переносить planning как замену текущему main**: будущую интеграцию надо отдельно согласовать с новыми платежными контрактами. PR #373 не содержит новых AI-миграций, провайдеров, публичных voice API или worker обогащения. Его изменения не присутствуют в проверенном main, и active production SHA не F. [E01/E07, S10–S12]

Из 13 открытых PR только #373 относится к AI parser foundation. Релевантные соседние: #299–302 performance; #233 карта; #220 атомарность сохранения; #206 auth; #161 monitoring/DR. Открытость старого PR сама по себе не доказывает отсутствие аналогичного изменения в main: например, gzip уже виден в main. Автоматических merge не было.

Архитектурные документы P местами всё ещё говорят «после ответов заказчика», упоминают cost cap и старый следующий PR audit-tool. Решения владельца в начале customer review и данное задание выше этих фрагментов: batch ASR, text-only ответы, 3/200, Madrid midnight, существующий TOP, никакого месячного cutoff. Старые вопросы не являются новым блокером.

## 4. Production и релизы

Хост `vmi3640228`; `/srv/112233.es/current` указывает на `/srv/112233.es/releases/M`. Публичный `/build-info.json` возвращает `{"commit":"M"}`. Релизная запись M имеет `status=success`, `old_sha=d890f2bb0ff82f22c1d8fda366e1c4c2db037e22`, timestamp `2026-10-25T10:09:47Z`. Timestamp metadata не следует путать с временем завершения всех контейнеров. Последний успешный manual deployment: [run 40183294613](https://github.com/antony502189-max/Ttest/actions/runs/40183294613), создан 10:04:59 UTC 25 октября. [E02/E03/E08]

Последний failure в просмотренных десяти manual runs: [39810963175](https://github.com/antony502189-max/Ttest/actions/runs/39810963175), SHA `2ab3d5dbbed1c21b2e09672538f75b98e357284d`, 22 октября 16:05:40 UTC. Следующий запуск был cancelled, затем есть успешные релизы. Причина исторического deploy failure не установлена; он не является доказательством текущей неисправности.

В момент snapshot `lslocks` не показал lock в /srv/112233.es; проверка имён процессов не нашла release/rollback/backup operation. Это ограниченное наблюдение, не гарантия отсутствия будущего или иначе названного процесса. Ничего не запускалось и lock-файлы не изменялись.

### Контейнеры

| Контейнер ttest-production-* | State / health | RestartCount | StartedAt UTC |
|---|---|---:|---|
| frontend-1 | running / healthy | 0 | 2026-10-25 10:15:27 |
| backend-1 | running / healthy | 0 | 2026-10-25 10:15:15 |
| external-listings-worker-1 | running / healthy | 0 | 2026-10-25 10:15:15 |
| mail-worker-1 | running / healthy | 0 | 2026-10-25 10:15:14 |
| redis-1 | running / healthy | 0 | 2026-10-18 13:20:17 |
| minio-1 | running / healthy | 0 | 2026-10-18 13:20:17 |
| postgres-1 | running / healthy | 0 | 2026-10-18 13:20:17 |
| minio-init-1 | exited / exit 0 | N/A | одноразовая инициализация |
| traefik-traefik-1 | running / healthcheck отсутствует | 0 | 2026-10-18 13:20:17 |

Traefik отвечает через публичный HTTPS; отсутствие Docker healthcheck не означает unhealthy. Только Traefik публикует host ports 80/443 (IPv4/IPv6); перечисленные 8000/8080/5432/6379/9000 у приложения — внутренние порты контейнеров. Backend command: один `uvicorn app.main:app --host 0.0.0.0 --port 8000`, без `--workers`. Mail command: `python -m app.commands.outbox_worker`; importer: `python -m app.workers.external_listings --loop`. [VERIFIED_PRODUCTION, E02/E04/E06]

Публичные `/api/health/live` и `/api/health/ready`: HTTP 200 `status=ok`; readiness проверяет PostgreSQL, Redis и storage. `pg_isready`: accepting connections; Redis PING: PONG. `/api/docs` и `/api/openapi.json`: 404. `/metrics` на публичном origin возвращает **HTML SPA**, а не Prometheus: HTTP 200 не подтверждает публичную экспозицию метрик. Внутренний `/metrics` реализован; наличие collector/scrape/alerts отдельно не установлено. [E03, S01/S13]

## 5. Эффективные настройки

Ниже значения прочитаны из `get_settings()` внутри работающего backend-контейнера; это effective settings нового процесса с тем же env, а не извлечение Python heap долгоживущего процесса. Worker-specific overrides отдельно не прочитаны. [VERIFIED_PRODUCTION, E04]

| Настройка | Значение |
|---|---|
| APP_ENV | production |
| FRONTEND_APP_URL / FRONTEND_ORIGINS | https://app.112233.es / только этот origin |
| DB pool / overflow / acquire timeout | 5 / 5 / 30 s на процесс |
| DB statement / lock timeout | 60 000 / 10 000 ms |
| image / video upload bytes | 8 MiB / 100 MiB; это не лимиты будущего аудио |
| EXTERNAL_IMPORT_ENABLED | true |
| EXTERNAL_IMPORT_SOURCES | fotocasa,milanuncios,pisocompartido,pisos,alquilerdocentecanarias,flatio |
| NATIONWIDE_ENABLED | true; отличается от false в Settings default |
| PRESERVE_EXISTING_DATA / REMOVAL_CHECK_ENABLED | true / false |
| interval / concurrency per source / request timeout | 7 200 s / 2 / 25 s |
| scope max pages / details | 2 / 50 |
| Playwright | true |
| min healthy sources / stale threshold | 3 / 300 s |
| mail interval / batch | 10 s / 50 |
| Redis / JWT / SMTP | configured; значения секретов не извлекались |
| Sentry DSN | не настроен в проверенных effective settings |
| GROQ_API_KEY / DEEPSEEK_API_KEY / OPENAI_API_KEY | не заданы в backend env |
| METRICS_ENABLED | true |

Same-origin API `/api/v1` подтверждён публичными ответами и кодом frontend transport. Nginx общий request body **256 KiB**, read/send timeout **30 s**, connect timeout **5 s**; upload locations имеют отдельные 9/105 MiB бюджеты. Новый voice endpoint без отдельного location унаследует 256 KiB. Нельзя просто поднять глобальный предел JSON до размера аудио. CORS allowlist, secure refresh cookies, security headers и очистка proxy IP реализованы. Эффективный Nginx-файл отдельно `nginx -T` не выгружался; соответствующие лимиты — VERIFIED_CODE_MAIN, запрет микрофона дополнительно VERIFIED_PRODUCTION по ответу `/`. [S01/S07/S09]

Redis: `used_memory_human=1.23M`, AOF enabled, last AOF write / RDB save status ok, `maxmemory=0`, policy `noeviction`. Следовательно, у Redis нет явного memory cap; это операционный риск при AI sessions и новой кардинальности ключей, а не признак текущего дефицита. [E04]

## 6. БД и реальный каталог

PostgreSQL executable: **16.4**, image family `postgis/postgis:16-3.4`. Реальная SQL `postgis_full_version()` не выполнялась: extension version **UNKNOWN**. В deploy-info `revision_before` и `revision_after` равны **0066_complimentary_ads (head)**, совпадают с head исходной migration chain M. Это VERIFIED_PRODUCTION относительно **содержимого metadata**, но прямое текущее `alembic_version` не проверено. Diagram docs/architecture всё ещё пишет 0001..0056: документация устарела. [E04/E06, S14]

| Измерение | Результат | Граница |
|---|---:|---|
| public eligible canonical listings | 1 163 | visibility + price policy, не все published и не все строки |
| long | 1 132 | тот же публичный endpoint |
| holiday | 31 | отдельный режим |
| exact roomType=Habitación individual | 96 | легальный фильтр DTO |
| exact roomType=Habitación compartida | 0 | измеренный ноль только публичной выдачи |
| exact roomType=Estudio | 169 | легальный фильтр DTO |
| остальные типы в общей выдаче | не измерены по каждому типу | нельзя назвать остаток «shared rooms» |
| все / draft / hidden / closed / pending / rejected | N/A | нет разрешённого SQL inventory |
| owner/external; с фото/описанием/URL/capacity | N/A | нет соответствующих aggregate endpoints/read-only DB |
| размер БД, таблиц, retention, index validity, connections | N/A | не измерялись |

Ограниченная первая страница 50 карточек содержала 11 individual rooms, 5 studios и **34 `Apartamento de 1 dormitorio`**. Это доказательство наличия квартир в настоящих записях, но **не репрезентативная оценка долей**: порядок newest с TOP первым. В search DTO `ALLOWED_ROOM_TYPES` содержит только individual/shared/studio. Значит, каталог шире разрешённых точных фильтров; AI не должен молча сводить квартиру к студии. Общее число квартир и домов не установлено. [E05, S03/S05]

Региональные public counts при `{}`:

| ID | Автономное сообщество | Count |
|---|---|---:|
| 01 | Andalucía | 306 |
| 02 | Aragón | 24 |
| 03 | Asturias | 48 |
| 04 | Illes Balears | 6 |
| 05 | Canarias | 181 |
| 06 | Cantabria | 32 |
| 07 | Castilla y León | 77 |
| 08 | Castilla-La Mancha | 45 |
| 09 | Cataluña | 39 |
| 10 | Comunitat Valenciana | 56 |
| 11 | Extremadura | 36 |
| 12 | Galicia | 54 |
| 13 | Madrid | 10 |
| 14 | Murcia | 38 |
| 15 | Navarra | 4 |
| 16 | País Vasco | 11 |
| 17 | La Rioja | 0 |

Сумма регионов **967**, общая выдача **1 163**, разница **196**. Counts региона зависят от public `location` и геометрии; разницу нельзя автоматически назвать «196 без координат»: возможны точки вне геометрии, неполная география и изменение каталога между последовательными запросами. Это реальный сигнал для read-only географического аудита. Адресная точность и confirmed-geo % **не измерены**. [E05; S02:521–547]

Код схемы содержит indexes по status, price/search-составляющим в миграциях, Geography, source identity, timestamps и partial removal cursor; uniqueness source_name+external_id и source_url. Факт успешного применения/эффективности каждого индекса, ANALYZE и query plans не подтверждён. Нужны безопасные EXPLAIN на replica; бессмысленно гарантировать производительность по наличию файла миграции. [VERIFIED_CODE_MAIN, S05/S14]

## 7. Импорт, источники и качество

Фактический вызов `configured_sources()` в контейнере дал **Fotocasa, Milanuncios, PisoCompartido, Pisos, AlquilerDocenteCanarias, Flatio, Habitaclia**. Последний добавляется `app/__init__.py` → `install_habitaclia_source()` при APP_ENV=production, независимо от списка env. Idealista и ThinkSpain имеют классы, но отсутствуют в effective source list. [VERIFIED_PRODUCTION E04; VERIFIED_CODE_MAIN S06]

| Источник | Effective adapter | records / active / canonicals / published | desc p50/p95 / policy coverage | успешный импорт / свежесть |
|---|---|---|---|---|
| Fotocasa | да | N/A | N/A | UNKNOWN |
| Milanuncios | да | N/A | N/A | UNKNOWN |
| PisoCompartido | да | N/A | N/A | UNKNOWN |
| Pisos | да | N/A | N/A | UNKNOWN |
| AlquilerDocenteCanarias | да | N/A | N/A | UNKNOWN |
| Flatio | да | N/A | N/A | UNKNOWN |
| Habitaclia | да, canary через install hook | N/A | N/A | UNKNOWN |
| Idealista / ThinkSpain | нет в effective list | исторические строки N/A | N/A | не утверждается |

В bounded выборке последних 2 000 log lines за 6 h importer: 1 810 INFO, 3 WARNING, 5 ERROR; `external_import_finished` 1 (12:21:33 UTC), `external_import_scope_finished` 8 (последний 12:24:54), `external_source_failed` 4, `external_source_http_error` 2, browser blocked 3; HTTP status 403 встречается 7 раз. Число HTTP errors и ERROR events имеет разные знаменатели; их нельзя складывать как количество failed sources. `external_import_finished` логируется **до** проверки healthy-sources и nationwide scopes, поэтому не доказывает полностью успешный цикл. [E06; S06:299–359]

Наблюдаемость ограничена кодом JsonFormatter: он сохраняет timestamp/level/logger/message и только request_id/method/path/status/duration_ms/actor_id. Поля extra `source`, `sources`, `scope`, `counters`, `result`, `run_id` worker сообщений отбрасываются. Поэтому связать эти события с конкретным источником из сохранённых structured logs нельзя. Подробности есть в DB import-run/state, но безопасный доступ к ним не установлен. **Это подтверждённый дефект диагностики**, не основание запускать importer заново. [S13:50–64, E06]

Цепочка main: bounded discovery → public fetch с guarded HTTP/опциональным Playwright → adapter parse → normalize category/rent/location/price → upsert source snapshot → canonical selection/dedup → commit → gallery I/O. Source identity и photo dedup различны: source_name+external_id/URL не заменяются AI content hash. Глобальная photo identity исключает title/address/contact как достаточное основание дубля; same-source repost имеет дополнительные строгие условия. Сеть не должна удерживать открытую DB transaction. [S05/S06]

`normalized_snapshot()` сериализует **весь dataclass вместе с raw_payload**. Generic raw содержит JSON-LD, embedded JSON и до 200 000 HTML characters. Это не полный архив страницы и не безопасный LLM input. AlquilerDocente/Flatio/Habitaclia сокращают raw: неперенесённые structured keys впоследствии могут быть невосстановимы без нового fetch. Selected description в normalizer сохраняется без общего slicing, но исходный parser может выбрать meta summary или обрезать DOM regex. Card API намеренно выдаёт только первые **240** символов description; AI enrichment нельзя строить по card DTO. [S02:689, S05/S06; S12]

Canonical поля меняет выигравший primary snapshot; secondary facts остаются в source snapshots. Выбор completeness не равен надёжности policies. При смене primary новый snapshot может изменить правила/capacity/описание; конфликт-resolver нескольких источников отсутствует. Изменение **только** pets/smoking/capacity в main не входит в fingerprint: snapshot обновляется, ранний unchanged оставляет canonical stale. PR #373 добавляет отсутствующие scalar fields и grammar, сохраняя null/false/0. Первый штатный sync после будущего релиза обновит старые digests, может тронуть catalog version и gallery path. Масштаб не измерен; identity/dedup и TOP этим PR не меняются. [S05:781–814; S06:755–870; S10]

Preserve=true запрещает обычной деактивации менять строки; removal-check=false. В логах 87 `external_source_deactivation_review_required`. Это работа существующего защитного режима, а не разрешение убрать gate. AI freshness должен учитывать, что сохранённое объявление не гарантированно проверено как доступное сейчас. [E04/E06; S06:1031–1052]

Статические адресные улучшения: Fotocasa/PisoCompartido — route-bound full description + nested DOM fixtures; generic Idealista/Milanuncios/Pisos/ThinkSpain — не выдавать meta за полный текст; Flatio/AlquilerDocente/Habitaclia — сохранять малый allowlist structured facts с provenance. **Приоритет между ними пока UNKNOWN**: production coverage не измерена. Habitaclia не восстанавливать координатами page viewport. Не требуется переписывать весь importer. [S12, INFERRED]

### Совместимость данных

ORM defaults `pets/children/smoking/empadronamiento/bills=False`, `furnished=True`, `room_capacity=1`, `room_size=1`, stay/deposit=0 не являются доказательствами. Nullable columns и None из importer не восстанавливают происхождение исторических значений. `room_capacity_v2` хранит 1–10, legacy scalar ограничен 2 при projection; >10 пока только snapshot. Couples поле есть в room_details, но NormalizedListing не несёт отдельного couples mapping. [S05/S06, S10]

Реальное покрытие capacity, adults/children, couples/friends, species/size pets, indoor/outdoor smoking, furnishing, bills, deposit, stays/dates, amenities, balcony и tenant restrictions **N/A**. Для каждого нужен отдельный `explicit_true / explicit_false / conditional / unknown / conflict / legacy_unverified` статус с evidence. Число ненулевых bool не равно полноте подтверждённых правил.

## 8. API поиска и frontend

`POST /api/v1/listings/search/cards`: `ListingCardSearchRequest` → `enforce_listing_view_access` → `search_public_cards` → `visible_query` + `apply_search_filters` → keyset seek → `ListingCardSearchResponse`. Max page 50; cursor привязан к фильтрам и sort, base64 с проверкой структуры, не заявляется криптографически подписанным. Exact count отдельно от select limit+1. Visibility исключает неопубликованные/deleted, blocked/deleted owner и активные ограничения; применяется действующий rental price cap. Не копировать SQL заново в AI route. [S02–S04]

Есть `/listings/search`, `/listings/map`, `/listings/regions/counts`, `/listings/cards/resolve`, saved-search/history/notification/account endpoints. GET `/listings/catalog-version` может создавать state при отсутствии строки; поэтому он не использован в аудите как гарантированно немутирующий. Map и similar/detail имеют свои DTO/guards. Матрица AI-критериев находится во втором отчёте.

Desktop: HomePage/SearchForm → SearchPage → `searchPublicListings()` → PropertyCard. Mobile: mobile-app-v2 → MobileSearchResults re-export → mobile-search-results-v2 с собственным `MobileResultCard`. Оба используют существующий card API, gallery failover, favorites и TOP badge. External desktop link открывает sourceUrl в новой вкладке; mobile использует window.open; internal listing detail сохраняет свой route, external detail умеет redirect. Это **два существующих renderer**, не один универсальный компонент. [S07/S08]

Filters изменяемы программно (`setFilters`, query/rentalMode, `filtersToParams`/`filtersFromParams`); запросы имеют AbortController и очистку cursor. Mobile хранит собственные draft/applied filters и search-session references, desktop использует context+URL. AI patch должен атомарно обновлять обе проекции и сбрасывать cursor только при изменении intent; серверная AI conversation отсутствует. Гарантии сохранения всех фильтров после произвольного reload/Back нуждаются в будущих E2E, а не следуют из наличия context. [S07/S08]

## 9. Авторизация, rate limiting, сохранения

JWT содержит user/sub и persisted session sid. DB проверяет session expiry/revocation, blocked/deleted user; current_user добавляет moderation. Refresh: HttpOnly, Secure production, SameSite=Lax, path=/api/v1/auth; cookie mutations требуют allowed Origin. 200 AI requests следует выдавать существующему authenticated user независимо от host/tenant role, с теми же ban guards. Email verification не встроена в generic current_user: вводить её как новое скрытое условие квоты без решения владельца нельзя. [S09]

Redis limiter: Lua INCR+EXPIRE атомарны, key `ttest:rate:{clientIP}:{method}:{bucket}`; окно начинается с первого запроса, попытка считается до результата, rejected attempts тоже increment. Он не знает Madrid calendar, user ID, успешность, reserve/release или idempotency. При outage через 5 s retry применяется process-local OrderedDict/deque с asyncio lock. Это допустимый текущий throttling fallback, но не точная общая AI quota. [S01/S09]

SavedSearch: JSONB filters + polygon + rental_mode + query + province; auth/ownership на routes/service, max 50 per user, payload cap 16 KiB/500 nodes. JSONB может вместить versioned AI intent без обязательной новой колонки, но `_saved_search_payload` сейчас переводит лишь известные старые поля. Просто положить `aiIntent` в JSONB недостаточно: alerts его проигнорируют. На frontend saveCurrentSearch поддерживает также local guest save и показывает обещание alerts; **AI save/alerts надо явно gated registration**, сохранив обычный guest UX отдельно. [S05/S11]

Импорт нового/restored published listing вызывает notify_saved_search_matches в той же DB unit; создаётся notification с unique recipient+idempotency key `saved-search:{search}:{listing}`, плюс mail outbox. Обычное update не запускает этот путь; поздний AI enrichment требует нового идемпотентного re-match hook, иначе алерт потеряется. Closed/removed исключаются visibility, favorites имеют unavailable notification. Mail leasing SKIP LOCKED, lease ownership finalization, bounded retries/backoff пригодны как **паттерн**, а не как готовая AI queue. Реальная доставка писем/backlog N/A; worker healthy не доказывает доставку. [S06:969–980, S11/S15]

Web push найден в advertising_alerts для рекламного waitlist; это не общий транспорт saved-search notifications. Не объявлять существующие listing alerts автоматически push-enabled. [S15]

## 10. CI/CD и безопасность релизов

Main protection: GitHub branch API `protected=false`, protection endpoint 404, repository rulesets `[]`. То есть обязательные PR checks **не принуждаются branch protection**. Это отдельно от manual deploy guard. Production environment имеет required_reviewers (2), prevent_self_review=false, custom branch policy main. Поэтому manual gate есть, но self-approval разрешён. [VERIFIED_CI/E09]

Manual deployment YAML — только workflow_dispatch с checkbox; verify-release требует точный main, merged PR и checks `snapshot, security-static, safeguards, full-audit, backend-production, frontend-static, validate`, условно backend/frontend payments. Последующая forced-command SSH роль не даёт обычный shell. Rollback не отменяет платежи/изменённые данные и не обещает destructive downgrade; freeze baseline и expand-only migrations защищают совместимость. Эти свойства подтверждены кодом, recovery drill в этом аудите не проводился. [S14]

| Проверка | SHA / результат | Доказательство |
|---|---|---|
| #372 PR head | `3aa0231c…`: required checks success; visual comparison jobs skipped | run 40135786785 и связанные runs, E08 |
| текущий main M | manual production success; public-contract success; **full-audit failure**, Pages build failure | runs 40183294613, 40182094744, 40138694278, 40138693927 |
| main full-audit | backend 843 passed/7 skipped; integration 312 passed; далее full-stack suite с 10 failed / 13 passed | job 121005614722; создание fixture listing отклонено address validation: HTTP422 вместо201 |
| main Pages | failure в Configure Pages, Get Pages site failed | job 121005613505; Pages не является production |
| #373 final head F | backend, security-static, backend-payments, frontend-payments success | E07/E08 |
| #373 backend F | **904 passed, 7 skipped; integration 88 passed**, lint/typecheck steps success | run 40136990342/job 121000495159 |
| #373 code revision | `6e8500dcb75d80f00b452b1b9a014a8988b2ecd4`: те же 904/88 | job 120999670539 |

Нельзя писать «весь текущий CI зелёный». Release guard проверял зелёный PR head, тогда как post-merge main workflow имеет отдельные failures. У десяти full-stack cases (desktop/mobile в tests/full-stack/backend-integration.spec.ts и filter-layer-parity.spec.ts) fixture creation получает HTTP422: `Address, postcode and map location must identify the same Spanish address`, ожидая201. В backend-integration helper это assert на строке133, до собственно проверки выдачи. Это VERIFIED_CI симптом несогласованности fixture/address contract; более глубокая причина геокодирования и поведение production этим не доказаны. Исправление fixtures/contract проверить до launch отдельным PR; CI без разрешения не перезапускался. Local tests в этом аудите не запускались: executable code не менялся; существующие конкретные CI результаты прочитаны независимо от текста PR.

## 11. Ресурсы и ограничения

6 CPU; RAM total 17 984 MiB, available 15 968 MiB; swap 0; filesystem 968 GiB, used 100 GiB, available 869 GiB (11% used). Load average 0.91/0.88/0.78. Это моментные значения. Docker sample: importer ~100% одного CPU / 302.7 MiB; backend 0.41% / 143.5 MiB; mail 8.63% / 103 MiB; MinIO 600.4 MiB; PostgreSQL 215.9 MiB; Redis 11.37 MiB. Нет оснований вычислять гарантированную concurrent user capacity из одного sample. [E02]

TLS 1.3 certificate verification прошёл с VPS к api.groq.com, api.openai.com, api.deepseek.com; HTTP inference/paid calls не делались. Это подтверждает outbound network+TLS, но не API credentials, balance, model entitlement, rate limits или latency. Upload bandwidth, disk IOPS, DB connection headroom/max_connections, request p95, queue backlog и peak-hour saturation **UNKNOWN**. Без тяжёлого benchmark рекомендован небольшой старт; расчёты во втором отчёте. [E04]

## 12. Приоритетные риски и блокеры

| Приоритет | Риск / доказательство | Что требуется до запуска |
|---|---|---|
| P0 | Ошибочные «можно с животными/детьми» из defaults, stale fingerprint, конфликтов | provenance, schema, conservative matching, gold-set; #373 review |
| P0 | Нет корректной AI quota/reservation/idempotency, memory fallback неточный | durable ledger и единый text/voice debit |
| P0 | Нет outbound privacy boundary и согласованного provider processing | минимизация PII, endpoint-specific retention, договорные параметры; ключи server-only |
| P1 | Фильтр квартир не соответствует фактическим данным | явное решение taxonomy без silent remap, регрессии старого поиска |
| P1 | Микрофон запрещён, voice request упрётся в 256 KiB/30 s | scoped policy/audio endpoint/валидация и fallback UX |
| P1 | Import logs теряют source/counters; healthy worker скрывает partial failures | allowlisted diagnostics, read-only source/run aggregates |
| P1 | Без read-only DB неизвестны coverage/freshness/backfill/connection headroom | approved replica/роль и ограниченные агрегаты |
| P1 | Main unprotected + post-merge audit failures | отдельное исправление/решение владельца, CI evidence на будущей финальной ревизии |
| P1 | Redis no memory cap; enrichment может конкурировать с импортом | отдельные prefixes/TTL/concurrency/queue isolation, алерты |
| P1 | TOP ordering нельзя менять чистым relevance sort | сохранить tier+boost order, проверить keyset и pagination |
| P2 | Географическая разница 196, неустановленная точность координат | replica audit; сохранять существующую карту без угадывания точек |

Tourist-rental legal/source-permission review остаётся отдельной задачей. Этот аудит не устанавливает юридическую допустимость всех источников и не меняет admission/removal или holiday policy.

## 13. Реестр неизвестного

**BLOCKED доступом:** текущий SQL Alembic head, PostGIS extension version, полный inventory/statuses/owners/types; по каждому source records/active/canonicals/published, freshness p50/p95, description/fullness/compatibility %, conflicts, last useful import; DB/table sizes, retention, live indexes/plans/connections, outbox backlog.

**UNKNOWN измерениями:** реальная ASR accuracy по RU/ES, latency/cost в этом продукте, provider account limits/privacy settings, peak capacity, bandwidth, recovery effectiveness, SMTP delivery и collector alerts. Они не мешают offline ADR и контрактам, но ограничивают готовность production launch.

## 14. Приложение: доказательства

Операционные выдержки и компактные GitHub snapshots сохранены в `evidence/observations.json`; машинные ссылки/границы также в `audit-summary.json`. Ни один source fixture не использован как production measurement.

| ID | Среда / SHA | Метод | Что подтверждает / ограничение |
|---|---|---|---|
| E01 | GitHub M/P/F | ls-remote + PR API + exact Git objects | refs/head/state; может измениться после проверки |
| E02 | production M, 14:07–14:08 UTC | readlink, docker ps/inspect/stats, uptime/free/df, lslocks | services/restarts/resources snapshot; не load test |
| E03 | public M | HTTPS GET build-info, /, health, docs | release/readiness/headers; /metrics — HTML |
| E04 | production M, 14:09/14:13 UTC | allowlisted Settings, source list, Redis INFO, postgres --version, TLS | конфигурация нового процесса/сеть; не DB inventory и не provider inference |
| E05 | public DB behind M, 14:11/14:13/14:15 UTC | bounded read-only card counts + region counts; первые 50 type labels | публичные агрегаты, не весь DB catalog; запросы не единый snapshot |
| E06 | production M, 14:10 UTC | bounded logs → remote fixed-label aggregates; deploy-info allowlist | partial errors, metadata; не сырые журналы/не source success matrix |
| E07 | GitHub F/B | PR #373 API + diff + exact source | только branch foundation |
| E08 | CI M/#372/F | existing checks/jobs/log numeric summaries | конкретные runs/SHAs, не повторный CI |
| E09 | GitHub settings | branches/protection/rulesets + production env policy API | main unprotected, env manual gate; настройки во времени |

Ниже S-ссылки обозначают VERIFIED_CODE_MAIN(M), кроме явно отмеченных P/F. Метод — чтение точного исходника/диффа, дата 2026-10-25; сами по себе они не подтверждают миграцию, production data или браузерный runtime. Пять runtime source files S01/S02/rate-limit/S06/notifications сверены с Git blobs M; Windows CRLF checkout не использовался как byte-equivalence эталон.

- **S01:** [main.py:118](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/main.py#L118), [headers:136](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/main.py#L136), [health:379](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/main.py#L379).
- **S02:** [repositories/listings.py:272](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/repositories/listings.py#L272), filters:338–518, ordering:551–615, cards:634–729, promotion:89–137.
- **S03:** [schemas/listings.py:12](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/schemas/listings.py#L12), search:454–607, cards:617–658.
- **S04:** [api/v1/listings.py:217](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/api/v1/listings.py#L217), regions:174–182; [db/session.py:8](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/db/session.py#L8).
- **S05:** [models/__init__.py:127](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/models/__init__.py#L127), sources:206–245, saved:324–334; [models/room_details.py:15](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/models/room_details.py#L15).
- **S06:** [external_sources.py:721](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/external_sources.py#L721), parse:1296–1444, normalize:1447–1533, config:2376; [external_import.py:493](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/external_import.py#L493), snapshots:594–665, upsert:668–990, deactivate:1031; [worker:44](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/workers/external_listings.py#L44), cycle:284–365; [Habitaclia install:527](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/habitaclia_source.py#L527).
- **S07:** [SearchPage.tsx:205](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/pages/SearchPage.tsx#L205), cards:773/820; [marketplace.tsx:477](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/components/marketplace.tsx#L477); [src/api/listings.ts:348](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/api/listings.ts#L348); [nginx:60](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/deploy/nginx.conf#L60).
- **S08:** [mobile-search-results-v2.tsx:158](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/components/mobile-search-results-v2.tsx#L158), requests:271/296, open:544/644, filters:560–613; [app-context.tsx:597](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/contexts/app-context.tsx#L597); [ListingPage.tsx:30](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/src/pages/ListingPage.tsx#L30).
- **S09:** [rate_limit.py:15](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/rate_limit.py#L15); [dependencies.py:17](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/api/dependencies.py#L17); [auth.py:40](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/api/v1/auth.py#L40).
- **S10 (F):** [PR #373 diff](https://github.com/antony502189-max/Ttest/pull/373/files); [listing_evidence.py:1](https://github.com/antony502189-max/Ttest/blob/fcae378d9dbbc8447f18df150327180f6f2c8231/backend/app/services/listing_evidence.py#L1).
- **S11:** [notifications.py:46](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/notifications.py#L46), translate:143–221, matches:251–285; [search_state.py:260](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/search_state.py#L260); [saved_searches.py:20](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/api/v1/saved_searches.py#L20).
- **S12 (F):** [ai_listing_input.py:45](https://github.com/antony502189-max/Ttest/blob/fcae378d9dbbc8447f18df150327180f6f2c8231/backend/app/services/ai_listing_input.py#L45), builder:126–193; [audit CLI:228](https://github.com/antony502189-max/Ttest/blob/fcae378d9dbbc8447f18df150327180f6f2c8231/backend/app/commands/audit_ai_listing_data.py#L228); [PARSER_DATA_AUDIT:20](https://github.com/antony502189-max/Ttest/blob/fcae378d9dbbc8447f18df150327180f6f2c8231/docs/ai-voice-search/PARSER_DATA_AUDIT.md#L20).
- **S13:** [observability.py:50](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/core/observability.py#L50).
- **S14:** [manual deploy workflow:1](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/.github/workflows/manual-production-deploy.yml#L1); [production-audit.yml:18](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/.github/workflows/production-audit.yml#L18); [0066 migration:5](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/alembic/versions/0066_complimentary_advertisements.py#L5); deploy/deploy-release.sh и rollback-release.sh, docs/production-operations.md — read-only source review.
- **S15:** [mail.py:105](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/mail.py#L105); [advertising_alerts.py:99](https://github.com/antony502189-max/Ttest/blob/1292c6807ece59999238bb31c80e09ef7e2c3212/backend/app/services/advertising_alerts.py#L99).

Связанные документы: [готовность AI](AI_INTEGRATION_READINESS.md), [последовательность PR](AI_IMPLEMENTATION_SEQUENCE.md), [JSON](audit-summary.json).
