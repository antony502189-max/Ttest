# PR408 — исправления независимого deep review, 04.11.2026

Review относится к `a1e58024621531ded64527aea7da5adbe745690b`, base `ecfe3a7b114c4142b396c2b64a918d34f105e8cf`. GitHub PR open/draft/merged=false и remote refs проверены до правок. SHA256 предоставленного review: `154c6250cf23def40f0192f05a005c3e933da1f6a5717833b6550fddb84964df`; полный внешний документ не публиковался.

Application/test/boundary source: `1542814f7abdf3ab5b7eb237a7ea4e4884b56981`. Работа S2.2/A3/A9, в том же PR и worktree. Два намеренных локальных документа с итогами прошлого CI сохранены и включаются в обновление отчётов.

## Исправления и контракт

**R-01 — side effects.** Публичный `GET /listings/{id}` действительно вызывает `register_view` и может установить `listing_visitor`. Его использование для камеры удалено полностью. `VerifiedCardResult.map_center` теперь содержит только ID проверенной карточки и приблизительные latitude/longitude из `Listing.location`. Читается bounded набор уже возвращённых card IDs в той же read-only REPEATABLE READ транзакции; exact geometry, contacts и detail/gallery не читаются для карты. Новых routes, таблиц, миграций и paid/query операций нет. Пустая страница даёт null. Frontend проверяет принадлежность center к карточкам и допустимость координат; неизвестный/непригодный center даёт overview.

**R-03 — blocking detail.** Карта монтируется сразу. Нет вспомогательного detail GET, его15s timeout, auth refresh и gallery hydration в пути открытия карты. Slow/404/503 detail route вообще не вызывается; map endpoint работает независимо. Базовая карта доступна и при отсутствии metadata. Новый center поступает вместе с уже полученной страницей, без дополнительного HTTP round trip. Это устранение зависимости, не новая provider latency certification.

**R-02 — область после live refresh.** Center страницы передаётся как camera target. Существующий Map/SVG сохраняется. При новом center автоматическая камера следует результатам; после пользовательского pan/zoom камера сохраняется. Если в видимом bbox нет маркеров при положительном total списка, UI объясняет: результаты могут находиться в другой области **или каталог мог измениться**. Кнопка «Mostrar el área de resultados»/lab equivalent возвращает к center страницы, без нового AI query/debit. При total0 нет этой подсказки/кнопки. Новое поведение есть у production и explicit lab alias. Для lab center-aware grid заменяет фиксированный Adeje-origin; lab остаётся без внешних тайлов.

**R-04 — consistency.** Сохранён существующий live-read контракт из `ai_verified_cards.py`: cards и map отдельно перепроверяют текущую eligibility в своих read-only snapshot. `result_ref`/`intent_hash` связывают критерии, **не состав каталога в одну секунду**. Строгий межзапросный snapshot token не был гарантией текущего контура и этим исправлением не вводится. UI теперь явно сообщает: список и карта обновляются отдельно, объявления могут измениться между чтениями, карта показывает только видимую область. География center согласована со страницей cards, но не заменяет live recheck карты. Никакие stale proofs/markers не удерживаются ради искусственного совпадения.

**R-05 — статус.** Датированный итог прошлого CI `a1e58024` (8SUCCESS/2SKIPPED, три skipped Full audit steps) уже сохранён локально в3.6; теперь этот appendix публикуется в Git вместе с fixes. Immutable validation прежних запусков не переписывается: его pending относится к моменту capture. Статус последнего head берётся из [PR checks](https://github.com/antony502189-max/Ttest/pull/408/checks) и датированного PR description, отдельно от historical heads и local PASS. План3.7 не объявляет прошлый CI сертификатом нового source.

## Проверки и evidence

- RED browser на исходном runtime:2FAIL — открытие карты вызывает detail и зависание detail блокирует map read. Новые fixtures уже передавали read-only center, старый frontend его не использовал.
- RED PostgreSQL/HTTP:2FAIL после исправления synthetic email fixture на допустимый домен — отсутствует map_center. Первый development запуск auth case остановился на reserved email domain; этот setup failure не выдан за product finding.
- GREEN: guest/auth HTTP query/cards/map/reload не меняют `Listing.views`/`ListingView`, не устанавливают `listing_visitor`. Два явных detail GET дают ровно1уникальный view. Center равен public approximate geometry, без exact/contact fields.
- Actual PostgreSQL proof-epoch test: после cards200 исходные source proofs изменены; map200 имеет тот же intent_hash и0markers, следующая cards page0/center=null. Parser calls=1, quota used=1. Это подтверждение live recheck и предела hash, не атомарности.
- Focused browser:12production и12alias cases PASS до двух дополнительных fallback cases. Cross-region auto/manual, explicit show-area,0total, catalog change между cards/map, same Map/SVG, viewport request, no extra query/debit, mismatch и race. Full suites включают эти cases и два новых metadata fallback cases; counts не суммируются.
- Backend unit:1752PASS/16SKIP. Targeted actual PostgreSQL/HTTP/cards/map/gallery/views:65PASS/1SKIP. Targeted camera2PASS входят в65. Dense-map skip и warnings отражены в raw XML; это не большой benchmark.
- TypeScript, lint/i18n, Ruff app/tests/lab, mypy175files, migrations head и `alembic check`,5build-mode и provenance947PASS. Общий frontend lint содержит6прежних warnings в других файлах; новых нет.
- Полные browser/lab:93/93 и27/27 PASS на source1542814f. Raw результаты в [validation](pr408-deep-review-fixes-evidence/validation.json); старые84/18 не перенесены на новый source.

Команды: existing `playwright.ai-search.config.ts` и `playwright.ai-lab.config.ts` последовательно; `pytest -q -m 'not integration'`; integration набор `test_ai_verified_cards.py`, `test_ai_http.py`, `test_ai_operating_freshness.py`, `test_listing_gallery_cards.py`, `test_listing_view_limits.py`; `tsc -b`; Oxlint/i18n; Ruff/mypy; existing build matrix/provenance. Raw logs/XML, exact-source caveats и SHA256 — в новом evidence, локальные paths очищены при публикации.

## Среда и оставшиеся границы

Owned PG/PostGIS `ttest-pr408-deep-review-pg`, loopback55443/ttest_test, purpose label `pr408-deep-review`, container `05fcaa8cf44d31852929e700e907f3c7f019859aa18aeab3fa5dfbfc3d8b49a9`. Первый migrate слишком рано попал в старт сервера и не считается PASS; после pg_isready migrations и checks завершились успешно. Container/anonymous volume удалены после завершения всех pytest процессов и schema check с проверкой ID/label. Application/closed-lab containers не менялись. Старый root checkout не переключался; синхронизируется только canonical plan.

Local browser APIs и Maps SDK synthetic; real Google Maps/provider, production catalog, p95/capacity и deployed runtime не сертифицированы. Новых paid calls/crawling/backfill/budget mutations/activation/merge/deploy нет. S2 partial; standing refresh/durability/lifecycle, реальные data/provider/performance/release gates и S3–S7/B2–B6 остаются открытыми. Voice/saved/delivery обязательны.


## После финального exact-head CI

Head `587b5f5322845af40423b97938204b12e00f79ff`: **13workflow runs,11SUCCESS/2SKIPPED**, без failure/cancelled. [Frontend](https://github.com/antony502189-max/Ttest/actions/runs/41880247546), [combined facts/PostGIS/HTTP/browser](https://github.com/antony502189-max/Ttest/actions/runs/41880247381), [Full audit](https://github.com/antony502189-max/Ttest/actions/runs/41880247239), backend quota/sessions, parser foundation и остальные применимые аудиты успешны. Phase2 visual parity и PR298 UI parity skipped. Full audit126750507908 имеет3conditional skipped steps: production deployment configuration, dependency security policy, complete local audit. Их выполнение не заявляется.

Snapshot `output/pr408-deep-final-ci-587b5f53.json`, SHA256 `54f470cbabf460937b4395ced5b619398e10659f27e7360e6325134e6d34939e`. Финальный CI статус опубликован в PR description; appendix и canonical plan сохранены локально без изменения проверенного head. Raw validation остаётся историческим local capture. PR draft/open/merged=false подтверждён после CI; следующее действие — повторное review R01–R05. Merge/deploy не выполнялись.
