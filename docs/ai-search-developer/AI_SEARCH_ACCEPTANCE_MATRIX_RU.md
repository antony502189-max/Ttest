# S1.1 — исполнимая матрица A1–A12

Единственный маршрут работ — [единый план](../ai-search-completion-plan.md).
Эта матрица связывает приёмочные критерии с существующими тестами и фиксирует пробелы, а не заменяет план.
База: merged main `ece1632e2872240a36646ddf0b2518a027d67d84` (#404).

Машиночитаемый источник: [acceptance-matrix.v1.json](acceptance-matrix.v1.json).
У каждого A-критерия есть этап S, наборы тестов и незакрытые требования. В `suites` указаны точные пути, среда и предел доказательства.
Все A1–A12 остаются частично выполненными: успешный локальный прогон не переводит продуктовый критерий в PASS.

## Запуск

Из корня актуального checkout, Python 3.12+ с зависимостями `backend[dev]` и установленными Node/npm-зависимостями:

```powershell
python scripts/ai-search-acceptance.py
python scripts/ai-search-acceptance.py --run unit --output output/ai-search-s1/unit.json
python scripts/ai-search-acceptance.py --run mock-browser --output output/ai-search-s1/browser.json
python scripts/ai-search-acceptance.py --run unit --criterion A6 --output output/ai-search-s1/voice.json
```

Без `--run` проверяются структура A1–A12 и наличие всех ссылок. Запуск выбирает только соответствующие наборы; остальные получают `not_run`.
Отчёт сохраняет HEAD, dirty status, Python, SHA256 входов, команды, логи, результаты и оставшиеся gaps. Он всегда содержит `product_acceptance=false`.
`unit` использует synthetic fixtures/MockTransport/временные журналы, `mock-browser` — существующие отдельные Playwright-конфигурации.
Применяемый Python выбирается самим вызывающим процессом; PYTHONPATH указывает на backend текущего checkout.

Наборы `disposable-service` описывают существующие реальные SQL/HTTP тесты. Их команды и loopback test DSN/Redis окружение уже закреплены в `.github/workflows/ai-search-facts.yml`; матрица их автоматически не запускает и не изменяет схему сервера.
Наборы `gated` связывают существующие full-stack/provider/capacity drivers. Их наличие не разрешает новый LIVE, paid calls, работу с настоящим budget journal, outbound, ingestion или production.

## Обязательные критерии и текущие доказательства

| ID / этап | Исполнимые наборы | Что ещё требуется |
| --- | --- | --- |
| A1 / S3.4 | intent, facts, facts-pg, real-provider | Настоящая модель ES/RU/EN → все typed fields → SQL IDs/причины на пригодном каталоге |
| A2 / S3.4 | intent, quota-pg, real-provider | Настоящие follow-up/отрицания/ambiguity/unknown/conflict/no-change/unsupported без потери hard |
| A3 / S2.2–S2.3 | facts, facts-pg, http-pg, browser | Реальные coverage/freshness/update/retirement; сохранение TOP/boost/native/external/gallery/favorites/€1000 cap |
| A4 / S3.2 | quota, quota-pg, closed-stack | Guest3/auth200, Madrid/DST, eligible zero=debit1, no-coverage/error=no debit в целевой runtime |
| A5 / S3.2–S3.3 | quota-pg, http-pg, browser, pairing, closed-stack | Целевая ownership/retry/reload/timeout/login/logout/ACK recovery с настоящими зависимостями |
| A6 / S4.1 | voice, quota-pg | Real ASR+microphone/UI/HTTP/media/codecs/duration, смешанная речь; Send→cards и один debit |
| A7 / S4.2 | saved, quota-pg, http-pg, browser | Public owned snapshot create/retry/disable и UI после регистрации; нынешний UI покрывает list/delete |
| A8 / S4.3 | saved, quota-pg, http-pg | Rematch/delivery worker, fencing/retry/idempotency/live eligibility, disable/delete races и отсутствие дублей |
| A9 / S4.4 | browser, pairing, http-pg, closed-stack | Расширить 12 locale/viewport text smoke до всех состояний/error/retry/a11y/voice/save/register |
| A10 / S5.2–S5.3 | operations, capacity | Browser voice p95≤10s; отдельный SQL/map p95≤500ms,p99≤1000ms,0 ошибок,100k/500k/1m,c50/100/200 |
| A11 / S6.1–S6.2 | operations, facts-pg, http-pg, closed-stack, real-provider | Provider/account/privacy, real catalog, production migrations/backup/erasure/supervision/telemetry |
| A12 / S7.1–S7.3 | closed-stack, real-provider, capacity | Deployed SHA/capabilities, A1–A11, реальный pilot и согласованный период наблюдения |

## Связь с существующими fixtures и drivers

- `backend/lab/intent_cases.v1.json`: исторический corpus 24, ES/RU/EN. Это ограниченный synthetic eval, не исчерпывающая приёмка всех supported fields. Новая матрица не меняет corpus/допуск или бюджет прежнего эксперимента.
- `backend/tests/fixtures/ai_hard_match/synthetic.json`, `backend/tests/ai_facts_pg/typed_match_cases.py`: typed SQL/unknown/conflict fixtures; не рабочий каталог.
- `backend/tests/ai_search_pg/test_voice_execution.py`: ASR+intent fake в одной durable operation, replay/debit/faults; не browser microphone и не реальный ASR.
- `backend/tests/ai_search_pg/test_saved_searches.py`, integration saved/review: owned snapshots/CAS/ACK/retry/dry-run. `test_ai_saved_search_boundary.py` проверяет, что AI/неизвестные matcher не попадут в legacy delivery; это не работающий AI delivery.
- `scripts/accept-ai-text-lab.mjs`, `accept-ai-parser-ui.mjs`, `accept-ai-release.mjs`, `accept-ai-release-ops.mjs`: готовые synthetic stack drivers, повторно не создаются.
- `tests/ai-home-search.spec.ts`: существующие recovery/map/cards contracts расширены 12 A9 cases (ES/RU/EN × 320/390/768/1440), включая локализованные доступные имена, единственный query POST, empty result, отсутствие горизонтального overflow, возврат фокуса и доступность обычного поиска.

Не закрыты и не ослаблены provider/data/performance/release gates. Нет новых реальных calls или уведомлений.

## Точный охват прежнего intent corpus v1

Это инвентаризация сохранённых expected criteria, **не** новый semantic/model прогон.
ES: 7 cases (balcony/budget/pets); RU: 8 (balcony/budget/furnished/party/pets);
EN: 8 (balcony/budget/furnished/party); смешанный ES/EN: `mixed-two-criteria`.
Всего 24. Исходные IDs/тексты/expected/rejections остаются в неизменённом JSON.
Успешные expected cases не покрывают на всех языках geography/accommodation/smoking/
amenities/bills/deposit/dates/stay/rental_mode и комбинации условий. Отдельный conflict-dates
не доказывает успешный поиск по датам. Дальнейшее расширение corpus относится к S3.4;
прежний closed LIVE admission автоматически на новые cases не распространяется.
