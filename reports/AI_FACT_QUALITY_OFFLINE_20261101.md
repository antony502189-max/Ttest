# Качество каталога: offline результат пункта 5

1 ноября 2026, Europe/Moscow. Пункт 5 НЕ завершён: настоящий каталог не измерялся.

Проверяемый source: `fc0fbd39c6ef760d7f8efcea9b27dda794b47cf3`.
База: `5fb1c464bd11129ebe17c27e977a438808af024d`.

## Матрица и границы

[JSON](ai-fact-quality-evidence/coverage.json) воспроизводится командой
`PYTHONPATH=backend python backend/lab/fact_coverage.py`.
Адаптеры обнаруживаются AST из `external_sources.py`, поля — из `FactKey`.
Для каждого источника и поля отдельно записаны capability, real coverage,
real freshness, ссылка на код и условия. `supported` означает только возможность
bridge при проверенном mapping/evidence; `unknown` у внешнего адаптера означает
отсутствие аттестованного source-to-AI mapping, а не отсутствие поля на сайте.
Legacy normalized value не становится evidence автоматически.

Text bridge: pets, children, couples, smoking, capacity_total. Structured bridge:
те же поля плюс furnished, bills_included, balcony, terrace, amenity.
Smoking и capacity требуют явного scope. Students-only отвергается;
empadronamiento пропускается с явным skipped_provider_fields. Party rule,
price/period/currency, geography, availability и категории не извлекаются bridge.
Сохранённые metadata categories не являются подтверждёнными facts.
Наличие EUR Money и SQL price guards не доказывает извлечение цены источника.

Источники инвентаря: Idealista, Fotocasa, Milanuncios, PisoCompartido, Pisos,
ThinkSpain, AlquilerDocenteCanarias, Flatio. Ни один не разрешён этим отчётом
для нового crawling/ingestion. Реальных проверенных записей: 0.

## Проверки

Изолированный Linux snapshot создан `git -c core.autocrlf=false archive HEAD`.
[Хеши всех файлов](ai-fact-quality-evidence/tested-source-sha256.json),
[offline harness](ai-fact-quality-evidence/checks.py),
[unit log](ai-fact-quality-evidence/unit.log), [Ruff](ai-fact-quality-evidence/ruff.log).
Целевой набор: 222 PASS; Ruff PASS. Добавлены golden проверки отсутствия
подтверждения при ценах monthly/nightly/weekly, USD/EUR, party и marketing claims.
Существующие тесты уже проверяют отрицания, конфликты structured/text,
scope/capacity, hash/identity binding и условные правила; механизмы не дублировались.

PG harness: [команда](ai-fact-quality-evidence/pg-checks.py),
[результат](ai-fact-quality-evidence/pg.log). Отдельная synthetic БД
`ai_facts_test_quality`, PostgreSQL без host ports и внешней сети;
runner использует только её loopback. Старые audit/capacity ресурсы не используются.
PG suite проверяет реальные SQL/migrations, смену цены/источника, retirement,
remap/delete, direct writes, proof invalidation/reprepare, period/currency,
public/time guards. Это correctness, не нагрузочное измерение.

## Конкретная политика для последующего согласования

Предлагаемый первый источник — предоставленный владельцем bounded export Flatio
до 100 объявлений с подтверждённым правом использования; альтернатива — собственные
объявления с согласованием владельца данных. Автоматический сбор сайтов пока не
предлагается включать. Credentials, challenge обход и контакты не нужны.

Минимум: opaque source/record IDs, canonical ID, source status, timestamp последней
успешной проверки и изменения контента, hash/version, короткие очищенные clauses,
reviewed structured field/path, точное значение с единицами/period/currency/scope.
Цена должна содержать явную валюту, период и признак exact/from; неизвестное не
заменять EUR/monthly. Хранить происхождение каждого evidence span и версии
mapping/extractor/taxonomy. Не нужны фотографии, контакты, имена, profile links,
полные HTML/raw payload, cookies, адрес квартиры и история переписки.
Очиститель — minimization boundary, не доказательство полного удаления PII.

Предлагаемые сроки для отдельного pilot: raw export только в изолированном
временном хранилище до 24 часов; очищенные evidence/facts до 30 дней; технические
счётчики без текста до 90 дней. Удаление источника требует reconciliation,
инвалидирования зависимых proof и физической очистки evidence, batches и копий
по расписанию; retirement само по себе физическим удалением не является.
Эти сроки — предложение, автоматический cleanup ими ещё не реализован.

Freshness: price/availability подтверждать не старше 24 часов, остальные правила
не старше 7 суток; недоступный источник не продлевает last_successful_check_at.
Stored hash equality не обновляет возраст. При нарушении freshness — исключение
из подтверждённого matching до успешной проверки, затем pipeline и prepare proof.
Эти pilot thresholds ещё требуют согласования и отдельного enforcement; их нельзя
выдать за действующую общую runtime policy.

Для real отчёта нужны отдельные denominators: eligible records, confirmed match,
confirmed mismatch, unknown/missing, conditional, conflict, stale, source error.
Zero confirmed match при unknown не доказывает отсутствие вариантов. Текущая
матрица не заменяет эти catalog counters; UI/product различение и измерение
реального покрытия остаются открытой частью пункта 5.

LLM extraction, если будет выбрано, выполняется при подготовке facts; outgoing
payload только очищенные clauses и whitelist structured values. Сейчас отправок
объявлений и provider calls: 0. Разрешение на synthetic intent не распространяется
на этот payload. Пункт 3 пропущен; ISSUE-004 OPEN / capacity BLOCKED.
Результаты пунктов 1–2 не переносились на новый SHA; merge/public activation нет.

PG итог точного source: **284 PASS за 82.57 s**, без skips/failures
([JUnit](ai-fact-quality-evidence/pg.xml)). Проверки 222 unit + 284 PG PASS
относятся только к перечисленным наборам, не ко всей CI или browser certification.
Все созданные этим прогоном контейнеры остановлены после проверки.
