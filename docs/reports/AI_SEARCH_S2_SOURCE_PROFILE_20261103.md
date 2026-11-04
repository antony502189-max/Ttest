# S2.1 — профиль источников и недостающие измерения, 03.11.2026

База: merged main `ece1632e2872240a36646ddf0b2518a027d67d84`.
Использованы существующие offline primitives, новая система аудита не создавалась.
Результаты: [profile.json](ai-search-s2-profile-20261103-evidence/profile.json),
[synthetic audit](ai-search-s2-profile-20261103-evidence/synthetic-audit.json),
[source/field capabilities](ai-search-s2-profile-20261103-evidence/offline-field-capabilities.json).

Из пяти fixture source records выбран существующим auditor только active subset:4.
Idealista/Flatio/Habitaclia/Fotocasa имеют по1 active synthetic record; removed Idealista исключён;
остальные source adapters имеют нулевой fixture denominator. Это не количество объявлений на сайте.
Explicit в legacy description audit не означает public/eligible/verified AI projection.
Наличие координат не означает подтверждённый регион. Реальные public/eligible/verified/unknown,
regional breakdown и freshness оставлены **null / не измерено**, а не0 или100%.

| Источник / слой | Что подтверждено сейчас | Что требуется для S2.1 |
| --- | --- | --- |
| Flatio |1 synthetic active row; исторический разрешённый pilot73/8, индивидуальные данные удалены | Новый разрешённый актуальный snapshot/деноминатор по выбранным регионам и полям; standing-ingestion scope |
| Idealista/Habitaclia/Fotocasa | По1 synthetic active row; audit различает explicit/unknown/conditional/conflict | Source-specific current mapping/evidence, coverage/freshness и разрешённый scope |
| Остальные adapters | Только наличие класса в исходниках, real mapping/coverage unknown | Подтверждение каждого source→field mapping до обещания покрытия |
| Bridge text | pets/children/couples/smoking/capacity_total при reviewed evidence и scope | Проверка реального source input; legacy defaults не доказательство |
| Bridge structured | Предыдущие +furnished/bills_included/balcony/terrace/amenity | Reviewed exact structured mapping и текущая provenance |

Freshness profile: source `last_success_at`, не projection/reprepare time; будущая/пустая дата не свежесть.
Для исторического Flatio pilot согласованы price/availability≤24h, policy fields≤7d,
raw≤24h/evidence≤30d; это **не** global production defaults и не новое разрешение ingestion.
`audit_catalog` уже умеет READ ONLY/REPEATABLE READ, bound≤1000 с отказом при overflow,
eligible buckets и source freshness. Перед реальным измерением нужны точные public/economic/time
eligibility predicate, разрешённый cohort/source/region и policy. Переносить legacy проценты в эти buckets нельзя.

Воспроизведение synthetic результата из корня checkout:

```powershell
$env:PYTHONPATH = "backend"
python -m app.commands.audit_ai_listing_data --input backend/tests/fixtures/ai_listing_audit.json --output output/ai-search-s2-audit.json
python -m lab.fact_coverage
```

Existing `test_audit_ai_listing_data.py`:7 PASS,1.09s; CLI repeatability/aggregate privacy/read-only guards. Input/output hashes и JUnit сохранены рядом с профилем.

S2.1 остаётся частично выполненным. Нет подключения к рабочей БД, чтения real source data,
crawling/backfill, provider calls или изменения настоящего journal. Профиль конкретизирует
недостающие измерения и сохраняет B4; он не выбирает первоначальное покрытие за владельца данных.
Далее независимая локальная S2.2–S2.3: проверить существующую source-check→fact→proof
цепочку и её synthetic fault contracts; реальные измерения S2.1 остаются отдельным требованием.
