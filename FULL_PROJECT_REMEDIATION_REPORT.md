# Исправления полного аудита проекта

Дата: **18 октября 2026**, Europe/Moscow. Рабочая ветка: `codex/province-search-top`, исходный HEAD: `15b673864c28ec90c85e78f4cb37eedadfe982c2`.

Подтвержденные FINDING-001…010 исправлены в рабочей копии и проверены регрессиями. Это результат локальной реализации, а не разрешение на production release. Коммиты, push, PR, merge, deploy и настоящие платежи не выполнялись. Production данные не менялись.

Первоначальный `FULL_PROJECT_AUDIT_REPORT.md`, весь `artifacts/audit-2026-10-17/` и ранее существовавшие untracked платежные документы/скрипты сохранены. Исходные negative probes остаются историческими доказательствами старого HEAD; исправленное поведение проверяют новые тесты в `backend/tests/integration/test_audit_remediation.py`, `test_verified_geography.py`, `backend/tests/test_address_geography.py` и `tests/audit-remediation.spec.ts`.

## Принятые пользователем бизнес-решения

В этом чате пользователь прямо подтвердил:

1. Три TOP — **на муниципалитет**, а не на провинцию.
2. Территорию TOP определяет **адрес владельца**, а не адрес недвижимости.
3. Для подтверждения адреса владельца **достаточно геокодера**; проверка проживания по документам не требуется.

Поэтому прежняя модель «52 province pools из Listing.postcode» заменена. В backend включен официальный справочник **8132 муниципальных кодов INE на 01.01.2026**. Проверенный адрес владельца хранится приватно в User; муниципальный код фиксируется в reservation/order и promotion. Изменение муниципалитета владельца блокируется при действующем TOP или незавершенной/неурегулированной покупке любого его объявления.

**Провинциальный поиск недвижимости сохранен:** он использует географию самой недвижимости. Например, недвижимость в Madrid может относиться к TOP-пулу владельца в Getafe; это следует из подтвержденного решения. Несколько муниципальных пулов могут иметь объявления в одной провинции. Лимит три нельзя теперь проверять простым подсчетом всех promoted в province 28.

Источники данных: [INE](https://www.ine.es/daco/daco42/codmun/26codmun.xlsx), [контракт CartoCiudad IGN/CNIG](https://github.com/IDEESpain/Cartociudad). Генератор `scripts/build-municipality-catalog.py` сохраняет источник, дату и SHA-256 исходного XLSX. Геометрия провинций/камеры взята из [click_that_hood](https://github.com/codeforgermany/click_that_hood/blob/main/public/data/spain-provinces.geojson), с тем же MIT license, который уже используется для community geometry проекта.

## Реестр исправлений

| Finding | Исправление | Проверяемое доказательство |
|---|---|---|
| **001, P1** — четвертый TOP при финансовом rebuild | Проверяется фактическое восстановление/расширение, независимо от `fulfilled`/`review_required`. Под capacity lock проверяется и итоговый агрегированный интервал. Недоступная вместимость оставляет payment на review, сохраняет service history и уведомляет владельца. | Реальный PostgreSQL + signed `charge.dispute.closed=won`: admin shortening получает 409; отдельно воспроизведено историческое сокращение projection, после продажи трех мест normal snapshot не создает четвертый. Проверены DB, public search и повторная доставка. |
| **002, P1** — импорт теряется в provincial search | Введен canonical `Listing.province_code`; importer и общий primary snapshot writer сохраняют structured province. Country/coordinates проверяются на противоречие с геометрией. Пустой postcode импорта не заменяется фиктивным. Read fallback сохраняет совместимость старого локального каталога. | Настоящий upsert Madrid без postcode включается в search/cards/map/counts28 и исключается из08. Повторный snapshot и dry-run/apply проверены. Existing source-failover/idempotency suite снова проходит. |
| **003, P1** — подмена postcode/координат | Server-side CartoCiudad проверяет полную effective address при create/address PATCH, включая partial PATCH и повторную публикацию через PATCH. Требуются portal, номер, корректный индекс, country, INE municipality, согласованный street/city и координаты. TOP-пул берется только из отдельно проверенного адреса владельца. Group sync переносит canonical geography и verification timestamp; защищенные sibling TOP проверяются. | Raw authenticated API с независимыми фиксированными provider records: Madrid+08001, blank/garbage postcode, другой street/номер и Barcelona coordinates со старым адресом отклоняются. Owner Getafe + property Madrid дает municipality28065. Active/pending owner move получает409. |
| **004, P1** — Tenerife-only address paths | Smart, exact/fallback и подключенный location enhancer используют Spain scope. Убрано обязательное наличие старого hidden city до resolution. Smart/exact selection передает полный canonical address в React state, а не только DOM values/coordinates. | Настоящие typing → prediction click для Madrid, Las Palmas, Palma, Ceuta, Melilla: обновлены postcode, city, province и map point. Дополнительно выполнен реальный публичный CartoCiudad smoke-test: муниципалитет28079/провинция28. |
| **005, P1** — admin удаляет оплату / ложный restore | Legacy PUT/DELETE защищены от paid/pending TOP под тем же capacity lock. Операторский restore проверяет/ремонтирует фактическую projection с eligibility/capacity и audit, сохраняя исходный период. Неполная legacy history получает409, а не `resolved:true`. | DELETE и сокращение оплаченного TOP получают409. Отдельно искусственно удаленная историческая projection действительно восстановлена. Проверены повторный restore, review/refund/dispute и idempotency старого payment suite. |
| **006, P2** — saved provincial alerts теряют scope | `provinceCode` хранится отдельным nullable полем SavedSearch, проходит write/patch/import/response и используется notifications. Frontend сохраняет и восстанавливает scope, включая `q=España&provincia=28`. Legacy city searches восстанавливаются с явным `ubicacion=ciudad`; массовой переинтерпретации нет. Исправлена история провинциальных поисков. | В БД provincial alert получает Madrid и Getafe, исключает Barcelona; старый city Madrid alert получает только Madrid. Проверен outbox. Browser round-trip сохраняет code-only scope и оставляет legacy Madrid городом после reload. |
| **007, P2** — desktop redesign / потеря действий | Возвращена approved `LocationSelector` оболочка, светлые строки и map/draw/nearby actions. Province choices встроены в нее; desktop не использует mobile full-height dark class. | Повторное сравнение с экспортом **parent1b2805e4**, одинаковые pinned dependencies/fonts: обе оболочки x32/y34/**1216×832**, четыре действия совпадают, font403=0. Осмотрены 320/768/1280, исправлено обрезание названий province rows. |
| **008, P2** — старая camera перекрывает провинцию | Добавлены bounds всех52 провинций и `provinceMapCamera`. Явная province selection имеет приоритет над remembered camera. List/map используют общий canonical request geography; legacy city restore не превращается в province. | Browser с Tenerife history и `q=España&provincia=28&vista=mapa` открывает Madrid. Реальный backend map с Madrid bounds возвращает импорт;08 при тех же bounds его исключает. Полный live Google/browser/backend E2E не заявляется. |
| **009, P2** — daily fulfillment пропускает eligibility | Daily/monthly TOP используют один `eligible()`. Сверяется муниципальный snapshot покупки. Уже активная услуга при restriction/withdrawal/republication-to-pending переводится на review, с сохранением reservation и исходного периода. | Пять SQL/API сценариев изменения во время оплаты: owner blocked, user restriction, listing restriction, исчезновение media, недопустимая цена → paid/review_required, без promotion, с уведомлением. Отдельно проверены три изменения уже активного TOP и сохранение service history/capacity. |
| **010, P2** — красные gates / фиктивное покрытие | Исправлены imports/types, mocks SQL locks и time assertion. Старые synthetic addresses получили номер; payment fixtures имеют отдельно заданный verified owner municipality. Новые adversarial tests обходят вспомогательный fixture client и используют независимые provider evidence. Province/UI regressions добавлены в production-audit CI. | Ruff/Mypy/unit/PostGIS и S3 gates проходят; frontend выполнен на dependencies из lockfile в отдельной папке. Проверены schema parity, immutable/expand migration guard, bundle security и audit policy. |

### Политика оплаченного периода

Обычная модерация и уход объявления из публикации не уничтожают оплаченный interval и не перепродают его место. Order попадает на review, projection/municipality/history сохраняются до исходного окончания или явного финансового resolution. Автоматического продления за скрытые дни и настоящего автоматического refund не добавлено: оператор использует существующие audited refund/restore endpoints. При восстановлении нельзя вытеснить три других действующих покупки.

Транзакционный advertising advisory lock сохраняется общим для scarce advertising products. Перестройка locking/sharding не выполнялась без отдельного доказательства корректности. Одновременные запросы используют настоящие PostgreSQL sessions/locks, а не только SQL-shape mocks.

### Граница доверия геокодера

CartoCiudad вызывается сервером по фиксированному HTTPS origin через существующий guarded transport PR346/348: public-IP pinning, отсутствие произвольного URL/redirect, timeout8s и response cap64KiB. В запросе postcode идет в `cod_postal_filter`, а не вторым номером внутри `q`; именно это проверено реальным публичным smoke-test и transport regression. Provider outage/malformed/oversized ответ дает503; несовпадение адреса дает422. Автоматического принятия client province нет.

Допуск map point — 250м от подтвержденного portal. Это ограниченный допуск точки, а не возможность выбрать иной муниципальный пул: муниципальный код владельца возвращает серверный геокодер, клиент его не задает. Проверка существования адреса не доказывает проживание — пользователь явно выбрал именно такую политику.

Private address доступен только через `/users/me/address`, не добавлен в публичные profile/listing DTO. Удаление своего аккаунта очищает новые private fields. HTTPX INFO logging для URL геокодера подавлен, чтобы query с адресом не попадал в журнал; это проверено тестом. Реальные адреса аккаунтов во время работы внешнему провайдеру не отправлялись.

## Миграция и backfill

Добавлена **expand-only** миграция `0064_verified_geography`: nullable поля пользователя, listing, saved search и муниципальные snapshots order/promotion; индексы canonical geography. Выпущенные миграции не изменены. Downgrade сохраняет расширенные данные для совместимости старых binaries.

**Production migration/backfill не запускались.** Перед включением новой продажи TOP оператору необходимо:

1. Применить миграцию и получить read-only план на нужной БД:

   ```text
   python -m app.commands.backfill_geography --expected-database DATABASE_NAME
   ```

2. Проверить `provinces`, `unknown`, `localAddressVerificationRequired`, `topBindings` и `capacityConflicts`. Команда не выводит private address, не делает geocoder calls и никогда не выводит адрес владельца из адреса недвижимости.
3. Владельцы подтверждают свой адрес через профиль. Для legacy owner без прежней association первая верификация разрешена даже при старом TOP; **она не привязывает старую услугу автоматически**. Local legacy listings проходят обычную проверенную адресную правку; отсутствующая география не выдумывается.
4. После review оператор может отдельно применить imported canonical provinces (`--apply`) и согласованные TOP associations (`--apply --bind-top`), всегда указывая `--expected-database`. Binding отклоняется при неизвестных owners или пересечении более трех distinct listings в любом интервале. Исторические спорные/overbooked услуги требуют финансового resolution. При rollout все TOP writers должны использовать новую муниципальную модель; старый writer с лимитом по postcode не является совместимым способом продажи.

Dry-run делает rollback. Проверка имени БД обязательна. Проверены dry-run без изменений, apply на **тестовых** imported данных, bootstrap legacy owner и отказ привязать четыре overlapping TOP. Сроки/статусы платежей при backfill не переписываются.

Пока есть действующие legacy promotions/unresolved reservations без муниципальной association, новая продажа TOP консервативно блокируется. Это намеренный этап безопасного перехода, а не автоматическое присвоение старых покупок произвольному муниципалитету.

## Исполненные проверки

Основные финальные логи находятся в `artifacts/remediation-2026-10-17/`. Рабочие изменения не закоммичены: проверена working copy поверх исходного HEAD. Перечень/хеши source files и версии окружения записаны рядом с логами.

| Проверка | Результат | Артефакт |
|---|---|---|
| Backend Ruff | PASS | `ruff-final.log` |
| Backend Mypy | PASS,112 source files | `mypy-final.log` |
| Backend unit | **800 passed,7 skipped** | `unit-final.log`, `unit-final.xml` |
| PostgreSQL/PostGIS integration | **280 passed** | `integration-final.log`, `integration-final.xml` |
| Geography/legacy bootstrap/S3 targeted | **5 passed**, в том числе MinIO round-trip | `geography-s3-final.log/xml` |
| TypeScript | PASS | `typecheck-final.log` |
| Frontend lint/i18n | PASS; существующие hook/unused warnings сохранены | `lint-final.log` |
| Vite build / production bundle | PASS; предупреждение large chunk остается | `build-final.log` |
| npm production audit policy | PASS, повтор ранее разрешенной проверки `--omit=dev` | `npm-security-final.log` |
| Province/owner/UI browser suite | **24 passed** | `browser-final.log` |
| Admin-performance active regressions | **8 passed**; opt-in benchmark не заявляется | `admin-performance-final.log` |
| Parent/fixed design comparison | PASS оболочки/действий; font403=0 | `design-comparison.json`, `selector-parent-1280.png`, `selector-fixed-1280.png` |
| Реальный публичный CartoCiudad example | PASS,28079/28 | `geocoder-public-smoke.log` |
| Supply-chain/migration governance | PASS | `supply-chain-final.log`, `migration-final.log` |
| Offline wheel packaging | PASS, оба runtime JSON включены | `wheel.log` |
| CLI backfill dry-run | PASS, `mode=dry-run`, `ownerAddressesInferred=0` | `backfill-dry-run.json` |

Frontend dependencies установлены отдельно в `output/remediation-frontend` командой `npm ci --ignore-scripts --no-audit`; пользовательский `node_modules` не изменен. Typecheck/build/browser выполнялись с тем же зафиксированным lockfile graph. Audit policy запущена отдельно через npm, с корректным `npm_execpath`. Проверка supply chain не заменена обновлением dependency pins.

Python suite использует `output/release-venv/Scripts/python.exe`; это pinned release окружение аудита, а не PATH PyManager stub. Для wheel использован bundled Python с доступным setuptools, офлайн. Windows sandbox не позволяет часть socket/temporary build операций; соответствующие проверки выполнены через разрешенный elevated execution на синтетических сервисах. Это не обход product checks.

Новые Docker PostgreSQL/Redis/MinIO были отдельными от `ttest-*`: порты55441/56381/59000. Миграции и очистка fixtures применялись только к `remediation_test`. Stripe HTTP всегда заменен sandbox doubles. Старые финансовые репродукции изменены по смыслу: PASS означает отказ от неправильного grant/мутации либо правильное восстановление, а не сохранение бага.

## Матрица T01–T30 с уточненным бизнес-правилом

`PASS` относится к указанному исполненному уровню. Реальные платежи/production не подразумеваются.

| ID | Результат | Доказательство / предел |
|---|---|---|
| T01 | PASS API/UI | Property address→verified province; отдельно owner geocoder→INE municipality. |
| T02 | PASS guarded writes | Effective address PATCH сверяется сервером; owner move проверяет live/pending purchases. |
| T03 | PASS | Empty/garbage/incomplete address дает422; provider outage503. |
| T04 | PASS | Hidden city; province/municipality не выбираются request-field override. |
| T05 | PASS DB | Ноль TOP→3 slots. |
| T06 | PASS DB | Один TOP→2 slots. |
| T07 | PASS DB | Два TOP→1 slot. |
| T08 | PASS DB | Три TOP→unavailable/checkout409; finance rebuild также не дает четвертый. |
| T09 | PASS DB | Madrid/Getafe независимы, хотя находятся в одной провинции; property address не меняет pool. |
| T10 | PASS browser | Sold-out message, disabled continue,320/1280. |
| T11 | PASS unit | Earliest interval, schedules, renewals, exact boundary, legacy>3. |
| T12 | PASS browser | Ноль вызывает authoritative fetch; оплата не разрешается самим таймером. |
| T13 | PASS DB | Concurrent last-slot requests дают200/409. |
| T14 | PASS DB | Unpaid/failed/expired paths не grant; старые payment fixtures достигают основных assertions. |
| T15 | PASS DB | Concurrent/repeated callbacks дают один grant и notification. |
| T16 | PASS browser | Настоящий reload повторно получает availability. |
| T17 | PASS browser | Server-relative timer не зависит от смещения wall clock; новый +24h и прежние skew probes. |
| T18 | PASS DB | Expiry освобождает slot без cleanup; отдельно interleaving во время provider IO. |
| T19 | PASS DB/API | Active/pending pool move запрещен; server validation не принимает физический move со старым индексом. |
| T20 | PASS raw API | Forged valid-other postcode/coordinates отклоняются; literal scope fields не становятся authority. |
| T21 | PASS suite | Ownership/admin allowlist regressions сохранены. |
| T22 | PASS fixtures / production pending | Импорт без postcode и legacy bootstrap/backfill проверены; реальные production данные не обследовались. |
| T23 | PASS backend/UI subset | Homepage hero/payment и approved promotion choices сохранены. |
| T24 | PASS backend | Seven bottom-ad slots и прежний lifecycle не заменены муниципальным лимитом. |
| T25 | PASS targeted | Saved alerts, code-only restore, map camera, address input, existing admin regressions. Полный сайт не сертифицирован. |
| T26 | PASS targeted design |320/768/1280; parent shell/actions/fonts сравнивались. Не full-site pixel/a11y certification. |
| T27 | PASS DB safety | Late paid после resale→review, без четвертого grant; настоящий refund не выполнялся. |
| T28 | PASS DB sessions | Три overlapping callbacks используют реальные SQL locks. Не отдельные worker OS processes. |
| T29 | PASS fresh process | Новый Python process/connection читает persisted active TOP и2slots. Hard-kill live server не выполнялся. |
| T30 | PASS API/finance | Full municipality direct checkout409 и normal financial refresh не обходят capacity. |

## Матрица платежей A–J

| Сценарий | Результат |
|---|---|
| A. Двое за последний слот | PASS concurrent HTTP/PostgreSQL,200/409. |
| B. Late success после expiry | PASS: paid/review_required, без displaced grant. |
| C. Повторный webhook | PASS: один эффективный grant/notification. |
| D. Пользователь не вернулся из Checkout | PASS worker recovery без browser redirect/webhook. |
| E. Direct purchase при full pool | PASS409; другой муниципалитет независим. |
| F. Expiry во время provider IO | PASS: provider call приостановлен, reservation виден в другой сессии; истечение и следующий checkout/callback не превышают3. |
| G. Смена адреса/пула | PASS active/pending guard, owner/property separation и raw address validation. |
| H. Сбой до fulfillment commit | PASS rollback/retry/duplicate; hard-kill process не заявляется. |
| I. Workers одного события | PASS независимых DB sessions + advisory/row locks; multi-process stress не выполнялся. |
| J. Быстрые запросы одного listing | PASS: один order/provider URL, reservation до external IO. |

Дополнительно: admin PUT/DELETE, отсутствующая historical projection, normal/out-of-order finance snapshots, пять eligibility изменений, active moderation/withdraw/republication review, transient/malformed availability, imported geography и saved alert/outbox.

## Что осталось за пределами локального исправления

- Применение миграции и проверенного backfill к production — отдельная операторская операция. Нельзя выдавать readiness новой продажи TOP до разбора unknown/overbooked legacy services.
- Windows local gates не подменяют Linux/Python3.13/Node22 CI на immutable commit. Исходные production protections PR345/346/348 и approved PR347 не удалены; dependency pins/guarded transport/video код не ослаблены.
- Семь unit skips: три opt-in external research и четыре native FFmpeg/FFprobe проверки, для которых Windows binaries отсутствуют. S3 отдельно проверен в изолированном MinIO. Полный real-native video run остается задачей CI.
- Не выполнялись настоящие Stripe charge/refund, live Google Places E2E, multi-host/multi-process stress, hard-kill сервера, production load/EXPLAIN, полная accessibility/full-site visual сертификация. Публичный CartoCiudad smoke-test проверяет один настоящий адрес и контракт, а не покрытие всех адресов Испании.
- Неизвестный Stripe create outcome сохраняет безопасную reservation/review, не освобождается по локальному TTL; прежний безопасный принцип оставлен. Нового unverified abandon/refund automation не добавлено.

Бизнес-вопросы о муниципалитетах, источнике адреса и способе его проверки решены пользователем; незаданных предположений вместо этих ответов не использовано.

Временные Vite servers4192/4193/4194 остановлены; созданные этой работой PostgreSQL/Redis/MinIO контейнеры удалены после проверок. Рабочие `ttest-*` контейнеры не были целями очистки. Подтверждение: `artifacts/remediation-2026-10-17/cleanup.log`.


## Интеграция с main — 20 октября 2026

PR #360 совмещает муниципальный лимит TOP с тарифами main на 12/24/72 часа.
Доступность, повторная покупка и fulfillment проверяют точный оплаченный интервал;
старые day/month orders сохраняют исходную длительность. Невыпущенная географическая
миграция перенесена в `0065_verified_geography` после существующей
`0064_hourly_promotion_orders`, чтобы сохранить одну линейную цепочку и неизменность
выпущенной истории. Результаты проверок интеграции приведены в описании PR.
