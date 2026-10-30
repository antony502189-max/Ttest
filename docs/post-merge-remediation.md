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

В следующей lab1548ec6b source8346a1b9 прошёл весь seed/preflight100k,
но строгая приёмка отклонила одну load-волну: wall-clock интервалы оказались
короче perf_counter длительностей примерно на4.416s. Raw timing не исправлялся;
seed500k остановлен через SIGINT после выявления несогласованности, trigger
восстановлен в finally, manifests и monitoring сохранены. Приёмка осталась FAIL.
Новые timestamps используют UTC anchor при старте процесса плюс elapsed
монотонного таймера; исходные wall-clock значения также сохраняются.
Monitor применяет тот же принцип. Проверка consistency/SLO не ослаблена.
Следующая свежая lab не переиспользует данные предыдущих запусков.

Дополнительные forced Back cases выявили ещё две формы ISSUE-002: браузерный
Back на тот же q и fallback Back прямой ссылки. History уже меняет URL, пока
HashRouter ещё не выполнил render; поздний idle возвращал старую map route.
Camera/polygon callbacks теперь также сверяют route authority с фактическим
hash URL браузера. Оба reproduction сначала FAIL, после исправления все пять
forced idle cases прошли по два раза. Актуальные architecture/database/index/
troubleshooting ссылки обновлены до0074; датированные snapshots сохранены.
Суперседированный Back/hash переход также сбрасывает pending camera route и
ожидающий camera update, сохраняя возможность запомнить следующую область.
Финально:18 forced idle/recall checks passed (три повтора),67 map/navigation
tests passed,168 toolchain/PG contracts passed +28 Windows checks отдельно;
lint/typecheck/build passed. Пересекающиеся suites не суммируются как уникальные.

Это большой прогон с возможной длительностью в несколько часов. Даже успешный
synthetic capacity не разрешает публичный AI: privacy/retention/freshness,
runtime policy и provider rollout остаются отдельными согласованиями.

## Итог авторизованного прогона

Source `6548a2aeccb65d1bdec13d40cf9d0e43bd22b13c`, experiment
`aa2f9d3367a44c42acde8ce8b29ee220`: **protocol COMPLETE, SLO FAIL**.
100k: 2 504 ошибки / 3 600 попыток; 500k: 1 684 / 2 600; 1m: 1 697 / 2 600.
Ни один из 54 сценариев не прошёл SLO. Все seed/load/plan/resource/stability/
cancellation attestations подтверждены, warnings отсутствуют; acceptance exit 1.
Первый start measure 1m остановлен NOWAIT guard из-за autovacuum до timed SQL;
после завершения обслуживания повторена только measure-фаза с новым run ID.
Сравнение timestamp в обвязке переведено на DateTimeOffset без изменения данных.

Дополнительно профилированы реальные card-cursor aggregates на 1m. Один
proof_population_signature занимает 2.55–5.86 s при concurrency 1; этот
diagnostic profile не сертифицирует полный card/HTTP путь.
Все lab DB остановлены, public AI не включался. Performance blocker остаётся
открытым; зелёный CI не является разрешением на активацию.

[Отчёт исправлений](../reports/POST_MERGE_REMEDIATION.md),
[подробные замеры](../reports/AI_MAP_CAPACITY_REMEDIATION.md),
[raw archives и hashes](../reports/post-merge-remediation-evidence/capacity-evidence-index.json).

## Последующая SQL-диагностика и исправления, 31 октября

После завершения baseline в `2dc411f4` устранены две подтверждённые лишние
операции: canonical whole-row to_jsonb восемь раз на digest и flattening proof
EXISTS в hash join, сканирующий весь proof catalog и повторяющий digest.
LIMIT/OFFSET query boundaries сохраняют ровно тот же v2 JSON/digest и
correlated PK lookup; correctness guards остаются до count/order/LIMIT.
Регрессии проверяют независимый старый digest в трёх timezone, minimal/extended
legacy schemas, отсутствующие canonical rows, bookkeeping, remap/delete,
конкурентный CAS и actual EXPLAIN с 2048 unrelated proofs.

235 fact/proof, 57 cards/map/saved-search integration, 1565 unit и 10 capacity
acceptance/safety tests passed; 31 unit skips (28 Windows-only + 3 opt-in).
Ruff/mypy PASS. Test Redis был поднят после setup connection-refused;
последующий интеграционный прогон успешен.

Bounded sequential diagnostic на уже созданной synthetic 1m DB не менял
данные и не выполнял новый большой нагрузочный прогон: concurrency 1,
viewport 0/300/302, два повторения на каждый из старого и нового source SHA,
SHARE freeze, readonly query transactions, private network и прежние limits.
Exact source archives экспортированы через git archive, старый hash совпал
с исходным experiment. Raw capacity directory доступен driver только readonly;
новая диагностика записана отдельно. Первую попытку остановила strict JSON
валидация входа до map SQL; после использования model_validate_json измерение
прошло. Все предыдущие файлы сохранены локально, timings не исправлялись.

При 300 кандидатах второй запрос ускорился 2544.2→361.5ms; actual EXPLAIN
2587.008→349.226ms. Scan 1000001 proof rows заменён на 300 PK lookups.
При 302 кандидатах запрос всё ещё занимает 2076.2ms; cluster-statement JIT
1416.251ms из 1698.023ms execution — отдельное подтверждённое узкое место.
Membership/counts/остальные поля совпали; floating-point AVG координат отличается
максимум на 7.11e-15 градуса. Это не p95/p99 и не SLO certification.
Cursor population aggregate не изменён. ISSUE-004 остаётся OPEN.

В `e5b7f098` исправлена также устаревшая рекомендация summarizer: она больше
не объявляет любой новый запуск неизмеренным после UNION. Каждый результат
ограничен собственной source provenance. Критерии и приёмка не ослаблены.
[Новые raw/JUnit и hashes](../reports/post-merge-remediation-evidence/proof-optimization-evidence.json).

## Продолжение ISSUE-004: JIT, карта и cursor population

31 октября работа продолжена в том же draft PR по ранее данному разрешению
на новый изолированный 100k/500k/1m прогон. Merge и публичная активация запрещены.
Новые результаты должны относиться к новому exact source SHA и свежему dataset.

AI card/map transactions применяют `SET LOCAL jit = off`; настройка автоматически
восстанавливается при commit/rollback/cancellation и reuse pool. Benchmark
фиксирует dispatch и включает его время в query_ms/total; EXPLAIN использует ту
же настройку. Deadline5s, pool30 и SLO не изменены.

На zoom≥13 карта один раз материализует полностью проверенное множество,
затем возвращает маркеры при count≤300 либо агрегирует кластеры. Вторая проверка
того же множества после probe устранена. Все guards остаются до count/агрегации.

Миграция `0075_ai_proof_population` заменяет полное чтение proof-множества для
cursor context на O(1) epoch/revision. Транзакционные statement triggers на
`ai_query_proofs` покрывают INSERT/COPY/bulk, ON CONFLICT, UPDATE, DELETE и
TRUNCATE, включая direct SQL. Номер меняется один раз на statement; идентичная
подготовка не меняет его. Конкурентные записи сериализуются на одном counter;
rollback откатывает proof и counter вместе, RR snapshot видит согласованную пару.
Пропавший counter блокирует query; пересоздание получает новый epoch.

Это версия **подготовленного proof-множества**, не cache live eligibility.
Источники, canonical/room, batches/facts, remap/delete по-прежнему проверяются
полным `query-proof.v2` digest на каждом запросе до count/order/LIMIT. Для них
новые writer hooks не требуются: механизм актуальности не заменён версией.
Нет TTL или зависимости от reconciler. Изменения другого resolver/vocabulary и
восстановление прежнего множества консервативно сбрасывают cursor; прежний
aggregate при восстановлении множества мог сохранить cursor. Старые cursors
после rollout отклоняются из-за смены формата context.

Полный повторный capacity ещё не подтверждён; ISSUE-004 остаётся OPEN.
