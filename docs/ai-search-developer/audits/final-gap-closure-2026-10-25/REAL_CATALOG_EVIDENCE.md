# Реальный каталог: доказательства, границы измерения и план DBA

Наблюдение: **2026-10-25**, public HTTPS samples в20:19UTC (23:19 Europe/Minsk). Актуальный public build — `1292c6807ece59999238bb31c80e09ef7e2c3212` (M). Код parser foundation — `fcae378d9dbbc8447f18df150327180f6f2c8231` (F), только открытый #373. Developer docs — `85fa9ad7ebff15634b34bd341882d302398b6dfc` (H). Ссылки R/C/P/D ведут в [реестр](FINAL_GAP_CLOSURE_AUDIT.md#12-реестр-доказательств), где указаны SHA, path:line, метод, среда и ограничения.

## 1. Что действительно измерено

**Полная production data readiness не измерена.** Отдельная разрешённая read-only DB роль/реплика не установлена в этой сессии. Пароль сервера не предоставляет такую роль и не использован. Root SSH, application DSN и чужие credentials не применялись как обход. Никакой SQL ниже не выполнялся на production. Статус DB inventory и trustworthy matching coverage — **BLOCKED**, численные значения — **null**, а не0. [D01]

Пять завершённых HTTPS чтений (build, root headers, три search requests) плюс один первоначальный GET build, результат которого не вошёл в sample из-за локальной ошибки обработки. Нет циклического опроса и нагрузки. Search route проверен как bounded read-only по C03/C04; anonymous access guard сразу возвращает без DB writes. `/catalog-version`, который способен создавать singleton, не использован. Ответы свернуты в safe aggregates, тексты/URLs/IDs карточек в отчёт не перенесены. [C12/P01–P03]

| Запрос public cards | Numerator/denominator | Наблюдение | Классификация/ограничение |
|---|---|---|---|
| long,limit20 | 20 returned /1134 total по API | 16Pisos,1Fotocasa,3 без primarySource;10individual,8one-bedroom,2studio | VERIFIED_PRODUCTION P02; первая страница, порядок коммерческий, не random sample |
| holiday,limit20 | 20returned /31total | 19Pisos,1без primarySource;1individual,16one-bedroom,3studio | VERIFIED_PRODUCTION P02; другое последовательное окно |
| long,Adeje,maxPrice700,limit20 | 6returned /6total | 1Fotocasa,5без primarySource;6individual | VERIFIED_PRODUCTION P03; не AI pet/occupancy match |
| Сумма total двух режимов | 1134+31=1165 | публично eligible, не все строки DB | INFERRED арифметика P02; не единая MVCC transaction |

Историческая выдача1163 (1132+31) из прошлого аудита не переписана. Нельзя из разницы2 вывести2 новых imported records, успешный источник или доступность жилья. Отсутствующий primarySource не доказывает native, поэтому в sample используется «без primarySource», а не native count. [R04/P02/P03]

## 2. Матрица реальной готовности каталога

Для всех строк production selection date=2026-10-25; где n/d неизвестны — **не измерено D01**. Поля перечислены по VERIFIED_CODE_MAIN M C11. «Удобочитаемое описание» не означает наличие нужного разрешения.

| Измерение | Numerator | Denominator/selection | Значение |
|---|---|---|---|
| Все canonical listings | count(listings) | все строки, deleted отдельно | null |
| Published raw / hidden / closed / pending / rejected / draft | count по status | все listings; не путать с public eligibility | null |
| Реально public eligible U | distinct listing.id | точный visible_query: price+owner+restrictions | null для DB snapshot; публичные totals см.§1 |
| Native / external | count по is_external | все и U отдельно | null |
| Source records / active / inactive | count по current_status | external_listing_sources, fixed labels | null |
| Canonicals с active sources | count distinct canonical_listing_id | active source records; отдельно intersectU | null |
| Duplicate source keys / URLs | число повторных ключей | source+external_id / source_url; constraints не заменяют проверку | null |
| Multi-source dwellings | count canonical с>1source | активные source rows, distinctcanonical | null |
| Дубликаты самой dwelling | ручной подтверждённый dedup | нельзя вывести из multi-source count или похожего текста | null |
| Rental mode / type / province / region | count по fixed category | все, U, per-source отдельно | null |
| Usable descriptions | n clean descriptions с содержательным evidence | U canonical и active source records отдельно | null |
| Пустые/недостаточные descriptions | n по length bins и quality review | те же denominator; truncation отдельно | null |
| Missing structured fields | null/empty/legacy_unverified по полю | U×source×type×mode | null |
| Trustworthy compatibility | n с validated evidence нужного состояния | U или active source-by-type; критерий отдельно | null |
| Joint match readiness | n со всеми hard fields доказанными и свежими | U для конкретного набора hard constraints | null |

**На критический вопрос о проценте usable каталога:** сейчас ответ null. Нет единственного корректного «процента AI-ready»: coverage для small dog+couple+2people отличается от price+city. Нельзя усреднить отдельные поля и назвать это вероятностью точной рекомендации. Рассчитывать per-criterion и joint coverage в согласованных сценариях, сохраняя denominator и дату snapshot. [D01/C03/C07, INFERRED]

### Состояния evidence, которые должен измерить DBA-процесс

Для каждого criterion: `explicit_allow`, `explicit_deny`, `conditional`, `unknown`, `conflict`, `legacy_unverified`. Для чисел/дат вместо allow/deny используются подтверждённые value/range и статус качества; отсутствие числа не0. `explicit` grammar F надо разделить по boolean value, а не объявлять весь explicit разрешением. Grammar не распознаёт все языки/conditions, её unknown — «не распознано этим методом», не обязательно «отсутствует в тексте». [C07]

| Семейство | Проверяемые поля/qualifiers | Production n/d по каждому состоянию |
|---|---|---|
| Люди | maximum_capacity, свободные места, пара, друзья/группа, дети/возраст/число | null/null |
| Питомцы | разрешение/запрет, dog/cat/other, размер/вес/число, approval conditions | null/null |
| Курение | глобальное, indoors, outdoors, balcony-only | null/null |
| Обстановка/деньги | furnished, deposit amount/cadence/currency, bills whole/partial | null/null |
| Удобства | balcony, terrace отдельно; private/shared; иные allowlisted amenities | null/null |
| Длительность | minimum months/nights, available_from/until, verified vacancy | null/null |
| Иные условия | restrictions/tenant types/empadronamiento, scope/evidence | null/null |

Процент состояния s: **100×n(s)/N(selection)**. Включать unknown и legacy_unverified в denominator, иначе полнота искусственно завышается. Если N=0, percentage=null. Joint known coverage — count distinct eligible canonical, где resolver имеет evidence-backed current value для всех выбранных hard fields; это ещё не count подходящих конкретному пользователю (allow и deny оба известны). Match-ready count вычислять отдельно. Не складывать per-source canonical counts: одна dwelling может иметь несколько источников. [INFERRED на C03/C07/C11]

## 3. Источники: реальная health/quality matrix

Дата всех строк2026-10-25. Config столбец — **VERIFIED_CODE_MAIN M**, не актуальный env. Все run/freshness/coverage столбцы — **BLOCKED D01**. Sample — VERIFIED_PRODUCTION P02/P03. H historical runtime обозначен явно, не current settings.

| Source | Config/registration evidence | Наличие в новых sample | Success/failed/partial/403/accepted/last sync | Description+policy coverage |
|---|---|---|---|---|
| Idealista | зарегистрирован; вне compose default; retired candidate если выключен | не наблюдался, отсутствие не доказано | null | null |
| Fotocasa | зарегистрирован, compose default | long page1; Adeje page1 (могут совпадать) | null | null |
| Milanuncios | зарегистрирован, compose default; retired logic зависит от enabled set | не наблюдался в этих страницах | null | null |
| PisoCompartido | зарегистрирован, compose default | не наблюдался | null | null |
| Pisos | зарегистрирован, compose default | long16,holiday19 | null | null |
| ThinkSpain | зарегистрирован, вне compose default; retired candidate | не наблюдался | null | null |
| AlquilerDocenteCanarias | зарегистрирован, compose default | не наблюдался | null | null |
| Flatio | зарегистрирован, compose default | не наблюдался | null | null |
| Habitaclia | отдельный production install hook | не наблюдался | null | null |
| Native listings | не адаптер; отдельно is_external=false | без primarySource нельзя доказать native | неприменимо к import runs | null |

Фактически включённые источники, интервалы checks, последняя успешная синхронизация, accepted unique listings, stale records, identity conflicts и canonical lag должны прийти из согласованного DB snapshot + allowlisted effective config. Worker healthy может означать, что полезно завершилась минимальная группа источников; другие в том же cycle могут быть blocked/failed. Исторический seven-adapter runtime не доказывает семь полезных источников. [C05/C06/R04]

### Где теряется evidence по коду

Это **кодовые риски**, не measured production loss rates. Shared generic parse — M `external_sources.py:1296–1444`, normalize1447–1533; source overrides и F audit16–78 проверены. Политики из raw widgets автоматически не переносятся в typed snapshot. [C05/C07]

| Source | Сохраняемый description/raw и конкретный gap | Следующая проверка без crawl |
|---|---|---|
| Idealista | generic JSON-LD/embedded→meta; может остаться краткий summary/не тот объект | route-bound description на существующем разрешённом snapshot |
| Fotocasa | scored embedded→DOM→generic; DOM regex/nested element truncation; structured policies не mapped | ID binding/full description/widget facts, source:1567–1616 |
| Milanuncios | generic description, category/location inference из copy | owner policy vs page chrome, source:1828–1860 |
| PisoCompartido | DOM description override, widget tenant policies отдельно не mapped | text length vs stored widget evidence, source:1876–1960 |
| Pisos | generic description, dedicated price/type/gallery; policy provenance нет | full description/structured policy mapping, source:1985–2098 |
| ThinkSpain | generic description и route rental mode; English policy widgets отдельно не mapped | EN conditions/cadence, source:2109–2127 |
| AlquilerDocenteCanarias | DOM description; raw заменён compact source/id/updated; unmapped keys после import не восстановить | проверить retained description и доступные compact keys, source:2179–2244 |
| Flatio | selected Room/Apartment JSON-LD; compact raw availability; occupancy/amenity fields не mapped | разрешённые typed provider facts, source:2305–2373 |
| Habitaclia | route-matched Next state+DOM description, compact raw; viewport координаты намеренно suppressed | policy keys/summary completeness, habitaclia_source.py:421–524; не возвращать придуманные pins |

#373 fingerprint добавляет optional scalar values с различением null/false/0. Это закрывает «поле изменилось, importer счёл unchanged» для перечисленных полей. Не закрывает DOM truncation, unmapped source widget, исторический origin defaults, все языки, conflict resolver, lifecycle invalidation и fact persistence. `couples_allowed` есть в evidence grammar, но не в NormalizedListing dataclass как полноценное persisted provenance field. Новая версия fingerprint сама вызывает одно refresh сравнение при очередном обычном импорте; аудит не запускал этот import. [C07/C05]

## 4. Какие разрешения нужны

Нужен **утверждённый DBA оператором канал**: read-only replica либо отдельная login-role без superuser/CREATEROLE/CREATEDB/BYPASSRLS и без членства в app writer/owner roles. Только CONNECT/USAGE и SELECT на нужные **колонки** или заранее управляемые read-only views. Создание/выдача прав — отдельная будущая операторская операция, этим аудитом не выполнена. Нельзя считать `SET TRANSACTION READ ONLY` заменой разрешённой роли. [D01, INFERRED]

Минимальный scope:

- `listings`: id,owner_user_id,status,deleted_at,is_external,rental_mode,room_type,province_code,monthly_price,description,home_description и отдельно согласованные compatibility fields; **не** street/exact_location/contacts.
- `users`: только id,deleted_at,blocked; не email/name/phone/auth.
- `user_restrictions`: user_id,revoked_at,starts_at,ends_at; `listing_restrictions`: listing_id,revoked_at,starts_at,ends_at; не reasons/comments.
- `external_listing_sources`: id,source_name,external_id,source_url (ключи только для локального duplicate count),canonical_listing_id,scope_key,current_status,timestamps,fingerprint,last_state_check_result; **не full raw_payload**. Source URLs/IDs не публиковать.
- Для evidence — DBA-controlled view с отдельно выбранными JSON paths title/description/policies/category/mode, либо оператор локально выполняет JSON extraction без передачи всей колонки. PostgreSQL column grant на JSONB не умеет разрешить только поддерево: SELECT(normalized_payload) даст доступ и к nested raw, поэтому такой grant не называть минимальным.
- `external_import_runs`: source_name,scope_key,started_at,finished_at,result,counters,discovery_complete,http_status,challenge_type,next_check_at; counters/labels санитизировать. Не final_url,last_error,diagnostic_paths.
- `external_import_scopes`: source_name,scope_key,enabled,interval_seconds,next_run_at,last_run_at,last_result — без discovery URLs/checkpoint. `alembic_version`: version_num. Статистика/pg_indexes через согласованный read-only metadata channel; pg_stat_activity — только aggregates без query text.

Доступ выдаётся через approved secret manager/PG service + защищённый passfile/certificate, не пароль в chat/GitHub/argv. Ничего из присланных владельцем секретов в этот public handoff не перенесено.

## 5. Reviewed bounded query plan для оператора

**Это процедура будущего read-only запуска, не готовые результаты.** Запросы проверены статически по schema M/C11; не проходили execution/EXPLAIN на production. DBA сначала сверяет actual schema/Alembic и permissions. Если table/column отличается, остановиться, не применять миграцию из инструкции.

### Шаг 1: preflight и лимиты

Оператор выбирает read-only service, открывает psql без персональных records в терминальном журнале. Например `psql "service=ai_audit_ro" -X -v ON_ERROR_STOP=1 -f reviewed-audit.sql`; service name предварительно настраивает DBA, никаких credentials в аргументах. Файл находится в закрытом рабочем каталоге; вывод — только safe aggregates. Не использовать app `.env`, root shell или production audit command неизвестного состава.

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '500ms';
SET LOCAL idle_in_transaction_session_timeout = '15s';
SET LOCAL work_mem = '8MB';
SET LOCAL max_parallel_workers_per_gather = 0;
SELECT current_setting('transaction_read_only') AS transaction_ro,
       current_setting('default_transaction_read_only') AS default_ro,
       pg_is_in_recovery() AS is_replica,
       transaction_timestamp() AS observed_at;
SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls
FROM pg_roles WHERE rolname = current_user;
SELECT version_num FROM public.alembic_version;
SELECT relname, n_live_tup, n_dead_tup, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname='public' AND relname IN
 ('listings','external_listing_sources','external_import_runs');
ROLLBACK;
```

RO must be on; роль/наследование grants подтверждает DBA отдельно. `n_live_tup` — **оценка**, не catalog count. Replica lag получить из штатного monitoring с учётом idle primary (возраст replay timestamp сам по себе не точный lag). Любой timeout/lag/cancellation → остановить, не повышать лимит автоматически.

Cost preflight O(metadata). Длительность неизвестна. Max_parallel=0/work_mem/timeout уменьшают нагрузку, но READ ONLY SELECT всё равно потребляет CPU/IO и AccessShare locks; replica предпочтительна.

### Шаг 2: точный inventory U и dimensions

Для каждого блока — новая короткая repeatable-read read-only transaction с теми же SET LOCAL; итоговый runtime budget одного запуска **до60s**, не бесконечный snapshot. Один snapshot предпочтителен для сопоставляемых counts; если лимит не позволяет — разные окна явно пометить, не объединять как одну консистентную выборку.

```sql
WITH inventory AS (
 SELECT l.id, l.status, l.deleted_at, l.is_external,
        l.rental_mode, l.room_type, l.province_code,
        (l.status='published' AND l.deleted_at IS NULL
         AND u.deleted_at IS NULL AND u.blocked IS FALSE
         AND (l.rental_mode<>'long' OR
              (l.monthly_price>0 AND l.monthly_price<=1000))
         AND NOT EXISTS (
           SELECT 1 FROM public.user_restrictions r
           WHERE r.user_id=u.id AND r.revoked_at IS NULL
             AND r.starts_at<=now() AND (r.ends_at IS NULL OR r.ends_at>now()))
         AND NOT EXISTS (
           SELECT 1 FROM public.listing_restrictions r
           WHERE r.listing_id=l.id AND r.revoked_at IS NULL
             AND r.starts_at<=now() AND (r.ends_at IS NULL OR r.ends_at>now()))
        ) AS usable
 FROM public.listings l LEFT JOIN public.users u ON u.id=l.owner_user_id
 -- FK owner expected; missing owner must never pass visibility:
 WHERE u.id IS NOT NULL
)
SELECT status, (deleted_at IS NOT NULL) AS deleted, is_external,
       rental_mode, room_type, province_code,
       count(*) AS n, count(*) FILTER (WHERE usable) AS usable_n
FROM inventory
GROUP BY status,(deleted_at IS NOT NULL),is_external,rental_mode,room_type,province_code;
```

Дополнительно `SELECT count(*) FROM listings` и orphan owner count через LEFT JOIN (без WHERE) сверяют полный inventory: основной query соответствует visibility join и не является total при повреждённой FK. `room_type` перед public export сворачивать в fixed four categories/Other, не публиковать arbitrary text label. Province_code→autonomous community сопоставлять официальным фиксированным справочником проекта; не вводить новую геолокацию. Spatial region counters отдельно по существующим functions и только с разрешённым EXPLAIN: geography precision/неизвестный province не исправлять догадкой.

Cost O(listings+owner/restriction probes), counts могут читать все страницы. Сначала **EXPLAIN (FORMAT JSON)** без ANALYZE; вывести только оценённые rows/cost/index names, не константы/IDs. Не выполнять EXPLAIN ANALYZE на primary. Если ожидание превышает5s/допустимые pages по решению DBA — перейти на replica/offline export.

### Шаг 3: source inventory, freshness и duplicates

```sql
SELECT source_name, current_status, scope_key,
       count(*) AS source_records,
       count(DISTINCT canonical_listing_id) AS canonical_n,
       count(*) FILTER (WHERE last_success_at IS NULL) AS no_success_n,
       min(last_success_at) AS oldest_success,
       max(last_success_at) AS newest_success,
       max(last_discovered_at) AS newest_discovery,
       max(last_state_check_at) AS newest_state_check,
       count(*) FILTER (WHERE last_state_check_result IN
          ('removed','expired','not_found')) AS removal_evidence_n
FROM public.external_listing_sources
GROUP BY source_name,current_status,scope_key;

SELECT count(*) AS duplicated_keys, coalesce(sum(n-1),0) AS surplus_rows
FROM (SELECT count(*) AS n FROM public.external_listing_sources
      GROUP BY source_name,external_id HAVING count(*)>1) d;
SELECT count(*) AS duplicated_urls, coalesce(sum(n-1),0) AS surplus_rows
FROM (SELECT count(*) AS n FROM public.external_listing_sources
      GROUP BY source_url HAVING count(*)>1) d;
SELECT count(*) AS multi_source_canonicals
FROM (SELECT canonical_listing_id FROM public.external_listing_sources
      WHERE current_status='active'
      GROUP BY canonical_listing_id HAVING count(*)>1) d;
```

В закрытом analysis добавить source×mode×type×U join, но считать source rows и **distinct** canonical раздельно. Для active источников profile ages last_success/content_observed/state_check по agreed bins; p50/p95 nearest rank на replica, включая unknown отдельно. `last_success` может быть state check без нового description; `content_updated` может быть unchanged refresh. Поэтому нельзя выдать их разницу за измеренный canonical update lag. Для подтверждённого content lag нужен совпадающий hash/version и change timestamp; иначе metric=null. [C05/C06]

Cost O(source rows), group/distinct возможен sort/hash и disk spill. URL duplicates уже ограничены unique index по code, но runtime index validity неизвестна. Не экспортировать ключи/URL групп, только count. Все arbitrary source/status/scope labels привести к allowlist/Other перед публикацией.

### Шаг 4: последние runs, фактические intervals и полезные imports

```sql
WITH bounded AS (
 SELECT source_name,scope_key,started_at,finished_at,result,
        discovery_complete,http_status,counters
 FROM public.external_import_runs
 WHERE started_at >= now()-interval '7 days'
 ORDER BY started_at DESC LIMIT 2000
), sequenced AS (
 SELECT *, lag(started_at) OVER
   (PARTITION BY source_name,scope_key ORDER BY started_at) AS prior_start
 FROM bounded
)
SELECT source_name,scope_key,result,discovery_complete,http_status,
       count(*) AS run_n,
       max(finished_at) AS latest_finish,
       max(finished_at) FILTER (WHERE result='success') AS last_success_finish,
       min(started_at-prior_start) AS min_observed_interval,
       max(started_at-prior_start) AS max_observed_interval,
       sum(CASE WHEN (counters->>'accepted_rentals') ~ '^[0-9]{1,12}$'
            THEN (counters->>'accepted_rentals')::bigint ELSE 0 END) AS accepted_events,
       count(*) FILTER (WHERE http_status=403) AS run_http403_n
FROM sequenced
GROUP BY source_name,scope_key,result,discovery_complete,http_status;
```

Report включает selected_run_n, oldest selected date, факт достижения LIMIT2000 и retention gap. 7days/2000 — bounded window, не вся история; `last_success_finish` здесь означает последний success **в окне**, вне окна неизвестен. accepted missing/invalid counters дополнительно считать как unknown, не интерпретировать суммарный0 как доказанные0 imports. Failed browser operations/403, не попавшие в run.http_status, так не измеряются: нужен отдельный safe diagnostic aggregate, без raw exception URLs.

Success rate: numerator count(success) / denominator count(finished success+failed+partial+blocked) для source/scope/window; running отдельно. Accepted events не равно unique usable source rows. Time between runs не равно interval успешной detail verification; для source checks нужна история, а не один last_state_check. Retention и schedule backoff могут смещать выборку. Подтвердить schema/index plan source+result+finished и finished retention index; started sort может потребовать scan. Для selective source ограничение7days всё равно проверять plan. [C05/C06/C14]

### Шаг 5: descriptions, provenance и joint readiness

Сначала operator-local projection (без raw) batch500 с keyset id, title/description/category/mode и выбранными structured values. Никаких контактов/адресов в export. На replica отдельный controlled cleanup+bounded grammar F; ручной обезличенный review части real evidence только после privacy-authorized отбора. Для всего каталога полное чтение descriptions O(total description bytes); на primary только маленькая предварительная партия при разрешении DBA, полные проценты исключительно после полного согласованного denominator.

Не публиковать фиктивные explicit percentages по120 sampled texts как full catalog. Если sample, фиксировать seed/strata/source/type/window/selection и uncertainty; long generic summaries и неподдерживаемые языки разметить отдельно. Gold precision extraction и data coverage — разные метрики. Синтетические fixtures F ни в один production numerator не входят.

Нынешний `audit_ai_listing_data --database` F проверен: явный `AI_AUDIT_DATABASE_URL`, не app settings, read-only repeatable-read, timeout60s/lock3s, stream500. Но query **не имеет LIMIT**, accumulator хранит lengths/canonical groups в RAM, выбран только active source status, **не U**, нет полной category/region/native/freshness/run матрицы, explicit allow/deny объединены. Поэтому **не запускать его вслепую на primary как финальный аудит**. Предпочтительна replica с утверждённым объёмом или controlled offline projection и отдельным join inventory. Оператору сначала воспроизвести его read-only поведение в disposable PostgreSQL, затем отдельно разрешить bounded dataset. CLI не устанавливает provenance задним числом. [C07]

Итоговая таблица после исполнения должна иметь `snapshot_at, release_sha, schema_head, selection, source, type, rental_mode, criterion, state, numerator, denominator, percentage, evidence_method, limitations`; отдельно joint scenario_id. Unmeasured остаётся null. Public cells с малыми группами подавлять по agreed privacy rule (например n<5 — **предложение**, не существующая policy); denominator suppression не превращать в нулевую полноту.

## 6. Результат и следующий минимальный шаг

Сейчас безопасно заключить: каталог поддерживает существующий поиск; в public pages присутствуют реальные imported карточки Pisos/Fotocasa и one-bedroom taxonomy; code позволяет хранить source snapshots и runs. **Нельзя** заключить, что все источники свежи, что объявление доступно сейчас, что small dog/couple/smoking точно покрыты или что известен объём enrichment. [P02/P03/C05/C11/D01]

Разблокирование: DBA подтверждает read-only service/replica и перечисленные column/view grants, выполняет preflight→EXPLAIN→ограниченные агрегаты→reviewed evidence profiling и отдаёт только sanitized counts/method/date. Это адресное измерение AI-02, а не повод повторять общий repository audit. Пока доступ не выдан, ADR/quota/mock work продолжается; catalog-wide backfill и production activation gate остаются открытыми.
