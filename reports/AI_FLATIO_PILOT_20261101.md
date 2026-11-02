# Пункт 5: измеренный закрытый Flatio pilot

1 ноября 2026, Europe/Moscow.

**Пункт 5 выполнен в согласованном объёме закрытого Flatio pilot: до 100 публичных
объявлений, без LLM.** Настоящий источник измерен; это не выпуск production,
не сертификация остальных источников и не гарантия свойств жилья на месте.

## Разрешение и границы

Пользователь явно выбрал до 100 публичных объявлений Flatio и согласовал сроки:
raw до 24 часов, очищенные evidence до 30 дней, price/availability freshness
24 часа, остальные policy facts 7 суток. Максимальные сроки хранения не требуют
сохранять данные весь срок: после прогона записи удалены полностью.

Использован существующий Santa Cruz discovery: два публичных sitemap, room и
apartment routes. robots.txt доступен и допускает эти пути; /api, поиск внутренних
фрагментов, auth, browser rendering, contacts/images и обход challenge не нужны.
GET последовательно с интервалом не менее секунды, HTTPS/public network guard,
проверка точного хоста/пути, отсутствие redirects/env proxy, response limit 4 MiB.
Ни ключей, ни внешней модели не было. Public runtime остаётся disabled.

Первый сбор выявил ошибку нового фильтра пилота: сравнение addressRegion только
с canonical province отвергало `Tenerife`. Фильтр исправлен на существующий
`is_in_import_scope` с явно выбранными structured province/city/country, без
street address, coordinates, title/description fallback. Никакие production
eligibility policies не ослаблялись. После исправления повторно проверены те же
73 уникальных объявления; исходный сбор сохранён отдельно как неуспешный этап
admission, а не принятие пустой когорты. Source и selected-fact hashes при
повторном наблюдении 73/73 не изменились. Это несколько минут наблюдения, не
измерение недельной source health.

## Настоящее покрытие

73 обнаружены, 73 успешно прочитаны, 0 HTTP/access failures. Последний сбор:
**1 ноября 2026 01:13:57–01:15:18 Europe/Moscow**. Это census выбранных sitemap
routes в существующем географическом scope, не случайная выборка всего Flatio.

В продуктовый scope проходят **8** записей. Исключения могут пересекаться:
58 — economic guard (месячная цена выше допустимого порога либо неподтверждённая),
30 — не InStock, 26 — тип/размер жилья вне scope, 1 — недостаточно географии.
[Счётчики сбора](ai-flatio-pilot-evidence/collection.json),
[повторное наблюдение](ai-flatio-pilot-evidence/reobservation.json).

| Поле | Подтверждено источником / прочитано | Граница |
|---|---:|---|
| monthly price EUR/MON | 73/73 | offer и specification обязаны совпадать; без конверсии/догадок |
| capacity_total | 73/73 | occupancy.maxValue rented unit; не available_spots |
| furnished | 73/73 | явный structured boolean, включая false |
| bills_included | 73/73 | только explicit utilitiesIncluded |
| amenity: wifi | 73/73 | только propertyID wifi; не все amenities |
| pets | 9/73 | 64 unknown; текстовая policy или неразобранное ограничение блокирует broad guarantee |
| остальные 15 FactKey | 0/73 | unsupported этим mapping; остаются unknown, не разрешёнными |

Evidence хранит исходное boolean/number/whitelisted enum или выбранный JSON
fragment с реальным provider path. Противоречия structured fields объединяются
существующим bridge merge в conflict. Отсутствие поля не превращается в false.
Общий smokingAllowed не задаёт indoors/outdoors scope. InStock не доказывает
свободные места и диапазон дат. Состав жильцов (party) не равен вечеринкам.
Категория, geography/INE, minimum/maximum stay, dates и другие неподдерживаемые
fields не добавляются из legacy/default/marketing значений.

Это измерение опубликованных структурированных утверждений источника, не
оценка всей семантики описаний и не независимая проверка жилья. Полные описания
не сохраняются; grammar используется только как консервативный veto для pets.
Неподдерживаемые текстовые условия не объявляются покрытыми. Отдельная модель
извлечения при необходимости будет запускаться при подготовке facts, не при
чтении карточек, и потребует отдельного согласования payload/расходов.

## Pipeline, proof и недостаток данных

На отдельной PostgreSQL без host ports, в fresh disposable schema выполнены
настоящие FactPipeline.observe → claim → complete → projection → QueryProofs.prepare.
Legacy stand-ins минимальны, AI migrations/SQL настоящие; это не application DB
и не новый browser/HTTP прогон. Все **8/8** допустимых записей прошли pipeline и
подготовку proof. Экономика/public visibility/freshness проверяются до SQL count.

| Критерий на 8 eligible | match | mismatch | unknown |
|---|---:|---:|---:|
| бюджет ≤1000 EUR/monthly | 8 | 0 | 0 |
| бюджет ≤1 EUR/monthly | 0 | 8 | 0 |
| Wi-Fi | 8 | 0 | 0 |
| одна небольшая собака | 3 | 0 | 5 |
| размещение двух взрослых | 0 | 0 | 8 |

Нет совпадений и недостаток подтверждённого inventory различаются. Остальные
buckets этого snapshot — 0; их семантика проверена synthetic goldens. SQL
verified-match count совпал с quality counters во всех пяти сценариях.
[Результат](ai-flatio-pilot-evidence/real-cohort-result.json).

Retirement локальной копии реального sampled source немедленно инвалидировал
proof. Изменение/удаление/remap, цена, time expiry, rollback и reprepare проверены
существующими и новыми synthetic PG cases. Источник Flatio не изменялся этим
прогоном: реальные объявления только читались. Срок 30 дней не выдаётся за
реально выжданные 30 дней; механизм retention/time boundary проверен управляемым
временем на synthetic данных, а новые real evidence до окончания прогона не expired.

## Source и проверки

Проверенный exact source **32b4af3271eb9197a5538a9b3760bad7f6b7bd25**.
Collection source `d48c57fe`: его collector и mapping byte-identical окончательному
source; [attestation](ai-flatio-pilot-evidence/attestation.json).
Все **474 backend files /439 Python** сверены с Git blobs. Linux modes извлечены
из `git -c core.autocrlf=false archive`, lint не ослаблялся.
Pinned tools image sha256:1ff5de84b825934599a53fd69add14bb6784d6399a1464e4a38255b2d234a902.

- **1631 unit PASS /39 optional-platform SKIP**, Ruff PASS, mypy PASS (159 files).
- **290 PG PASS**, включая opt-in real cohort; отдельно real cohort 1 PASS.
- Девять новых mapping goldens: missing, false, deny, conflict, unhandled pets,
  period/currency/price disagreement, scope и sensitive-field minimization.
- Source/mutation/retention/freshness correctness не считается performance release.

[Unit](ai-flatio-pilot-evidence/unit.log), [PG](ai-flatio-pilot-evidence/pg.log),
[Ruff](ai-flatio-pilot-evidence/ruff.log), [mypy](ai-flatio-pilot-evidence/mypy.log).
[Offline harness](ai-flatio-pilot-evidence/offline-checks.py),
[PG harness](ai-flatio-pilot-evidence/pg-checks.py),
[Git blob verifier](ai-flatio-pilot-evidence/verify-blobs.py).
Новый запуск collector — отдельное обращение к изменяемому источнику, а не
воспроизведение прежнего snapshot. Private records не опубликованы, повторять
real этап можно только в разрешённых пределах; тест по умолчанию skipped без
явного AI_FLATIO_PILOT_DATA. Артефакты старых запусков не перезаписывать.

## Удаление и последующие этапы

Raw HTML находился только в RAM; disk raw retention фактически 0. Временный
minimized dataset и все AI schemas удалены; собственные containers и anonymous
PG volume удалены. Сохраняются только агрегаты, код, hashes и test evidence,
без listing IDs/URLs, индивидуальных цен, contacts, descriptions и фотографий.
[Проверка очистки](ai-flatio-pilot-evidence/cleanup.json).

Согласованные сроки применены к этому пилоту. Постоянный real ingestion,
scheduler, удаление legacy raw/backup/export copies, UI wiring новых counters,
другие источники и полноценная operational source health требуют отдельной
интеграции; этот этап их не активирует. Продуктовые и эксплуатационные правила
остаются в пункте 6, общая приёмка/выпуск — в пункте 7.

Можно возвращаться к пункту 4: live intent/model quality пока не измерены,
provider calls для intent в этом чате = 0. Пункт 3 пропущен, ISSUE-004 OPEN /
capacity BLOCKED. Draft PR #403, no merge/public AI/deploy.
