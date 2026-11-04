# PR408 — исправления внешнего review, 04.11.2026

Проверенный исходный head: `857bafa9beff2b40264c13c788c04866f8c94adb`, base `ecfe3a7b114c4142b396c2b64a918d34f105e8cf`. GitHub PR open/draft/merged=false и ls-remote сверены до изменений; concurrent changes не было. Исправления: source `c2e932fd3670ad294bd6ed2623bab539e30a2c56`. Scope: S2.2/A3/A9, без нового roadmap.

## Findings

| ID | Причина и исправление | Проверка и предел |
| --- | --- | --- |
| F-01 | Lab alias игнорировал refreshVersion. `src/lab/ai-synthetic-map.tsx:6` принимает prop, effect на строке25 зависит от него; abort, zoom и offset сохранены | Настоящий Vite `ai-synthetic-lab` alias, mocked API: исходный runtime RED по отсутствующему fresh-source. Runtime regressions проверяют same-ref/hash, один новый POST после refresh, cards503 без нового POST, поздний старый ответ, сохранение SVG/zoom/offset |
| F-02 | Предсуществующий дефект воспроизведён с Tenerife history и Madrid-only API. Карточки намеренно не имеют координат: `ai-result-map.tsx:16` при открытии нового результата читает existing public detail первой карточки, использует только approximate coordinates. `results-map.tsx:361` выбирает initial camera для independentSearch; обычная карта сохраняет старый маршрут выбора | До fix RED: Madrid marker отсутствует при bbox старой камеры. Новый тест утверждает Madrid center, видимость только при попадании в bbox, реальный SDK bounds/zoom и identity/camera после ручного pan+refresh. Один дополнительный first-card public-detail read при открытии карты; abort передан через existing getPublicListing. Новых API/schema нет |
| F-03 | Ошибка map после успешных cards оставляла только предложение двигать карту. `results-map.tsx:152,881` добавляет loading/error/read-only retry для serverSource; lab имеет аналогичный retry | Cards200 → map503 → retry200; старые маркеры очищаются, камера сохраняется, нового query/debit нет. Retry не представляет stale markers как свежие. Использованы существующие кнопки/переводы; CSS не менялся |
| F-04 | Один hash для двух разных intents делал fixture нереалистичной. `tests/ai-home-search.spec.ts:400` строит разные SHA256 от synthetic v1/v2; каждый query/cards/result/map получает согласованный hash | Утверждаются различие hashes, expected_version0/1, разные operation keys, порядок и число map POST. Старый v1 hash на v2 map отвергается, маркеров нет. Это synthetic binding contract, не сертификация Python canonical encoder или model semantics |
| F-05 | Старые mocks отдавали marker при любом viewport и не проверяли identity/camera | Новый `tests/ai-map-refresh-review.spec.ts:97`, включён в обе конфигурации.5cases ×2runtime variants,390px: success/cards503/late/map503/mismatch; геометрический bbox filter, точный request body, SDK bounds/center/zoom, same Map object или same SVG, offset, list/map toggle, query=1/remaining=2. Stock Test SDK имеет фиксированные bounds; только эта fixture связывает их с фактическими center/zoom, production SDK не менялся |
| F-06 | Локальный workspace prefix попал в red.log | Prefix заменён на `<workspace>`, полезный stack сохранён; validation содержит исходный digest, причину преобразования и новый artifact hash. Старый run не пересоздавался и не выдан за новый. Проверены остальные текстовые PR408 evidence на local user paths и common credential patterns:0matches; это scoped scan, не аудит всего репозитория |
| F-07 | На момент первоначального отчёта CI ещё шёл | GitHub независимо подтвердил для857bafa9:10runs,8success/2skipped; Full audit job126639884201 имеет три skipped conditional steps. Исторический CI snapshot сохранён отдельно. Он не сертифицирует новый c2e932fd или последующие docs heads |

## Локальные проверки

Команды выполняются из existing worktree, Node24/Playwright1.61.1; node bin добавлен в PATH. Все внешние browser requests блокируются fixture; providers/настоящие источники не вызываются.

- `node node_modules/typescript/bin/tsc -b --pretty false`: exit0.
- `node node_modules/oxlint/bin/oxlint`: exit0,6старых warnings в других файлах; новых warnings в изменённых файлах нет.
- `node scripts/check-i18n-source.mjs`: exit0.
- `node scripts/test-ai-lab-input-policy.mjs`: exit0.
- `node scripts/verify-ai-lab-provenance.mjs ...`: exit0,947inputs, historicalEvidenceAppliesToCurrentRuntime=false.
- `node scripts/check-ai-lab-builds.mjs output/pr408-review-build-matrix`: exit0,5/5, включая production и explicit lab. Два сообщения invalid config — ожидаемые negative cases.
- Focused production tests:6PASS (five viewport cases + repaired journey), включая mismatch/retry. Финально на c2e932fd:84/84browser и18/18lab PASS (13прежних pairing +5новых alias runtime cases). Raw logs, hashes и source caveats — в [validation](pr408-review-fixes-evidence/validation.json); focused cases входят в полные counts.

Прежние79PASS не перенесены на изменённый source. В процессе разработки исправлены fixture JSON public detail (обязательный amenities array) и ожидание завершения lab pan перед подсчётом запросов; эти ошибки не выданы за product findings. Ранний параллельный запуск двух Vite modes дал startup blank page; финальные режимы запускаются последовательно. Stock SDK fixed-bounds shortcut заменён только в focused fixture. Принятый RED F-02 — повтор после исправления формата saved history и camera-dependent bounds.

Backend/PostGIS tests локально не запускались: backend/schema не менялись, application/lab containers не трогались. Backend bbox/intent binding сверены по `ai_verified_cards.py:193`; прежние backend PASS остаются историческими. Новая CI/backend проверка учитывается отдельно по exact head.

## CI и границы

Для исходного857bafa9: [frontend](https://github.com/antony502189-max/Ttest/actions/runs/41848788835) и [Full audit](https://github.com/antony502189-max/Ttest/actions/runs/41848788798) SUCCESS. Skipped workflows: Phase2 visual parity и PR298 UI parity. Skipped Full audit steps: production deployment configuration, dependency security policy, complete local audit. Эти три шага не заявляются выполненными.

CI исправленного head фиксируется отдельно; до финального snapshot новый exact-head PASS не заявляется. PR остаётся draft, merge/deploy не выполняются. Дополнительное чтение public detail может завершиться ошибкой или не дать координат: тогда AI карта использует общий Spain/Canaries overview, а не предыдущую ручную область. Центр первой карточки не обещает охват всех результатов нескольких регионов. Bbox-empty не переименован в отсутствие результатов запроса.

S2 partial; standing refresh/durability/lifecycle, real coverage/provider/data/performance/release gates и S3–S7/B2–B6 OPEN. Voice/saved/delivery обязательны. Ни платных calls, crawling/backfill, budget mutations, больших benchmarks, activation, ни изменений дизайна/production data не выполнялось.
