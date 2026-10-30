# Исправления post-merge аудита main

База аудита: `7d4c125574927181511c5f1bc7e201e20a8840a8`.
Исходный отчёт остаётся историческим документом; этот файл описывает remediation.

## CI, адреса и release evidence

`scripts/start-fullstack-audit.sh` — общий PR/main test-only launcher. Он применяет
`docker-compose.fullstack-test.yml` и для старта backend, и для seed; production
image/Compose и строгая проверка адреса не меняются. Оба audit entrypoint вызывают
этот launcher. Регрессия исполняет его с fake Docker/curl и сверяет аргументы.

`AI Search combined facts quota sessions` и `AI Search private frontend` теперь
запускаются на каждом push в main без path filters. Первый включает настоящий
HTTP/frontend recovery и guest-cookie browser test. Широкие backend/marketplace,
publication/auth и mobile browser проверки остаются в Full audit: дублировать
все тяжёлые PR workflows на main не требуется.

Manual production workflow по-прежнему требует явного deploy confirmation и
успешных проверок merged PR. Дополнительно `verify-main-checks.py` требует
успешные **последние** push runs на точном main SHA: Full audit, Security audit,
Capacity smoke safeguards, оба AI workflow. Учитываются workflow path, branch,
event, SHA, номер запуска и попытки. Отсутствующий/старый/PR-only/queued/failed/
cancelled/skipped run блокирует release. Страница optional Pages в этот gate
не входит. Изменения не запускают production deployment.

## Карта

Все локальные writers карты используют `commitMapRoute`: URL ref публикуется
до вызова Router. Camera idle ссылается на тот же актуальный route; после выхода
в List/Filters он отбрасывается. Новые tests принудительно доставляют idle между
semantic route push и React commit для Search this area, List и Filters.
Дизайн и значения фильтров не меняются.

## Необязательный Pages preview

Build/lint/typecheck preview исполняются всегда. Configure/upload/deploy требуют
repository variable `PAGES_PREVIEW_ENABLED=true`; без неё workflow явно сообщает,
что публикация отключена, и не обращается к отсутствующему Pages site. Если
владелец хочет preview, он сначала настраивает Pages для GitHub Actions, затем
включает переменную. Включённый, но неправильно настроенный Pages по-прежнему
даёт ошибку: 404/permissions не маскируются. Настройки GitHub здесь не менялись.

## Capacity: проверка готовности и отдельный запрос на ресурсы

`scripts/check-ai-map-capacity.py EVIDENCE_DIR --expected-sha MEASURED_SHA`
пересчитывает v2 evidence из raw attempts/plans/resources/manifests. Он требует
совпадения измеренного source SHA, `protocol_complete=true` **и** `slo_passed=true`.
Один только exit0 summarizer означает полноту протокола, не прохождение SLO.
Поддельный/старый summary.json, незавершённый масштаб и raw failures не проходят
приёмку. Эта команда ничего не включает и не выполняет нагрузку.

**ISSUE-004 нельзя закрыть без новых реальных измерений.** Малые тесты и новый
acceptance gate не заменяют результаты. 30 октября 2026 владелец отдельно
разрешил описанный ниже изолированный прогон («Разрешаю указанный изолированный
прогон»). Это разрешение относится только к synthetic lab и не включает public AI.
Протокол: [MAP_CAPACITY_PROTOCOL.md](ai-search-developer/MAP_CAPACITY_PROTOCOL.md).

Проверяемый план такого разрешения:

- отдельная новая synthetic lab, отдельные network/container/experiment IDs;
  существующие application/staging/production/старые benchmark DB не используются;
- PostgreSQL16/PostGIS3.4 pinned image, internal network, без published DB ports;
- DB: **8 CPU / 8 GiB RAM**, driver: **2 CPU / 2 GiB RAM**, pool30;
- запас диска перед стартом: **100 GiB**; измерения отдельно от browser/CI нагрузок;
- масштабы **100k / 500k / 1m**, 10 synthetic provider identities,
  20 observations/listing, baseline 2 source records/listing;
- concurrency50/100/200, viewport300/10k/all, zoom8/13, 200 attempts/case либо
  предусмотренная протоколом полностью failed первая волна; без исключения ошибок;
- raw/manifests/source hash, actual/estimated планы, dataset stability locks,
  resource monitor и cancellation/pool-reuse evidence — по действующему протоколу;
- критерии: p95≤500ms, p99≤1000ms, без ошибок; всё пересчитывается acceptance gate;
- никаких реальных providers/ASR/crawls/payments/notifications/публичного AI.

Launcher и monitor принимают `-LabId` для новой namespace; без него сохраняется
старое поведение. Launcher дополнительно принимает `-DependencyImage`, разрешает
его в immutable image ID и связывает ID с experiment provenance. Проверки
internal network, pinned DB image, exact DB/container identity и resource limits
сохранены. Новые measurements не должны переиспользовать исторические 20261028 DB.

Первый новый initialize выявил старый дефект benchmark guard: открытая
транзакция с advisory lock удерживала snapshot и блокировала concurrent index
migration. Initialize теперь удерживает session advisory lock в AUTOCOMMIT;
namespace блокировки общий с seed/measure, взаимное исключение сохраняется.
Измерение по-прежнему держит transaction advisory lock и SHARE freeze всех
таблиц. Реальные PG tests проверяют concurrent index внутри guard, исключение
параллельного seed и освобождение lock при успехе/ошибке; suite22 passed.
Прерванный initialize сохранён отдельно и не является capacity measurement.

В следующей новой lab seed100k завершил загрузку и проверку production digest,
но подготовительный VACUUM ANALYZE получил lock timeout1s, общий с query engine.
Для этого единственного maintenance statement задано ограниченное ожидание60s;
прежний timeout восстанавливается при успехе и ошибке. Измеряемые SQL сохраняют
свои прежние лимиты. PG regression воспроизводит конфликт
ShareUpdateExclusive дольше1s и проверяет восстановление настройки также после
statement cancellation; полный toolchain suite24 passed. Этот неуспешный seed
тоже сохранён отдельно; новые измерения выполняются в следующей свежей lab.

В lab1632199c на source9c9a520c завершены этапы100k/500k с полными
attestations, но SLO провален. Набор1m создан и проверен при seed, однако
measure прерван до первого map-запроса: предварительный count20m facts
унаследовал measured statement timeout5s. Обе попытки, paired monitor events
и failed manifests сохранены. Отдельный read-only EXPLAIN count занял3.435s;
это диагностический прогон с другим timeout, не capacity result.

Предварительная проверка набора теперь выполняется в отдельной repeatable-read,
read-only транзакции с SET LOCAL statement_timeout60s. После выхода прежний
лимит measured engine5s восстанавливается автоматически, включая ошибки.
Отдельные PG tests доказывают успешное выполнение validation дольше исходного
таймаута, read-only snapshot и реальный timeout последующего query на той же
pool connection. ANALYZE и VACUUM ANALYZE используют maintenance wait60s.
Измеряемые запросы и пороги SLO не изменены. Для полного нового протокола
используется следующая свежая lab с новым source SHA; данные и timings старых
экспериментов в неё не переносятся.

Это большой прогон с возможной длительностью в несколько часов. Даже успешный
synthetic capacity не разрешает публичный AI: privacy/retention/freshness,
runtime policy и provider rollout остаются отдельными согласованиями.
