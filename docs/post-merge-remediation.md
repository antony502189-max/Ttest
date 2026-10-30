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
acceptance gate не заменяют результаты. Старое stop instruction сохраняется до
отдельного явного разрешения владельца, как требовалось в исходном audit prompt
и [MAP_CAPACITY_PROTOCOL.md](ai-search-developer/MAP_CAPACITY_PROTOCOL.md).

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

Это большой прогон с возможной длительностью в несколько часов. Даже успешный
synthetic capacity не разрешает публичный AI: privacy/retention/freshness,
runtime policy и provider rollout остаются отдельными согласованиями.
