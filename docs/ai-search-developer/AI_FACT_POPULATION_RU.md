# Производительность: версия каталога фактов

31 октября 2026. Первый отдельный результат пункта 3; ISSUE-004 остаётся OPEN.

## Изменение

До этого каждое чтение AI-карточек считало `count(*) / sum(revision)` по всей
`ai_fact_catalogs` для подписи курсора. Теперь миграция
`0076_ai_fact_population` устанавливает singleton `epoch/revision`, который
читается за постоянное число строк. Новая зависимость включена в подписанный
контекст курсора; прежние курсоры после обновления требуют начала с первой
страницы. Повторный inference или списание для обновления результата не нужны.

Statement triggers меняют версию в той же транзакции, что и каталог. Покрыты
INSERT, UPDATE, DELETE, COPY, ON CONFLICT и TRUNCATE, включая прямой SQL.
Пустые операции и идентичные UPDATE/upsert не меняют версию. Перестановка
ревизий с прежними count/sum и восстановление старых значений консервативно
инвалидируют курсор. Rollback/savepoint возвращает прежний контекст.

Отсутствующая служебная запись не разрешает чтение карточек: repository
выбрасывает ошибку. Следующая изменяющая каталог операция создаёт новую запись
со случайным epoch, поэтому старый курсор не оживает. Удаление/изменение самой
служебной таблицы или отключение триггеров привилегированным администратором
не являются поддерживаемым способом редактирования каталога.

Миграция не сканирует и не переписывает существующий каталог. Она держит
`SHARE ROW EXCLUSIVE` lock во время установки состояния и триггеров. Старый
бинарный код продолжает читать count/sum; добавленная таблица при rollback
сохраняется. Это не разрешение применять миграцию к application/production DB.

## Что остаётся на пути чтения

Это идентичность каталога для пагинации, а не версия актуальности объявления.
Полный `query-proof.v2` digest продолжает проверять источники, canonical/room,
facts/batches/projection и remap/delete. Public eligibility, moderation, blocked
owners, время действия TOP/freshness и текущие цены также проверяются перед
count/order/seek/LIMIT и агрегацией карты. Карта этим изменением не ускорена.

Поток записи получает дополнительную блокировку одной строки на изменяющий
statement. Это осознанный обмен полного сканирования при каждом чтении на
транзакционную запись версии. Высокая пропускная способность импортера и
конкуренция записей этим небольшим тестом не сертифицированы.

## Воспроизведение

Использовать отдельную disposable loopback PostGIS DB с именем
`ai_facts_test_*`, без application data. Зависимости из `backend[dev]` с
`backend/constraints.txt`. Обычный runtime остаётся disabled.

```powershell
$env:APP_ENV = 'test'
$env:AI_FACTS_TEST_DATABASE_URL = 'postgresql+psycopg://ai_lab:ai_lab@127.0.0.1:5432/ai_facts_test_population'
python -m pytest -q -s backend/tests/ai_facts_pg/test_fact_population.py backend/tests/ai_facts_pg/test_combined_schema.py
```

В выводе `FACT_POPULATION_BOUNDED_PLAN` сохранены настоящие
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` старого и нового запросов на 4096
синтетических строках. Тест проверяет число прочитанных строк, не порог latency.
Это маленькая диагностика, не concurrency/capacity/SLO acceptance.

При запуске Linux-тестов из Windows собирать снимок командой
`git -c core.autocrlf=false archive HEAD`, чтобы Bash получал LF и реальные
Git modes. Windows bind mount показывает executable bit у обычных файлов и
не подходит для проверки Ruff EXE; проверять извлечённый Git archive.

Полный исторический migration chain, `alembic check`, unit и existing
card/map/HTTP/ownership/quota tests выполняются дополнительно. Итоговые
результаты и exact source: [отчёт](../../reports/AI_FACT_POPULATION_20261031.md).

## Следующий основной прототип

Для устранения live digest нужен отдельный контракт атомарной инвалидации,
который пока не реализован и не включён:

| Зависимость | Что должно инвалидироваться в транзакции записи |
|---|---|
| canonical/room | Старый и новый listing ID; прямой SQL, удаление, изменение любых проверяемых полей |
| external source | Текущий/бывший canonical и все ранее связанные AI source identities; remap/delete и новые связи |
| AI sources | Старые/новые canonical, source record и batch associations |
| facts/batches | Все canonical, ссылающиеся на старый/новый batch, без доверия заявленному canonical внутри payload |
| projection/catalog | Старые/новые listing ID, смена generation/resolver/vocabulary и удаление |
| public eligibility | Живые условия moderation, owner/block, price и time-dependent TOP/freshness до любого count/LIMIT/aggregate |

Нельзя заменить перечисленное текущим singleton. Особенно нужно доказать
конкурентное создание/перенос связей: чтение зависимостей из триггера без общей
синхронизации может пропустить незакоммиченную связь. Для prepare нужен CAS
по тому же атомарному состоянию, включая rollback/cancel и неизвестный commit
acknowledgement. Отсутствующая/устаревшая версия должна исключать объявление.

После bounded correctness tests и реальных планов можно отдельно оценивать
новый exact SHA на свежем synthetic dataset по согласованному протоколу.
Исторические timings не переносятся; новые большие нагрузки этим шагом
не запускались. [План](AI_CONTOUR_ROADMAP_RU.md),
[протокол capacity](MAP_CAPACITY_PROTOCOL.md).
